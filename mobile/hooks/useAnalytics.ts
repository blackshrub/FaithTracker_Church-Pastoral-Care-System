/**
 * useAnalytics - Hook for fetching analytics data
 *
 * Provides analytics data for the dashboard including:
 * - Member statistics
 * - Demographics (age, gender, category distribution)
 * - Engagement trends
 * - Financial aid summary
 * - Care events by type
 */

import { useQuery } from '@tanstack/react-query';

import api from '@/services/api';
import { API_ENDPOINTS } from '@/constants/api';
import type { AnalyticsDashboard } from '@/types';

// ============================================================================
// TYPES
// ============================================================================

export type TimeRange = 'all' | 'year' | '6months' | '3months' | 'month';

interface UseAnalyticsOptions {
  timeRange?: TimeRange;
  enabled?: boolean;
}

// ============================================================================
// HOOK
// ============================================================================

export function useAnalytics({ timeRange = 'all', enabled = true }: UseAnalyticsOptions = {}) {
  return useQuery({
    queryKey: ['analytics-dashboard', timeRange],
    queryFn: async (): Promise<AnalyticsDashboard> => {
      const response = await api.get(API_ENDPOINTS.ANALYTICS.DASHBOARD, {
        params: { time_range: timeRange },
      });
      return response.data;
    },
    enabled,
    staleTime: 5 * 60 * 1000, // 5 minutes
    gcTime: 30 * 60 * 1000, // 30 minutes
  });
}

/**
 * Hook for engagement trends data (30-day)
 */
export function useEngagementTrends(enabled = true) {
  return useQuery({
    queryKey: ['engagement-trends'],
    queryFn: async () => {
      const response = await api.get(API_ENDPOINTS.ANALYTICS.ENGAGEMENT_TRENDS);
      return response.data;
    },
    enabled,
    staleTime: 10 * 60 * 1000, // 10 minutes
  });
}

/**
 * Hook for demographic trends with AI insights
 */
export function useDemographicTrends(enabled = true) {
  return useQuery({
    queryKey: ['demographic-trends'],
    queryFn: async () => {
      const response = await api.get(API_ENDPOINTS.ANALYTICS.DEMOGRAPHIC_TRENDS);
      return response.data;
    },
    enabled,
    staleTime: 30 * 60 * 1000, // 30 minutes
  });
}

export default useAnalytics;
