/**
 * AI Hub - Types for the AI Stack Dashboard
 * 
 * These types define the structure of AI tool data displayed in the AI Hub.
 * Data is fetched from /data/ai-tools.json at runtime.
 */

export type ToolType = 
  | 'Plugin' 
  | 'MCP' 
  | 'Skill' 
  | 'Agent' 
  | 'Langgraph Agent'
  | 'Service' 
  | 'Platform' 
  | 'Multi-Agent'

export type ProdReadyStatus = 'Yes' | 'Partially' | 'No' | 'Preview'

export interface Tool {
  /** Unique identifier for the tool (URL-safe slug) */
  id: string
  /** SDLC stage this tool belongs to */
  stage: string
  /** Emoji representing the stage */
  stageEmoji: string
  /** Tool name */
  name: string
  /** Type of AI tool */
  type: ToolType
  /** Point of contact person */
  poc: string
  /** Owning team */
  team: string
  /** List of capabilities */
  canDo: string[]
  /** List of limitations */
  cantDo: string[]
  /** Current state/status description */
  state: string
  /** Production readiness status */
  prodReady: ProdReadyStatus
  /** Slack channel for support (optional) */
  slackChannel?: string
  /** Documentation link (optional) */
  docsLink?: string
}

export interface AiToolsData {
  /** Schema version */
  version: string
  /** Last updated date (ISO 8601) */
  updated: string
  /** Total number of tools */
  count: number
  /** Array of tools */
  tools: Tool[]
}

export interface AiHubStats {
  total: number
  ga: number
  preview: number
  dev: number
}
