import { DiscoverQueryRequest, StreamChunk } from "@/types/discover";
import { getApiBaseUrl } from "@/lib/environment";

export interface StreamCallbacks {
  onText: (text: string) => void;
  onSessionId: (sessionId: string) => void;
  onError: (error: string, errorType?: string) => void;
  onDone: () => void;
  onThinkingStart?: () => void;
  onThinking?: (text: string) => void;
  onToolUseStart?: (toolName: string) => void;
  onContentBlockStop?: () => void;
}

export async function streamDiscover(
  request: DiscoverQueryRequest,
  callbacks: StreamCallbacks,
  signal?: AbortSignal,
): Promise<void> {
  const apiBaseUrl = getApiBaseUrl();
  const token = localStorage.getItem("auth_token");
  
  const response = await fetch(`${apiBaseUrl}/api/v1/discover/query/stream`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      query: request.query,
      skill_name: request.skill_name,
      session_id: request.session_id ?? null,
    }),
    signal,
  });

  if (!response.ok) {
    throw new Error(`Discover API error: ${response.status} ${response.statusText}`);
  }

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      if (signal?.aborted) {
        await reader.cancel();
        return;
      }

      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (!line.startsWith("data:")) continue;

        try {
          const data: StreamChunk = JSON.parse(line.substring(5).trim());

          switch (data.type) {
            case "text":
              if (data.text) callbacks.onText(data.text);
              break;
            case "session_start":
            case "session_id":
              if (data.session_id) callbacks.onSessionId(data.session_id);
              break;
            case "thinking_start":
              callbacks.onThinkingStart?.();
              break;
            case "thinking":
              if (data.text) callbacks.onThinking?.(data.text);
              break;
            case "subagent_text":
              if (data.text) callbacks.onThinking?.(data.text);
              break;
            case "tool_use_start":
              if (data.tool_name) callbacks.onToolUseStart?.(data.tool_name);
              break;
            case "content_block_stop":
              callbacks.onContentBlockStop?.();
              break;
            case "error":
              callbacks.onError(data.error || "Unknown streaming error", data.error_type);
              break;
            case "done":
              callbacks.onDone();
              break;
          }
        } catch {
          // Skip malformed JSON lines
        }
      }
    }
  } catch (err) {
    if (signal?.aborted) return;
    throw err;
  }
}
