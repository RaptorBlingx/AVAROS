import type { Message } from "../../hooks/useConversation";
import ChatInput from "./ChatInput";
import MessageHistory from "./MessageHistory";
import ModeToggle from "./ModeToggle";

type ChatPanelProps = {
  messages: Message[];
  isProcessing: boolean;
  isConnected: boolean;
  canReplay: boolean;
  onSendText: (text: string) => Promise<void>;
  onReplayResponse: (text: string) => void;
  onClearConversation: () => void;
};

export default function ChatPanel({
  messages,
  isProcessing,
  isConnected,
  canReplay,
  onSendText,
  onReplayResponse,
  onClearConversation,
}: ChatPanelProps) {
  return (
    <section className="voice-chat-panel" aria-label="Chat panel">
      <ModeToggle />
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

