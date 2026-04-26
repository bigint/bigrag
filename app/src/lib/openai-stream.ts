export type OpenAIMessage = { role: "system" | "user" | "assistant"; content: string };

export type StreamOptions = {
  apiKey: string;
  model: string;
  messages: OpenAIMessage[];
  temperature?: number;
  signal?: AbortSignal;
  onToken: (delta: string) => void;
};

export class OpenAIStreamError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

export const streamOpenAI = async (opts: StreamOptions): Promise<void> => {
  const res = await fetch("https://api.openai.com/v1/chat/completions", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${opts.apiKey}`,
    },
    body: JSON.stringify({
      model: opts.model,
      messages: opts.messages,
      temperature: opts.temperature ?? 0.2,
      stream: true,
    }),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    let detail = "OpenAI request failed";
    try {
      const err = (await res.json()) as { error?: { message?: string } };
      if (err.error?.message) detail = err.error.message;
    } catch {
      detail = `${res.status} ${res.statusText}`;
    }
    throw new OpenAIStreamError(detail, res.status);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const frames = buffer.split("\n\n");
    buffer = frames.pop() ?? "";

    for (const frame of frames) {
      const dataLines = frame
        .split("\n")
        .filter((line) => line.startsWith("data: "))
        .map((line) => line.slice(6));
      for (const payload of dataLines) {
        if (payload === "[DONE]") return;
        try {
          const parsed = JSON.parse(payload) as {
            choices?: { delta?: { content?: string } }[];
          };
          const delta = parsed.choices?.[0]?.delta?.content;
          if (delta) opts.onToken(delta);
        } catch {}
      }
    }
  }
};
