/**
 * usePrefetch - Advanced prefetching hook for instant navigation
 *
 * Prefetches data on hover/focus to eliminate loading states
 * when users navigate between pages. This is the #1 technique
 * for making a React app feel "instant".
 *
 * Usage:
 * const { prefetchMember, prefetchDashboard } = usePrefetch();
 * <Link onMouseEnter={() => prefetchMember(id)} ...>
 */

import { useQueryClient } from '@tanstack/react-query';
import { useCallback, useRef } from 'react';
import api from '@/lib/api';

// Debounce prefetch to avoid excessive requests on rapid mouse movements
const PREFETCH_DELAY = 100; // ms - wait before prefetching
const PREFETCH_STALE_TIME = 1000 * 60 * 5; // 5 minutes - how long prefetched data stays fresh

export function usePrefetch() {
  const queryClient = useQueryClient();
  const timeoutRef = useRef({});

  /**
   * Prefetch member detail data (member + care events + timelines)
   * Call this on hover over member links
   */
  const prefetchMember = useCallback((memberId) => {
    if (!memberId) return;

    // Clear any pending prefetch for this member
    if (timeoutRef.current[`member-${memberId}`]) {
      clearTimeout(timeoutRef.current[`member-${memberId}`]);
    }

    timeoutRef.current[`member-${memberId}`] = setTimeout(async () => {
      // Prefetch all member data in the same structure as MemberDetail expects
      // This must match the queryFn in MemberDetail.jsx exactly
      queryClient.prefetchQuery({
        queryKey: ['member', memberId],
        queryFn: async () => {
          const [memberRes, eventsRes, griefRes, accidentRes, aidSchedulesRes] = await Promise.all([
            api.get(`/members/${memberId}`),
            api.get(`/care-events?member_id=${memberId}`),
            api.get(`/grief-support/member/${memberId}`).catch(() => ({ data: [] })),
            api.get(`/accident-followup/member/${memberId}`).catch(() => ({ data: [] })),
            api.get(`/financial-aid-schedules/member/${memberId}`).catch(() => ({ data: [] }))
          ]);

          const sortedEvents = (eventsRes.data || []).sort((a, b) => {
            const dateCompare = new Date(b.event_date) - new Date(a.event_date);
            if (dateCompare !== 0) return dateCompare;
            return new Date(b.created_at) - new Date(a.created_at);
          });

          return {
            member: memberRes.data,
            careEvents: sortedEvents,
            griefTimeline: griefRes.data,
            accidentTimeline: accidentRes.data,
            aidSchedules: aidSchedulesRes.data || []
          };
        },
        staleTime: PREFETCH_STALE_TIME,
      });
    }, PREFETCH_DELAY);
  }, [queryClient]);

  /**
   * Prefetch dashboard data
   * Call this when navigating back to dashboard
   */
  const prefetchDashboard = useCallback(() => {
    if (timeoutRef.current.dashboard) {
      clearTimeout(timeoutRef.current.dashboard);
    }

    timeoutRef.current.dashboard = setTimeout(() => {
      queryClient.prefetchQuery({
        queryKey: ['dashboard', 'reminders'],
        queryFn: () => api.get('/dashboard/reminders').then(r => r.data),
        staleTime: PREFETCH_STALE_TIME,
      });

      queryClient.prefetchQuery({
        queryKey: ['members', 'basic'],
        queryFn: () => api.get('/members?limit=100').then(r => r.data),
        staleTime: PREFETCH_STALE_TIME,
      });
    }, PREFETCH_DELAY);
  }, [queryClient]);

  /**
   * Prefetch members list
   * Call when hovering over Members nav link
   */
  const prefetchMembersList = useCallback((page = 1, search = '') => {
    if (timeoutRef.current.membersList) {
      clearTimeout(timeoutRef.current.membersList);
    }

    timeoutRef.current.membersList = setTimeout(() => {
      queryClient.prefetchQuery({
        queryKey: ['members', 'list', { page, search }],
        queryFn: () => api.get(`/members?page=${page}&search=${search}`).then(r => r.data),
        staleTime: PREFETCH_STALE_TIME,
      });
    }, PREFETCH_DELAY);
  }, [queryClient]);

  /**
   * Cancel all pending prefetches
   * Call on component unmount or route change
   */
  const cancelPrefetch = useCallback(() => {
    Object.values(timeoutRef.current).forEach(clearTimeout);
    timeoutRef.current = {};
  }, []);

  return {
    prefetchMember,
    prefetchDashboard,
    prefetchMembersList,
    cancelPrefetch,
  };
}

export default usePrefetch;
