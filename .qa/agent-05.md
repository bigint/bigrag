# Agent 5: Chat Playground

## Tested
- /chat (collections: arxiv, test)

## Environment Note
End-to-end browser testing was severely hampered by the shared Chrome tab pool. Ten parallel QA agents continuously created, navigated, and closed tabs in the same Chrome window, which (a) saturated the dev server's HTTP/1.1 connection pool so that authenticated `GET /v1/auth/me` requests sat in `pending` for 25-40s while direct `curl` to the same endpoint returned in ~2ms, (b) repeatedly stole my freshly created tabs out from under me mid-test (other agents navigated my tab to `/overview`, `/models`, `/collections/arxiv/settings`, etc. between my batched actions), and (c) periodically closed the entire MCP tab group. Newly created tabs also did not inherit the auth session cookie from the existing logged-in tabs, so I could not freely spin up a private tab — I had to compete with other agents for one of the existing authenticated tabs. As a result I was able to confirm the chat shell loads (sidebar, "Chat" highlighted, Yoginth user pill, `Loading chat` spinner), I observed `GET /v1/chat/question-suggestions?collection=arxiv` return 200, but I was never able to drive the chat input itself to verify streaming, citations clicks, regenerate/copy/edit, abort, or per-collection suggestion persistence end-to-end through the browser. Findings below combine the partial browser observations with code review of the chat playground sources.

## Issues

### [P2] No "regenerate", "copy", or "edit" controls on chat messages
- Route: /chat
- Reproduction: 1. Open /chat (with arxiv collection, key set). 2. Send any message and wait for a reply. 3. Hover/inspect the assistant message bubble.
- Expected: Per the QA brief, regenerate / copy / edit buttons should exist on chat messages.
- Actual: `app/src/features/chat/chat-messages.tsx` renders the assistant `<article>` with only the answer text, sources `<details>`, and a latency ledger. There is no regenerate button, no copy-to-clipboard button, and no edit-user-message UI anywhere in `chat-messages.tsx` or `chat-page.tsx`. The Zustand store (`chat-store.ts`) likewise exposes no regenerate / edit / delete-message actions. Only `startNewChat` exists, and it is never wired to a UI control either.
- Console: n/a (missing feature)
- Network: n/a
- Suspected source: /Users/yoginth/bigrag/app/src/features/chat/chat-messages.tsx; /Users/yoginth/bigrag/app/src/features/chat/chat-store.ts

### [P2] No persisted conversation history / no way to resume a previous chat
- Route: /chat
- Reproduction: 1. Open /chat, send a message, get a reply. 2. Navigate away (e.g., click "Overview"). 3. Click "Chat" again.
- Expected: The previous conversation is restored, or there is some "previous chats" surface.
- Actual: `useChatStore` is an in-memory zustand store with no persist middleware, and `ChatPage` does not load any prior thread from the server. The `ChatPage` cleanup effect even aborts any in-flight stream on unmount. Switching to a different collection and back also clears the messages because `selectCollection` resets `messages` to `[]` when the collection name changes. There is no "history" sidebar, no thread list, no resume.
- Console: n/a
- Network: n/a
- Suspected source: /Users/yoginth/bigrag/app/src/features/chat/chat-store.ts:28-33, /Users/yoginth/bigrag/app/src/features/chat/chat-page.tsx:87-94

