import { type RequestClient, USER_AGENT } from "../core.js";
import type {
  ChatCreateBody,
  ChatCreateResponse,
  ChatDetailResponse,
  ChatListResponse,
  ChatStreamEvent,
} from "../types.js";

export class ChatResource {
  constructor(private readonly _client: RequestClient) {}

  create(body: ChatCreateBody): Promise<ChatCreateResponse> {
    return this._client._request("POST", "/v1/chat", { json: { ...body, stream: false } });
  }

  async *stream(body: ChatCreateBody): AsyncGenerator<ChatStreamEvent> {
    const headers: Record<string, string> = {
      "Content-Type": "application/json",
      "User-Agent": USER_AGENT,
    };
    if (this._client.apiKey) headers.Authorization = `Bearer ${this._client.apiKey}`;
    const response = await this._client._fetch(`${this._client.baseUrl}/v1/chat`, {
      method: "POST",
      headers,
      body: JSON.stringify({ ...body, stream: true }),
    });
    if (!response.ok || !response.body) {
      throw new Error(await response.text().catch(() => response.statusText));
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const frames = buffer.split("\n\n");
      buffer = frames.pop() ?? "";
      for (const frame of frames) {
        const event = parseFrame(frame);
        if (event) yield event;
      }
    }
  }

  list(options: { limit?: number; offset?: number } = {}): Promise<ChatListResponse> {
    const params: Record<string, string> = {};
    if (options.limit !== undefined) params.limit = String(options.limit);
    if (options.offset !== undefined) params.offset = String(options.offset);
    return this._client._request("GET", "/v1/chat", { params });
  }

  get(conversationId: string): Promise<ChatDetailResponse> {
    return this._client._request("GET", `/v1/chat/${conversationId}`);
  }

  update(conversationId: string, body: { title: string }): Promise<ChatDetailResponse> {
    return this._client._request("PATCH", `/v1/chat/${conversationId}`, { json: body });
  }

  delete(conversationId: string): Promise<{ status: "deleted" }> {
    return this._client._request("DELETE", `/v1/chat/${conversationId}`);
  }
}

function parseFrame(frame: string): ChatStreamEvent | null {
  let eventName = "message";
  const data: string[] = [];
  for (const line of frame.split("\n")) {
    if (line.startsWith("event: ")) eventName = line.slice(7).trim();
    else if (line.startsWith("data: ")) data.push(line.slice(6));
  }
  const payload = data.join("\n");
  if (!payload || payload === "[DONE]") return null;
  return { event: eventName, data: JSON.parse(payload) } as ChatStreamEvent;
}
