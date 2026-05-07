/* eslint-disable @typescript-eslint/no-explicit-any -- TODO: Fix types gradually */
/**
 * React hook for knowledge agent streaming.
 * 
 * Provides a React interface for streaming communication with knowledge agents,
 * including message handling, tool execution tracking, and connection management.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { StreamingClient, StreamingEvent, AgentInfo } from '@/lib/streaming';

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
  status?: 'sending' | 'sent' | 'error';
}

export interface ToolExecution {
  id: string;
  name: string;
  args: any;
  result?: any;
  status: 'executing' | 'completed' | 'error';
  startTime: Date;
  endTime?: Date;
}

export interface ConnectionStatus {
  connected: boolean;
  sessionId: string | null;
  reconnecting: boolean;
  error: string | null;
}

export interface UseKnowledgeAgentStreamingReturn {
  // Messages
  messages: ChatMessage[];
  sendMessage: (message: string) => Promise<void>;
  
  // Tool executions
  toolExecutions: ToolExecution[];
  
  // Connection
  connectionStatus: ConnectionStatus;
  connect: (agentId: string) => Promise<void>;
  disconnect: () => Promise<void>;
  
  // Agent info
  agentInfo: AgentInfo | null;
  
  // State
  isLoading: boolean;
  isSending: boolean;
  error: string | null;
  
  // Available agents
  availableAgents: AgentInfo[];
  loadAvailableAgents: () => Promise<void>;
}

export function useKnowledgeAgentStreaming(): UseKnowledgeAgentStreamingReturn {
  // State
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [toolExecutions, setToolExecutions] = useState<ToolExecution[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<ConnectionStatus>({
    connected: false,
    sessionId: null,
    reconnecting: false,
    error: null,
  });
  const [agentInfo, setAgentInfo] = useState<AgentInfo | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isSending, setIsSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [availableAgents, setAvailableAgents] = useState<AgentInfo[]>([]);

  // Refs
  const clientRef = useRef<StreamingClient | null>(null);
  const currentMessageRef = useRef<ChatMessage | null>(null);
  const currentAgentIdRef = useRef<string | null>(null);

  /**
   * Handle streaming events from the agent.
   */
  const handleStreamingEvent = useCallback((event: StreamingEvent) => {
    console.log('Processing streaming event:', event);

    switch (event.event_type) {
      case 'tool_execution_start': {
        // Skip unknown tool executions
        if (event.data.tool_name === 'unknown') {
          console.log('Skipping unknown tool execution');
          break;
        }
        
        const newExecution: ToolExecution = {
          id: `${event.data.tool_name}_${Date.now()}`,
          name: event.data.tool_name,
          args: event.data.tool_args,
          status: 'executing',
          startTime: new Date(event.timestamp),
        };
        
        setToolExecutions(prev => [...prev, newExecution]);
        break;
      }

      case 'tool_execution_complete':
        // Skip unknown tool executions
        if (event.data.tool_name === 'unknown') {
          console.log('Skipping unknown tool completion');
          break;
        }
        
        setToolExecutions(prev => prev.map(exec => 
          exec.name === event.data.tool_name && exec.status === 'executing'
            ? {
                ...exec,
                result: event.data.tool_result,
                status: 'completed' as const,
                endTime: new Date(event.timestamp)
              }
            : exec
        ));
        break;

      case 'agent_message':
        // Handle streaming text from agent
        if (event.data.partial) {
          // Update current message with new content
          if (currentMessageRef.current) {
            currentMessageRef.current.content += event.data.content;
            setMessages(prev => prev.map(msg => 
              msg.id === currentMessageRef.current?.id 
                ? { ...msg, content: currentMessageRef.current.content }
                : msg
            ));
          } else {
            // Start new message
            const newMessage: ChatMessage = {
              id: `agent_${Date.now()}`,
              role: 'assistant',
              content: event.data.content,
              timestamp: new Date(event.timestamp),
              status: 'sent'
            };
            currentMessageRef.current = newMessage;
            setMessages(prev => [...prev, newMessage]);
          }
        } else {
          // Complete message
          const completeMessage: ChatMessage = {
            id: `agent_${Date.now()}`,
            role: 'assistant',
            content: event.data.content,
            timestamp: new Date(event.timestamp),
            status: 'sent'
          };
          
          if (currentMessageRef.current) {
            // Update existing partial message
            setMessages(prev => prev.map(msg => 
              msg.id === currentMessageRef.current?.id 
                ? completeMessage
                : msg
            ));
          } else {
            // Add new complete message
            setMessages(prev => [...prev, completeMessage]);
          }
          currentMessageRef.current = null;
        }
        break;

      case 'turn_complete':
        // Finalize the current conversation turn
        currentMessageRef.current = null;
        setIsSending(false);
        console.log('Turn completed');
        break;

      case 'error':
        console.error('Agent error:', event.data);
        setError(event.data.message || 'Agent processing error');
        setIsSending(false);
        currentMessageRef.current = null;
        break;

      case 'connection_opened':
        console.log('Connection established');
        break;

      case 'connection_closed':
        console.log('Connection closed');
        break;
    }
  }, []);

  /**
   * Handle connection status changes.
   */
  const handleConnectionChange = useCallback((connected: boolean) => {
    setConnectionStatus(prev => ({
      ...prev,
      connected,
      reconnecting: !connected && prev.connected, // Reconnecting if was connected
    }));
  }, []);

  /**
   * Connect to a knowledge agent.
   */
  const connect = useCallback(async (agentId: string) => {
    try {
      setIsLoading(true);
      setError(null);

      // Store current agent ID for automatic session creation
      currentAgentIdRef.current = agentId;

      // Find agent info
      const agent = availableAgents.find(a => a.id === agentId);
      if (agent) {
        setAgentInfo(agent);
      }

      // Create client and session
      const client = new StreamingClient();
      const sessionId = await client.createSession(agentId);
      
      // Store client reference first
      clientRef.current = client;
      
      // Set initial connection status (not connected yet)
      setConnectionStatus({
        connected: false,
        sessionId,
        reconnecting: false,
        error: null,
      });
      
      // Connect to stream - handleConnectionChange will set connected: true when ready
      client.connectStream(handleStreamingEvent, handleConnectionChange);

      console.log(`Created session ${sessionId} for agent ${agentId}, establishing SSE connection...`);
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Connection failed';
      setError(errorMessage);
      setConnectionStatus(prev => ({
        ...prev,
        connected: false,
        error: errorMessage,
      }));
    } finally {
      setIsLoading(false);
    }
  }, [availableAgents, handleStreamingEvent, handleConnectionChange]);

  /**
   * Disconnect from the current agent.
   */
  const disconnect = useCallback(async () => {
    if (clientRef.current) {
      await clientRef.current.close();
      clientRef.current = null;
    }

    setConnectionStatus({
      connected: false,
      sessionId: null,
      reconnecting: false,
      error: null,
    });
    setMessages([]);
    setToolExecutions([]);
    setAgentInfo(null);
    setError(null);
    currentMessageRef.current = null;
    currentAgentIdRef.current = null;
  }, []);

  /**
   * Send a message to the agent.
   */
  const sendMessage = useCallback(async (message: string) => {
    try {
      setIsSending(true);
      setError(null);

      // Auto-reconnect if needed
      if (!clientRef.current && currentAgentIdRef.current) {
        console.log('No client, reconnecting to agent...');
        await connect(currentAgentIdRef.current);
      }

      if (!clientRef.current) {
        throw new Error('Unable to establish connection to agent');
      }

      // Add user message to chat
      const userMessage: ChatMessage = {
        id: `user_${Date.now()}`,
        role: 'user',
        content: message,
        timestamp: new Date(),
        status: 'sending'
      };
      setMessages(prev => [...prev, userMessage]);

      // Send to agent with automatic session creation if needed
      await clientRef.current.sendMessage(message, currentAgentIdRef.current || undefined);
      
      // Update user message status to sent on success
      setMessages(prev => prev.map(msg => 
        msg.role === 'user' && msg.status === 'sending' && msg.id === userMessage.id
          ? { ...msg, status: 'sent' as const }
          : msg
      ));
      
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Failed to send message';
      setError(errorMessage);
      setIsSending(false);
      
      // Update user message status
      setMessages(prev => prev.map(msg => 
        msg.role === 'user' && msg.status === 'sending'
          ? { ...msg, status: 'error' as const }
          : msg
      ));
    }
  }, [connect]);

  /**
   * Load available knowledge agents.
   */
  const loadAvailableAgents = useCallback(async () => {
    try {
      const agents = await StreamingClient.getAvailableAgents();
      setAvailableAgents(agents);
    } catch (error) {
      console.error('Failed to load available agents:', error);
      setError('Failed to load available agents');
    }
  }, []);

  /**
   * Clean up on unmount.
   */
  useEffect(() => {
    return () => {
      if (clientRef.current) {
        clientRef.current.close();
      }
    };
  }, []);

  /**
   * Load available agents on mount.
   */
  useEffect(() => {
    loadAvailableAgents();
  }, [loadAvailableAgents]);

  return {
    // Messages
    messages,
    sendMessage,
    
    // Tool executions
    toolExecutions,
    
    // Connection
    connectionStatus,
    connect,
    disconnect,
    
    // Agent info
    agentInfo,
    
    // State
    isLoading,
    isSending,
    error,
    
    // Available agents
    availableAgents,
    loadAvailableAgents,
  };
}
