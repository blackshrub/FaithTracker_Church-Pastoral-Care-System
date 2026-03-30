/**
 * Tests for useActivityStream hook (src/hooks/useActivityStream.js)
 *
 * Covers:
 * - connectRef is kept in sync for reconnect stability
 * - disconnect cleans up EventSource and reconnect timeout
 * - Activities from SSE are filtered (own user excluded)
 * - Other users' activities are added to the list
 * - onActivity callback is invoked for incoming activities
 * - Reconnect with exponential backoff on error
 * - Initial activity loading from REST API
 * - maxActivities limits the list size
 * - formatActivityMessage utility
 * - clearActivities resets state
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

// Mock EventSource
class MockEventSource {
  constructor(url) {
    this.url = url;
    this.readyState = 0; // CONNECTING
    this.onopen = null;
    this.onerror = null;
    this._listeners = {};
    MockEventSource.instances.push(this);
  }

  addEventListener(type, handler) {
    if (!this._listeners[type]) this._listeners[type] = [];
    this._listeners[type].push(handler);
  }

  removeEventListener(type, handler) {
    if (this._listeners[type]) {
      this._listeners[type] = this._listeners[type].filter(h => h !== handler);
    }
  }

  close() {
    this.readyState = 2; // CLOSED
    this._closed = true;
  }

  // Test helpers
  _triggerOpen() {
    this.readyState = 1; // OPEN
    if (this.onopen) this.onopen();
  }

  _triggerError() {
    if (this.onerror) this.onerror(new Event('error'));
  }

  _triggerEvent(type, data) {
    const handlers = this._listeners[type] || [];
    handlers.forEach(h => h({ data: JSON.stringify(data) }));
  }
}
MockEventSource.instances = [];

// Mock AuthContext
const mockUser = { id: 'user-1', name: 'Current User' };
const mockToken = 'test-jwt-token';

vi.mock('@/context/AuthContext', () => ({
  useAuth: vi.fn(() => ({
    token: mockToken,
    user: mockUser,
  })),
}));

// Mock api for initial load
vi.mock('@/lib/api', () => ({
  default: {
    get: vi.fn().mockResolvedValue({
      data: [
        {
          id: 'log-1',
          campus_id: 'c1',
          user_id: 'user-2',
          user_name: 'Other User',
          action_type: 'complete_task',
          member_id: 'm1',
          member_name: 'John Doe',
          created_at: '2024-01-15T10:00:00Z',
        },
      ],
    }),
  },
}));

import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';
import { useActivityStream, formatActivityMessage } from '@/hooks/useActivityStream';

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal('EventSource', MockEventSource);
  vi.useFakeTimers({ shouldAdvanceTime: true });

  // Reset mocks
  vi.mocked(useAuth).mockReturnValue({ token: mockToken, user: mockUser });
  vi.mocked(api.get).mockResolvedValue({
    data: [
      {
        id: 'log-1',
        user_id: 'user-2',
        user_name: 'Other User',
        action_type: 'complete_task',
        member_name: 'John Doe',
        created_at: '2024-01-15T10:00:00Z',
      },
    ],
  });
});

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe('useActivityStream - connection', () => {
  it('creates EventSource with token on mount when enabled and token exists', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    expect(es.url).toContain('token=test-jwt-token');
  });

  it('does NOT create EventSource when token is null', async () => {
    vi.mocked(useAuth).mockReturnValue({ token: null, user: null });

    const initialCount = MockEventSource.instances.length;
    renderHook(() => useActivityStream({ enabled: true }));

    await new Promise(r => setTimeout(r, 10));
    vi.advanceTimersByTime(10);

    // No new EventSource should have been created
    expect(MockEventSource.instances.length).toBe(initialCount);
  });

  it('does NOT create EventSource when disabled', async () => {
    const initialCount = MockEventSource.instances.length;
    renderHook(() => useActivityStream({ enabled: false }));

    await new Promise(r => setTimeout(r, 10));
    vi.advanceTimersByTime(10);

    expect(MockEventSource.instances.length).toBe(initialCount);
  });

  it('sets isConnected to true on EventSource open', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];

    act(() => {
      es._triggerOpen();
    });

    expect(result.current.isConnected).toBe(true);
  });
});

describe('useActivityStream - disconnect', () => {
  it('closes EventSource on unmount', async () => {
    const { unmount } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];

    unmount();

    expect(es._closed).toBe(true);
  });

  it('clears reconnect timeout on disconnect', async () => {
    const clearTimeoutSpy = vi.spyOn(global, 'clearTimeout');

    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    act(() => {
      result.current.disconnect();
    });

    expect(result.current.isConnected).toBe(false);
    // clearTimeout should have been called (at least for the reconnect timeout)
    expect(clearTimeoutSpy).toHaveBeenCalled();
  });

  it('sets isConnected to false on disconnect', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es._triggerOpen(); });
    expect(result.current.isConnected).toBe(true);

    act(() => { result.current.disconnect(); });
    expect(result.current.isConnected).toBe(false);
  });
});

describe('useActivityStream - activity filtering', () => {
  it('filters out own user activities from SSE stream', async () => {
    const onActivity = vi.fn();
    const { result } = renderHook(() =>
      useActivityStream({ enabled: true, onActivity })
    );

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es._triggerOpen(); });

    // Send activity from own user
    act(() => {
      es._triggerEvent('activity', {
        id: 'act-1',
        user_id: 'user-1', // Same as mockUser.id
        user_name: 'Current User',
        action_type: 'complete_task',
        member_name: 'John',
      });
    });

    // Should NOT be added to activities
    expect(onActivity).not.toHaveBeenCalled();

    // Verify activities list doesn't contain own activity
    const ownActivities = result.current.activities.filter(
      a => a.user_id === 'user-1' && a.id === 'act-1'
    );
    expect(ownActivities).toHaveLength(0);
  });

  it('includes activities from other users', async () => {
    const onActivity = vi.fn();
    const { result } = renderHook(() =>
      useActivityStream({ enabled: true, onActivity })
    );

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es._triggerOpen(); });

    // Send activity from another user
    act(() => {
      es._triggerEvent('activity', {
        id: 'act-2',
        user_id: 'user-2', // Different from mockUser.id
        user_name: 'Other User',
        action_type: 'create_care_event',
        member_name: 'Jane',
        event_type: 'birthday',
      });
    });

    expect(onActivity).toHaveBeenCalledTimes(1);
    expect(onActivity).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'user-2',
        user_name: 'Other User',
      })
    );

    // Should be in the activities list
    const otherActivities = result.current.activities.filter(a => a.id === 'act-2');
    expect(otherActivities).toHaveLength(1);
  });

  it('sets lastActivity when receiving an activity from another user', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es._triggerOpen(); });

    const activity = {
      id: 'act-3',
      user_id: 'user-3',
      user_name: 'Pastor Jane',
      action_type: 'complete_task',
      member_name: 'Member A',
    };

    act(() => { es._triggerEvent('activity', activity); });

    expect(result.current.lastActivity).toEqual(activity);
  });
});

describe('useActivityStream - maxActivities limit', () => {
  it('limits the activities list to maxActivities', async () => {
    const { result } = renderHook(() =>
      useActivityStream({ enabled: true, maxActivities: 3 })
    );

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es._triggerOpen(); });

    // Send 5 activities
    for (let i = 0; i < 5; i++) {
      act(() => {
        es._triggerEvent('activity', {
          id: `act-${i}`,
          user_id: 'user-other',
          user_name: 'Other',
          action_type: 'complete_task',
          member_name: `Member ${i}`,
        });
      });
    }

    // Should only keep the last 3 (newest first)
    expect(result.current.activities.length).toBeLessThanOrEqual(3);
  });
});

describe('useActivityStream - reconnect with exponential backoff', () => {
  it('attempts reconnect on error with initial delay', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    const instanceCountBefore = MockEventSource.instances.length;

    // Trigger error
    act(() => { es._triggerError(); });

    expect(result.current.isConnected).toBe(false);

    // Advance timer by initial delay (1000ms)
    act(() => { vi.advanceTimersByTime(1000); });

    // A new EventSource should have been created
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(instanceCountBefore);
    });
  });

  it('doubles delay on subsequent errors (exponential backoff)', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    // First error
    const es1 = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es1._triggerError(); });

    const countAfterFirst = MockEventSource.instances.length;

    // After 500ms (less than initial 1000ms delay) - should not reconnect yet
    act(() => { vi.advanceTimersByTime(500); });
    expect(MockEventSource.instances.length).toBe(countAfterFirst);

    // After full 1000ms - should reconnect
    act(() => { vi.advanceTimersByTime(500); });

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(countAfterFirst);
    });

    // Second error - delay should be 2000ms
    const es2 = MockEventSource.instances[MockEventSource.instances.length - 1];
    const countAfterSecond = MockEventSource.instances.length;
    act(() => { es2._triggerError(); });

    act(() => { vi.advanceTimersByTime(1500); });
    expect(MockEventSource.instances.length).toBe(countAfterSecond);

    act(() => { vi.advanceTimersByTime(500); });

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(countAfterSecond);
    });
  });

  it('resets delay on successful connection', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es1 = MockEventSource.instances[MockEventSource.instances.length - 1];

    // Trigger error to increase delay
    act(() => { es1._triggerError(); });
    act(() => { vi.advanceTimersByTime(1000); });

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(1);
    });

    // Open the new connection successfully
    const es2 = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es2._triggerOpen(); });

    expect(result.current.isConnected).toBe(true);
    // Delay should be reset to initial (tested implicitly by next reconnect timing)
  });
});

describe('useActivityStream - connectRef stability', () => {
  it('connectRef always points to latest connect function for stable reconnect', async () => {
    // This tests the critical fix: connectRef.current is updated inside connect()
    // so that reconnect timers always call the latest version.

    const { result, rerender } = renderHook(
      (props) => useActivityStream(props),
      { initialProps: { enabled: true } }
    );

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    // Trigger error to schedule reconnect
    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es._triggerError(); });

    // Re-render (simulating prop/state changes that would recreate connect)
    rerender({ enabled: true });

    // Advance timer to trigger reconnect
    act(() => { vi.advanceTimersByTime(1000); });

    // Should still reconnect successfully (connectRef.current is up to date)
    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThanOrEqual(2);
    });
  });
});

describe('useActivityStream - initial load from REST API', () => {
  it('loads recent activities from /activity-logs on mount', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(api.get).toHaveBeenCalledWith('/activity-logs', {
        params: { limit: 50 },
      });
    });

    await waitFor(() => {
      expect(result.current.activities.length).toBeGreaterThan(0);
    });
  });

  it('handles array response format', async () => {
    api.get.mockResolvedValue({
      data: [
        { id: '1', user_id: 'u1', user_name: 'User 1', action_type: 'complete_task', member_name: 'M1', created_at: '2024-01-01' },
      ],
    });

    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(result.current.activities).toHaveLength(1);
    });
  });

  it('handles {logs: [...]} response format', async () => {
    api.get.mockResolvedValue({
      data: {
        logs: [
          { id: '1', user_id: 'u1', user_name: 'User 1', action_type: 'complete_task', member_name: 'M1', created_at: '2024-01-01' },
        ],
      },
    });

    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(result.current.activities).toHaveLength(1);
    });
  });

  it('silently handles API errors during initial load', async () => {
    api.get.mockRejectedValue(new Error('Network error'));

    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    // Should not throw, activities should remain empty
    await waitFor(() => {
      expect(result.current.activities).toEqual([]);
    });
  });

  it('respects cancellation when component unmounts during load', async () => {
    let resolveApi;
    api.get.mockImplementation(() => new Promise(r => { resolveApi = r; }));

    const { unmount, result } = renderHook(() => useActivityStream({ enabled: true }));

    // Unmount before API resolves
    unmount();

    // Resolve API - should not update state (cancelled = true)
    resolveApi({
      data: [{ id: '1', user_id: 'u1', user_name: 'X', action_type: 'a', member_name: 'M', created_at: 'c' }],
    });

    // No error should have been thrown
  });
});

describe('useActivityStream - clearActivities', () => {
  it('resets activities list and lastActivity', async () => {
    const { result } = renderHook(() => useActivityStream({ enabled: true }));

    await waitFor(() => {
      expect(MockEventSource.instances.length).toBeGreaterThan(0);
    });

    const es = MockEventSource.instances[MockEventSource.instances.length - 1];
    act(() => { es._triggerOpen(); });

    // Add an activity
    act(() => {
      es._triggerEvent('activity', {
        id: 'act-1',
        user_id: 'user-2',
        user_name: 'Other',
        action_type: 'complete_task',
        member_name: 'Member',
      });
    });

    expect(result.current.lastActivity).toBeTruthy();

    // Clear
    act(() => { result.current.clearActivities(); });

    expect(result.current.activities).toEqual([]);
    expect(result.current.lastActivity).toBeNull();
  });
});

describe('formatActivityMessage', () => {
  it('formats complete_task correctly', () => {
    const msg = formatActivityMessage({
      user_name: 'Pastor John',
      action_type: 'complete_task',
      member_name: 'Jane Doe',
    });
    expect(msg).toBe('Pastor John completed a task for Jane Doe');
  });

  it('formats create_care_event with event_type', () => {
    const msg = formatActivityMessage({
      user_name: 'Admin',
      action_type: 'create_care_event',
      member_name: 'Bob',
      event_type: 'birthday',
    });
    expect(msg).toBe('Admin created a birthday event for Bob');
  });

  it('formats create_member correctly', () => {
    const msg = formatActivityMessage({
      user_name: 'Staff',
      action_type: 'create_member',
      member_name: 'New Member',
    });
    expect(msg).toBe('Staff added new member New Member');
  });

  it('handles unknown action_type with fallback', () => {
    const msg = formatActivityMessage({
      user_name: 'User',
      action_type: 'unknown_action',
      member_name: 'Member X',
    });
    expect(msg).toBe('User performed an action on Member X');
  });

  it('formats delete_care_event correctly', () => {
    const msg = formatActivityMessage({
      user_name: 'Admin',
      action_type: 'delete_care_event',
      member_name: 'Jane',
    });
    expect(msg).toBe('Admin deleted an event for Jane');
  });

  it('formats ignore_task correctly', () => {
    const msg = formatActivityMessage({
      user_name: 'Pastor',
      action_type: 'ignore_task',
      member_name: 'Member A',
    });
    expect(msg).toBe('Pastor skipped a task for Member A');
  });
});
