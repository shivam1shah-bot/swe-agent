/**
 * TypeScript interfaces for GitHub PR Metrics data.
 * These interfaces match the data schema provided by the GitHub metrics script.
 */

export interface Comment {
  id: number;
  url: string;
  created_at: string;
  body: string;
  user: string;
  is_bot: boolean;
}

export interface PRData {
  number: number;
  title: string;
  url: string;
  state: "open" | "closed" | "merged";
  created_at: string;
  merged_at?: string;
  bot_comments_count: number;
  has_ai_review?: boolean;
  comments: Comment[];
}

export interface AIReviewedPRData extends PRData {
  ai_effectiveness: "sufficient" | "insufficient";
  review_thread_count: number;
  ai_review_comments_count: number;
}

export interface PRRerunData {
  pr_number: number;
  title: string;
  url: string;
  rerun_count: number;
  rerun_dates: string[];
}

export interface BotAnalytics {
  total_bot_comments: number;
  merged_prs_with_bot_comments: number;
  merged_prs_with_bot_data: PRData[];
}

export interface AIReviewerAnalytics {
  total_ai_review_label_additions: number;
  prs_with_reruns: number;
  average_reruns_per_pr: number;
  max_reruns_in_single_pr: number;
  prs_with_reruns_data: PRRerunData[];
}

export interface AIEffectivenessMetrics {
  ai_reviewed_prs: number;
  ai_reviewed_and_merged_prs: number;
  merged_with_ai_only: number;
  merged_with_ai_and_human_reviews: number;
  change_requests_needed: number;
  comment_only_reviews: number;
  approvals_needed: number;
  average_human_reviews_after_ai: number;
  max_human_reviews_after_ai: number;
  complexity_adjusted_score: number;
  total_lines_reviewed: number;
  effective_lines_handled: number;
  small_prs_count: number;
  medium_prs_count: number;
  large_prs_count: number;
  small_prs_effectiveness: number;
  medium_prs_effectiveness: number;
  large_prs_effectiveness: number;
  ai_reviewed_merged_prs_data: AIReviewedPRData[];
}

export interface ModelUsageData {
  model_name: string;
  model_provider: "openai" | "anthropic" | "google" | "other";
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost: number;
  request_count: number;
  average_response_time_ms: number;
}

export interface AIUsageMetrics {
  total_tokens_consumed: number;
  total_cost: number;
  cost_by_operation: {
    code_review: number;
    pr_comments: number;
    documentation: number;
    other: number;
  };
  models_used: ModelUsageData[];
  cost_per_pr_reviewed: number;
  cost_per_comment: number;
  peak_usage_day: {
    date: string;
    tokens: number;
    cost: number;
  };
}

export interface RepositoryMetrics {
  repository: string;
  prs_raised: number;
  prs_merged: number;
  comments_added: number;
  date_range: string;
  bot_analytics: BotAnalytics;
  ai_reviewer_analytics: AIReviewerAnalytics;
  ai_effectiveness_metrics: AIEffectivenessMetrics;
  ai_usage_metrics: AIUsageMetrics;
  prs_raised_data: PRData[];
}

export interface GitHubMetrics {
  generated_at: string;
  metrics: RepositoryMetrics[];
}

// API Response interfaces
export interface GitHubMetricsResponse {
  success: boolean;
  data?: GitHubMetrics;
  last_updated?: string;
  filename?: string;
}

// UI-specific interfaces
export interface MetricCardProps {
  title: string;
  value: string | number;
  description?: string;
  icon?: React.ComponentType<{ className?: string }>;
  trend?: {
    value: number;
    isPositive: boolean;
  };
  className?: string;
}

export interface RepositoryCardProps {
  repository: RepositoryMetrics;
  isExpanded?: boolean;
  onToggleExpand?: () => void;
}

export interface ChartDataPoint {
  name: string;
  value: number;
  percentage?: number;
}

export interface EffectivenessData {
  small_prs: {
    count: number;
    effectiveness: number;
  };
  medium_prs: {
    count: number;
    effectiveness: number;
  };
  large_prs: {
    count: number;
    effectiveness: number;
  };
}
