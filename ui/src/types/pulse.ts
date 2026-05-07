// ─── Pulse (AI Usage Analytics) Type Definitions ───

// Formatter helpers (ported from frontend/src/utils/formatters.js)
export function fmtCost(c: number | null | undefined): string {
  if (!c && c !== 0) return '\u2014'
  if (c >= 1) return '$' + c.toFixed(2)
  if (c >= 0.001) return '$' + c.toFixed(4)
  return '$' + c.toFixed(5)
}

export function fmtTokens(n: number | null | undefined): string {
  if (!n) return '0'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  if (n >= 1_000) return Math.round(n / 1_000) + 'K'
  return n.toLocaleString()
}

export function fmtTime(ts: string | number | null | undefined): string {
  if (!ts) return ''
  try {
    const d = new Date(ts)
    const now = new Date()
    const s = (now.getTime() - d.getTime()) / 1000
    if (s < 60) return Math.floor(s) + 's ago'
    if (s < 3600) return Math.floor(s / 60) + 'm ago'
    if (s < 86400) return Math.floor(s / 3600) + 'h ago'
    return d.toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })
  } catch {
    return String(ts).slice(0, 10)
  }
}

export function modelShort(m: string | null | undefined): string {
  return (m || '').replace('claude-', '').replace(/-\d{4}-\d{2}-\d{2}$/, '')
}

export function fmtCompact(n: number | null | undefined): string {
  if (!n && n !== 0) return '0'
  if (n < 10000) return Math.round(n).toLocaleString()
  if (n >= 1_000_000_000) return (n / 1_000_000_000).toFixed(1) + 'B'
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + 'M'
  return (n / 1_000).toFixed(1) + 'K'
}

// ─── Tooltip content ───
export const pulseTooltips = {
  totalCost: "Estimated total cost across all AI prompts, calculated using each model's per-token pricing.",
  totalTokens: "Sum of all input and output tokens consumed across every AI interaction.",
  totalPrompts: "Total number of AI prompts sent across all tracked repositories and developers.",
  aiLines: "Lines of code written or modified with AI assistance, based on git diff attribution.",
  cacheSavings: "Money saved by using cached input tokens instead of re-sending at full price.",
  reposTracked: "Number of repositories currently tracked for AI usage analytics.",
  weeklyCostChart: "Weekly AI spending (bars) overlaid with prompts sent (line). Rising costs with stable prompts may indicate heavier usage per session.",
  modelDistribution: "Prompts per Claude model. Opus is most capable but costlier; Sonnet offers a good cost/capability balance.",
  turnType: "Turn types: 'write' = AI modified files, 'read' = read-only, 'mixed' = both, 'text' = conversation.",
}

// ─── API Response Types ───

export interface PulseOverview {
  total_cost_usd: number
  total_tokens: number
  total_prompts: number
  total_ai_lines: number
  total_human_lines: number
  ai_percentage: number
  cache_saved_usd: number
  repo_count: number
  weekly: PulseWeeklyData[]
  model_distribution: Record<string, number>
  turn_type_dist: Record<string, number>
}

export interface PulseWeeklyData {
  week: string
  cost: number
  prompts: number
  ai_lines: number
  tokens: number
}

export interface PulseRepo {
  rank: number
  repo: string
  total_cost_usd: number
  total_tokens: number
  total_prompts: number
  write_prompts: number
  read_prompts: number
  ai_lines: number
  human_lines: number
  ai_percentage: number
  commits: number
  contributors: number
  models: string[]
  contributor_list?: PulseContributor[]
}

export interface PulseContributor {
  email: string
  prompts: number
  tokens: number
  cost_usd: number
}

export interface PulseCommit {
  rank: number
  commit_sha: string
  commit_message: string
  commit_author: string
  author_email: string
  branch: string
  repo: string
  ai_percentage: number
  total_tokens: number
  input_tokens: number
  output_tokens: number
  cache_read: number
  cache_creation: number
  cost_usd: number
  ai_lines: number
  human_lines: number
  prompt_count: number
  timestamp: string | number
  prompts?: PulseCommitPrompt[]
}

export interface PulseCommitPrompt {
  prompt: string
  model: string
  cost_usd: number
  total_tokens: number
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_creation_tokens: number
  turn_type: string
  timestamp: string
  branch?: string
  author?: string
  tools_used: string[]
  skill_invoked?: string
  assistant_preview?: string
}

export interface PulsePromptDetail {
  rank: number
  prompt_id?: string
  prompt: string
  model: string
  turn_type: string
  input_tokens: number
  output_tokens: number
  cache_read_tokens: number
  cache_creation_tokens: number
  total_tokens: number
  cost_usd: number
  timestamp: string | number
  author: string
  repo: string
  branch?: string
  skill_invoked?: string
  tools_used?: string[]
  assistant_preview?: string
}

export interface PulsePerson {
  rank: number
  email: string
  total_prompts: number
  write_prompts: number
  read_prompts: number
  ai_lines: number
  commits: number
  total_tokens: number
  total_cost_usd: number
  repos?: string[]
  top_prompts?: PulsePromptDetail[]
}

export interface PulseQueryParams {
  days?: number | null
  sort?: string
  repo?: string | null
  email?: string | null
  limit?: number
  offset?: number
}

export interface PulsePaginatedResponse<T> {
  total: number
  offset: number
  limit: number
  repos?: T[]
  commits?: T[]
  prompts?: T[]
  people?: T[]
}
