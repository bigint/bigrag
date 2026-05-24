import { ChatInput } from "@/features/chat/chat-input";
import { ChatMessages } from "@/features/chat/chat-messages";
import { LoadingState, NoCollectionsState } from "@/features/chat/chat-page-states";
import { EmptyPrompts } from "@/features/chat/empty-prompts";
import { useChatPageController } from "@/features/chat/use-chat-page-controller";

export const ChatPage = () => {
  const chat = useChatPageController();

  return (
    <div className="relative flex min-h-0 flex-1 overflow-hidden bg-background">
      <section className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {chat.loading ? (
          <LoadingState />
        ) : chat.collections.length === 0 ? (
          <NoCollectionsState />
        ) : (
          <div className="relative flex min-h-0 flex-1 flex-col overflow-hidden">
            {chat.messages.length === 0 ? (
              <EmptyPrompts
                collection={chat.collection}
                collectionCount={chat.collections.length}
                disabled={chat.disabled}
                hasOpenAIKey={chat.state.hasOpenAIKey}
                isGeneratingQuestions={chat.generateQuestionsPending}
                onGenerateQuestions={chat.handleGenerateQuestions}
                onSelect={chat.handleSend}
                questions={chat.questions}
              />
            ) : (
              <ChatMessages
                isStreaming={chat.isStreaming}
                messages={chat.messages}
                onClear={chat.handleClear}
                onEditUserMessage={chat.handleEditUserMessage}
                onRegenerate={chat.handleRegenerate}
                onResume={chat.handleRegenerate}
              />
            )}
            <ChatInput
              collection={chat.collection}
              collections={chat.collections}
              disabled={chat.disabled}
              isStreaming={chat.isStreaming}
              onCollectionChange={chat.handleCollectionChange}
              onPatch={chat.patchState}
              onSend={chat.handleSend}
              onStop={chat.stopStreaming}
              saving={chat.saving}
              state={chat.state}
            />
          </div>
        )}
      </section>
    </div>
  );
};
