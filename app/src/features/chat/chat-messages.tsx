import { Trash2 } from "lucide-react";
import { type RefObject, useEffect, useRef } from "react";
import { AssistantMessage } from "@/features/chat/assistant-message";
import type { ChatMessage } from "@/features/chat/chat-message-types";
import { UserMessage } from "@/features/chat/user-message";

export type { ChatMessage } from "@/features/chat/chat-message-types";

interface Props {
  isStreaming: boolean;
  messages: ChatMessage[];
  onClear?: () => void;
  onEditUserMessage?: (messageId: string, content: string) => void;
  onRegenerate?: (messageId: string) => void;
  onResume?: (messageId: string) => void;
}

const useAutoScrollChat = (
  bottomRef: RefObject<HTMLDivElement | null>,
  messages: ChatMessage[],
  isStreaming: boolean,
) => {
  useEffect(() => {
    if (messages.length === 0 && !isStreaming) return;
    bottomRef.current?.scrollIntoView({
      behavior: "instant",
    });
  }, [bottomRef, messages, isStreaming]);
};

export const ChatMessages = ({
  isStreaming,
  messages,
  onClear,
  onEditUserMessage,
  onRegenerate,
  onResume,
}: Props) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useAutoScrollChat(bottomRef, messages, isStreaming);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto overflow-x-hidden px-4 py-6 md:px-6 lg:px-10">
      <div className="mx-auto flex min-w-0 max-w-4xl flex-col gap-4" role="log">
        {messages.length > 0 && onClear && (
          <div className="flex justify-end">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1.5 text-xs font-semibold text-muted-foreground hover:bg-muted hover:text-foreground"
              onClick={onClear}
            >
              <Trash2 className="size-3.5" />
              Clear
            </button>
          </div>
        )}
        {messages.map((message, index) =>
          message.role === "user" ? (
            <UserMessage
              content={message.content}
              id={message.id}
              key={message.id}
              onEdit={onEditUserMessage}
            />
          ) : (
            <AssistantMessage
              isStreaming={
                isStreaming && index === messages.length - 1 && message.role === "assistant"
              }
              key={message.id}
              message={message}
              onRegenerate={onRegenerate}
              onResume={onResume}
            />
          ),
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
};
