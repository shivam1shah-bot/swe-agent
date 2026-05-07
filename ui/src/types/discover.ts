/**
 * Discover feature types - migrated from discover-ui
 */

// Chat and messaging types
export interface CodeRef {
  file_path: string;
  line_number: number;
  snippet: string;
  repository: string;
}

export interface DocLink {
  title: string;
  url: string;
  source: string;
}

export interface DiscoverQueryRequest {
  query: string;
  skill_name: string;
  session_id?: string;
}

export interface DiscoverQueryResponse {
  answer: string;
  code_refs: CodeRef[];
  doc_links: DocLink[];
  session_id: string;
}

export interface ToolUseInfo {
  name: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  code_refs?: CodeRef[];
  doc_links?: DocLink[];
  timestamp: Date;
  isLoading?: boolean;
  isStreaming?: boolean;
  isProcessing?: boolean;
  thinking?: string;
  isThinking?: boolean;
  activeTools?: ToolUseInfo[];
  processingStatus?: string;
  startedAt?: number;
  completedAt?: number;
}

export interface StreamChunk {
  type:
    | "session_start"
    | "text"
    | "session_id"
    | "done"
    | "error"
    | "thinking_start"
    | "thinking"
    | "tool_use_start"
    | "content_block_stop"
    | "subagent_text";
  text?: string;
  session_id?: string;
  error?: string;
  error_type?: string;
  tool_name?: string;
}

// Storage types
export interface StoredChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  code_refs?: CodeRef[];
  doc_links?: DocLink[];
  timestamp: string;
}

export interface ChatHistoryEntry {
  id: string;
  query: string;
  title?: string;
  timestamp: string;
  messages?: StoredChatMessage[];
  session_id?: string;
  saved_expires_at?: string;
  share_url?: string;
  share_expires_at?: string;
}

// Service response types
export interface SaveConversationResponse {
  success: boolean;
  expires_at: string;
}

export interface ShareLinkResponse {
  share_id: string;
  url: string;
  expires_at: string;
}

export interface StoredMessagePayload {
  id: string;
  role: string;
  content: string;
  code_refs?: unknown[];
  doc_links?: string[];
  timestamp: string;
}

// MCP Tool types
export interface McpTool {
  id: string;
  name: string;
  displayName: string;
  description: string;
  icon: string;
  authType: "oauth" | "api_key" | "token" | "none";
  category: string;
  status: "connected" | "error" | "needs_credentials" | "unknown";
  lastSync?: string;
  latency?: number;
}

export interface McpCredential {
  id: string;
  toolId: string;
  type: "oauth" | "api_key" | "token";
  value: string;
  updatedAt: string;
}

// Search result types
export interface SearchResult {
  id: string;
  title: string;
  description: string;
  tool: string;
  toolName: string;
  type: string;
  url?: string;
  timestamp: string;
  metadata?: Record<string, unknown>;
}

// Agent types (for future use)
export interface Agent {
  id: string;
  name: string;
  description: string;
  icon: string;
  domain: string;
}

// Handoff types
export interface HandoffSessionData {
  initial_query?: string;
  resume_session_id?: string | null;
  runtime_session_id?: string;
  auto_run?: boolean;
  ref_id?: string;
}

export interface PendingMessage {
  question: string;
  answer?: string;
}
