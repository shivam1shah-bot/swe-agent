import { McpTool } from "@/types/discover";
import { getApiBaseUrl } from "@/lib/environment";

export class ToolsServiceError extends Error {
  status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export const toolsService = {
  async getTools(): Promise<McpTool[]> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");

    const response = await fetch(`${apiBaseUrl}/api/v1/discover/tools`, {
      headers: {
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
    });

    if (!response.ok) {
      throw new ToolsServiceError(response.status, `Failed to get tools: ${response.status}`);
    }

    return response.json();
  },

  async getToolStatus(toolId: string): Promise<Pick<McpTool, "status" | "lastSync" | "latency">> {
    const apiBaseUrl = getApiBaseUrl();
    const token = localStorage.getItem("auth_token");

    const response = await fetch(
      `${apiBaseUrl}/api/v1/discover/tools/${encodeURIComponent(toolId)}/status`,
      {
        headers: {
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
      }
    );

    if (!response.ok) {
      throw new ToolsServiceError(response.status, `Failed to get tool status: ${response.status}`);
    }

    return response.json();
  },
};
