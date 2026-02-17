import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { useHiveMind } from "../contexts/HiveMindContext";
import { useVoice } from "../contexts/VoiceContext";

export type ConversationInputMode = "voice" | "text";

export interface Message {
  id: string;
  text: string;
  source: "user" | "avaros";
  inputMode: ConversationInputMode;
  timestamp: Date;
}

const MAX_MESSAGES = 50;

function createMessageId(): string {
  if (typeof crypto !== "undefined" && "randomUUID" in crypto) {
    return crypto.randomUUID();
  }
  return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 7)}`;
}

function trimToRecent(messages: Message[]): Message[] {
  if (messages.length <= MAX_MESSAGES) return messages;
  return messages.slice(messages.length - MAX_MESSAGES);
}

export function useConversation(): {
  messages: Message[];
  isProcessing: boolean;
  addUserMessage: (text: string, inputMode: ConversationInputMode) => void;
  addAvarosResponse: (text: string) => void;
  clearConversation: () => void;
} {
  const { on } = useHiveMind();
  const { finalTranscript } = useVoice();

  const [messages, setMessages] = useState<Message[]>([]);
  const [isProcessing, setIsProcessing] = useState(false);
  const lastTranscriptRef = useRef("");
  const pendingInputModeRef = useRef<ConversationInputMode>("text");

  const appendMessage = useCallback((message: Message) => {
    setMessages((prev) => trimToRecent([...prev, message]));
  }, []);

  const addUserMessage = useCallback(
    (text: string, inputMode: ConversationInputMode) => {
      const normalized = text.trim();
      if (!normalized) return;

      pendingInputModeRef.current = inputMode;
      appendMessage({
        id: createMessageId(),
        text: normalized,
        source: "user",
        inputMode,
        timestamp: new Date(),
      });
      setIsProcessing(true);
    },
    [appendMessage],
  );

  const addAvarosResponse = useCallback(
    (text: string) => {
      const normalized = text.trim();
      if (!normalized) return;

      appendMessage({
        id: createMessageId(),
        text: normalized,
        source: "avaros",
        inputMode: pendingInputModeRef.current,
        timestamp: new Date(),
      });
      setIsProcessing(false);
    },
    [appendMessage],
  );

  useEffect(() => {
    return on("speak", (msg) => {
      const text = (msg.data.utterance as string | undefined) ?? "";
      if (text.trim()) {
        addAvarosResponse(text);
      }
    });
  }, [on, addAvarosResponse]);

  useEffect(() => {
    const transcript = finalTranscript.trim();
    if (!transcript) {
      lastTranscriptRef.current = "";
      return;
    }
    if (transcript === lastTranscriptRef.current) {
      return;
    }
    lastTranscriptRef.current = transcript;
    addUserMessage(transcript, "voice");
  }, [finalTranscript, addUserMessage]);

  const clearConversation = useCallback(() => {
    setMessages([]);
    setIsProcessing(false);
  }, []);

  return useMemo(
    () => ({
      messages,
      isProcessing,
      addUserMessage,
      addAvarosResponse,
      clearConversation,
    }),
    [
      messages,
      isProcessing,
      addUserMessage,
      addAvarosResponse,
      clearConversation,
    ],
  );
}

