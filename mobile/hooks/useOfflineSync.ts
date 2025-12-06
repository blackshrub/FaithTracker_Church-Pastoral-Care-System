/**
 * useOfflineSync - Hook for offline-first mutations with automatic sync
 *
 * Provides React integration for the offline queue:
 * - Optimistic updates
 * - Automatic retry when online
 * - Pending operations count
 * - Sync status
 *
 * Usage:
 * const {
 *   isOnline,
 *   pendingCount,
 *   queueOperation,
 *   sync
 * } = useOfflineSync();
 *
 * // Queue operation for later sync
 * await queueOperation({
 *   type: 'COMPLETE_EVENT',
 *   endpoint: '/care-events/123/complete',
 *   method: 'POST'
 * });
 */

import { useState, useEffect, useCallback } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import Toast from 'react-native-toast-message';

import { offlineQueue, QueuedOperation, QueueStats, OperationExecutor } from '@/lib/offlineQueue';
import { useNetwork } from '@/hooks/useNetwork';
import api from '@/services/api';

// ============================================================================
// TYPES
// ============================================================================

interface QueueOperationInput {
  type: string;
  endpoint: string;
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  payload?: Record<string, unknown>;
}

interface QueueOperationResult {
  success: boolean;
  data?: unknown;
  queued: boolean;
}

interface UseOfflineSyncReturn {
  isOnline: boolean;
  isSyncing: boolean;
  pendingCount: number;
  stats: QueueStats;
  queueOperation: (operation: QueueOperationInput) => Promise<QueueOperationResult>;
  sync: () => Promise<{ synced: number; failed: number }>;
  getPending: () => Promise<QueuedOperation[]>;
  clearQueue: () => Promise<void>;
  clearCompleted: () => Promise<number>;
}

// ============================================================================
// HOOK
// ============================================================================

export function useOfflineSync(): UseOfflineSyncReturn {
  const queryClient = useQueryClient();
  const { isOnline } = useNetwork();

  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [stats, setStats] = useState<QueueStats>({
    total: 0,
    pending: 0,
    failed: 0,
    completed: 0,
    permanentlyFailed: 0,
  });

  // Subscribe to queue changes
  useEffect(() => {
    const updateStats = async () => {
      const queueStats = await offlineQueue.getStats();
      setPendingCount(queueStats.pending + queueStats.failed);
      setStats(queueStats);
    };

    updateStats();
    return offlineQueue.subscribe(updateStats);
  }, []);

  // Auto-sync when coming back online
  useEffect(() => {
    if (isOnline && pendingCount > 0 && !isSyncing) {
      sync();
    }
  }, [isOnline, pendingCount]);

  /**
   * Queue an operation for offline sync
   */
  const queueOperation = useCallback(
    async (operation: QueueOperationInput): Promise<QueueOperationResult> => {
      // Try to execute immediately if online
      if (isOnline) {
        try {
          const response = await api({
            url: operation.endpoint,
            method: operation.method,
            data: operation.payload,
          });
          return { success: true, data: response.data, queued: false };
        } catch (error: unknown) {
          // Check if it's a network error
          const isNetworkError =
            error &&
            typeof error === 'object' &&
            'response' in error &&
            !(error as { response?: unknown }).response;

          if (isNetworkError) {
            // Network error - queue for later
            await offlineQueue.enqueue(operation);
            Toast.show({
              type: 'info',
              text1: 'Offline',
              text2: 'Operation queued for sync when online',
            });
            return { success: true, queued: true };
          }
          throw error;
        }
      }

      // Offline - queue the operation
      await offlineQueue.enqueue(operation);
      Toast.show({
        type: 'info',
        text1: 'You are offline',
        text2: 'Operation will sync when connected',
      });
      return { success: true, queued: true };
    },
    [isOnline]
  );

  /**
   * Sync all pending operations
   */
  const sync = useCallback(async (): Promise<{ synced: number; failed: number }> => {
    if (!isOnline || isSyncing) {
      return { synced: 0, failed: 0 };
    }

    setIsSyncing(true);

    try {
      const executor: OperationExecutor = async (operation) => {
        const response = await api({
          url: operation.endpoint,
          method: operation.method,
          data: operation.payload,
        });
        return response.data;
      };

      const result = await offlineQueue.sync(executor);

      if (result.synced > 0) {
        // Invalidate queries to refresh data
        queryClient.invalidateQueries();
        Toast.show({
          type: 'success',
          text1: 'Synced',
          text2: `${result.synced} pending operation${result.synced > 1 ? 's' : ''} synced`,
        });
      }

      if (result.failed > 0) {
        Toast.show({
          type: 'error',
          text1: 'Sync Warning',
          text2: `${result.failed} operation${result.failed > 1 ? 's' : ''} failed to sync`,
        });
      }

      return result;
    } catch (error) {
      Toast.show({
        type: 'error',
        text1: 'Sync failed',
        text2: 'Please try again later',
      });
      return { synced: 0, failed: 0 };
    } finally {
      setIsSyncing(false);
    }
  }, [isOnline, isSyncing, queryClient]);

  /**
   * Get pending operations
   */
  const getPending = useCallback(async (): Promise<QueuedOperation[]> => {
    return offlineQueue.getPending();
  }, []);

  /**
   * Clear all pending operations
   */
  const clearQueue = useCallback(async (): Promise<void> => {
    await offlineQueue.clear();
    Toast.show({
      type: 'success',
      text1: 'Queue cleared',
      text2: 'All pending operations removed',
    });
  }, []);

  /**
   * Clear only completed/failed operations
   */
  const clearCompleted = useCallback(async (): Promise<number> => {
    const count = await offlineQueue.clearCompleted();
    if (count > 0) {
      Toast.show({
        type: 'success',
        text1: 'Cleaned up',
        text2: `${count} completed operation${count > 1 ? 's' : ''} removed`,
      });
    }
    return count;
  }, []);

  return {
    isOnline,
    isSyncing,
    pendingCount,
    stats,
    queueOperation,
    sync,
    getPending,
    clearQueue,
    clearCompleted,
  };
}

