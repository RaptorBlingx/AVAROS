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
          const svc = new HiveMindService({
            url: config.hivemind_url,
            accessKey: config.hivemind_key,
            accessSecret: config.hivemind_secret,
          });

          // Wire state changes
          svc.onStateChange((state) => setConnectionState(state));

          // Wire speak events to lastResponse
          svc.onSpeak((text) => setLastResponse(text));

          serviceRef.current = svc;
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
    [],
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
      on,
    }),
    [
      connectionState,
      voiceEnabled,
      connect,
      disconnect,
      sendUtterance,
      lastResponse,
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
