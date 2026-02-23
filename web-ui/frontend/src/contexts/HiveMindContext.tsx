/**
 * React context that provides the HiveMind WebSocket connection to all
 * components.  Reads configuration from the backend voice config
 * endpoint and manages the connection lifecycle.
 *
 * Usage:
 *   Wrap the app: <HiveMindProvider>...</HiveMindProvider>
 *   In components:  const { isConnected, sendUtterance } = useHiveMind();
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";

import { getVoiceConfig } from "../api/client";
import {
  HiveMindService,
  type ConnectionState,
  type HiveMindConnectionDetails,
  type OVOSMessage,
} from "../services/hivemind";

// ── Context types ──────────────────────────────────────

interface HiveMindContextValue {
  /** Current websocket connection state */
  connectionState: ConnectionState;
  /** Whether voice is enabled by backend config */
  voiceEnabled: boolean;
  /** Shorthand: state === "connected" */
  isConnected: boolean;
  /** Connect to HiveMind (no-op if already connected) */
  connect: () => Promise<void>;
  /** Disconnect from HiveMind */
  disconnect: () => void;
  /** Send a text utterance to OVOS */
  sendUtterance: (text: string) => Promise<void>;
  /** Last speak response from OVOS */
  lastResponse: string | null;
  /** Clear the currently shown speak response */
  clearLastResponse: () => void;
  /** True while OVOS is producing audio output */
  isSpeaking: boolean;
  /** True while skill handler is running */
  isProcessing: boolean;
  /** Clear processing state (e.g. user cancelled); UI-only, does not abort backend */
  cancelProcessing: () => void;
  /** Optional text from enclosure.mouth.text */
  mouthText: string | null;
  /** Current connection details for status popup */
  connectionDetails: HiveMindConnectionDetails;
  /** Subscribe to a specific OVOS bus event */
  on: (eventType: string, callback: (msg: OVOSMessage) => void) => () => void;
}

interface PendingSubscription {
  eventType: string;
  callback: (msg: OVOSMessage) => void;
  unsubscribe: (() => void) | null;
}

const HiveMindContext = createContext<HiveMindContextValue | null>(null);

// ── Provider ───────────────────────────────────────────

interface HiveMindProviderProps {
  children: ReactNode;
}

