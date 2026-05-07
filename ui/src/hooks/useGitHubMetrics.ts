/**
 * Custom hook for fetching GitHub metrics data with auto-refresh capability.
 * Follows Single Responsibility Principle - handles only data fetching logic.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { GitHubMetrics, GitHubMetricsResponse } from '@/types/github-metrics';
import { getApiBaseUrl } from '@/lib/environment';
import { getAuthHeader } from '@/lib/auth';

interface UseGitHubMetricsOptions {
  autoRefresh?: boolean;
  refreshInterval?: number; // in milliseconds
}

interface UseGitHubMetricsReturn {
  data: GitHubMetrics | null;
  isLoading: boolean;
  error: string | null;
  lastUpdated: string | null;
  filename: string | null;
  refetch: () => Promise<void>;
}

export function useGitHubMetrics(options: UseGitHubMetricsOptions = {}): UseGitHubMetricsReturn {
  const { autoRefresh = true, refreshInterval = 30000 } = options; // Default 30 seconds
  
  const [data, setData] = useState<GitHubMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<string | null>(null);
  const [filename, setFilename] = useState<string | null>(null);
  
  const intervalRef = useRef<NodeJS.Timeout | null>(null);

  const fetchMetrics = useCallback(async () => {
    try {
      setIsLoading(true);
      setError(null);

      // Get auth header and API base URL from the existing configuration system
      const authHeader = await getAuthHeader();
      const apiBaseUrl = getApiBaseUrl();

      const response = await fetch(`${apiBaseUrl}/api/v1/code-review/metrics`, {
        method: 'GET',
        headers: {
          'Content-Type': 'application/json',
          ...authHeader, // Use the existing auth system
        },
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        
        if (response.status === 404) {
          throw new Error(
            errorData.detail?.message || 
            'No GitHub metrics file found. Please upload a metrics JSON file first.'
          );
        }
        
        if (response.status === 422) {
          throw new Error(
            errorData.detail?.message || 
            'Invalid metrics file format. Please check your JSON file.'
          );
        }

        throw new Error(`Failed to fetch metrics: ${response.status} ${response.statusText}`);
      }

      const result: GitHubMetricsResponse = await response.json();

      if (!result.success || !result.data) {
        throw new Error('Invalid response format from server');
      }

      setData(result.data);
      setLastUpdated(result.last_updated || null);
      setFilename(result.filename || null);

    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to fetch GitHub metrics';
      setError(errorMessage);
      console.error('Error fetching GitHub metrics:', err);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // Auto-refresh setup
  useEffect(() => {
    if (autoRefresh && refreshInterval > 0) {
      intervalRef.current = setInterval(fetchMetrics, refreshInterval);

      return () => {
        if (intervalRef.current) {
          clearInterval(intervalRef.current);
        }
      };
    }
  }, [autoRefresh, refreshInterval, fetchMetrics]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, []);

  return {
    data,
    isLoading,
    error,
    lastUpdated,
    filename,
    refetch: fetchMetrics,
  };
}