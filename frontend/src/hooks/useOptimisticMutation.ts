/**
 * useOptimisticMutation - Optimistic update patterns for instant UI
 *
 * Makes the UI feel instant by updating immediately before server confirms.
 * If server fails, automatically rolls back to previous state.
 *
 * This is the #2 technique for "instant" feel after prefetching.
 */

import { useMutation, useQueryClient, type QueryKey } from '@tanstack/react-query';
import { toast } from 'sonner';
import type { AxiosResponse } from 'axios';

import api from '@/lib/api';
import type { CareEvent, Member } from '@/types';

// ==================== Complete Event ====================

interface CompleteEventVariables {
  eventId: string | undefined;
  memberId: string;
  // Optional — when 'birthday' (or eventId is undefined) we route through the
  // by-member endpoint, which creates the care_event row on demand. Birthdays
  // are computed at dashboard-render time from member.birth_date and may not
  // have a care_event row yet, so /care-events/${eventId}/complete would 404
  // with eventId=undefined.
  type?: string;
}

interface CompleteEventContext {
  previousEvents: CareEvent[] | undefined;
  previousDashboard: unknown;
  dashboardKey: QueryKey | undefined;
}

/**
 * Optimistic mutation for completing a care event
 * UI updates instantly, rolls back on error
 */
