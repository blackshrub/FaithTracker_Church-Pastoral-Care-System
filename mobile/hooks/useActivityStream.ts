/**
 * useActivityStream - Real-time activity updates via Server-Sent Events
 *
 * Connects to the SSE endpoint and provides real-time activity notifications.
 * Uses a fetch-based implementation compatible with React Native.
 *
 * Features:
 * - Auto-reconnect with exponential backoff
 * - Connection state tracking
 * - Activity event callbacks
 * - Automatic cleanup on unmount
 * - Loads recent activities on mount
 *
 * Usage:
 * const { isConnected, lastActivity, activities } = useActivityStream({
 *   onActivity: (activity) => {
 *     // Handle new activity
 *     Toast.show({ text1: `${activity.user_name} completed a task` });
 *   }
 * });
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { AppState, AppStateStatus } from 'react-native';

import { useAuthStore } from '@/stores/auth';
import { API_ENDPOINTS } from '@/constants/api';
import api from '@/services/api';
import type { ActivityEvent, ActivityActionType } from '@/types';

// ============================================================================
// CONSTANTS
// ============================================================================

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8001/api';
const MAX_RECONNECT_DELAY = 30000; // 30 seconds max
const INITIAL_RECONNECT_DELAY = 1000; // 1 second initial
const MAX_ACTIVITIES = 50;

// ============================================================================
// TYPES
// ============================================================================

interface UseActivityStreamOptions {
  onActivity?: (activity: ActivityEvent) => void;
  enabled?: boolean;
  maxActivities?: number;
}

interface UseActivityStreamReturn {
  isConnected: boolean;
  lastActivity: ActivityEvent | null;
  activities: ActivityEvent[];
  error: string | null;
  connect: () => void;
  disconnect: () => void;
  clearActivities: () => void;
}

// ============================================================================
// SSE PARSER
// ============================================================================

/**
 * Parse SSE event from raw text chunk
 */
function parseSSEEvent(chunk: string): { event?: string; data?: string } | null {
  const lines = chunk.split('\n');
  let event: string | undefined;
  let data: string | undefined;

  for (const line of lines) {
    if (line.startsWith('event:')) {
      event = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      data = line.slice(5).trim();
    }
  }

  if (event || data) {
    return { event, data };
  }
  return null;
}

// ============================================================================
// HOOK
// ============================================================================

export function useActivityStream({
  onActivity,
  enabled = true,
  maxActivities = MAX_ACTIVITIES,
}: UseActivityStreamOptions = {}): UseActivityStreamReturn {
  const { token, user } = useAuthStore();

  const [isConnected, setIsConnected] = useState(false);
  const [lastActivity, setLastActivity] = useState<ActivityEvent | null>(null);
  const [activities, setActivities] = useState<ActivityEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  const abortControllerRef = useRef<AbortController | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY);
  const onActivityRef = useRef(onActivity);

  // Keep callback ref updated
  useEffect(() => {
    onActivityRef.current = onActivity;
  }, [onActivity]);

  /**
   * Connect to SSE endpoint using fetch with streaming
   */
  const connect = useCallback(async () => {
    if (!token || !enabled) return;

    // Close existing connection
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    const abortController = new AbortController();
    abortControllerRef.current = abortController;

    try {
      const url = `${API_BASE_URL}${API_ENDPOINTS.ACTIVITY.STREAM}?token=${encodeURIComponent(token)}`;

      const response = await fetch(url, {
        method: 'GET',
        headers: {
          Accept: 'text/event-stream',
          'Cache-Control': 'no-cache',
        },
        signal: abortController.signal,
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }

      if (!response.body) {
        throw new Error('No response body');
      }

      setIsConnected(true);
      setError(null);
      reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();

        if (done) {
          break;
        }

        buffer += decoder.decode(value, { stream: true });

        // Process complete events (separated by double newlines)
        const events = buffer.split('\n\n');
        buffer = events.pop() || ''; // Keep incomplete event in buffer

        for (const eventText of events) {
          if (!eventText.trim()) continue;

          const parsed = parseSSEEvent(eventText);
          if (!parsed) continue;

          if (parsed.event === 'heartbeat') {
            // Connection is alive
            continue;
          }

          if (parsed.event === 'activity' && parsed.data) {
            try {
              const activity = JSON.parse(parsed.data) as ActivityEvent;

              // Skip own activities
              if (activity.user_id === user?.id) continue;

              setLastActivity(activity);
              setActivities((prev) => {
                const updated = [activity, ...prev].slice(0, maxActivities);
                return updated;
              });

              // Call callback if provided
              onActivityRef.current?.(activity);
            } catch (e) {
              console.warn('Failed to parse activity:', e);
            }
          }
        }
      }
    } catch (err: unknown) {
      // Ignore abort errors (intentional disconnection)
      if (err instanceof Error && err.name === 'AbortError') {
        return;
      }

      setIsConnected(false);
      setError(err instanceof Error ? err.message : 'Connection failed');

      // Schedule reconnect with exponential backoff
      const delay = reconnectDelayRef.current;
      reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY);
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, delay);
    }
  }, [token, enabled, user?.id, maxActivities]);

  /**
   * Disconnect from SSE endpoint
   */
  const disconnect = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    setIsConnected(false);
  }, []);

  /**
   * Clear activity history
   */
  const clearActivities = useCallback(() => {
    setActivities([]);
    setLastActivity(null);
  }, []);

  // Load recent activities when component mounts and token is available
  useEffect(() => {
    let cancelled = false;

    const loadRecentActivities = async () => {
      if (!enabled || !token) return;

      try {
        const response = await api.get(API_ENDPOINTS.ACTIVITY.LOGS, {
          params: { limit: maxActivities },
        });

        if (cancelled) return;

        // Transform API response to ActivityEvent format
        const logs = Array.isArray(response.data)
          ? response.data
          : response.data?.logs || [];

        const transformed: ActivityEvent[] = logs.map((log: Record<string, unknown>) => ({
          id: log.id as string,
          campus_id: log.campus_id as string,
          user_id: log.user_id as string,
          user_name: log.user_name as string,
          user_photo_url: log.user_photo_url as string | undefined,
          action_type: log.action_type as ActivityActionType,
          member_id: log.member_id as string | undefined,
          member_name: log.member_name as string | undefined,
          care_event_id: log.care_event_id as string | undefined,
          event_type: log.event_type as string | undefined,
          notes: log.notes as string | undefined,
          timestamp: (log.created_at as string) || (log.timestamp as string),
        }));

        setActivities(transformed);
      } catch (err) {
        // Silently fail - activity feed is optional
        console.warn('Failed to load recent activities:', err);
      }
    };

    loadRecentActivities();
    return () => {
      cancelled = true;
    };
  }, [enabled, token, maxActivities]);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    if (enabled && token) {
      connect();
    }
    return () => disconnect();
  }, [connect, disconnect, enabled, token]);

  // Handle app state changes (reconnect when coming to foreground)
  useEffect(() => {
    const handleAppStateChange = (nextAppState: AppStateStatus) => {
      if (nextAppState === 'active' && enabled && token && !isConnected) {
        connect();
      } else if (nextAppState === 'background') {
        disconnect();
      }
    };

    const subscription = AppState.addEventListener('change', handleAppStateChange);
    return () => subscription.remove();
  }, [connect, disconnect, enabled, token, isConnected]);

  return {
    isConnected,
    lastActivity,
    activities,
    error,
    connect,
    disconnect,
    clearActivities,
  };
}

