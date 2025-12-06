/**
 * useOptimisticMutation - Optimistic update patterns for instant UI
 *
 * Makes the UI feel instant by updating immediately before server confirms.
 * If server fails, automatically rolls back to previous state.
 *
 * This is the #2 technique for "instant" feel after prefetching.
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import api from '@/lib/api';

/**
 * Optimistic mutation for completing a care event
 * UI updates instantly, rolls back on error
 */
export function useCompleteEventOptimistic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ eventId }) =>
      api.post(`/care-events/${eventId}/complete`),

    // Optimistically update before server responds
    onMutate: async ({ eventId, memberId }) => {
      // Cancel outgoing refetches
      await queryClient.cancelQueries({ queryKey: ['careEvents', memberId] });
      await queryClient.cancelQueries({ queryKey: ['dashboard'] });

      // Snapshot previous values for rollback
      const previousEvents = queryClient.getQueryData(['careEvents', memberId]);
      const previousDashboard = queryClient.getQueryData(['dashboard', 'reminders']);

      // Optimistically update care events
      queryClient.setQueryData(['careEvents', memberId], (old) => {
        if (!old) return old;
        const events = Array.isArray(old) ? old : old.items || [];
        return events.map(event =>
          event.id === eventId
            ? { ...event, completed: true, completed_at: new Date().toISOString() }
            : event
        );
      });

      // Optimistically update dashboard
      queryClient.setQueryData(['dashboard', 'reminders'], (old) => {
        if (!old) return old;
        return {
          ...old,
          today_tasks: old.today_tasks?.filter(t => t.id !== eventId) || [],
          overdue_tasks: old.overdue_tasks?.filter(t => t.id !== eventId) || [],
        };
      });

      return { previousEvents, previousDashboard };
    },

    // Rollback on error
    onError: (err, variables, context) => {
      if (context?.previousEvents) {
        queryClient.setQueryData(['careEvents', variables.memberId], context.previousEvents);
      }
      if (context?.previousDashboard) {
        queryClient.setQueryData(['dashboard', 'reminders'], context.previousDashboard);
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

/**
 * Optimistic mutation for ignoring a care event
 */
export function useIgnoreEventOptimistic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ eventId }) =>
      api.post(`/care-events/${eventId}/ignore`),

    onMutate: async ({ eventId, memberId }) => {
      await queryClient.cancelQueries({ queryKey: ['careEvents', memberId] });
      await queryClient.cancelQueries({ queryKey: ['dashboard'] });

      const previousEvents = queryClient.getQueryData(['careEvents', memberId]);
      const previousDashboard = queryClient.getQueryData(['dashboard', 'reminders']);

      // Optimistically mark as ignored
      queryClient.setQueryData(['careEvents', memberId], (old) => {
        if (!old) return old;
        const events = Array.isArray(old) ? old : old.items || [];
        return events.map(event =>
          event.id === eventId
            ? { ...event, ignored: true, ignored_at: new Date().toISOString() }
            : event
        );
      });

      // Remove from dashboard
      queryClient.setQueryData(['dashboard', 'reminders'], (old) => {
        if (!old) return old;
        return {
          ...old,
          today_tasks: old.today_tasks?.filter(t => t.id !== eventId) || [],
          overdue_tasks: old.overdue_tasks?.filter(t => t.id !== eventId) || [],
        };
      });

      return { previousEvents, previousDashboard };
    },

    onError: (err, variables, context) => {
      if (context?.previousEvents) {
        queryClient.setQueryData(['careEvents', variables.memberId], context.previousEvents);
      }
      if (context?.previousDashboard) {
        queryClient.setQueryData(['dashboard', 'reminders'], context.previousDashboard);
      }
      toast.error('Failed to ignore task. Please try again.');
    },

    onSettled: (_, __, { memberId }) => {
      queryClient.invalidateQueries({ queryKey: ['careEvents', memberId] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Optimistic mutation for updating member data
 */
export function useUpdateMemberOptimistic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ memberId, data }) =>
      api.put(`/members/${memberId}`, data),

    onMutate: async ({ memberId, data }) => {
      await queryClient.cancelQueries({ queryKey: ['member', memberId] });

      const previousMember = queryClient.getQueryData(['member', memberId]);

      // Optimistically update member
      queryClient.setQueryData(['member', memberId], (old) => ({
        ...old,
        ...data,
        updated_at: new Date().toISOString(),
      }));

      return { previousMember };
    },

    onError: (err, { memberId }, context) => {
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

/**
 * Optimistic mutation for creating care event
 */
export function useCreateEventOptimistic() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data) =>
      api.post('/care-events', data),

    onMutate: async (data) => {
      await queryClient.cancelQueries({ queryKey: ['careEvents', data.member_id] });

      const previousEvents = queryClient.getQueryData(['careEvents', data.member_id]);

      // Optimistically add new event with temp ID
      const tempEvent = {
        ...data,
        id: `temp-${Date.now()}`,
        created_at: new Date().toISOString(),
        completed: false,
        ignored: false,
      };

      queryClient.setQueryData(['careEvents', data.member_id], (old) => {
        if (!old) return [tempEvent];
        const events = Array.isArray(old) ? old : old.items || [];
        return [tempEvent, ...events];
      });

      return { previousEvents, tempEvent };
    },

    onError: (err, data, context) => {
      if (context?.previousEvents) {
        queryClient.setQueryData(['careEvents', data.member_id], context.previousEvents);
      }
      toast.error('Failed to create event. Please try again.');
    },

    onSuccess: (response, data, context) => {
      // Replace temp event with real event from server
      queryClient.setQueryData(['careEvents', data.member_id], (old) => {
        if (!old) return [response.data];
        const events = Array.isArray(old) ? old : old.items || [];
        return events.map(e =>
          e.id === context.tempEvent.id ? response.data : e
        );
      });
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
