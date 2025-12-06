/**
 * Dashboard Hooks
 *
 * Data fetching hooks for the dashboard/Today screen
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import Toast from 'react-native-toast-message';
import api from '@/services/api';
import { API_ENDPOINTS } from '@/constants/api';
import {
  USE_MOCK_DATA,
  mockGetDashboardReminders,
  mockCompleteCareEvent,
  mockIgnoreCareEvent,
  mockCompleteGriefStage,
  mockMarkAidDistributed,
} from '@/services/mockApi';
import type { DashboardReminders, DashboardStats } from '@/types';

/**
 * Fetch dashboard reminders (today's tasks)
 */
export function useDashboardReminders() {
  return useQuery<DashboardReminders>({
    queryKey: ['dashboard', 'reminders'],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        return mockGetDashboardReminders();
      }
      const { data } = await api.get(API_ENDPOINTS.DASHBOARD.REMINDERS);
      return data;
    },
    staleTime: 2 * 60 * 1000, // 2 minutes
    refetchInterval: 5 * 60 * 1000, // Refetch every 5 minutes
  });
}

/**
 * Fetch dashboard stats
 */
export function useDashboardStats() {
  return useQuery<DashboardStats>({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => {
      const { data } = await api.get(API_ENDPOINTS.DASHBOARD.STATS);
      return data;
    },
    staleTime: 5 * 60 * 1000, // 5 minutes
  });
}

/**
 * Complete a care event task
 */
export function useCompleteTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ eventId, type }: { eventId: string; type: string }) => {
      if (USE_MOCK_DATA) {
        switch (type) {
          case 'birthday':
          case 'care_event':
            await mockCompleteCareEvent(eventId);
            break;
          case 'grief_stage':
            await mockCompleteGriefStage(eventId);
            break;
          case 'financial_aid':
            await mockMarkAidDistributed(eventId);
            break;
          default:
            await mockCompleteCareEvent(eventId);
        }
        return;
      }
      switch (type) {
        case 'birthday':
        case 'care_event':
          await api.post(API_ENDPOINTS.CARE_EVENTS.COMPLETE(eventId));
          break;
        case 'grief_stage':
          await api.post(API_ENDPOINTS.GRIEF_SUPPORT.COMPLETE(eventId));
          break;
        case 'accident_followup':
          await api.post(API_ENDPOINTS.ACCIDENT_FOLLOWUP.COMPLETE(eventId));
          break;
        case 'financial_aid':
          await api.post(API_ENDPOINTS.FINANCIAL_AID.MARK_DISTRIBUTED(eventId));
          break;
        default:
          throw new Error(`Unknown task type: ${type}`);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      Toast.show({
        type: 'success',
        text1: 'Task Completed',
        text2: 'The task has been marked as done',
        visibilityTime: 2000,
      });
    },
    onError: () => {
      Toast.show({
        type: 'error',
        text1: 'Error',
        text2: 'Failed to complete task',
        visibilityTime: 3000,
      });
    },
  });
}

/**
 * Ignore a task
 */
export function useIgnoreTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ eventId, type }: { eventId: string; type: string }) => {
      if (USE_MOCK_DATA) {
        await mockIgnoreCareEvent(eventId);
        return;
      }
      switch (type) {
        case 'birthday':
        case 'care_event':
          await api.post(API_ENDPOINTS.CARE_EVENTS.IGNORE(eventId));
          break;
        case 'grief_stage':
          await api.post(API_ENDPOINTS.GRIEF_SUPPORT.IGNORE(eventId));
          break;
        case 'accident_followup':
          await api.post(API_ENDPOINTS.ACCIDENT_FOLLOWUP.IGNORE(eventId));
          break;
        case 'financial_aid':
          await api.post(API_ENDPOINTS.FINANCIAL_AID.IGNORE(eventId));
          break;
        default:
          throw new Error(`Unknown task type: ${type}`);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      Toast.show({
        type: 'info',
        text1: 'Task Skipped',
        text2: 'The task has been marked as ignored',
        visibilityTime: 2000,
      });
    },
    onError: () => {
      Toast.show({
        type: 'error',
        text1: 'Error',
        text2: 'Failed to ignore task',
        visibilityTime: 3000,
      });
    },
  });
}

/**
 * Mark a member as contacted (creates a regular_contact care event)
 * Used for at-risk and disconnected members in the Overdue tab
 */
export function useMarkMemberContacted() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (memberId: string) => {
      if (USE_MOCK_DATA) {
        // In mock mode, just simulate success
        return;
      }
      await api.post(API_ENDPOINTS.CARE_EVENTS.CREATE, {
        member_id: memberId,
        event_type: 'regular_contact',
        event_date: new Date().toISOString().split('T')[0],
        title: 'Contact made',
        completed: true,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['members'] });
      Toast.show({
        type: 'success',
        text1: 'Contact Marked',
        text2: 'Member contact has been recorded',
        visibilityTime: 2000,
      });
    },
    onError: () => {
      Toast.show({
        type: 'error',
        text1: 'Error',
        text2: 'Failed to mark contact',
        visibilityTime: 3000,
      });
    },
  });
}
