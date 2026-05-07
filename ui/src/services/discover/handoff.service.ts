import { PendingMessage } from "@/types/discover";
import { getApiBaseUrl } from "@/lib/environment";

export class HandoffServiceError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const handoffService = {
  async attachSession(refId: string, sessionId: string): Promise<void> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");

    const response = await fetch(
      `${apiBaseUrl}/api/v1/discover/handoff/${encodeURIComponent(refId)}/attach`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ session_id: sessionId }),
      }
    );

    if (!response.ok) {
      let detail = `Handoff attach failed with ${response.status}`;
      try {
        const payload = await response.json();
        if (payload?.detail) detail = String(payload.detail);
      } catch {
        // ignore
      }
      throw new HandoffServiceError(response.status, detail);
    }
  },

  async getPendingMessages(runtimeSessionId: string): Promise<PendingMessage[]> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");

    const response = await fetch(
      `${apiBaseUrl}/api/v1/discover/handoff/pending/${encodeURIComponent(runtimeSessionId)}`,
      {
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }
    );

    if (!response.ok) {
      throw new HandoffServiceError(response.status, `Failed to get pending messages: ${response.status}`);
    }

    return response.json();
  },
};
