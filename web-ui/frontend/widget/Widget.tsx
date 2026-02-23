import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
} from "react";

import { normalizeUtteranceForIntent } from "../src/services/intent-normalizer";
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
  const preferredOrder: WidgetMode[] = ["push-to-talk", "text", "wake-word"];
  const nextMode = preferredOrder.find((mode) => !disabledModes.includes(mode));
  return nextMode ?? "text";
}

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

function levenshteinDistance(a: string, b: string): number {
  const rows = a.length + 1;
  const cols = b.length + 1;
  const dp = Array.from({ length: rows }, () => Array<number>(cols).fill(0));

  for (let i = 0; i < rows; i += 1) dp[i][0] = i;
  for (let j = 0; j < cols; j += 1) dp[0][j] = j;

  for (let i = 1; i < rows; i += 1) {
    for (let j = 1; j < cols; j += 1) {
      const cost = a[i - 1] === b[j - 1] ? 0 : 1;
      dp[i][j] = Math.min(
        dp[i - 1][j] + 1,
        dp[i][j - 1] + 1,
        dp[i - 1][j - 1] + cost,
      );
    }
  }
  return dp[a.length][b.length];
}

function isWakeAssistantToken(rawToken: string): boolean {
  const token = rawToken.toLowerCase().replace(/[^a-z]/g, "");
  if (!token) return false;

  const known = new Set([
    "avaros",
    "alvaros",
    "albertos",
    "avaroz",
    "avarus",
    "avaross",
    "avarros",
    "alvarez",
    "averos",
    "averos",
    "aberos",
    "abaros",
    "avros",
    "avaris",
  ]);
  if (known.has(token)) return true;
  if ((token.startsWith("ava") || token.startsWith("alva") || token.startsWith("ave") || token.startsWith("aba")) && token.length >= 4) {
    return true;
  }
  return levenshteinDistance(token, "avaros") <= 3;
}

function looksLikeDirectCommand(raw: string): boolean {
  const normalized = raw.toLowerCase().trim();
  return /^(show|compare|check|what if|what is|trend|anomaly|energy|scrap)\b/.test(
    normalized,
  );
}

function parseWakeWordUtterance(raw: string): { hasWakeWord: boolean; command: string } {
  const cleaned = raw.trim();
  if (!cleaned) return { hasWakeWord: false, command: "" };

  const wakeMatch = /(?:^|\b)(hey|hi|ok|okay|a|hei|hay)\s+([a-zA-Z]+)[\s,.:;-]*/i.exec(cleaned);
  if (wakeMatch && wakeMatch.index !== undefined) {
    const assistantToken = wakeMatch[2] ?? "";
    if (isWakeAssistantToken(assistantToken)) {
      const wakeEndIndex = wakeMatch.index + wakeMatch[0].length;
      const command = cleaned.slice(wakeEndIndex).trim();
      return { hasWakeWord: true, command };
    }
  }

  const words = cleaned.toLowerCase().split(/\s+/);
  if (words.length <= 3) {
    for (const word of words) {
      const stripped = word.replace(/[^a-z]/g, "");
      if (isWakeAssistantToken(stripped)) {
        const idx = cleaned.toLowerCase().indexOf(word);
        const command = cleaned.slice(idx + word.length).trim();
        return { hasWakeWord: true, command };
      }
    }
  }

  return { hasWakeWord: false, command: cleaned };
}

