import { McpCredential } from "@/types/discover";
import { getApiBaseUrl } from "@/lib/environment";

/**
 * Credentials Service
 *
 * NOTE: Credentials are stored ONLY on the backend. This service acts as a
 * proxy to the discover backend's credential management endpoints. No client-side
 * storage is used for security reasons.
 */

export class CredentialsServiceError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const credentialsService = {
  async getCredential(toolId: string): Promise<McpCredential | null> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");

    const response = await fetch(
      `${apiBaseUrl}/api/v1/discover/credentials/${encodeURIComponent(toolId)}`,
      {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }
    );

    if (response.status === 404) {
      return null;
    }

    if (!response.ok) {
      throw new CredentialsServiceError(response.status, `Failed to get credential: ${response.status}`);
    }

    return response.json();
  },

  async saveCredential(credential: Omit<McpCredential, "id" | "updatedAt">): Promise<McpCredential> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");

    const newCredential: McpCredential = {
      ...credential,
      id: crypto.randomUUID(),
      updatedAt: new Date().toISOString(),
    };

    const response = await fetch(`${apiBaseUrl}/api/v1/discover/credentials`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify(newCredential),
    });

    if (!response.ok) {
      throw new CredentialsServiceError(response.status, `Failed to save credential: ${response.status}`);
    }

    return response.json();
  },

  async deleteCredential(toolId: string): Promise<void> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");

    const response = await fetch(
      `${apiBaseUrl}/api/v1/discover/credentials/${encodeURIComponent(toolId)}`,
      {
        method: "DELETE",
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }
    );

    if (!response.ok && response.status !== 404) {
      throw new CredentialsServiceError(response.status, `Failed to delete credential: ${response.status}`);
    }
  },
};
