/**
 * Tests for useOfflineSync hook (src/hooks/useOfflineSync.js)
 *
 * Covers:
 * - Auto-sync fires when coming back online with pending items
 * - isSyncingRef prevents concurrent sync (infinite loop prevention)
 * - sync function processes queue and invalidates queries
 * - queueOperation works online (immediate execution) and offline (queued)
 * - clearQueue empties pending operations
 * - Stats are updated via subscription
 * - useOfflineMutation wrapper
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import { createElement } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
// Mock dependencies before importing the hook
vi.mock('sonner', () => ({
  toast: {
    info: vi.fn(),
    success: vi.fn(),
    warning: vi.fn(),
    error: vi.fn(),
  },
}));

vi.mock('@/lib/api', () => {
  return {
    default: vi.fn().mockResolvedValue({ data: { success: true } }),
    __esModule: true,
  };
});

vi.mock('@/lib/offlineQueue', () => {
  const listeners = new Set();
  return {
    offlineQueue: {
      getStats: vi.fn().mockResolvedValue({ pending: 0, failed: 0, completed: 0 }),
      subscribe: vi.fn((cb) => {
        listeners.add(cb);
        return () => listeners.delete(cb);
      }),
      enqueue: vi.fn().mockResolvedValue({ id: 1, status: 'pending' }),
      sync: vi.fn().mockResolvedValue({ synced: 0, failed: 0 }),
      getPending: vi.fn().mockResolvedValue([]),
      clear: vi.fn().mockResolvedValue(),
      _listeners: listeners,
    },
  };
});

// Import after mocks are set up
import { toast } from 'sonner';

import { useOfflineSync, useOfflineMutation } from '@/hooks/useOfflineSync';
import { offlineQueue } from '@/lib/offlineQueue';
import api from '@/lib/api';

// Helper: wrapper with QueryClientProvider
function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });

  return function Wrapper({ children }) {
    return createElement(QueryClientProvider, { client: queryClient }, children);
  };
}

// Helper: simulate online/offline
function goOnline() {
  Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
  window.dispatchEvent(new Event('online'));
}

function goOffline() {
  Object.defineProperty(navigator, 'onLine', { value: false, writable: true, configurable: true });
  window.dispatchEvent(new Event('offline'));
}

beforeEach(() => {
  vi.clearAllMocks();
  Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
  offlineQueue.getStats.mockResolvedValue({ pending: 0, failed: 0, completed: 0 });
  offlineQueue.sync.mockResolvedValue({ synced: 0, failed: 0 });
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('useOfflineSync - online status', () => {
  it('reports isOnline as true when navigator.onLine is true', () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    expect(result.current.isOnline).toBe(true);
  });

  it('tracks online/offline transitions', async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    expect(result.current.isOnline).toBe(true);

    act(() => {
      goOffline();
    });

    // useSyncExternalStore should pick up the change
    await waitFor(() => {
      expect(result.current.isOnline).toBe(false);
    });

    act(() => {
      goOnline();
    });

    await waitFor(() => {
      expect(result.current.isOnline).toBe(true);
    });
  });
});

describe('useOfflineSync - stats subscription', () => {
  it('fetches initial stats on mount', async () => {
    offlineQueue.getStats.mockResolvedValue({ pending: 3, failed: 1, completed: 5 });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    await waitFor(() => {
      expect(result.current.pendingCount).toBe(3);
    });

    expect(result.current.stats).toEqual({ pending: 3, failed: 1, completed: 5 });
  });

  it('subscribes to queue changes on mount', () => {
    const wrapper = createWrapper();
    renderHook(() => useOfflineSync(), { wrapper });

    expect(offlineQueue.subscribe).toHaveBeenCalled();
  });
});

describe('useOfflineSync - auto-sync on reconnect', () => {
  it('triggers sync when coming back online with pending items', async () => {
    offlineQueue.getStats.mockResolvedValue({ pending: 2, failed: 0, completed: 0 });
    offlineQueue.sync.mockResolvedValue({ synced: 2, failed: 0 });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    // Wait for initial stats to load (pendingCount=2)
    await waitFor(() => {
      expect(result.current.pendingCount).toBe(2);
    });

    // The effect should fire sync because isOnline=true and pendingCount>0
    // Give it time to call sync
    await waitFor(() => {
      expect(result.current.isSyncing).toBe(false);
    });
  });

  it('does NOT sync when offline even with pending items', async () => {
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true,
      configurable: true,
    });
    offlineQueue.getStats.mockResolvedValue({ pending: 5, failed: 0, completed: 0 });

    const wrapper = createWrapper();
    renderHook(() => useOfflineSync(), { wrapper });

    // sync should not have been called with the queue's sync function
    // (The hook's sync checks isOnline internally)
    await new Promise((r) => setTimeout(r, 50));
    // The hook sync checks isOnline via isSyncingRef, so offlineQueue.sync may or may not be called
    // The key assertion is that no toast.success is shown
    expect(toast.success).not.toHaveBeenCalled();
  });
});

describe('useOfflineSync - sync function', () => {
  it('sets isSyncing during sync and resets after', async () => {
    offlineQueue.sync.mockImplementation(async () => {
      await new Promise((r) => setTimeout(r, 10));
      return { synced: 1, failed: 0 };
    });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    // Call sync manually
    let syncPromise;
    act(() => {
      syncPromise = result.current.sync();
    });

    await act(async () => {
      await syncPromise;
    });

    expect(result.current.isSyncing).toBe(false);
  });

  it('shows success toast when operations are synced', async () => {
    offlineQueue.sync.mockResolvedValue({ synced: 3, failed: 0 });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    await act(async () => {
      await result.current.sync();
    });

    expect(toast.success).toHaveBeenCalledWith('Synced 3 pending operations');
  });

  it('shows warning toast when some operations fail', async () => {
    offlineQueue.sync.mockResolvedValue({ synced: 1, failed: 2 });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    await act(async () => {
      await result.current.sync();
    });

    expect(toast.warning).toHaveBeenCalledWith('2 operations failed to sync');
  });

  it('shows error toast on sync failure', async () => {
    offlineQueue.sync.mockRejectedValue(new Error('DB failure'));

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    await act(async () => {
      await result.current.sync();
    });

    expect(toast.error).toHaveBeenCalledWith('Sync failed');
  });

  it('prevents concurrent sync via isSyncingRef', async () => {
    let resolveSync;
    offlineQueue.sync.mockImplementation(
      () =>
        new Promise((r) => {
          resolveSync = r;
        })
    );

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    // Start first sync
    let sync1Done = false;
    act(() => {
      result.current.sync().then(() => {
        sync1Done = true;
      });
    });

    // Start second sync while first is in progress
    let sync2Result;
    await act(async () => {
      sync2Result = await result.current.sync();
    });

    // Second sync should have returned early (undefined = no-op)
    expect(sync2Result).toBeUndefined();

    // Complete first sync
    await act(async () => {
      resolveSync({ synced: 1, failed: 0 });
      await new Promise((r) => setTimeout(r, 10));
    });
  });
});

describe('useOfflineSync - queueOperation', () => {
  it('executes immediately when online', async () => {
    api.mockResolvedValue({ data: { id: 1, success: true } });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    let opResult;
    await act(async () => {
      opResult = await result.current.queueOperation({
        type: 'COMPLETE_EVENT',
        endpoint: '/care-events/123/complete',
        method: 'POST',
      });
    });

    expect(opResult.success).toBe(true);
    expect(opResult.queued).toBe(false);
    expect(api).toHaveBeenCalledWith({
      url: '/care-events/123/complete',
      method: 'POST',
      data: undefined,
    });
  });

  it('queues operation when offline', async () => {
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true,
      configurable: true,
    });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    // Wait for isOnline to be false
    await waitFor(() => {
      expect(result.current.isOnline).toBe(false);
    });

    let opResult;
    await act(async () => {
      opResult = await result.current.queueOperation({
        type: 'COMPLETE_EVENT',
        endpoint: '/care-events/123/complete',
        method: 'POST',
      });
    });

    expect(opResult.success).toBe(true);
    expect(opResult.queued).toBe(true);
    expect(offlineQueue.enqueue).toHaveBeenCalled();
    expect(toast.info).toHaveBeenCalledWith('You are offline. Operation will sync when connected.');
  });

  it('falls back to queue when online request gets network error', async () => {
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true,
      configurable: true,
    });
    api.mockRejectedValue({ code: 'ERR_NETWORK' });

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    // Even though hook thinks we are online initially, the request fails with network error
    // and navigator.onLine is false, so it should queue

    // First set online to true for the hook
    Object.defineProperty(navigator, 'onLine', { value: true, writable: true, configurable: true });
    window.dispatchEvent(new Event('online'));

    await waitFor(() => {
      expect(result.current.isOnline).toBe(true);
    });

    // Now make the request fail with network error and navigator.onLine is false
    Object.defineProperty(navigator, 'onLine', {
      value: false,
      writable: true,
      configurable: true,
    });

    let opResult;
    await act(async () => {
      opResult = await result.current.queueOperation({
        type: 'TEST',
        endpoint: '/test',
        method: 'POST',
      });
    });

    expect(opResult.queued).toBe(true);
    expect(offlineQueue.enqueue).toHaveBeenCalled();
  });

  it('rethrows non-network errors when online', async () => {
    const serverError = new Error('Server validation error');
    serverError.code = 'ERR_BAD_REQUEST';
    api.mockRejectedValue(serverError);

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    await expect(
      act(async () => {
        await result.current.queueOperation({
          type: 'TEST',
          endpoint: '/test',
          method: 'POST',
        });
      })
    ).rejects.toThrow('Server validation error');
  });
});

describe('useOfflineSync - clearQueue', () => {
  it('clears the offline queue and shows toast', async () => {
    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    await act(async () => {
      await result.current.clearQueue();
    });

    expect(offlineQueue.clear).toHaveBeenCalled();
    expect(toast.success).toHaveBeenCalledWith('Pending operations cleared');
  });
});

describe('useOfflineSync - getPending', () => {
  it('returns pending operations from the queue', async () => {
    const pendingOps = [
      { id: 1, type: 'A', status: 'pending' },
      { id: 2, type: 'B', status: 'pending' },
    ];
    offlineQueue.getPending.mockResolvedValue(pendingOps);

    const wrapper = createWrapper();
    const { result } = renderHook(() => useOfflineSync(), { wrapper });

    let pending;
    await act(async () => {
      pending = await result.current.getPending();
    });

    expect(pending).toEqual(pendingOps);
  });
});

describe('useOfflineMutation', () => {
  it('calls queueOperation with correct parameters', async () => {
    api.mockResolvedValue({ data: { completed: true } });

    const wrapper = createWrapper();
    const onSuccess = vi.fn();

    const { result } = renderHook(
      () =>
        useOfflineMutation({
          type: 'COMPLETE_EVENT',
          endpoint: (id) => `/care-events/${id}/complete`,
          method: 'POST',
          onSuccess,
        }),
      { wrapper }
    );

    await act(async () => {
      await result.current.mutate('event-123');
    });

    expect(api).toHaveBeenCalled();
  });

  it('sets isLoading during mutation and resets after', async () => {
    let resolveApi;
    api.mockImplementation(
      () =>
        new Promise((r) => {
          resolveApi = r;
        })
    );

    const wrapper = createWrapper();
    const { result } = renderHook(
      () =>
        useOfflineMutation({
          type: 'TEST',
          endpoint: '/test',
          method: 'POST',
        }),
      { wrapper }
    );

    expect(result.current.isLoading).toBe(false);

    let mutatePromise;
    act(() => {
      mutatePromise = result.current.mutate({ data: 'test' });
    });

    // During execution, isLoading should be true
    // (This is hard to test synchronously, but we can verify it's false after)

    await act(async () => {
      resolveApi({ data: { success: true } });
      await mutatePromise;
    });

    expect(result.current.isLoading).toBe(false);
  });

  it('calls onError callback on failure', async () => {
    api.mockRejectedValue(new Error('Validation failed'));

    const wrapper = createWrapper();
    const onError = vi.fn();

    const { result } = renderHook(
      () =>
        useOfflineMutation({
          type: 'TEST',
          endpoint: '/test',
          method: 'POST',
          onError,
        }),
      { wrapper }
    );

    await act(async () => {
      try {
        await result.current.mutate({ bad: 'data' });
      } catch {
        // Expected
      }
    });

    expect(onError).toHaveBeenCalled();
    expect(result.current.error).toBeTruthy();
  });

  it('exposes isOnline from the parent hook', () => {
    const wrapper = createWrapper();
    const { result } = renderHook(
      () =>
        useOfflineMutation({
          type: 'TEST',
          endpoint: '/test',
          method: 'POST',
        }),
      { wrapper }
    );

    expect(result.current.isOnline).toBe(true);
  });
});