// ============================================================================
// OFFLINE MUTATION HOOK
// ============================================================================

interface UseOfflineMutationOptions {
  type: string;
  endpoint: string | ((payload: unknown) => string);
  method?: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  onSuccess?: (data: unknown) => void;
  onError?: (error: unknown) => void;
}

interface UseOfflineMutationReturn {
  mutate: (payload?: unknown, options?: { onSuccess?: (data: unknown) => void; onError?: (error: unknown) => void }) => Promise<QueueOperationResult>;
  mutateAsync: (payload?: unknown, options?: { onSuccess?: (data: unknown) => void; onError?: (error: unknown) => void }) => Promise<QueueOperationResult>;
  isLoading: boolean;
  isPending: boolean;
  error: unknown;
  isOnline: boolean;
}

/**
 * Hook for creating offline-capable mutations
 *
 * Usage:
 * const completeMutation = useOfflineMutation({
 *   type: 'COMPLETE_EVENT',
 *   endpoint: (eventId) => `/care-events/${eventId}/complete`,
 *   method: 'POST',
 *   onSuccess: () => queryClient.invalidateQueries(['dashboard'])
 * });
 *
 * await completeMutation.mutate(eventId);
 */
export function useOfflineMutation({
  type,
  endpoint,
  method = 'POST',
  onSuccess,
  onError,
}: UseOfflineMutationOptions): UseOfflineMutationReturn {
  const { queueOperation, isOnline } = useOfflineSync();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const mutate = useCallback(
    async (
      payload?: unknown,
      options?: { onSuccess?: (data: unknown) => void; onError?: (error: unknown) => void }
    ): Promise<QueueOperationResult> => {
      setIsLoading(true);
      setError(null);

      try {
        const endpointUrl = typeof endpoint === 'function' ? endpoint(payload) : endpoint;

        const result = await queueOperation({
          type,
          endpoint: endpointUrl,
          method,
          payload: typeof endpoint === 'function' ? undefined : (payload as Record<string, unknown>),
        });

        if (result.success && !result.queued) {
          onSuccess?.(result.data);
          options?.onSuccess?.(result.data);
        }

        return result;
      } catch (err) {
        setError(err);
        onError?.(err);
        options?.onError?.(err);
        throw err;
      } finally {
        setIsLoading(false);
      }
    },
    [queueOperation, type, endpoint, method, onSuccess, onError]
  );

  return {
    mutate,
    mutateAsync: mutate,
    isLoading,
    isPending: isLoading,
    error,
    isOnline,
  };
}

export default useOfflineSync;
