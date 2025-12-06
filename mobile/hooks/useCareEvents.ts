/**
 * Care Events Hooks
 *
 * Data fetching hooks for care events with mock data support
 */

import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api from '@/services/api';
import { API_ENDPOINTS } from '@/constants/api';
import {
  USE_MOCK_DATA,
  mockGetCareEvents,
  mockCreateCareEvent,
  mockCompleteCareEvent,
  mockIgnoreCareEvent,
  mockCompleteGriefStage,
  mockMarkAidDistributed,
} from '@/services/mockApi';
import {
  mockGriefStages,
  mockAccidentFollowups,
  mockFinancialAidSchedules,
  mockCareEvents,
  mockMemberListItems,
  simulateApiDelay,
  mockUser,
} from '@/lib/mockData';
import type {
  CareEvent,
  CreateCareEventRequest,
  CareEventFilters,
  GriefStage,
  AccidentFollowup,
  AccidentFollowupStage,
  FinancialAidSchedule,
  MemberListItem,
} from '@/types';

/**
 * Fetch care events for a member
 */
export function useMemberCareEvents(memberId: string) {
  return useQuery<CareEvent[]>({
    queryKey: ['careEvents', memberId],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        return mockGetCareEvents({ member_id: memberId });
      }

      const { data } = await api.get(API_ENDPOINTS.CARE_EVENTS.LIST, {
        params: { member_id: memberId },
      });
      return data;
    },
    enabled: !!memberId,
  });
}

/**
 * Fetch all care events with filters
 */
export function useCareEvents(filters: CareEventFilters = {}) {
  return useQuery<CareEvent[]>({
    queryKey: ['careEvents', filters],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        return mockGetCareEvents(filters);
      }

      const { data } = await api.get(API_ENDPOINTS.CARE_EVENTS.LIST, {
        params: filters,
      });
      return data;
    },
  });
}

/**
 * Fetch single care event
 */
export function useCareEvent(eventId: string) {
  return useQuery<CareEvent>({
    queryKey: ['careEvent', eventId],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        const event = mockCareEvents.find((e) => e.id === eventId);
        if (!event) throw new Error('Event not found');
        return event;
      }

      const { data } = await api.get(API_ENDPOINTS.CARE_EVENTS.DETAIL(eventId));
      return data;
    },
    enabled: !!eventId,
  });
}

/**
 * Create a new care event
 */
export function useCreateCareEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (event: CreateCareEventRequest) => {
      if (USE_MOCK_DATA) {
        return mockCreateCareEvent(event);
      }

      const { data } = await api.post<CareEvent>(API_ENDPOINTS.CARE_EVENTS.CREATE, event);
      return data;
    },
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ['careEvents', variables.member_id] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
      queryClient.invalidateQueries({ queryKey: ['member', variables.member_id] });
      queryClient.invalidateQueries({ queryKey: ['griefTimeline', variables.member_id] });
      queryClient.invalidateQueries({ queryKey: ['accidentTimeline', variables.member_id] });
      queryClient.invalidateQueries({ queryKey: ['financialAid', variables.member_id] });
    },
  });
}

/**
 * Update a care event
 */
export function useUpdateCareEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({ eventId, data }: { eventId: string; data: Partial<CareEvent> }) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        const index = mockCareEvents.findIndex((e) => e.id === eventId);
        if (index !== -1) {
          mockCareEvents[index] = { ...mockCareEvents[index], ...data };
          return mockCareEvents[index];
        }
        throw new Error('Event not found');
      }

      const response = await api.put<CareEvent>(API_ENDPOINTS.CARE_EVENTS.UPDATE(eventId), data);
      return response.data;
    },
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['careEvent', data.id] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Complete a care event
 */