export function HiveMindProvider({ children }: HiveMindProviderProps) {
  const [connectionState, setConnectionState] =
    useState<ConnectionState>("disconnected");
  const [voiceEnabled, setVoiceEnabled] = useState(false);
  const [lastResponse, setLastResponse] = useState<string | null>(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [mouthText, setMouthText] = useState<string | null>(null);
  const [connectionDetails, setConnectionDetails] =
    useState<HiveMindConnectionDetails>({
      url: "",
      latencyMs: null,
      sessionId: null,
    });
  const [serviceVersion, setServiceVersion] = useState(0);

  const serviceRef = useRef<HiveMindService | null>(null);
  const configLoadedRef = useRef(false);
  const pendingSubscriptionsRef = useRef<Map<number, PendingSubscription>>(
    new Map(),
  );
  const pendingSubscriptionIdRef = useRef(0);

  const flushPendingSubscriptions = useCallback(() => {
    const svc = serviceRef.current;
    if (!svc) return;

    for (const subscription of pendingSubscriptionsRef.current.values()) {
      if (!subscription.unsubscribe) {
        subscription.unsubscribe = svc.on(
          subscription.eventType,
          subscription.callback,
        );
      }
    }
  }, []);

  // Load voice config from backend once
  useEffect(() => {
    if (configLoadedRef.current) return;
    configLoadedRef.current = true;

    void getVoiceConfig()
      .then((config) => {
        setVoiceEnabled(config.voice_enabled);

        if (config.voice_enabled) {
          const cryptoKeyCandidate =
            typeof config.hivemind_secret === "string"
              ? config.hivemind_secret.slice(0, 16)
              : "";
          const svc = new HiveMindService({
            url: config.hivemind_url,
            clientName: config.hivemind_name,
            accessKey: config.hivemind_key,
            accessSecret: config.hivemind_secret,
            encryptionKey:
              cryptoKeyCandidate.length === 16 ? cryptoKeyCandidate : undefined,
          });
          setConnectionDetails(svc.getConnectionDetails());

          // Wire state changes
          svc.onStateChange((state) => {
            setConnectionState(state);
            setConnectionDetails(svc.getConnectionDetails());
          });

          // Wire speak events to lastResponse
          svc.onSpeak((text) => setLastResponse(text));

          // Required OVOS state mapping
          svc.on("recognizer_loop:audio_output_start", () =>
            setIsSpeaking(true),
          );
          svc.on("recognizer_loop:audio_output_end", () =>
            setIsSpeaking(false),
          );
          svc.on("mycroft.skill.handler.start", () => setIsProcessing(true));
          svc.on("mycroft.skill.handler.complete", () =>
            setIsProcessing(false),
          );
          svc.on("enclosure.mouth.text", (msg) => {
            const text =
              (msg.data.text as string | undefined) ??
              (msg.data.utterance as string | undefined) ??
              null;
            setMouthText(text);
          });
          svc.on("*", () => {
            setConnectionDetails(svc.getConnectionDetails());
          });

          serviceRef.current = svc;
          serviceRef.current = svc;
          setServiceVersion((prev) => prev + 1);
          flushPendingSubscriptions();
        }
      })
      .catch(() => {
        // Backend unavailable — voice stays disabled
        setVoiceEnabled(false);
      });

    return () => {
      for (const subscription of pendingSubscriptionsRef.current.values()) {
        subscription.unsubscribe?.();
      }
      pendingSubscriptionsRef.current.clear();
      serviceRef.current?.dispose();
      serviceRef.current = null;
    };
  }, [flushPendingSubscriptions]);

  const connect = useCallback(async () => {
    if (!serviceRef.current) return;
    await serviceRef.current.connect();
  }, []);

  const disconnect = useCallback(() => {
    serviceRef.current?.disconnect();
  }, []);

  const sendUtterance = useCallback(async (text: string) => {
    if (!serviceRef.current) {
      throw new Error("HiveMind service not initialized");
    }
    await serviceRef.current.sendUtterance(text);
  }, []);

  const on = useCallback(
    (eventType: string, callback: (msg: OVOSMessage) => void): (() => void) => {
      if (serviceRef.current) {
        return serviceRef.current.on(eventType, callback);
      }

      const id = pendingSubscriptionIdRef.current;
      pendingSubscriptionIdRef.current += 1;

      pendingSubscriptionsRef.current.set(id, {
        eventType,
        callback,
        unsubscribe: null,
      });

      return () => {
        const subscription = pendingSubscriptionsRef.current.get(id);
        if (!subscription) return;
        subscription.unsubscribe?.();
        pendingSubscriptionsRef.current.delete(id);
      };
    },
    [serviceVersion],
  );

  const clearLastResponse = useCallback(() => {
    setLastResponse(null);
  }, []);

  const cancelProcessing = useCallback(() => {
    setIsProcessing(false);
  }, []);

  const value = useMemo<HiveMindContextValue>(
    () => ({
      connectionState,
      voiceEnabled,
      isConnected: connectionState === "connected",
      connect,
      disconnect,
      sendUtterance,
      lastResponse,
      clearLastResponse,
      isSpeaking,
      isProcessing,
      cancelProcessing,
      mouthText,
      connectionDetails,
      on,
    }),
    [
      connectionState,
      voiceEnabled,
      connect,
      disconnect,
      sendUtterance,
      lastResponse,
      clearLastResponse,
      isSpeaking,
      isProcessing,
      cancelProcessing,
      mouthText,
      connectionDetails,
      on,
    ],
  );

  return (
    <HiveMindContext.Provider value={value}>
      {children}
    </HiveMindContext.Provider>
  );
}

// ── Hook ───────────────────────────────────────────────

export function useHiveMind(): HiveMindContextValue {
  const context = useContext(HiveMindContext);
  if (!context) {
    throw new Error("useHiveMind must be used within HiveMindProvider");
  }
  return context;
}
