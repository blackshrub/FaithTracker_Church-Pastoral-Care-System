/**
 * useReports - Hook for fetching report data
 *
 * Provides report data including:
 * - Monthly management reports
 * - Staff performance reports
 * - Yearly summary
 */

import { useQuery } from '@tanstack/react-query';

import api from '@/services/api';
import { API_ENDPOINTS } from '@/constants/api';
import type { MonthlyReport, StaffPerformanceReport } from '@/types';

// ============================================================================
// MONTHLY REPORT
// ============================================================================

interface UseMonthlyReportOptions {
  year: number;
  month: number;
  enabled?: boolean;
}

export function useMonthlyReport({ year, month, enabled = true }: UseMonthlyReportOptions) {
  return useQuery({
    queryKey: ['monthly-report', year, month],
    queryFn: async (): Promise<MonthlyReport> => {
      const response = await api.get(API_ENDPOINTS.REPORTS.MONTHLY, {
        params: { year, month },
      });
      return response.data;
    },
    enabled,
    staleTime: 10 * 60 * 1000, // 10 minutes
    gcTime: 60 * 60 * 1000, // 1 hour
  });
}

// ============================================================================
// STAFF PERFORMANCE REPORT
// ============================================================================

interface UseStaffPerformanceOptions {
  year: number;
  month: number;
  enabled?: boolean;
}

export function useStaffPerformance({ year, month, enabled = true }: UseStaffPerformanceOptions) {
  return useQuery({
    queryKey: ['staff-performance', year, month],
    queryFn: async (): Promise<StaffPerformanceReport> => {
      const response = await api.get(API_ENDPOINTS.REPORTS.STAFF_PERFORMANCE, {
        params: { year, month },
      });
      return response.data;
    },
    enabled,
    staleTime: 10 * 60 * 1000, // 10 minutes
    gcTime: 60 * 60 * 1000, // 1 hour
  });
}

// ============================================================================
// YEARLY SUMMARY
// ============================================================================

interface UseYearlySummaryOptions {
  year: number;
  enabled?: boolean;
}

export function useYearlySummary({ year, enabled = true }: UseYearlySummaryOptions) {
  return useQuery({
    queryKey: ['yearly-summary', year],
    queryFn: async () => {
      const response = await api.get(API_ENDPOINTS.REPORTS.YEARLY_SUMMARY, {
        params: { year },
      });
      return response.data;
    },
    enabled,
    staleTime: 30 * 60 * 1000, // 30 minutes
    gcTime: 2 * 60 * 60 * 1000, // 2 hours
  });
}

export default useMonthlyReport;
