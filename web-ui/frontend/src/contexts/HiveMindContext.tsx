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
  /** True while OVOS is producing audio output */
  isSpeaking: boolean;
  /** True while skill handler is running */
  isProcessing: boolean;
  /** Optional text from enclosure.mouth.text */
  mouthText: string | null;
  /** Current connection details for status popup */
  connectionDetails: HiveMindConnectionDetails;
  /** Subscribe to a specific OVOS bus event */
  on: (
    eventType: string,
    callback: (msg: OVOSMessage) => void,
  ) => () => void;
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
              cryptoKeyCandidate.length === 16
                ? cryptoKeyCandidate
                : undefined,
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
          svc.on("mycroft.skill.handler.start", () =>
            setIsProcessing(true),
          );
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
          setServiceVersion((prev) => prev + 1);
        }
      })
      .catch(() => {
        // Backend unavailable — voice stays disabled
        setVoiceEnabled(false);
      });

    return () => {
      serviceRef.current?.dispose();
      serviceRef.current = null;
    };
  }, []);

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
    (
      eventType: string,
      callback: (msg: OVOSMessage) => void,
    ): (() => void) => {
      if (!serviceRef.current) return () => {};
      return serviceRef.current.on(eventType, callback);
    },
    [serviceVersion],
  );

  const value = useMemo<HiveMindContextValue>(
    () => ({
      connectionState,
      voiceEnabled,
      isConnected: connectionState === "connected",
      connect,
      disconnect,
      sendUtterance,
      lastResponse,
      isSpeaking,
      isProcessing,
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
      isSpeaking,
      isProcessing,
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
