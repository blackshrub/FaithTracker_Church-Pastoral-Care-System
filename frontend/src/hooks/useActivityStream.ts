/**
 * useActivityStream - Real-time activity updates via Server-Sent Events
 *
 * Connects to the SSE endpoint and provides real-time activity notifications.
 * Automatically reconnects on connection loss.
 *
 * Features:
 * - Auto-reconnect with exponential backoff
 * - Connection state tracking
 * - Activity event callbacks
 * - Automatic cleanup on unmount
 *
 * Usage:
 * const { isConnected, lastActivity, activities } = useActivityStream({
 *   onActivity: (activity) => {
 *     // Handle new activity
 *     toast(`${activity.user_name} completed a task`);
 *   }
 * });
 */

import { useState, useEffect, useCallback, useRef } from 'react';

import { useAuth } from '@/context/AuthContext';
import api from '@/lib/api';
import type { ActivityLog } from '@/types';

// Note: VITE_BACKEND_URL already points to the API subdomain (e.g., https://api.pastoral.gkbj.org)
// No additional /api prefix needed - routes are at the root level
const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || '';
const MAX_RECONNECT_DELAY = 30000; // 30 seconds max
const INITIAL_RECONNECT_DELAY = 1000; // 1 second initial

export interface Activity {
  id: string;
  campus_id: string;
  user_id: string;
  user_name: string;
  user_photo_url?: string | null;
  action_type: string;
  member_id?: string | null;
  member_name?: string | null;
  care_event_id?: string | null;
  event_type?: string | null;
  notes?: string | null;
  timestamp: string;
}

export interface UseActivityStreamOptions {
  onActivity?: (activity: Activity) => void;
  enabled?: boolean;
  maxActivities?: number;
}

export interface UseActivityStreamReturn {
  isConnected: boolean;
  lastActivity: Activity | null;
  activities: Activity[];
  error: string | null;
  connect: () => void;
  disconnect: () => void;
  clearActivities: () => void;
}

/**
 * Hook for real-time activity stream via SSE
 */
export function useActivityStream({ onActivity, enabled = true, maxActivities = 50 }: UseActivityStreamOptions = {}): UseActivityStreamReturn {
  const { token, user } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [lastActivity, setLastActivity] = useState<Activity | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [error, setError] = useState<string | null>(null);

  const eventSourceRef = useRef<EventSource | null>(null);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY);
  const connectRef = useRef<(() => void) | null>(null);

  /**
   * Connect to SSE endpoint
   */
  const connect = useCallback(() => {
    if (!token || !enabled) return;

    // Keep ref in sync so reconnect timer always calls latest version
    connectRef.current = connect;

    // Close existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Clear any pending reconnect
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
    }

    try {
      // Note: EventSource doesn't support custom headers, so we use query param for auth
      const url = `${BACKEND_URL}/stream/activity?token=${encodeURIComponent(token)}`;
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY;
      };

      eventSource.onerror = () => {
        setIsConnected(false);
        eventSource.close();

        // Schedule reconnect with exponential backoff using stable ref
        const delay = reconnectDelayRef.current;
        reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY);
        reconnectTimeoutRef.current = setTimeout(() => connectRef.current?.(), delay);
      };

      // Handle heartbeat (keep-alive)
      eventSource.addEventListener('heartbeat', () => {
        // Connection is alive
      });

      // Handle activity events
      eventSource.addEventListener('activity', (e: MessageEvent) => {
        const activity: Activity = JSON.parse(e.data);

        // Skip own activities
        if (activity.user_id === user?.id) return;

        setLastActivity(activity);
        setActivities((prev) => {
          const updated = [activity, ...prev].slice(0, maxActivities);
          return updated;
        });

        // Call callback if provided
        if (onActivity) {
          onActivity(activity);
        }
      });
    } catch (err) {
      setError((err as Error).message);
    }
  }, [token, enabled, user?.id, onActivity, maxActivities]);

  /**
   * Disconnect from SSE endpoint
   */
  const disconnect = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
      eventSourceRef.current = null;
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

    const load = async () => {
      if (!enabled || !token) return;
      try {
        const response = await api.get('/activity-logs', { params: { limit: maxActivities } });
        if (cancelled) return;
        // API returns array directly, not {logs: [...]}
        const logs: ActivityLog[] = Array.isArray(response.data) ? response.data : (response.data?.logs || []);
        // Show ALL recent activities (including own) for initial display
        // Only real-time SSE filters out own activities
        const transformed: Activity[] = logs.map(log => ({
          id: log.id,
          campus_id: log.campus_id,
          user_id: log.user_id,
          user_name: log.user_name,
          user_photo_url: log.user_photo_url,
          action_type: log.action_type,
          member_id: log.member_id,
          member_name: log.member_name,
          care_event_id: log.care_event_id,
          event_type: log.event_type,
          notes: log.notes,
          timestamp: log.created_at
        }));
        setActivities(transformed);
      } catch (err) {
        // Silently fail - activity feed is optional
      }
    };

    load();
    return () => { cancelled = true; };
  }, [enabled, token, maxActivities]);

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    if (enabled && token) {
      connect();
    }
    return () => disconnect();
  }, [connect, disconnect, enabled, token]);

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

/**
 * Format activity for display
 */
export function formatActivityMessage(activity: Activity): string {
  const { user_name, action_type, member_name, event_type } = activity;

  const actionMessages: Record<string, string> = {
    // Correct action types matching backend ActivityActionType enum
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

export default useActivityStream;
