import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";

import { normalizeUtteranceForIntent } from "../src/services/intent-normalizer";
import { BackendWakeWordService } from "../src/services/wake-word-backend";
import type { DetectionPayload } from "../src/services/wake-word-backend";
import { ConnectionManager } from "./ConnectionManager";
import { WidgetButton } from "./WidgetButton";
import { WidgetPanel } from "./WidgetPanel";
import type {
  ChatMessage,
  WidgetConfig,
  WidgetConnectionState,
  WidgetMode,
  WidgetPublicApi,
  WidgetTheme,
  WidgetVisualState,
} from "./types";

type WidgetProps = {
  config: WidgetConfig;
  configError: string | null;
  onReady: (api: Omit<WidgetPublicApi, "destroy">) => void;
};

type BrowserSpeechRecognitionCtor = {
  new (): SpeechRecognition;
};

function getSpeechRecognitionCtor(): BrowserSpeechRecognitionCtor | null {
  const speechWindow = window as typeof window & {
    SpeechRecognition?: BrowserSpeechRecognitionCtor;
    webkitSpeechRecognition?: BrowserSpeechRecognitionCtor;
  };
  return speechWindow.SpeechRecognition ?? speechWindow.webkitSpeechRecognition ?? null;
}

function pickInitialMode(disabledModes: WidgetMode[]): WidgetMode {
  const preferredOrder: WidgetMode[] = ["wake-word", "push-to-talk", "text"];
  const nextMode = preferredOrder.find((mode) => !disabledModes.includes(mode));
  return nextMode ?? "text";
}

/** Cooldown to avoid re-prompting "How can I help you?" from TTS echo. */
const WAKE_WORD_PROMPT_COOLDOWN_MS = 3000;

function makeMessage(source: "user" | "avaros", text: string): ChatMessage {
  return {
    id:
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `${source}-${Date.now()}`,
    source,
    text,
    timestamp: new Date(),
  };
}