export function useCompleteCareEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (eventId: string) => {
      if (USE_MOCK_DATA) {
        return mockCompleteCareEvent(eventId);
      }

      await api.post(API_ENDPOINTS.CARE_EVENTS.COMPLETE(eventId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Ignore a care event
 */
export function useIgnoreCareEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (eventId: string) => {
      if (USE_MOCK_DATA) {
        return mockIgnoreCareEvent(eventId);
      }

      await api.post(API_ENDPOINTS.CARE_EVENTS.IGNORE(eventId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Delete a care event
 */
export function useDeleteCareEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (eventId: string) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        const index = mockCareEvents.findIndex((e) => e.id === eventId);
        if (index !== -1) {
          mockCareEvents.splice(index, 1);
        }
        return;
      }

      await api.delete(API_ENDPOINTS.CARE_EVENTS.DELETE(eventId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ============================================================================
// GRIEF SUPPORT HOOKS
// ============================================================================

/**
 * Fetch grief support timeline for a member
 */
export function useMemberGriefTimeline(memberId: string) {
  return useQuery<GriefStage[]>({
    queryKey: ['griefTimeline', memberId],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();

        // Get existing grief stages for this member
        const memberGriefStages = mockGriefStages.filter((s) => s.member_id === memberId);

        // Also generate stages from grief_loss care events
        const griefEvents = mockCareEvents.filter(
          (e) => e.member_id === memberId && e.event_type === 'grief_loss'
        );

        // Generate stages from events if we don't have specific stages
        if (griefEvents.length > 0 && memberGriefStages.length === 0) {
          const stages: GriefStage[] = [];
          const stageTypes = ['mourning', '1_week', '2_weeks', '1_month', '3_months', '6_months', '1_year'];
          const dayOffsets = [0, 7, 14, 30, 90, 180, 365];

          griefEvents.forEach((event) => {
            const eventDate = new Date(event.event_date);
            stageTypes.forEach((stage, index) => {
              const scheduledDate = new Date(eventDate);
              scheduledDate.setDate(scheduledDate.getDate() + dayOffsets[index]);

              stages.push({
                id: `grief_${event.id}_${stage}`,
                care_event_id: event.id,
                member_id: memberId,
                member_name: event.member_name,
                campus_id: event.campus_id,
                stage_type: stage,
                stage,
                scheduled_date: scheduledDate.toISOString().split('T')[0],
                completed: index < 2, // First 2 stages completed
                ignored: false,
                reminder_sent: true,
                created_at: event.created_at,
                updated_at: new Date().toISOString(),
              });
            });
          });
          return stages;
        }

        return memberGriefStages;
      }

      const { data } = await api.get(API_ENDPOINTS.GRIEF_SUPPORT.MEMBER(memberId));
      return data;
    },
    enabled: !!memberId,
  });
}

/**
 * Complete a grief stage
 */
export function useCompleteGriefStage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (stageId: string) => {
      if (USE_MOCK_DATA) {
        return mockCompleteGriefStage(stageId);
      }

      await api.post(API_ENDPOINTS.GRIEF_SUPPORT.COMPLETE(stageId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['griefTimeline'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Ignore a grief stage
 */
export function useIgnoreGriefStage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (stageId: string) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        const index = mockGriefStages.findIndex((s) => s.id === stageId);
        if (index !== -1) {
          mockGriefStages[index].ignored = true;
          mockGriefStages[index].ignored_at = new Date().toISOString();
        }
        return;
      }

      await api.post(API_ENDPOINTS.GRIEF_SUPPORT.IGNORE(stageId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['griefTimeline'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Undo a grief stage completion/ignore
 */
export function useUndoGriefStage() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (stageId: string) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        const index = mockGriefStages.findIndex((s) => s.id === stageId);
        if (index !== -1) {
          mockGriefStages[index].completed = false;
          mockGriefStages[index].ignored = false;
          mockGriefStages[index].completed_at = undefined;
          mockGriefStages[index].ignored_at = undefined;
        }
        return;
      }

      await api.post(API_ENDPOINTS.GRIEF_SUPPORT.UNDO(stageId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['griefTimeline'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ============================================================================
// ACCIDENT FOLLOWUP HOOKS
// ============================================================================

/**
 * Fetch accident followup timeline for a member
 */
export function useMemberAccidentTimeline(memberId: string) {
  return useQuery<AccidentFollowup[]>({
    queryKey: ['accidentTimeline', memberId],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();

        // First check pre-generated followups
        const preGenerated = mockAccidentFollowups.filter((f) => f.member_id === memberId);
        if (preGenerated.length > 0) {
          return preGenerated.map((f): AccidentFollowup => ({
            id: f.id,
            care_event_id: f.care_event_id,
            member_id: f.member_id,
            member_name: f.member_name,
            campus_id: f.campus_id,
            stage_type: f.stage,
            stage: f.stage,
            scheduled_date: f.scheduled_date,
            hospital_name: undefined,
            completed: f.completed,
            completed_at: (f as { completed_at?: string }).completed_at,
            ignored: f.ignored,
            notes: undefined,
            created_at: f.created_at,
            updated_at: f.updated_at,
          }));
        }

        // Fall back to generating from accident_illness care events
        const accidentEvents = mockCareEvents.filter(
          (e) => e.member_id === memberId && e.event_type === 'accident_illness'
        );

        const followups: AccidentFollowup[] = [];
        const stageTypes: AccidentFollowupStage[] = ['first_followup', 'second_followup', 'final_followup'];
        const dayOffsets = [3, 7, 14];

        accidentEvents.forEach((event) => {
          const eventDate = new Date(event.event_date);
          stageTypes.forEach((stage, index) => {
            const scheduledDate = new Date(eventDate);
            scheduledDate.setDate(scheduledDate.getDate() + dayOffsets[index]);

            followups.push({
              id: `accident_${event.id}_${stage}`,
              care_event_id: event.id,
              member_id: memberId,
              member_name: event.member_name,
              campus_id: event.campus_id,
              stage_type: stage,
              stage,
              scheduled_date: scheduledDate.toISOString().split('T')[0],
              hospital_name: event.hospital_name,
              completed: index === 0, // First stage completed
              ignored: false,
              notes: event.description,
              created_at: event.created_at,
              updated_at: new Date().toISOString(),
            });
          });
        });

        return followups;
      }

      const { data } = await api.get(API_ENDPOINTS.ACCIDENT_FOLLOWUP.MEMBER(memberId));
      return data;
    },
    enabled: !!memberId,
  });
}

/**
 * Complete an accident followup stage
 */
export function useCompleteAccidentFollowup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (stageId: string) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        return;
      }

      await api.post(API_ENDPOINTS.ACCIDENT_FOLLOWUP.COMPLETE(stageId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accidentTimeline'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Ignore an accident followup stage
 */
export function useIgnoreAccidentFollowup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (stageId: string) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        return;
      }

      await api.post(API_ENDPOINTS.ACCIDENT_FOLLOWUP.IGNORE(stageId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accidentTimeline'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Undo an accident followup completion/ignore
 */
export function useUndoAccidentFollowup() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (stageId: string) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        return;
      }

      await api.post(API_ENDPOINTS.ACCIDENT_FOLLOWUP.UNDO(stageId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['accidentTimeline'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ============================================================================
// FINANCIAL AID HOOKS
// ============================================================================

/**
 * Fetch financial aid schedules for a member
 */
export function useMemberFinancialAid(memberId: string) {
  return useQuery<FinancialAidSchedule[]>({
    queryKey: ['financialAid', memberId],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();

        // Get financial aid from mock data
        const memberAid = mockFinancialAidSchedules.filter((a) => a.member_id === memberId);

        // Also generate from financial_aid care events
        const aidEvents = mockCareEvents.filter(
          (e) => e.member_id === memberId && e.event_type === 'financial_aid'
        );

        const generatedAid: FinancialAidSchedule[] = aidEvents.map((event) => ({
          id: `aid_${event.id}`,
          member_id: memberId,
          member_name: event.member_name,
          campus_id: event.campus_id,
          title: event.title,
          aid_type: event.aid_type || 'emergency',
          aid_amount: event.aid_amount || 0,
          frequency: 'one_time' as const,
          start_date: event.event_date,
          is_active: true,
          ignored: event.ignored,
          ignored_occurrences: [],
          occurrences_completed: event.completed ? 1 : 0,
          notes: event.aid_notes || event.description,
          created_by: event.created_by_user_id,
          created_at: event.created_at,
          updated_at: event.updated_at,
        }));

        return [...memberAid, ...generatedAid];
      }

      const { data } = await api.get(API_ENDPOINTS.FINANCIAL_AID.MEMBER(memberId));
      return data;
    },
    enabled: !!memberId,
  });
}

/**
 * Mark financial aid as distributed
 */
export function useMarkAidDistributed() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (scheduleId: string) => {
      if (USE_MOCK_DATA) {
        return mockMarkAidDistributed(scheduleId);
      }

      await api.post(API_ENDPOINTS.FINANCIAL_AID.MARK_DISTRIBUTED(scheduleId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['financialAid'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Ignore financial aid payment
 */
export function useIgnoreAidPayment() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (scheduleId: string) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        const index = mockFinancialAidSchedules.findIndex((s) => s.id === scheduleId);
        if (index !== -1) {
          mockFinancialAidSchedules[index].ignored_occurrences.push(new Date().toISOString());
        }
        return;
      }

      await api.post(API_ENDPOINTS.FINANCIAL_AID.IGNORE(scheduleId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['financialAid'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

/**
 * Stop financial aid schedule
 */
export function useStopAidSchedule() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (scheduleId: string) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        const index = mockFinancialAidSchedules.findIndex((s) => s.id === scheduleId);
        if (index !== -1) {
          mockFinancialAidSchedules[index].is_active = false;
        }
        return;
      }

      await api.post(API_ENDPOINTS.FINANCIAL_AID.STOP(scheduleId));
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['financialAid'] });
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ============================================================================
// ADDITIONAL VISIT HOOKS
// ============================================================================

/**
 * Add additional visit to a care event
 */
export function useAddAdditionalVisit() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      parentEventId,
      data,
    }: {
      parentEventId: string;
      data: {
        visit_date: string;
        notes?: string;
        visitor_name?: string;
      };
    }) => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay();
        const parentEvent = mockCareEvents.find((e) => e.id === parentEventId);
        if (parentEvent) {
          const newVisit: CareEvent = {
            id: `visit_${Date.now()}`,
            member_id: parentEvent.member_id,
            member_name: parentEvent.member_name,
            campus_id: parentEvent.campus_id,
            event_type: 'regular_contact',
            event_date: data.visit_date,
            title: `Additional Visit - ${parentEvent.member_name}`,
            description: data.notes || '',
            completed: true,
            completed_at: new Date().toISOString(),
            completed_by_user_id: mockUser.id,
            completed_by_user_name: data.visitor_name || mockUser.name,
            ignored: false,
            created_by_user_id: mockUser.id,
            created_by_user_name: mockUser.name,
            created_at: new Date().toISOString(),
            updated_at: new Date().toISOString(),
          };
          mockCareEvents.unshift(newVisit);
          return newVisit;
        }
        throw new Error('Parent event not found');
      }

      const response = await api.post(
        API_ENDPOINTS.CARE_EVENTS.ADDITIONAL_VISIT(parentEventId),
        data
      );
      return response.data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['careEvents'] });
      queryClient.invalidateQueries({ queryKey: ['griefTimeline'] });
      queryClient.invalidateQueries({ queryKey: ['accidentTimeline'] });
      queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    },
  });
}

// ============================================================================
// MEMBER SEARCH FOR CARE EVENTS
// ============================================================================

/**
 * Search members for care event creation
 */
export function useSearchMembers(search: string) {
  return useQuery<MemberListItem[]>({
    queryKey: ['memberSearch', search],
    queryFn: async () => {
      if (USE_MOCK_DATA) {
        await simulateApiDelay(200, 400);

        if (!search.trim()) {
          // Return first 10 members when no search
          return mockMemberListItems.slice(0, 10);
        }

        const searchLower = search.toLowerCase();
        return mockMemberListItems.filter(
          (m) =>
            m.name.toLowerCase().includes(searchLower) ||
            m.phone?.includes(search)
        ).slice(0, 20);
      }

      const { data } = await api.get(API_ENDPOINTS.MEMBERS.LIST, {
        params: { search, limit: 20 },
      });
      return data;
    },
    enabled: true,
  });
}
