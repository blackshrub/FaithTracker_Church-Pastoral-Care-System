/**
 * useBulkMutation - Hook for bulk operations with progress tracking
 *
 * Provides bulk complete, ignore, and delete for care events with:
 * - Progress tracking
 * - Optimistic updates
 * - Automatic cache invalidation
 *
 * Usage:
 * const { bulkComplete, bulkIgnore, bulkDelete, isLoading, progress } = useBulkMutation();
 * await bulkComplete(['event-1', 'event-2', 'event-3']);
 */

import { useMutation, useQueryClient } from '@tanstack/react-query';
import { useState, useCallback } from 'react';
import { toast } from 'sonner';

import api from '@/lib/api';

export interface BulkProgress {
  current: number;
  total: number;
}

interface BulkCompleteResponse {
  completed_count: number;
}

interface BulkIgnoreResponse {
  ignored_count: number;
}

interface BulkDeleteResponse {
  deleted_count: number;
}

export interface UseBulkMutationReturn {
  bulkComplete: (eventIds: string[]) => Promise<BulkCompleteResponse>;
  bulkIgnore: (eventIds: string[]) => Promise<BulkIgnoreResponse>;
  bulkDelete: (eventIds: string[]) => Promise<BulkDeleteResponse>;
  isLoading: boolean;
  isCompleting: boolean;
  isIgnoring: boolean;
  isDeleting: boolean;
  progress: BulkProgress;
  reset: () => void;
}

/**
 * Hook for bulk care event operations
 */
export function useBulkMutation(): UseBulkMutationReturn {
  const queryClient = useQueryClient();
  const [progress, setProgress] = useState<BulkProgress>({ current: 0, total: 0 });

  /**
   * Invalidate all affected queries after bulk operation
   */
  const invalidateQueries = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ['dashboard'] });
    queryClient.invalidateQueries({ queryKey: ['careEvents'] });
    queryClient.invalidateQueries({ queryKey: ['reminders'] });
    queryClient.invalidateQueries({ queryKey: ['member'] });
    queryClient.invalidateQueries({ queryKey: ['activityLogs'] });
  }, [queryClient]);

  /**
   * Bulk complete mutation
   */
  const bulkCompleteMutation = useMutation<BulkCompleteResponse, Error, string[]>({
    mutationFn: async (eventIds) => {
      setProgress({ current: 0, total: eventIds.length });
      const response = await api.post('/care-events/bulk-complete', { event_ids: eventIds });
      return response.data;
    },
    onSuccess: (data) => {
      setProgress({ current: data.completed_count, total: data.completed_count });
      invalidateQueries();
      toast.success(`Completed ${data.completed_count} tasks`);
    },
    onError: (error: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(error.response?.data?.detail || 'Failed to complete tasks');
    },
    onSettled: () => {
      setTimeout(() => setProgress({ current: 0, total: 0 }), 1000);
    },
  });

  /**
   * Bulk ignore mutation
   */
  const bulkIgnoreMutation = useMutation<BulkIgnoreResponse, Error, string[]>({
    mutationFn: async (eventIds) => {
      setProgress({ current: 0, total: eventIds.length });
      const response = await api.post('/care-events/bulk-ignore', { event_ids: eventIds });
      return response.data;
    },
    onSuccess: (data) => {
      setProgress({ current: data.ignored_count, total: data.ignored_count });
      invalidateQueries();
      toast.success(`Ignored ${data.ignored_count} tasks`);
    },
    onError: (error: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(error.response?.data?.detail || 'Failed to ignore tasks');
    },
    onSettled: () => {
      setTimeout(() => setProgress({ current: 0, total: 0 }), 1000);
    },
  });

  /**
   * Bulk delete mutation
   */
  const bulkDeleteMutation = useMutation<BulkDeleteResponse, Error, string[]>({
    mutationFn: async (eventIds) => {
      setProgress({ current: 0, total: eventIds.length });
      const response = await api.post('/care-events/bulk-delete', { event_ids: eventIds });
      return response.data;
    },
    onSuccess: (data) => {
      setProgress({ current: data.deleted_count, total: data.deleted_count });
      invalidateQueries();
      toast.success(`Deleted ${data.deleted_count} events`);
    },
    onError: (error: Error & { response?: { data?: { detail?: string } } }) => {
      toast.error(error.response?.data?.detail || 'Failed to delete events');
    },
    onSettled: () => {
      setTimeout(() => setProgress({ current: 0, total: 0 }), 1000);
    },
  });

  return {
    // Mutation functions
    bulkComplete: bulkCompleteMutation.mutateAsync,
    bulkIgnore: bulkIgnoreMutation.mutateAsync,
    bulkDelete: bulkDeleteMutation.mutateAsync,

    // Loading states
    isLoading:
      bulkCompleteMutation.isPending ||
      bulkIgnoreMutation.isPending ||
      bulkDeleteMutation.isPending,

    isCompleting: bulkCompleteMutation.isPending,
    isIgnoring: bulkIgnoreMutation.isPending,
    isDeleting: bulkDeleteMutation.isPending,

    // Progress
    progress,

    // Reset
    reset: () => {
      bulkCompleteMutation.reset();
      bulkIgnoreMutation.reset();
      bulkDeleteMutation.reset();
      setProgress({ current: 0, total: 0 });
    },
  };
}

// ==================== Bulk Selection ====================

interface BulkSelectable {
  id: string;
}

export interface UseBulkSelectionReturn {
  selectedIds: string[];
  selectedCount: number;
  toggleSelection: (id: string) => void;
  selectAll: () => void;
  clearSelection: () => void;
  isSelected: (id: string) => boolean;
  isAllSelected: boolean;
  isSomeSelected: boolean;
}

/**
 * Hook for managing selection state in bulk operations
 */
export function useBulkSelection(items: BulkSelectable[] = []): UseBulkSelectionReturn {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const toggleSelection = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(items.map((item) => item.id)));
  }, [items]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const isSelected = useCallback((id: string) => selectedIds.has(id), [selectedIds]);

  const isAllSelected = items.length > 0 && selectedIds.size === items.length;
  const isSomeSelected = selectedIds.size > 0 && selectedIds.size < items.length;

  return {
    selectedIds: Array.from(selectedIds),
    selectedCount: selectedIds.size,
    toggleSelection,
    selectAll,
    clearSelection,
    isSelected,
    isAllSelected,
    isSomeSelected,
  };
}

export default useBulkMutation;
