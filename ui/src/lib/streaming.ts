/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
/**
 * Streaming client for knowledge agents.
 * 
 * Provides a generic streaming client that handles SSE connections,
 * message sending, and session management for knowledge agents.
 */

import { getApiBaseUrl } from './environment';
import { getAuthHeader } from './auth';

export interface StreamingEvent {
  event_type: string;
  data: any;
  timestamp: string;
  turn_complete?: boolean;
  session_id?: string;
}

export interface SessionInfo {
  session_id: string;
  agent_id: string;
  agent_name: string;
  status: string;
  created_at: string;
  transport_type: string;
}

export interface AgentInfo {
  id: string;
  name: string;
  description: string;
  capabilities: string[];
}

export class StreamingClient {
  private eventSource: EventSource | null = null;
  private sessionId: string | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 5000; // 5 seconds
  private onEventCallback: ((event: StreamingEvent) => void) | null = null;
  private onConnectionCallback: ((connected: boolean) => void) | null = null;

  /**
   * Create a new streaming session for a knowledge agent.
   */
  async createSession(agentId: string): Promise<string> {
    try {
      // Get auth header for API request
      const authHeader = await getAuthHeader();
      
      const response = await fetch(`${getApiBaseUrl()}/api/v1/knowledge-agents/chat/sessions`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader,
        },
        body: JSON.stringify({
          agent_id: agentId,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(`Failed to create session: ${errorData.detail || response.statusText}`);
      }

      const data = await response.json();
      this.sessionId = data.session_id;
      
      if (!this.sessionId) {
        throw new Error('Session ID not received from server');
      }
      
      console.log('Created streaming session:', data);
      return this.sessionId;
    } catch (error) {
      console.error('Error creating session:', error);
      throw error;
    }
  }

  /**
   * Connect to the SSE event stream.
   */
  connectStream(
    onEvent: (event: StreamingEvent) => void,
    onConnection?: (connected: boolean) => void
  ): void {
    if (!this.sessionId) {
      throw new Error('No active session. Call createSession() first.');
    }

    this.onEventCallback = onEvent;
    this.onConnectionCallback = onConnection || null;
    
    // Start the async SSE connection
    this._connectSSE().catch(error => {
      console.error('Failed to connect SSE:', error);
      this.onConnectionCallback?.(false);
    });
  }

  /**
   * Send a message to the knowledge agent.
   * Automatically creates a session if none exists.
   */
  async sendMessage(message: string, agentId?: string): Promise<void> {
    // Auto-create session if needed
    if (!this.sessionId && agentId) {
      console.log('No active session, creating one automatically...');
      await this.createSession(agentId);
    }
    
    if (!this.sessionId) {
      throw new Error('No active session and no agentId provided to create one.');
    }

    try {
      // Get auth header for API request
      const authHeader = await getAuthHeader();
      
      const response = await fetch(
        `${getApiBaseUrl()}/api/v1/knowledge-agents/chat/sessions/${this.sessionId}/messages`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...authHeader,
          },
          body: JSON.stringify({
            message,
          }),
        }
      );

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({ detail: 'Unknown error' }));
        throw new Error(`Failed to send message: ${errorData.detail || response.statusText}`);
      }

      console.log('Message sent successfully');
    } catch (error) {
      console.error('Error sending message:', error);
      throw error;
    }
  }

  /**
   * Close the streaming connection and session.
   */
  async close(): Promise<void> {
    // Close SSE connection
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }

    // Close session on server
    if (this.sessionId) {
      try {
        const authHeader = await getAuthHeader();
        await fetch(
          `${getApiBaseUrl()}/api/v1/knowledge-agents/chat/sessions/${this.sessionId}`,
          {
            method: 'DELETE',
            headers: {
              ...authHeader
            }
          }
        );
        console.log('Session closed successfully');
      } catch (error) {
        console.error('Error closing session:', error);
      }
      
      this.sessionId = null;
    }

    // Reset state
    this.reconnectAttempts = 0;
    this.onEventCallback = null;
    this.onConnectionCallback = null;
  }

  /**
   * Get information about the current session.
   */
  async getSessionInfo(): Promise<SessionInfo | null> {
    if (!this.sessionId) {
      return null;
    }

    try {
      // Get auth header for API request
      const authHeader = await getAuthHeader();
      
      const response = await fetch(
        `${getApiBaseUrl()}/api/v1/knowledge-agents/chat/sessions/${this.sessionId}`,
        {
          headers: authHeader,
        }
      );

      if (!response.ok) {
        return null;
      }

      const data = await response.json();
      return data.session;
    } catch (error) {
      console.error('Error getting session info:', error);
      return null;
    }
  }

  /**
   * Get list of available knowledge agents.
   */
  static async getAvailableAgents(): Promise<AgentInfo[]> {
    try {
      // Get auth header for API request
      const authHeader = await getAuthHeader();
      
      const response = await fetch(`${getApiBaseUrl()}/api/v1/knowledge-agents/chat/agents`, {
        headers: authHeader,
      });
      
      if (!response.ok) {
        throw new Error(`Failed to get agents: ${response.statusText}`);
      }

      const data = await response.json();
      return data.agents;
    } catch (error) {
      console.error('Error getting available agents:', error);
      throw error;
    }
  }

  /**
   * Check if client is connected.
   */
  isConnected(): boolean {
    return this.eventSource !== null && this.eventSource.readyState === EventSource.OPEN;
  }

  /**
   * Get current session ID.
   */
  getSessionId(): string | null {
    return this.sessionId;
  }

  private async _connectSSE(): Promise<void> {
    if (!this.sessionId) {
      console.error('Cannot connect SSE without session ID');
      return;
    }

    try {
      console.log(`Connecting to SSE stream for session: ${this.sessionId}`);
      
      // Get auth header for SSE request
      const authHeader = await getAuthHeader();
      
      // Use fetch instead of EventSource to support authentication headers
      const response = await fetch(
        `${getApiBaseUrl()}/api/v1/knowledge-agents/chat/sessions/${this.sessionId}/events`,
        {
          headers: {
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
            ...authHeader,
          },
        }
      );

      if (!response.ok) {
        throw new Error(`SSE connection failed: ${response.status} ${response.statusText}`);
      }

      if (!response.body) {
        throw new Error('Response body is null');
      }

      // Create a manual SSE reader
      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      // Create mock EventSource for compatibility
      this.eventSource = {
        readyState: 1, // OPEN
        close: () => {
          reader.cancel();
          this.eventSource = null;
        }
      } as EventSource;

      // Signal connection opened
      console.log('SSE connection opened');
      this.reconnectAttempts = 0;
      this.onConnectionCallback?.(true);

      // Process SSE stream manually
      this._processSSEStream(reader, decoder);

    } catch (error) {
      console.error('Error setting up SSE connection:', error);
      this.onConnectionCallback?.(false);
      
      // Auto-reconnect logic
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
        
        setTimeout(() => {
          this._connectSSE();
        }, this.reconnectDelay);
      }
    }
  }

  private async _processSSEStream(reader: ReadableStreamDefaultReader<Uint8Array>, decoder: TextDecoder): Promise<void> {
    let buffer = '';

    try {
      while (true) {
        const { done, value } = await reader.read();
        
        if (done) {
          console.log('SSE stream ended');
          this.onConnectionCallback?.(false);
          break;
        }

        // Decode the chunk and add to buffer
        buffer += decoder.decode(value, { stream: true });

        // Process complete SSE events
        const lines = buffer.split('\n');
        buffer = lines.pop() || ''; // Keep incomplete line in buffer

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = line.substring(6); // Remove 'data: '
              if (data.trim()) {
                const streamingEvent: StreamingEvent = JSON.parse(data);
                console.log('Received SSE event:', streamingEvent);
                this.onEventCallback?.(streamingEvent);
              }
            } catch (error) {
              console.error('Error parsing SSE event:', error);
            }
          }
        }
      }
    } catch (error) {
      console.error('Error reading SSE stream:', error);
      this.onConnectionCallback?.(false);
      
      // Auto-reconnect logic
      if (this.reconnectAttempts < this.maxReconnectAttempts) {
        this.reconnectAttempts++;
        console.log(`Attempting to reconnect (${this.reconnectAttempts}/${this.maxReconnectAttempts})...`);
        
        setTimeout(() => {
          this._connectSSE();
        }, this.reconnectDelay);
      }
    } finally {
      reader.releaseLock();
    }
  }
}
