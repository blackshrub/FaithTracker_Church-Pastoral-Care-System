/**
 * Route Loaders for React Router v7
 *
 * These loaders prefetch data in parallel with component loading,
 * reducing Time-to-Interactive (TTI) significantly.
 *
 * TanStack Query is still used for caching - loaders just prime the cache.
 *
 * IMPORTANT: Loaders are defensive - they catch all errors and return null
 * to prevent blocking navigation when user is not authenticated.
 */

import { QueryClient } from '@tanstack/react-query';
import api from './api';

// Shared query client for prefetching
let queryClient = null;

export const setQueryClient = (client) => {
  queryClient = client;
};

/**
 * Check if user is authenticated (has valid token)
 */
const isAuthenticated = () => {
  const token = localStorage.getItem('token');
  return !!token;
};

/**
 * Safe prefetch wrapper - catches all errors to prevent blocking navigation
 */
const safePrefetch = async (queryKey, queryFn, options = {}) => {
  if (!queryClient || !isAuthenticated()) return;

  try {
    await queryClient.prefetchQuery({
      queryKey,
      queryFn,
      staleTime: options.staleTime || 1000 * 30,
    });
  } catch (error) {
    // Silently fail - component will fetch data anyway
    console.debug(`Prefetch failed for ${queryKey.join('/')}:`, error.message);
  }
};

/**
 * Dashboard loader - prefetches reminders and members
 */
export const dashboardLoader = async () => {
  if (!isAuthenticated()) return null;

  // Prefetch in parallel - these match Dashboard.jsx actual API calls
  await Promise.allSettled([
    safePrefetch(
      ['dashboard-reminders'],
      () => api.get('/dashboard/reminders').then(res => res.data),
      { staleTime: 1000 * 30 }
    ),
    safePrefetch(
      ['members-list'],
      () => api.get('/members?limit=1000').then(res => res.data),
      { staleTime: 1000 * 60 }
    ),
  ]);

  return null;
};

/**
 * Members list loader - prefetches member list
 */
export const membersLoader = async () => {
  if (!isAuthenticated()) return null;

  await safePrefetch(
    ['members', { page: 1, limit: 50 }],
    () => api.get('/members?page=1&limit=50').then(res => res.data),
    { staleTime: 1000 * 30 }
  );

  return null;
};

/**
 * Member detail loader - prefetches member and care events
 */
export const memberDetailLoader = async ({ params }) => {
  if (!isAuthenticated() || !params.id) return null;

  await Promise.allSettled([
    safePrefetch(
      ['member', params.id],
      () => api.get(`/members/${params.id}`).then(res => res.data),
      { staleTime: 1000 * 30 }
    ),
    safePrefetch(
      ['member-care-events', params.id],
      () => api.get(`/care-events?member_id=${params.id}`).then(res => res.data),
      { staleTime: 1000 * 30 }
    ),
  ]);

  return null;
};

/**
 * Analytics loader - prefetches analytics data
 */
export const analyticsLoader = async () => {
  if (!isAuthenticated()) return null;

  await Promise.allSettled([
    safePrefetch(
      ['analytics-demographics'],
      () => api.get('/analytics/demographic-trends').then(res => res.data),
      { staleTime: 1000 * 60 * 5 }
    ),
    safePrefetch(
      ['analytics-grief'],
      () => api.get('/analytics/grief-completion-rate').then(res => res.data),
      { staleTime: 1000 * 60 * 5 }
    ),
    safePrefetch(
      ['financial-aid-summary'],
      () => api.get('/financial-aid/summary').then(res => res.data),
      { staleTime: 1000 * 60 * 5 }
    ),
  ]);

  return null;
};

/**
 * Financial aid loader
 */
export const financialAidLoader = async () => {
  if (!isAuthenticated()) return null;

  await Promise.allSettled([
    safePrefetch(
      ['financial-aid-summary'],
      () => api.get('/financial-aid/summary').then(res => res.data),
      { staleTime: 1000 * 60 }
    ),
    safePrefetch(
      ['financial-aid-schedules'],
      () => api.get('/financial-aid-schedules').then(res => res.data),
      { staleTime: 1000 * 60 }
    ),
  ]);

  return null;
};

/**
 * Admin loader - prefetches users and campuses
 */
export const adminLoader = async () => {
  if (!isAuthenticated()) return null;

  await Promise.allSettled([
    safePrefetch(
      ['admin-users'],
      () => api.get('/users').then(res => res.data),
      { staleTime: 1000 * 60 }
    ),
    safePrefetch(
      ['campuses'],
      () => api.get('/campuses').then(res => res.data),
      { staleTime: 1000 * 60 * 5 }
    ),
  ]);

  return null;
};

/**
 * Activity log loader
 */
export const activityLogLoader = async () => {
  if (!isAuthenticated()) return null;

  await Promise.allSettled([
    safePrefetch(
      ['activity-logs', { page: 1 }],
      () => api.get('/activity-logs?page=1&limit=50').then(res => res.data),
      { staleTime: 1000 * 30 }
    ),
    safePrefetch(
      ['activity-logs-summary'],
      () => api.get('/activity-logs/summary').then(res => res.data),
      { staleTime: 1000 * 60 }
    ),
  ]);

  return null;
};

/**
 * Reports loader
 */
export const reportsLoader = async () => {
  if (!isAuthenticated()) return null;

  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth() + 1;

  await Promise.allSettled([
    safePrefetch(
      ['monthly-report', year, month],
      () => api.get(`/reports/monthly?year=${year}&month=${month}`).then(res => res.data),
      { staleTime: 1000 * 60 * 5 }
    ),
    safePrefetch(
      ['staff-performance', year, month],
      () => api.get(`/reports/staff-performance?year=${year}&month=${month}`).then(res => res.data),
      { staleTime: 1000 * 60 * 5 }
    ),
  ]);

  return null;
};
