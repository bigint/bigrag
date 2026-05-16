import { beforeEach, describe, expect, it } from "vitest";
import type { ChatMessage } from "@/features/chat/chat-messages";
import { useChatStore } from "@/features/chat/chat-store";

const resetChatStore = () => {
  useChatStore.setState({
    collection: "",
    isStreaming: false,
    messages: [],
  });
};

const message = (id: string, content = ""): ChatMessage => ({
  content,
  id,
  role: "assistant",
});

describe("useChatStore", () => {
  beforeEach(() => {
    resetChatStore();
  });

  it("selects the first collection once and clears local messages on collection change", () => {
    useChatStore.getState().selectFirstCollection([{ name: "docs" }, { name: "support" }]);

    expect(useChatStore.getState().collection).toBe("docs");

    useChatStore.setState({
      messages: [message("assistant-1", "old")],
    });
    useChatStore.getState().selectCollection("support");

    expect(useChatStore.getState()).toMatchObject({
      collection: "support",
      messages: [],
    });

    useChatStore.getState().selectFirstCollection([{ name: "ignored" }]);

    expect(useChatStore.getState().collection).toBe("support");
  });

  it("appends and updates streamed messages", () => {
    useChatStore
      .getState()
      .appendMessages([
        { content: "Question", id: "user-temp", role: "user" },
        message("assistant-temp"),
      ]);
    useChatStore.getState().setStreaming(true);
    useChatStore.getState().updateMessage("assistant-temp", (item) => ({
      ...item,
      content: `${item.content}Hello`,
    }));
    useChatStore.getState().updateMessage("assistant-temp", (item) => ({
      ...item,
      content: `${item.content} world`,
    }));

    expect(useChatStore.getState().isStreaming).toBe(true);
    expect(useChatStore.getState().messages).toEqual([
      { content: "Question", id: "user-temp", role: "user" },
      { content: "Hello world", id: "assistant-temp", role: "assistant" },
    ]);
  });

  it("records errors, finalizes streaming, and resets a chat", () => {
    useChatStore.getState().appendMessages([message("assistant-1")]);
    useChatStore.getState().setStreaming(true);
    useChatStore.getState().updateMessage("assistant-1", (item) => ({
      ...item,
      errorMessage: "Provider failed",
      status: "error",
    }));
    useChatStore.getState().setStreaming(false);

    expect(useChatStore.getState().messages[0]).toMatchObject({
      errorMessage: "Provider failed",
      status: "error",
    });
    expect(useChatStore.getState().isStreaming).toBe(false);

    useChatStore.getState().startNewChat();

    expect(useChatStore.getState()).toMatchObject({
      isStreaming: false,
      messages: [],
    });
  });
});
