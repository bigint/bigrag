import { type RequestClient, USER_AGENT } from "../core.js";
import { errorForStatus } from "../errors.js";
import { parseSSEFrames } from "../sse.js";
import type { ChatCreateBody, ChatCreateResponse, ChatStreamEvent } from "../types/index.js";

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
      const message = await response.text().catch(() => response.statusText);
      throw errorForStatus(response.status, message);
    }

    for await (const frame of parseSSEFrames(response)) {
      yield { event: frame.event, data: JSON.parse(frame.data) } as ChatStreamEvent;
    }
  }
}
