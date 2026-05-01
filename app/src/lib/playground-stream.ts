type PlaygroundMessage = { role: "system" | "user" | "assistant"; content: string };

type StreamOptions = {
  model: string;
  messages: PlaygroundMessage[];
  temperature?: number;
  signal?: AbortSignal;
  onToken: (delta: string) => void;
};

class PlaygroundStreamError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
  }
}

export const streamPlaygroundChat = async (opts: StreamOptions): Promise<void> => {
  const res = await fetch("/api/bigrag/v1/playground/chat", {
    method: "POST",
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      model: opts.model,
      messages: opts.messages,
      temperature: opts.temperature ?? 0.2,
    }),
    signal: opts.signal,
  });

  if (!res.ok || !res.body) {
    let detail = "OpenAI request failed";
    try {
      const err = (await res.json()) as { detail?: string };
      if (err.detail) detail = err.detail;
    } catch {
      detail = `${res.status} ${res.statusText}`;
    }
    throw new PlaygroundStreamError(detail, res.status);
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
        let parsed: { delta?: string; error?: string };
        try {
          parsed = JSON.parse(payload) as { delta?: string; error?: string };
        } catch {
          continue;
        }
        if (parsed.error) throw new PlaygroundStreamError(parsed.error);
        if (parsed.delta) opts.onToken(parsed.delta);
      }
    }
  }
};