function deriveTheme(theme: WidgetTheme): "light" | "dark" {
  if (theme === "light") return "light";
  if (theme === "dark") return "dark";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function pickPreferredVoice(voices: SpeechSynthesisVoice[]): SpeechSynthesisVoice | null {
  if (!voices.length) return null;
  const samantha = voices.find((voice) => voice.name.toLowerCase().includes("samantha"));
  if (samantha) return samantha;

  const english = voices.find((voice) => voice.lang.toLowerCase().startsWith("en"));
  if (english) return english;

  return voices[0] ?? null;
}

export function Widget({ config, configError, onReady }: WidgetProps) {
  const rootRef = useRef<HTMLDivElement | null>(null);
  const managerRef = useRef<ConnectionManager | null>(null);
  const recognitionRef = useRef<SpeechRecognition | null>(null);
  const fallbackTimerRef = useRef<number | null>(null);
  const completionTimerRef = useRef<number | null>(null);
  const modeRef = useRef<WidgetMode>(pickInitialMode(config.disabledModes));
  const wakeWordArmedRef = useRef(false);
  const responseResolvedRef = useRef(true);
  const ttsVoiceRef = useRef<SpeechSynthesisVoice | null>(null);
  const backendWakeWordRef = useRef<BackendWakeWordService | null>(null);
  const wakeWordPromptCooldownRef = useRef(0);
  const appendMessageRef = useRef<(msg: ChatMessage) => void>(() => {});
  const speakAssistantTextRef = useRef<(text: string) => void>(() => {});

  const [panelOpen, setPanelOpen] = useState(false);
  const [inputValue, setInputValue] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [processing, setProcessing] = useState(false);
  const [connectionState, setConnectionState] = useState<WidgetConnectionState>("disconnected");
  const [mode, setMode] = useState<WidgetMode>(pickInitialMode(config.disabledModes));
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">(deriveTheme(config.theme));
  const [isTtsSpeaking, setIsTtsSpeaking] = useState(false);
  const setTtsSpeakingRef = useRef<(v: boolean) => void>(() => {});
  setTtsSpeakingRef.current = setIsTtsSpeaking;
  const [micActive, setMicActive] = useState(false);
  const [micPermission, setMicPermission] = useState<
    "prompt" | "granted" | "denied" | "unsupported"
  >("prompt");
  const [micError, setMicError] = useState<string | null>(null);
  const [wakeWordArmed, setWakeWordArmed] = useState(false);
  const [ttsVoice, setTtsVoice] = useState<SpeechSynthesisVoice | null>(null);

  useEffect(() => {
    ttsVoiceRef.current = ttsVoice;
  }, [ttsVoice]);

  const restartRecognitionRef = useRef<(() => void) | null>(null);

  const ttsWatcherRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const clearTtsWatcher = useCallback(() => {
    if (ttsWatcherRef.current !== null) {
      clearInterval(ttsWatcherRef.current);
      ttsWatcherRef.current = null;
    }
  }, []);

  const speakAssistantText = useCallback(
    (text: string) => {
      if (!("speechSynthesis" in window)) return;
      const cleaned = text.trim();
      if (!cleaned) return;

      clearTtsWatcher();

      // Pause browser STT during TTS to avoid echo pickup.
      if (recognitionRef.current) {
        try { recognitionRef.current.stop(); } catch { /* already stopped */ }
      }

      const utterance = new SpeechSynthesisUtterance(cleaned);
      utterance.lang = "en-US";
      const voice = ttsVoiceRef.current;
      if (voice) {
        utterance.voice = voice;
      }

      const onTtsDone = () => {
        clearTtsWatcher();
        setTtsSpeakingRef.current?.(false);
      };

      utterance.onend = onTtsDone;

      window.speechSynthesis.cancel();
      window.speechSynthesis.speak(utterance);
      setTtsSpeakingRef.current?.(true);

      ttsWatcherRef.current = setInterval(() => {
        if (!window.speechSynthesis.speaking) {
          onTtsDone();
        }
      }, 200);
    },
    [clearTtsWatcher],
  );

  // ── Backend Wake Word lifecycle ────────────────────

  const disposeBackendWakeWord = useCallback(() => {
    backendWakeWordRef.current?.dispose();
    backendWakeWordRef.current = null;
  }, []);

  const ensureConnected = useCallback(() => {
    if (configError) return;
    if (!managerRef.current) return;
    managerRef.current.connect();
  }, [configError]);

  const requestMicPermission = useCallback(async (): Promise<boolean> => {
    if (!navigator.mediaDevices?.getUserMedia) {
      setMicPermission("unsupported");
      setMicError("Microphone API is unavailable in this browser.");
      return false;
    }

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      stream.getTracks().forEach((track) => track.stop());
      setMicPermission("granted");
      setMicError(null);
      return true;
    } catch (error) {
      if (
        error instanceof DOMException &&
        (error.name === "NotAllowedError" || error.name === "PermissionDeniedError")
      ) {
        setMicPermission("denied");
        setMicError("Microphone permission blocked. Allow access and retry.");
        return false;
      }
      setMicPermission("denied");
      setMicError("Could not access microphone.");
      return false;
    }
  }, []);

  const clearFallbackTimer = useCallback(() => {
    if (fallbackTimerRef.current !== null) {
      window.clearTimeout(fallbackTimerRef.current);
      fallbackTimerRef.current = null;
    }
  }, []);

  const clearCompletionTimer = useCallback(() => {
    if (completionTimerRef.current !== null) {
      window.clearTimeout(completionTimerRef.current);
      completionTimerRef.current = null;
    }
  }, []);

  const appendMessage = useCallback((message: ChatMessage) => {
    setMessages((prev) => {
      const last = prev[prev.length - 1];
      if (
        last &&
        last.source === message.source &&
        last.text.trim() === message.text.trim()
      ) {
        return prev;
      }
      return [...prev.slice(-49), message];
    });
  }, []);

  const resolveAssistantMessage = useCallback(
    (text: string) => {
      const cleaned = text.trim();
      if (!cleaned) return;
      responseResolvedRef.current = true;
      clearFallbackTimer();
      clearCompletionTimer();
      setProcessing(false);
      appendMessage(makeMessage("avaros", cleaned));
      speakAssistantText(cleaned);
    },
    [appendMessage, clearCompletionTimer, clearFallbackTimer, speakAssistantText],
  );

  const handleCancelRequest = useCallback(() => {
    responseResolvedRef.current = true;
    clearFallbackTimer();
    clearCompletionTimer();
    setProcessing(false);
    appendMessage(makeMessage("avaros", "Request cancelled."));
  }, [appendMessage, clearCompletionTimer, clearFallbackTimer]);

  const stopListening = useCallback(() => {
    const recognition = recognitionRef.current;
    if (!recognition) {
      setMicActive(false);
      return;
    }

    recognition.onstart = null;
    recognition.onresult = null;
    recognition.onerror = null;
    recognition.onend = null;
    recognitionRef.current = null;

    try {
      recognition.stop();
    } catch {
      // Ignore stop errors from closed recognizers.
    }

    setMicActive(false);
  }, []);

  const sendText = useCallback(
    async (text: string) => {
      const cleaned = text.trim();
      if (!cleaned) return;
      if (configError) return;
      ensureConnected();
      const manager = managerRef.current;
      if (!manager) return;

      const toSend = normalizeUtteranceForIntent(cleaned);

      appendMessage(makeMessage("user", cleaned));
      setProcessing(true);
      responseResolvedRef.current = false;
      clearFallbackTimer();
      clearCompletionTimer();
      fallbackTimerRef.current = window.setTimeout(() => {
        responseResolvedRef.current = true;
        setProcessing(false);
        appendMessage(
          makeMessage(
            "avaros",
            "No response from AVAROS for this command. Check platform connectivity.",
          ),
        );
      }, 8000);

      try {
        await manager.sendUtterance(toSend);
      } catch {
        clearFallbackTimer();
        clearCompletionTimer();
        responseResolvedRef.current = true;
        setProcessing(false);
        appendMessage(makeMessage("avaros", "Send failed. Check connection."));
      }
    },
    [
      appendMessage,
      clearCompletionTimer,
      clearFallbackTimer,
      configError,
      ensureConnected,
    ],
  );

  const startListening = useCallback(async () => {
    if (configError) return;

    if (!window.isSecureContext && window.location.hostname !== "localhost") {
      setMicError("Microphone requires localhost or HTTPS.");
      return;
    }

    const activeMode = modeRef.current;
    if (activeMode === "text") {
      setMicError("Text mode active. Switch to voice mode.");
      return;
    }
    if (micPermission !== "granted") {
      const granted = await requestMicPermission();
      if (!granted) {
        setMicError("Allow microphone first.");
        return;
      }
    }

    const RecognitionCtor = getSpeechRecognitionCtor();
    if (!RecognitionCtor) {
      setMicError("Speech recognition not supported in this browser.");
      return;
    }

    if (recognitionRef.current) {
      stopListening();
    }
    setMicError(null);

    const recognition = new RecognitionCtor();
    recognitionRef.current = recognition;
    recognition.lang = "en-US";
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    // Never use continuous mode. In wake-word mode the backend handles
    // passive listening; browser STT only captures one command at a time.
    recognition.continuous = false;

    recognition.onstart = () => {
      setMicActive(true);
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (!result.isFinal) continue;
        const transcript = result[0]?.transcript?.trim();
        if (!transcript) continue;

        // Send the command to AVAROS.
        wakeWordArmedRef.current = false;
        setWakeWordArmed(false);
        void sendText(transcript);
        stopListening();
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (event.error === "no-speech" || event.error === "aborted") {
        // In wake-word armed mode, silence means user didn't follow up.
        if (wakeWordArmedRef.current) {
          wakeWordArmedRef.current = false;
          setWakeWordArmed(false);
        }
        return;
      }
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        setMicError("Microphone permission blocked. Allow access and retry.");
      } else if (event.error === "audio-capture") {
        setMicError("No microphone detected on this device.");
      } else if (event.error === "no-speech") {
        setMicError("No speech detected. Try again.");
      } else {
        setMicError("Voice capture failed. Try again.");
      }
    };

    recognition.onend = () => {
      recognitionRef.current = null;
      setMicActive(false);
      // If wake-word armed but no command captured, disarm.
      if (wakeWordArmedRef.current) {
        wakeWordArmedRef.current = false;
        setWakeWordArmed(false);
      }
    };

    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setMicActive(false);
      setMicError("Could not start microphone.");
    }
  }, [
    configError,
    micPermission,
    requestMicPermission,
    sendText,
    stopListening,
  ]);

  useEffect(() => {
    restartRecognitionRef.current = startListening;
  }, [startListening]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    wakeWordArmedRef.current = wakeWordArmed;
  }, [wakeWordArmed]);

  // Keep refs current so the onDetected handler never captures stale callbacks.
  appendMessageRef.current = appendMessage;
  speakAssistantTextRef.current = speakAssistantText;

  // ── Backend Wake Word: lifecycle + detection (single effect) ──
  useEffect(() => {
    if (mode !== "wake-word") {
      backendWakeWordRef.current?.dispose();
      backendWakeWordRef.current = null;
      return;
    }

    if (backendWakeWordRef.current) return;
    const bww = new BackendWakeWordService();
    backendWakeWordRef.current = bww;

    // Wire onDetected BEFORE startListening to avoid losing events.
    const unsubDetected = bww.onDetected((_payload: DetectionPayload) => {
      // Cooldown: suppress re-triggers within a short window (e.g. TTS echo).
      if (Date.now() < wakeWordPromptCooldownRef.current) return;
      if (window.speechSynthesis.speaking) return;

      wakeWordPromptCooldownRef.current = Date.now() + WAKE_WORD_PROMPT_COOLDOWN_MS;
      setPanelOpen(true);
      wakeWordArmedRef.current = true;
      setWakeWordArmed(true);
      appendMessageRef.current(makeMessage("avaros", "How can I help you?"));
      speakAssistantTextRef.current("How can I help you?");

      // After TTS finishes, start single-shot browser STT for command capture.
      const captureDelay = 1800; // rough TTS duration for "How can I help you?"
      setTimeout(() => {
        if (modeRef.current !== "wake-word") return;
        if (!wakeWordArmedRef.current) return;
        restartRecognitionRef.current?.();
      }, captureDelay);
    });

    // Initialize and start listening after handler is wired.
    void (async () => {
      try {
        await bww.initialize();
        await bww.startListening();
      } catch {
        // Backend unavailable — degrade to push-to-talk.
        bww.dispose();
        backendWakeWordRef.current = null;
        setMode((prev) => (prev === "wake-word" ? "push-to-talk" : prev));
        modeRef.current = "push-to-talk";
      }
    })();

    return () => {
      unsubDetected();
      bww.dispose();
      backendWakeWordRef.current = null;
    };
  }, [mode]);

  useEffect(() => {
    if (!("speechSynthesis" in window)) return;
    const synth = window.speechSynthesis;

    const syncVoices = () => {
      const voices = synth.getVoices();
      setTtsVoice(pickPreferredVoice(voices));
    };

    syncVoices();
    synth.addEventListener("voiceschanged", syncVoices);
    return () => synth.removeEventListener("voiceschanged", syncVoices);
  }, []);

  useEffect(() => {
    if (!navigator.permissions) return;
    void navigator.permissions
      .query({ name: "microphone" as PermissionName })
      .then((result) => {
        if (result.state === "granted") {
          setMicPermission("granted");
        } else if (result.state === "denied") {
          setMicPermission("denied");
        } else {
          setMicPermission("prompt");
        }
        result.onchange = () => {
          if (result.state === "granted") setMicPermission("granted");
          else if (result.state === "denied") setMicPermission("denied");
          else setMicPermission("prompt");
        };
      })
      .catch(() => undefined);
  }, []);

  useEffect(() => {
    if (configError) {
      setConnectionState("error");
      return;
    }

    const manager = new ConnectionManager(
      config.host,
      config.clientName,
      config.accessKey,
      config.accessSecret,
      config.encryptionKey,
    );
    managerRef.current = manager;
    const offState = manager.onState((nextState) => {
      setConnectionState(nextState);
    });
    const offSpeak = manager.onSpeak((text) => {
      resolveAssistantMessage(text);
    });
    const offMouthText = manager.on("enclosure.mouth.text", (message) => {
      const maybeText =
        (message.data.text as string | undefined) ??
        (message.data.utterance as string | undefined) ??
        "";
      if (!maybeText.trim()) return;
      resolveAssistantMessage(maybeText);
    });
    const offComplete = manager.on("mycroft.skill.handler.complete", (message) => {
      if (responseResolvedRef.current) return;
      clearCompletionTimer();
      const errorText =
        (message.data.exception as string | undefined) ??
        (message.data.error as string | undefined) ??
        "";
      completionTimerRef.current = window.setTimeout(() => {
        if (responseResolvedRef.current) return;
        if (errorText.trim()) {
          const cleaned = errorText
            .replace(/^\[[^\]]+\]\s*/u, "")
            .trim();
          resolveAssistantMessage(`Request failed: ${cleaned || "Unknown error."}`);
          return;
        }
        resolveAssistantMessage(
          "Request completed, but AVAROS did not return spoken output.",
        );
      }, 700);
    });

    return () => {
      offState();
      offSpeak();
      offMouthText();
      offComplete();
      manager.destroy();
      managerRef.current = null;
      clearFallbackTimer();
      clearCompletionTimer();
      stopListening();
      disposeBackendWakeWord();
      responseResolvedRef.current = true;
      setWakeWordArmed(false);
    };
  }, [
    appendMessage,
    clearCompletionTimer,
    clearFallbackTimer,
    config.accessKey,
    config.accessSecret,
    config.clientName,
    config.encryptionKey,
    config.host,
    configError,
    disposeBackendWakeWord,
    resolveAssistantMessage,
    stopListening,
  ]);

  useEffect(() => {
    if (config.theme !== "auto") {
      setResolvedTheme(config.theme);
      return;
    }

    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const update = () => {
      setResolvedTheme(media.matches ? "dark" : "light");
    };
    update();
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, [config.theme]);

  useEffect(() => {
    if (!panelOpen) {
      if (mode !== "wake-word") {
        stopListening();
      }
      setWakeWordArmed(false);
      return;
    }

    const onEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        if (processing) {
          handleCancelRequest();
          return;
        }
        setPanelOpen(false);
      }
    };

    const onOutsideClick = (event: MouseEvent) => {
      if (!rootRef.current) return;
      const path = event.composedPath();
      if (path.includes(rootRef.current)) return;
      setPanelOpen(false);
    };

    window.addEventListener("keydown", onEscape);
    document.addEventListener("mousedown", onOutsideClick);
    return () => {
      window.removeEventListener("keydown", onEscape);
      document.removeEventListener("mousedown", onOutsideClick);
    };
  }, [panelOpen, stopListening, mode, processing, handleCancelRequest]);

  useEffect(() => {
    // In wake-word mode, the backend service handles passive listening.
    // Browser STT is only started on-demand after detection.
    if (mode !== "wake-word") {
      setWakeWordArmed(false);
    }
  }, [mode]);

  useEffect(() => {
    onReady({
      open: () => {
        ensureConnected();
        setPanelOpen(true);
      },
      close: () => setPanelOpen(false),
      activateVoice: () => {
        ensureConnected();
        if (!config.disabledModes.includes("wake-word")) {
          setMode("wake-word");
        }
        void requestMicPermission()
          .then((granted) => {
            if (!granted) return;
            void startListening();
          })
          .catch(() => undefined);
      },
      send: (text: string) => {
        setPanelOpen(true);
        void sendText(text);
      },
      isConnected: () => managerRef.current?.isConnected() ?? false,
    });
  }, [
    config.disabledModes,
    ensureConnected,
    onReady,
    requestMicPermission,
    sendText,
    startListening,
  ]);

  const visualState: WidgetVisualState = useMemo(() => {
    if (configError) return "disabled";
    if (connectionState === "error") return "error";
    if (processing) return "processing";
    if (isTtsSpeaking) return "speaking";
    const isPassiveWakeWordListening =
      mode === "wake-word" && micActive && !wakeWordArmed && !panelOpen;
    if (isPassiveWakeWordListening) return "idle";
    if (micActive || (mode === "wake-word" && panelOpen)) return "listening";
    if (connectionState === "disconnected") return "error";
    return "idle";
  }, [
    configError,
    connectionState,
    micActive,
    mode,
    panelOpen,
    processing,
    isTtsSpeaking,
    wakeWordArmed,
  ]);

  const connectionTooltip =
    configError ??
    (connectionState === "connected"
      ? "Connected"
      : connectionState === "connecting"
        ? "Connecting..."
        : connectionState === "error"
          ? "Disconnected"
          : "Disconnected");

  const sendDisabled =
    processing || !inputValue.trim() || connectionState !== "connected" || Boolean(configError);

  const listeningSupported = mode !== "text" && getSpeechRecognitionCtor() !== null;

  const wrapperStyle: CSSProperties = {
    left: config.position.endsWith("left") ? `${config.offsetX}px` : "auto",
    right: config.position.endsWith("right") ? `${config.offsetX}px` : "auto",
    top: config.position.startsWith("top") ? `${config.offsetY}px` : "auto",
    bottom: config.position.startsWith("bottom") ? `${config.offsetY}px` : "auto",
  };

  return (
    <div ref={rootRef} className={`aw-widget aw-widget--${resolvedTheme}`} style={wrapperStyle}>
      {panelOpen ? (
        <div className="aw-widget-panel-anchor">
          <WidgetPanel
            mode={mode}
            disabledModes={config.disabledModes}
            messages={messages}
            connectionState={connectionState}
            listeningSupported={listeningSupported}
            listeningActive={micActive}
            micError={micError}
            inputValue={inputValue}
            processing={processing}
            sendDisabled={sendDisabled}
            visualState={visualState}
            onListenToggle={() => {
              if (micActive) {
                stopListening();
                return;
              }
              void startListening();
            }}
            onCancelRequest={handleCancelRequest}
            onInputChange={setInputValue}
            onSend={() => {
              const toSend = inputValue;
              setInputValue("");
              void sendText(toSend);
            }}
            onClear={() => setMessages([])}
            onStopSpeaking={() => setIsTtsSpeaking(false)}
            brandLogoSrc="/widget-logo.svg"
            onModeChange={(nextMode) => {
              if (config.disabledModes.includes(nextMode)) return;
              setMode(nextMode);
              if (nextMode === "text") {
                stopListening();
                setWakeWordArmed(false);
              }
            }}
          />
        </div>
      ) : null}

      <WidgetButton
        visualState={visualState}
        connectionState={connectionState}
        size={config.size}
        label={config.label}
        open={panelOpen}
        tooltip={connectionTooltip}
        onClick={() => {
          ensureConnected();
          setPanelOpen((prev) => !prev);
        }}
      />
    </div>
  );
}
