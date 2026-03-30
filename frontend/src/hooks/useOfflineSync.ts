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

import { useState, useEffect, useCallback, useRef, useSyncExternalStore } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { offlineQueue } from '@/lib/offlineQueue';
import api from '@/lib/api';

export interface QueueOperation {
  type: string;
  endpoint: string;
  method: string;
  payload?: unknown;
  optimisticUpdate?: Record<string, unknown>;
}

export interface QueuedOperation extends QueueOperation {
  id?: number;
  createdAt: string;
  status: 'pending' | 'failed' | 'completed' | 'permanently_failed';
  retryCount: number;
  lastError: string | null;
  updatedAt?: string;
}

export interface QueueStats {
  total?: number;
  pending: number;
  failed: number;
  completed: number;
}

export interface QueueOperationResult {
  success: boolean;
  data?: unknown;
  queued: boolean;
}

export interface SyncResult {
  synced: number;
  failed: number;
}

export interface UseOfflineSyncReturn {
  isOnline: boolean;
  isSyncing: boolean;
  pendingCount: number;
  stats: QueueStats;
  queueOperation: (operation: QueueOperation) => Promise<QueueOperationResult>;
  sync: () => Promise<SyncResult | undefined>;
  getPending: () => Promise<QueuedOperation[]>;
  clearQueue: () => Promise<void>;
}

/**
 * Subscribe to network status changes
 */
function subscribeToNetwork(callback: () => void): () => void {
  window.addEventListener('online', callback);
  window.addEventListener('offline', callback);
  return () => {
    window.removeEventListener('online', callback);
    window.removeEventListener('offline', callback);
  };
}

function getNetworkStatus(): boolean {
  return typeof navigator !== 'undefined' ? navigator.onLine : true;
}

/**
 * Hook for offline-first operations
 */
export function useOfflineSync(): UseOfflineSyncReturn {
  const queryClient = useQueryClient();
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const isSyncingRef = useRef(false);
  const [stats, setStats] = useState<QueueStats>({ pending: 0, failed: 0, completed: 0 });

  // Subscribe to network status
  const isOnline = useSyncExternalStore(subscribeToNetwork, getNetworkStatus);

  // Subscribe to queue changes
  useEffect(() => {
    const updateStats = async () => {
      const queueStats = await offlineQueue.getStats();
      setPendingCount(queueStats.pending);
      setStats(queueStats);
    };

    updateStats();
    return offlineQueue.subscribe(updateStats);
  }, []);

  /**
   * Sync all pending operations
   */
  const sync = useCallback(async (): Promise<SyncResult | undefined> => {
    if (!isOnline || isSyncingRef.current) return;

    isSyncingRef.current = true;
    setIsSyncing(true);
    try {
      const executor = async (operation: QueuedOperation) => {
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
        toast.success(`Synced ${result.synced} pending operations`);
      }

      if (result.failed > 0) {
        toast.warning(`${result.failed} operations failed to sync`);
      }

      return result;
    } catch (error) {
      toast.error('Sync failed');
    } finally {
      isSyncingRef.current = false;
      setIsSyncing(false);
    }
  }, [isOnline, queryClient]);

  // Auto-sync when coming back online
  useEffect(() => {
    if (isOnline && pendingCount > 0) {
      sync();
    }
  }, [isOnline, pendingCount, sync]);

  /**
   * Queue an operation for offline sync
   */
  const queueOperation = useCallback(
    async (operation: QueueOperation): Promise<QueueOperationResult> => {
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
          // If network error, queue for later
          const axiosError = error as { code?: string };
          if (!navigator.onLine || axiosError.code === 'ERR_NETWORK') {
            await offlineQueue.enqueue(operation);
            toast.info('Operation queued for sync when online');
            return { success: true, queued: true };
          }
          throw error;
        }
      }

      // Offline - queue the operation
      await offlineQueue.enqueue(operation);
      toast.info('You are offline. Operation will sync when connected.');
      return { success: true, queued: true };
    },
    [isOnline]
  );

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
    toast.success('Pending operations cleared');
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
  };
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

export interface UseOfflineMutationOptions<TPayload = unknown> {
  type: string;
  endpoint: string | ((payload: TPayload) => string);
  method?: string;
  onSuccess?: (data: unknown) => void;
  onError?: (error: unknown) => void;
}

export interface UseOfflineMutationReturn<TPayload = unknown> {
  mutate: (
    payload: TPayload,
    options?: { onSuccess?: (data: unknown) => void; onError?: (error: unknown) => void }
  ) => Promise<QueueOperationResult>;
  mutateAsync: (
    payload: TPayload,
    options?: { onSuccess?: (data: unknown) => void; onError?: (error: unknown) => void }
  ) => Promise<QueueOperationResult>;
  isLoading: boolean;
  isPending: boolean;
  error: unknown;
  isOnline: boolean;
}

export function useOfflineMutation<TPayload = unknown>({
  type,
  endpoint,
  method = 'POST',
  onSuccess,
  onError,
}: UseOfflineMutationOptions<TPayload>): UseOfflineMutationReturn<TPayload> {
  const { queueOperation, isOnline } = useOfflineSync();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const mutate = useCallback(
    async (
      payload: TPayload,
      options: { onSuccess?: (data: unknown) => void; onError?: (error: unknown) => void } = {}
    ): Promise<QueueOperationResult> => {
      setIsLoading(true);
      setError(null);

      try {
        const endpointUrl = typeof endpoint === 'function' ? endpoint(payload) : endpoint;

        const result = await queueOperation({
          type,
          endpoint: endpointUrl,
          method,
          payload: typeof endpoint === 'function' ? undefined : (payload as unknown),
        });

        if (result.success && !result.queued) {
          onSuccess?.(result.data);
          options.onSuccess?.(result.data);
        }

        return result;
      } catch (err) {
        setError(err);
        onError?.(err);
        options.onError?.(err);
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
