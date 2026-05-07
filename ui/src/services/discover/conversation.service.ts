import { 
  SaveConversationResponse, 
  ShareLinkResponse, 
  StoredMessagePayload 
} from "@/types/discover";
import { getApiBaseUrl } from "@/lib/environment";

export class ConversationServiceError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const conversationService = {
  async save(
    sessionId: string, 
    transcript: StoredMessagePayload[]
  ): Promise<SaveConversationResponse> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");
    
    const response = await fetch(
      `${apiBaseUrl}/api/v1/discover/sessions/${encodeURIComponent(sessionId)}/save`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ transcript }),
      }
    );

    if (!response.ok) {
      let detail = `Save failed with ${response.status}`;
      try {
        const payload = await response.json();
        if (payload?.detail) detail = String(payload.detail);
      } catch {
        // ignore
      }
      throw new ConversationServiceError(response.status, detail);
    }
    return response.json();
  },

  async share(
    sessionId: string, 
    transcript: StoredMessagePayload[] | null
  ): Promise<ShareLinkResponse> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");
    
    const body = transcript !== null ? { transcript } : {};
    const response = await fetch(
      `${apiBaseUrl}/api/v1/discover/sessions/${encodeURIComponent(sessionId)}/share`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      let detail = `Share failed with ${response.status}`;
      try {
        const payload = await response.json();
        if (payload?.detail) detail = String(payload.detail);
      } catch {
        // ignore
      }
      throw new ConversationServiceError(response.status, detail);
    }
    return response.json();
  },
};