// ============================================================================
// UTILITIES
// ============================================================================

/**
 * Format activity for display
 */
export function formatActivityMessage(activity: ActivityEvent): string {
  const { user_name, action_type, member_name, event_type } = activity;

  const actionMessages: Record<ActivityActionType, string> = {
    complete_task: `completed a task for ${member_name}`,
    ignore_task: `skipped a task for ${member_name}`,
    unignore_task: `restored a task for ${member_name}`,
    send_reminder: `sent a reminder for ${member_name}`,
    stop_schedule: `stopped a schedule for ${member_name}`,
    clear_ignored: `cleared ignored tasks for ${member_name}`,
    create_member: `added new member ${member_name}`,
    update_member: `updated ${member_name}'s profile`,
    delete_member: `deleted ${member_name}`,
    create_care_event: `created a ${event_type || 'care'} event for ${member_name}`,
    update_care_event: `updated an event for ${member_name}`,
    delete_care_event: `deleted an event for ${member_name}`,
  };

  const message = actionMessages[action_type] || `performed an action on ${member_name}`;
  return `${user_name} ${message}`;
}

/**
 * Get action type icon name (Lucide icon names)
 */
export function getActivityActionIcon(actionType: ActivityActionType): string {
  const icons: Record<ActivityActionType, string> = {
    complete_task: 'Check',
    ignore_task: 'X',
    unignore_task: 'RotateCcw',
    send_reminder: 'Bell',
    stop_schedule: 'StopCircle',
    clear_ignored: 'Trash2',
    create_member: 'UserPlus',
    update_member: 'Edit',
    delete_member: 'UserMinus',
    create_care_event: 'CalendarPlus',
    update_care_event: 'CalendarClock',
    delete_care_event: 'CalendarX',
  };
  return icons[actionType] || 'Activity';
}

/**
 * Get action type color classes
 */
export function getActivityActionColor(actionType: ActivityActionType): {
  bg: string;
  text: string;
} {
  const colors: Record<ActivityActionType, { bg: string; text: string }> = {
    complete_task: { bg: 'bg-green-100', text: 'text-green-700' },
    ignore_task: { bg: 'bg-gray-100', text: 'text-gray-600' },
    unignore_task: { bg: 'bg-blue-100', text: 'text-blue-700' },
    send_reminder: { bg: 'bg-blue-100', text: 'text-blue-700' },
    stop_schedule: { bg: 'bg-amber-100', text: 'text-amber-700' },
    clear_ignored: { bg: 'bg-gray-100', text: 'text-gray-600' },
    create_member: { bg: 'bg-teal-100', text: 'text-teal-700' },
    update_member: { bg: 'bg-amber-100', text: 'text-amber-700' },
    delete_member: { bg: 'bg-red-100', text: 'text-red-700' },
    create_care_event: { bg: 'bg-blue-100', text: 'text-blue-700' },
    update_care_event: { bg: 'bg-amber-100', text: 'text-amber-700' },
    delete_care_event: { bg: 'bg-red-100', text: 'text-red-700' },
  };
  return colors[actionType] || { bg: 'bg-gray-100', text: 'text-gray-600' };
}

export default useActivityStream;
