import type { ReactNode } from "react";
import type { Message } from "../../hooks/useConversation";
import ChatInput from "./ChatInput";
import MessageHistory from "./MessageHistory";
import ModeToggle from "./ModeToggle";

type ChatPanelProps = {
  messages: Message[];
  isProcessing: boolean;
  isConnected: boolean;
  canReplay: boolean;
  primaryAction?: ReactNode;
  onSendText: (text: string) => Promise<void>;
  onReplayResponse: (text: string) => void;
  onClearConversation: () => void;
};

export default function ChatPanel({
  messages,
  isProcessing,
  isConnected,
  canReplay,
  primaryAction,
  onSendText,
  onReplayResponse,
  onClearConversation,
}: ChatPanelProps) {
  return (
    <section className="voice-chat-panel" aria-label="Chat panel">
      <div className={`voice-chat-controls${primaryAction ? " voice-chat-controls--with-action" : ""}`}>
        <ModeToggle />
        {primaryAction ? (
          <div className="voice-chat-primary-action-wrap">{primaryAction}</div>
        ) : null}
      </div>
      <MessageHistory
        messages={messages}
        isProcessing={isProcessing}
        canReplay={canReplay}
        onReplay={onReplayResponse}
        onClear={onClearConversation}
      />
      <ChatInput
        isConnected={isConnected}
        disabled={isProcessing}
        onSend={onSendText}
      />
    </section>
  );
}

