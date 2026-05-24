export interface SSEFrame {
  event: string;
  data: string;
}

export async function* parseSSEFrames(response: Response): AsyncGenerator<SSEFrame> {
  const body = response.body;
  if (!body) return;

  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let event = "message";
  let dataLines: string[] = [];

  const flush = (): SSEFrame | null => {
    const payload = dataLines.join("\n");
    if (!payload || payload === "[DONE]") return null;
    return { event, data: payload };
  };

  const consumeLine = (rawLine: string): SSEFrame | null => {
    const line = rawLine.endsWith("\r") ? rawLine.slice(0, -1) : rawLine;
    if (line === "") {
      const frame = flush();
      event = "message";
      dataLines = [];
      return frame;
    }
    if (line.startsWith(":")) return null;
    if (line.startsWith("event:")) {
      event = line.slice(6).replace(/^ /, "");
    } else if (line.startsWith("data:")) {
      dataLines.push(line.slice(5).replace(/^ /, ""));
    }
    return null;
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split(/\r?\n/);
      buffer = lines.pop() ?? "";

      for (const rawLine of lines) {
        const frame = consumeLine(rawLine);
        if (frame) yield frame;
      }
    }

    const tail = buffer.endsWith("\r") ? buffer.slice(0, -1) : buffer;
    if (tail) consumeLine(tail);
    const trailing = flush();
    if (trailing) yield trailing;
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