export function useCompleteEventOptimistic() {
  const queryClient = useQueryClient();

  return useMutation<AxiosResponse, Error, CompleteEventVariables, CompleteEventContext>({
    mutationFn: ({ eventId, memberId, type }) =>
      type === 'birthday' || !eventId
        ? api.post(`/care-events/birthday/member/${memberId}/complete`)
        : api.post(`/care-events/${eventId}/complete`),

    // Optimistically update before server responds
    onMutate: async ({ eventId, memberId }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['careEvents', memberId] });
      await queryClient.cancelQueries({ queryKey: ['dashboard'] });

      // Snapshot previous values for rollback
      // Use getQueriesData with prefix match since dashboard key includes campus_id
      const previousEvents = queryClient.getQueryData<CareEvent[]>(['careEvents', memberId]);
      const dashboardEntries = queryClient.getQueriesData({ queryKey: ['dashboard', 'reminders'] });
      const dashboardKey = dashboardEntries[0]?.[0];
      const previousDashboard = dashboardEntries[0]?.[1];

      // Optimistically update care events
      queryClient.setQueryData<CareEvent[] | { items?: CareEvent[] }>(
        ['careEvents', memberId],
        (old) => {
          if (!old) return old;
          const events = Array.isArray(old) ? old : old.items || [];
          return events.map((event) =>
            event.id === eventId
              ? { ...event, completed: true, completed_at: new Date().toISOString() }
              : event
          );
        }
      );

      // Optimistically update dashboard (using actual key with campus_id)
      if (dashboardKey) {
        queryClient.setQueryData(dashboardKey, (old: Record<string, unknown> | undefined) => {
          if (!old) return old;
          return {
            ...old,
            today_tasks:
              (old.today_tasks as Array<{ id: string }>)?.filter((t) => t.id !== eventId) || [],
            overdue_tasks:
              (old.overdue_tasks as Array<{ id: string }>)?.filter((t) => t.id !== eventId) || [],
          };
        });
      }

      return { previousEvents, previousDashboard, dashboardKey };
    },

    // Rollback on error
    onError: (_err, variables, context) => {
      if (context?.previousEvents) {
        queryClient.setQueryData(['careEvents', variables.memberId], context.previousEvents);
      }
      if (context?.previousDashboard && context?.dashboardKey) {
        queryClient.setQueryData(context.dashboardKey, context.previousDashboard);
      }
      toast.error('Failed to complete task. Please try again.');
    },

    // Refetch to ensure consistency
    onSettled: (_, __, { memberId }) => {
      queryClient.invalidateQueries({ queryKey: ['careEvents', memberId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ==================== Ignore Event ====================

interface IgnoreEventVariables {
  eventId: string | undefined;
  memberId: string;
  // See CompleteEventVariables.type for rationale.
  type?: string;
}

interface IgnoreEventContext {
  previousEvents: CareEvent[] | undefined;
  previousDashboard: unknown;
  dashboardKey: QueryKey | undefined;
}

/**
 * Optimistic mutation for ignoring a care event
 */
export function useIgnoreEventOptimistic() {
  const queryClient = useQueryClient();

  return useMutation<AxiosResponse, Error, IgnoreEventVariables, IgnoreEventContext>({
    mutationFn: ({ eventId, memberId, type }) =>
      type === 'birthday' || !eventId
        ? api.post(`/care-events/birthday/member/${memberId}/ignore`)
        : api.post(`/care-events/${eventId}/ignore`),

    onMutate: async ({ eventId, memberId }) => {
      await queryClient.cancelQueries({ queryKey: ['careEvents', memberId] });
      await queryClient.cancelQueries({ queryKey: ['dashboard'] });

      const previousEvents = queryClient.getQueryData<CareEvent[]>(['careEvents', memberId]);
      const dashboardEntries = queryClient.getQueriesData({ queryKey: ['dashboard', 'reminders'] });
      const dashboardKey = dashboardEntries[0]?.[0];
      const previousDashboard = dashboardEntries[0]?.[1];

      // Optimistically mark as ignored
      queryClient.setQueryData<CareEvent[] | { items?: CareEvent[] }>(
        ['careEvents', memberId],
        (old) => {
          if (!old) return old;
          const events = Array.isArray(old) ? old : old.items || [];
          return events.map((event) =>
            event.id === eventId
              ? { ...event, ignored: true, ignored_at: new Date().toISOString() }
              : event
          );
        }
      );

      // Remove from dashboard (using actual key with campus_id)
      if (dashboardKey) {
        queryClient.setQueryData(dashboardKey, (old: Record<string, unknown> | undefined) => {
          if (!old) return old;
          return {
            ...old,
            today_tasks:
              (old.today_tasks as Array<{ id: string }>)?.filter((t) => t.id !== eventId) || [],
            overdue_tasks:
              (old.overdue_tasks as Array<{ id: string }>)?.filter((t) => t.id !== eventId) || [],
          };
        });
      }

      return { previousEvents, previousDashboard, dashboardKey };
    },

    onError: (_err, variables, context) => {
      if (context?.previousEvents) {
        queryClient.setQueryData(['careEvents', variables.memberId], context.previousEvents);
      }
      if (context?.previousDashboard && context?.dashboardKey) {
        queryClient.setQueryData(context.dashboardKey, context.previousDashboard);
      }
      toast.error('Failed to ignore task. Please try again.');
    },

    onSettled: (_, __, { memberId }) => {
      queryClient.invalidateQueries({ queryKey: ['careEvents', memberId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ==================== Update Member ====================

interface UpdateMemberVariables {
  memberId: string;
  data: Partial<Member>;
}

interface UpdateMemberContext {
  previousMember: Member | undefined;
}

/**
 * Optimistic mutation for updating member data
 */
export function useUpdateMemberOptimistic() {
  const queryClient = useQueryClient();

  return useMutation<AxiosResponse, Error, UpdateMemberVariables, UpdateMemberContext>({
    mutationFn: ({ memberId, data }) => api.put(`/members/${memberId}`, data),

    onMutate: async ({ memberId, data }) => {
      await queryClient.cancelQueries({ queryKey: ['member', memberId] });

      const previousMember = queryClient.getQueryData<Member>(['member', memberId]);

      // Optimistically update member
      queryClient.setQueryData<Member>(['member', memberId], (old) => ({
        ...old!,
        ...data,
        updated_at: new Date().toISOString(),
      }));

      return { previousMember };
    },

    onError: (_err, { memberId }, context) => {
      if (context?.previousMember) {
        queryClient.setQueryData(['member', memberId], context.previousMember);
      }
      toast.error('Failed to update member. Please try again.');
    },

    onSettled: (_, __, { memberId }) => {
      queryClient.invalidateQueries({ queryKey: ['member', memberId] });
      queryClient.invalidateQueries({ queryKey: ['members'] });
    },
  });
}

// ==================== Create Event ====================

interface CreateEventData {
  member_id: string;
  event_type: string;
  event_date: string;
  title: string;
  description?: string;
  [key: string]: unknown;
}

interface CreateEventContext {
  previousEvents: CareEvent[] | undefined;
  tempEvent: CareEvent;
}

/**
 * Optimistic mutation for creating care event
 */
export function useCreateEventOptimistic() {
  const queryClient = useQueryClient();

  return useMutation<AxiosResponse, Error, CreateEventData, CreateEventContext>({
    mutationFn: (data) => api.post('/care-events', data),

    onMutate: async (data) => {
      await queryClient.cancelQueries({ queryKey: ['careEvents', data.member_id] });

      const previousEvents = queryClient.getQueryData<CareEvent[]>(['careEvents', data.member_id]);

      // Optimistically add new event with temp ID
      const tempEvent = {
        ...data,
        id: `temp-${Date.now()}`,
        created_at: new Date().toISOString(),
        completed: false,
        ignored: false,
      } as unknown as CareEvent;

      queryClient.setQueryData<CareEvent[] | { items?: CareEvent[] }>(
        ['careEvents', data.member_id],
        (old) => {
          if (!old) return [tempEvent];
          if (Array.isArray(old)) return [tempEvent, ...old];
          // Preserve the {items: [...]} wrapper shape so downstream consumers
          // that read `.items` keep working. Previously this branch
          // collapsed to a flat array and broke list rendering on the
          // wrapped shape.
          return { ...old, items: [tempEvent, ...(old.items || [])] };
        }
      );

      return { previousEvents, tempEvent };
    },

    onError: (_err, data, context) => {
      if (context?.previousEvents) {
        queryClient.setQueryData(['careEvents', data.member_id], context.previousEvents);
      }
      toast.error('Failed to create event. Please try again.');
    },

    onSuccess: (response, data, context) => {
      // Replace temp event with real event from server, preserving the
      // wrapper shape if the cache holds {items: [...]} (consumers that
      // read .items would otherwise crash on the unwrapped array).
      queryClient.setQueryData<CareEvent[] | { items?: CareEvent[] }>(
        ['careEvents', data.member_id],
        (old) => {
          if (!old) return [response.data];
          if (Array.isArray(old)) {
            return old.map((e) => (e.id === context?.tempEvent.id ? response.data : e));
          }
          const items = (old.items || []).map((e) =>
            e.id === context?.tempEvent.id ? response.data : e
          );
          return { ...old, items };
        }
      );
    },

    onSettled: (_, __, data) => {
      queryClient.invalidateQueries({ queryKey: ['careEvents', data.member_id] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

export default {
  useCompleteEventOptimistic,
  useIgnoreEventOptimistic,
  useUpdateMemberOptimistic,
  useCreateEventOptimistic,
};