/** Ignore STT results that are our own TTS prompt (avoids acoustic feedback loop). */
function isOwnPromptEcho(transcript: string): boolean {
  const n = transcript.toLowerCase().trim().replace(/\s+/g, " ");
  const patterns = [
    "how can i help you",
    "hey can i help you",
    "how can i help",
    "hey can i help",
  ];
  return patterns.some((p) => n === p || n.startsWith(p + " ") || n.includes(" " + p));
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

      if (modeRef.current === "wake-word" && recognitionRef.current) {
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
        if (modeRef.current === "wake-word") {
          setTimeout(() => {
            restartRecognitionRef.current?.();
          }, 100);
        }
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

  const ensureConnected = useCallback(() => {
    if (configError) return;
    if (!managerRef.current) return;
    managerRef.current.connect();
  }, [configError]);

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

  const startListening = useCallback(() => {
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
    recognition.continuous = activeMode === "wake-word";

    recognition.onstart = () => {
      setMicActive(true);
    };

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      const currentMode = modeRef.current;
      for (let index = event.resultIndex; index < event.results.length; index += 1) {
        const result = event.results[index];
        if (!result.isFinal) continue;
        const transcript = result[0]?.transcript?.trim();
        if (!transcript) continue;

        if (currentMode === "wake-word") {
          if (window.speechSynthesis.speaking) continue;
          if (isOwnPromptEcho(transcript)) continue;
          const parsed = parseWakeWordUtterance(transcript);
          if (parsed.hasWakeWord && parsed.command) {
            wakeWordArmedRef.current = false;
            setWakeWordArmed(false);
            void sendText(parsed.command);
            continue;
          }

          if (parsed.hasWakeWord && !parsed.command) {
            wakeWordArmedRef.current = true;
            setWakeWordArmed(true);
            appendMessage(makeMessage("avaros", "How can I help you?"));
            speakAssistantText("How can I help you?");
            continue;
          }

          if (wakeWordArmedRef.current) {
            const lower = transcript.toLowerCase().trim();
            const isRetrigger = /^(hey|hi|ok|okay|hei|hay)\b/i.test(lower);
            if (isRetrigger) {
              wakeWordArmedRef.current = true;
              setWakeWordArmed(true);
              appendMessage(makeMessage("avaros", "How can I help you?"));
              speakAssistantText("How can I help you?");
              continue;
            }
            wakeWordArmedRef.current = false;
            setWakeWordArmed(false);
            void sendText(transcript);
            continue;
          }

          continue;
        }

        void sendText(transcript);
        stopListening();
      }
    };

    recognition.onerror = (event: SpeechRecognitionErrorEvent) => {
      if (modeRef.current === "wake-word") {
        if (event.error === "no-speech" || event.error === "aborted") {
          return;
        }
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
      if (modeRef.current !== "wake-word") {
        setMicActive(false);
        setWakeWordArmed(false);
        return;
      }
      if (window.speechSynthesis.speaking) {
        return;
      }
      setTimeout(() => {
        if (modeRef.current !== "wake-word") return;
        if (window.speechSynthesis.speaking) return;
        restartRecognitionRef.current?.();
      }, 50);
    };

    try {
      recognition.start();
    } catch {
      recognitionRef.current = null;
      setMicActive(false);
      setMicError("Could not start microphone.");
    }
  }, [appendMessage, configError, sendText, stopListening]);

  useEffect(() => {
    restartRecognitionRef.current = startListening;
  }, [startListening]);

  useEffect(() => {
    modeRef.current = mode;
  }, [mode]);

  useEffect(() => {
    wakeWordArmedRef.current = wakeWordArmed;
  }, [wakeWordArmed]);

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

    manager.connect();

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
      stopListening();
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
  }, [panelOpen, stopListening, processing, handleCancelRequest]);

  useEffect(() => {
    if (!panelOpen) return;
    if (mode === "wake-word" && !micActive && !recognitionRef.current) {
      startListening();
    }
    if (mode !== "wake-word") {
      setWakeWordArmed(false);
    }
  }, [micActive, mode, panelOpen, startListening]);

  useEffect(() => {
    onReady({
      open: () => {
        ensureConnected();
        setPanelOpen(true);
      },
      close: () => setPanelOpen(false),
      send: (text: string) => {
        setPanelOpen(true);
        void sendText(text);
      },
      isConnected: () => managerRef.current?.isConnected() ?? false,
    });
  }, [ensureConnected, onReady, sendText]);

  const visualState: WidgetVisualState = useMemo(() => {
    if (configError) return "disabled";
    if (connectionState === "error") return "error";
    if (processing) return "processing";
    if (isTtsSpeaking) return "speaking";
    if (micActive || (mode === "wake-word" && panelOpen)) return "listening";
    if (connectionState === "disconnected") return "error";
    return "idle";
  }, [configError, connectionState, micActive, mode, panelOpen, processing, isTtsSpeaking]);

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
              startListening();
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
