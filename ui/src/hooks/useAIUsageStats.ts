/**
 * Hook for fetching AI usage statistics.
 * Provides repository-level AI cost and token consumption data.
 */

import { useState, useEffect, useCallback } from 'react';
import { apiClient } from '@/lib/api';

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

export interface CostByOperation {
  code_review: number;
  pr_comments: number;
  documentation: number;
  other: number;
}

export interface MonthlyCostTrend {
  month: string;
  cost: number;
  tokens: number;
}

export interface PeakUsageDay {
  date: string;
  tokens: number;
  cost: number;
}

export interface AIUsageMetrics {
  total_tokens_consumed: number;
  total_cost: number;
  cost_by_operation: CostByOperation;
  models_used: ModelUsageData[];
  cost_per_pr_reviewed: number;
  cost_per_comment: number;

  peak_usage_day: PeakUsageDay;
}

export interface RepositoryBreakdown {
  repository: string;
  total_tokens: number;
  total_cost: number;
  prs_reviewed: number;
  cost_per_pr: number;
}

export interface AIUsageStatsData {
  success: boolean;
  total_repositories: number;
  aggregate_metrics: AIUsageMetrics;
  repository_breakdown: RepositoryBreakdown[];
  cost_optimization_suggestions: string[];
}

export interface UseAIUsageStatsOptions {
  autoRefresh?: boolean;
  refreshInterval?: number;
}

export interface UseAIUsageStatsReturn {
  data: AIUsageStatsData | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: string | null;
  refetch: () => Promise<void>;
}

export function useAIUsageStats(options: UseAIUsageStatsOptions = {}): UseAIUsageStatsReturn {
  const {
    autoRefresh = false,
    refreshInterval = 60000 // 1 minute default
  } = options;

  const [data, setData] = useState<AIUsageStatsData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setIsLoading(true);
    setError(null);

    try {
      const response = await apiClient.getAIUsageStats();
      
      if (response.success) {
        setData(response);
        setLastUpdated(new Date().toISOString());
        setError(null);
      } else {
        throw new Error('Failed to fetch AI usage statistics');
      }
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Unknown error occurred';
      setError(errorMessage);
      console.error('Error fetching AI usage stats:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial data fetch
  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Auto-refresh functionality
  useEffect(() => {
    if (!autoRefresh || refreshInterval <= 0) {
      return;
    }

    const interval = setInterval(() => {
      fetchData();
    }, refreshInterval);

    return () => clearInterval(interval);
  }, [autoRefresh, refreshInterval, fetchData]);

  const refetch = useCallback(async () => {
    await fetchData();
  }, [fetchData]);

  return {
    data,
    isLoading,
    error,
    lastUpdated,
    refetch
  };
}
