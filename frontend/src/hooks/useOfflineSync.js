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

import { useState, useEffect, useCallback, useSyncExternalStore } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';

import { offlineQueue } from '@/lib/offlineQueue';
import api from '@/lib/api';

/**
 * Subscribe to network status changes
 */
function subscribeToNetwork(callback) {
  window.addEventListener('online', callback);
  window.addEventListener('offline', callback);
  return () => {
    window.removeEventListener('online', callback);
    window.removeEventListener('offline', callback);
  };
}

function getNetworkStatus() {
  return typeof navigator !== 'undefined' ? navigator.onLine : true;
}

/**
 * Hook for offline-first operations
 */
export function useOfflineSync() {
  const queryClient = useQueryClient();
  const [pendingCount, setPendingCount] = useState(0);
  const [isSyncing, setIsSyncing] = useState(false);
  const [stats, setStats] = useState({ pending: 0, failed: 0, completed: 0 });

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

  // Auto-sync when coming back online
  useEffect(() => {
    if (isOnline && pendingCount > 0) {
      sync();
    }
  }, [isOnline]);

  /**
   * Queue an operation for offline sync
   */
  const queueOperation = useCallback(
    async (operation) => {
      // Try to execute immediately if online
      if (isOnline) {
        try {
          const response = await api({
            url: operation.endpoint,
            method: operation.method,
            data: operation.payload,
          });
          return { success: true, data: response.data, queued: false };
        } catch (error) {
          // If network error, queue for later
          if (!navigator.onLine || error.code === 'ERR_NETWORK') {
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
   * Sync all pending operations
   */
  const sync = useCallback(async () => {
    if (!isOnline || isSyncing) return;

    setIsSyncing(true);
    try {
      const executor = async (operation) => {
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
      setIsSyncing(false);
    }
  }, [isOnline, isSyncing, queryClient]);

  /**
   * Get pending operations
   */
  const getPending = useCallback(async () => {
    return offlineQueue.getPending();
  }, []);

  /**
   * Clear all pending operations
   */
  const clearQueue = useCallback(async () => {
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
export function useOfflineMutation({ type, endpoint, method = 'POST', onSuccess, onError }) {
  const { queueOperation, isOnline } = useOfflineSync();
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const mutate = useCallback(
    async (payload, options = {}) => {
      setIsLoading(true);
      setError(null);

      try {
        const endpointUrl = typeof endpoint === 'function' ? endpoint(payload) : endpoint;

        const result = await queueOperation({
          type,
          endpoint: endpointUrl,
          method,
          payload: typeof endpoint === 'function' ? undefined : payload,
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