### [P3] Markdown / code blocks are not rendered — assistant output is plain text with `whitespace-pre-wrap`
- Route: /chat
- Reproduction: 1. Ask the model a question that produces markdown (lists, code fences, headings). 2. Inspect the rendered answer.
- Expected: Lists render as lists, fenced code blocks render with monospace + syntax block (per the QA brief's "Code blocks / lists in answers — render correctly").
- Actual: `chat-messages.tsx` renders `message.content` through `renderInlineCitations` which only splits on `[\d+]` citation tokens and otherwise emits raw text inside a `whitespace-pre-wrap` div. No markdown parser (`react-markdown`, `marked`, etc.) is imported anywhere in `app/src/features/chat/`. Triple-backtick blocks, `**bold**`, `# heading`, and bullet `-` lines will all appear as literal characters.
- Console: n/a
- Network: n/a
- Suspected source: /Users/yoginth/bigrag/app/src/features/chat/chat-messages.tsx:46-82, 146-168

### [P3] Citation buttons do not link to source documents — only scroll to in-card source list
- Route: /chat
- Reproduction: 1. Receive an answer with `[1]` citations. 2. Click the `[1]` chip.
- Expected: Per QA brief: "do they have a doc title + page link? Click one — does it open the source?" Implies a link to the document viewer.
- Actual: `jumpToSource` in `chat-messages.tsx:93-106` only opens the sources `<details>` accordion within the same message card and scrolls to the matching `<li>`. It never navigates to `/collections/<name>/documents/<id>` or any document-viewer route. The `SourceCard` itself is also non-interactive — filename + page number are displayed but not wrapped in a link/button. To audit the actual source the user has to manually copy the document_id / page number and navigate elsewhere.
- Console: n/a
- Network: n/a
- Suspected source: /Users/yoginth/bigrag/app/src/features/chat/chat-messages.tsx:93-106, 256-317

### [P3] Chat input has no error UX surface for empty submissions or invalid models
- Route: /chat
- Reproduction: 1. Try to send an empty/whitespace-only message. 2. Try to send with no collection or no API key.
- Expected: Inline feedback on the input.
- Actual: `chat-input.tsx:68-73` silently returns when `value.trim()` is empty or `disabled` is true — no toast, no shake, nothing. For no-key/no-collection states, `handleSend` in `chat-page.tsx:162-169` fires `toast.error("Add your OpenAI API key first")` / `toast.error("Pick a collection first")` only on POST attempt; the send button is disabled before then so the toasts in practice never fire. The placeholder text is the only hint. There is no UI for setting an "invalid model" — the model picker is a fixed `OPENAI_MODELS` allowlist, so the "invalid model" error path in the brief is unreachable through the UI.
- Console: n/a
- Network: n/a
- Suspected source: /Users/yoginth/bigrag/app/src/features/chat/chat-input.tsx:68-73; /Users/yoginth/bigrag/app/src/features/chat/chat-page.tsx:161-169

### [P3] Switching collections silently destroys the current conversation with no confirmation
- Route: /chat
- Reproduction: 1. Send several messages against `arxiv`. 2. Open the collection picker and pick `test`. 3. Switch back to `arxiv`.
- Expected: Either preserve the conversation per collection (so switching arxiv ↔ test ↔ arxiv keeps the original arxiv thread), or warn before wiping.
- Actual: `selectCollection` in `chat-store.ts:28-33` clears `messages` whenever the new name differs from the current one, with no confirmation modal, no toast, and no undo. Switching to `test` to send one ad-hoc question and then switching back to `arxiv` loses everything you had with arxiv.
- Console: n/a
- Network: n/a
- Suspected source: /Users/yoginth/bigrag/app/src/features/chat/chat-store.ts:28-33

### [P4] Citation parser only recognises single-digit-group `[N]` and silently re-renders unknown numbers as raw text
- Route: /chat
- Reproduction: 1. Ask a question that returns 4 sources. 2. The model emits `[5]` (over-cite) or `[1,2]` (multi-cite, common LLM output).
- Expected: Either the unknown cite is hidden, or it shows a disabled tooltip; multi-cites are split into multiple chips.
- Actual: `CITATION_RE = /\[(\d+)\]/g` (chat-messages.tsx:42) only matches a single integer. `[1,2]` is left as literal text and never converted. Numbers > `chunkCount` fall through to the `else` branch and are rendered as raw `[5]` text, indistinguishable from a typo or markdown formatting noise. Worth at least logging or styling differently.
- Console: n/a
- Network: n/a
- Suspected source: /Users/yoginth/bigrag/app/src/features/chat/chat-messages.tsx:42, 59-76

### [P4] No way to delete or clear a single chat session from the UI
- Route: /chat
- Reproduction: 1. Send messages. 2. Look for a "new chat" / "clear" button.
- Expected: A user-visible affordance to reset the conversation (since the brief notes "clearing a chat session is OK").
- Actual: `chat-store.ts` exposes `startNewChat`, but no UI in `chat-page.tsx`, `chat-input.tsx`, or `chat-messages.tsx` invokes it. The only way to clear is to switch collections (which wipes silently, see above) or reload the tab (which also wipes because there is no persistence).
- Console: n/a
- Network: n/a
- Suspected source: /Users/yoginth/bigrag/app/src/features/chat/chat-store.ts:41-45

## Notes

- API surface for the suggestions persistence fix looks correct. `api/bigrag/services/chat/questions.py` stores suggestions under `UserPreference.data["chat"]["question_suggestions"][collection_name]` with `{questions, generated_at, model}`, keyed by `user_id` (so per-user-per-collection). `get_question_suggestions` reads back that same key; switching collections triggers a fresh `useQuery` with `queryKey: queryKeys.chat.questions({ collection })` (`app/src/hooks/use-chat.ts:13-21`), so arxiv and test will indeed have distinct cached suggestion sets and reload will refetch the persisted ones. Could not exercise this end-to-end through the browser due to the contention described above.
- One `GET /v1/chat/question-suggestions?collection=arxiv` request was observed returning 200 while the chat shell was rendering, confirming the GET path is reachable for an authenticated user.
- The default state in `chat-page.tsx:25-38` ships with `searchMode: "semantic"`, `rerank: false`, `topK: 5`, `temperature: 0.2`, `model: "gpt-4o-mini"`, and a non-empty system prompt; the `SettingsMenu`, `ModelMenu`, and `KeyMenu` popovers in `chat-input-controls` cover these (model picker, search/top-k/temperature/system-prompt, OpenAI key). Settings save via `useUpdatePreferences` — could not verify the network roundtrip due to contention.
- Stop/abort is implemented (`abortRef.current?.abort()` in `chat-page.tsx:142-146`) and the `<Square>` button swaps in for the send button while `isStreaming` is true (`chat-input.tsx:208-221`). The abort path explicitly marks the assistant message `status: "complete"` rather than `error`, which is a nice touch.
- Streaming consumer (`streamChat` in `app/src/lib/chat-stream.ts` — not read here) is invoked with SSE-style event handlers for `sources`, `delta`, `assistant_message`, `error`. Citations array arrives via the `sources` event before the first `delta`, which means `renderInlineCitations` has the correct `chunkCount` from the first character of streamed text — good design.
- `useAutoScrollChat` in `chat-messages.tsx:355-366` calls `scrollIntoView({ behavior: "instant" })` on every message change AND on every `isStreaming` toggle. During streaming this re-fires once per delta because `messages` is a new array reference each `updateMessage` call. On long responses this may jank low-end devices, though I could not measure.
- Empty-state ("Generate 5 questions") and refresh button are wired in `empty-prompts.tsx`. The refresh button is only shown when `hasQuestions` is true, so after the first generation; before generation only the big "Generate 5 questions" CTA is shown. Reasonable.
- No `/v1/` SSE/streaming endpoint errors observed in the (limited) network log capture. No console errors observed in the (limited) console log capture.
