/**
 * Route Loaders for React Router v7
 *
 * These loaders prefetch data in parallel with component loading,
 * reducing Time-to-Interactive (TTI) significantly.
 *
 * TanStack Query is still used for caching - loaders just prime the cache.
 */

import { QueryClient } from '@tanstack/react-query';
import api from './api';

// Shared query client for prefetching
let queryClient = null;

export const setQueryClient = (client) => {
  queryClient = client;
};

/**
 * Dashboard loader - prefetches all dashboard data in parallel
 */
export const dashboardLoader = async () => {
  if (!queryClient) return null;

  // Prefetch all dashboard data in parallel
  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: ['dashboard'],
      queryFn: () => api.get('/dashboard').then(res => res.data),
      staleTime: 1000 * 30,
    }),
    queryClient.prefetchQuery({
      queryKey: ['dashboard-birthdays'],
      queryFn: () => api.get('/dashboard/birthdays').then(res => res.data),
      staleTime: 1000 * 60,
    }),
    queryClient.prefetchQuery({
      queryKey: ['dashboard-grief'],
      queryFn: () => api.get('/dashboard/grief-support').then(res => res.data),
      staleTime: 1000 * 60,
    }),
  ]);

  return null;
};

/**
 * Members list loader - prefetches member list
 */
export const membersLoader = async () => {
  if (!queryClient) return null;

  await queryClient.prefetchQuery({
    queryKey: ['members', { page: 1, limit: 50 }],
    queryFn: () => api.get('/members?page=1&limit=50').then(res => res.data),
    staleTime: 1000 * 30,
  });

  return null;
};

/**
 * Member detail loader - prefetches member and care events
 */
export const memberDetailLoader = async ({ params }) => {
  if (!queryClient || !params.id) return null;

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: ['member', params.id],
      queryFn: () => api.get(`/members/${params.id}`).then(res => res.data),
      staleTime: 1000 * 30,
    }),
    queryClient.prefetchQuery({
      queryKey: ['member-care-events', params.id],
      queryFn: () => api.get(`/care-events?member_id=${params.id}`).then(res => res.data),
      staleTime: 1000 * 30,
    }),
  ]);

  return null;
};

/**
 * Analytics loader - prefetches analytics data
 */
export const analyticsLoader = async () => {
  if (!queryClient) return null;

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: ['analytics-demographics'],
      queryFn: () => api.get('/analytics/demographic-trends').then(res => res.data),
      staleTime: 1000 * 60 * 5,
    }),
    queryClient.prefetchQuery({
      queryKey: ['analytics-grief'],
      queryFn: () => api.get('/analytics/grief-completion-rate').then(res => res.data),
      staleTime: 1000 * 60 * 5,
    }),
  ]);

  return null;
};

/**
 * Financial aid loader
 */
export const financialAidLoader = async () => {
  if (!queryClient) return null;

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: ['financial-aid-summary'],
      queryFn: () => api.get('/financial-aid/summary').then(res => res.data),
      staleTime: 1000 * 60,
    }),
    queryClient.prefetchQuery({
      queryKey: ['financial-aid-schedules'],
      queryFn: () => api.get('/financial-aid-schedules').then(res => res.data),
      staleTime: 1000 * 60,
    }),
  ]);

  return null;
};

/**
 * Admin loader - prefetches users and campuses
 */
export const adminLoader = async () => {
  if (!queryClient) return null;

  await Promise.all([
    queryClient.prefetchQuery({
      queryKey: ['admin-users'],
      queryFn: () => api.get('/users').then(res => res.data),
      staleTime: 1000 * 60,
    }),
    queryClient.prefetchQuery({
      queryKey: ['campuses'],
      queryFn: () => api.get('/campuses').then(res => res.data),
      staleTime: 1000 * 60 * 5,
    }),
  ]);

  return null;
};

/**
 * Activity log loader
 */
export const activityLogLoader = async () => {
  if (!queryClient) return null;

  await queryClient.prefetchQuery({
    queryKey: ['activity-logs', { page: 1 }],
    queryFn: () => api.get('/activity-logs?page=1&limit=50').then(res => res.data),
    staleTime: 1000 * 30,
  });

  return null;
};

/**
 * Reports loader
 */
export const reportsLoader = async () => {
  if (!queryClient) return null;

  const now = new Date();
  await queryClient.prefetchQuery({
    queryKey: ['monthly-report', now.getFullYear(), now.getMonth() + 1],
    queryFn: () => api.get(`/reports/monthly?year=${now.getFullYear()}&month=${now.getMonth() + 1}`).then(res => res.data),
    staleTime: 1000 * 60 * 5,
  });

  return null;
};
