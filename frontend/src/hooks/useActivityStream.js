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

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';
const MAX_RECONNECT_DELAY = 30000; // 30 seconds max
const INITIAL_RECONNECT_DELAY = 1000; // 1 second initial

/**
 * Hook for real-time activity stream via SSE
 */
export function useActivityStream({ onActivity, enabled = true, maxActivities = 50 } = {}) {
  const { token, user } = useAuth();
  const [isConnected, setIsConnected] = useState(false);
  const [lastActivity, setLastActivity] = useState(null);
  const [activities, setActivities] = useState([]);
  const [error, setError] = useState(null);

  const eventSourceRef = useRef(null);
  const reconnectTimeoutRef = useRef(null);
  const reconnectDelayRef = useRef(INITIAL_RECONNECT_DELAY);

  /**
   * Connect to SSE endpoint
   */
  const connect = useCallback(() => {
    if (!token || !enabled) return;

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
      // In production, consider using a fetch-based polyfill for SSE with headers
      const url = `${API_BASE_URL}/stream/activity?token=${encodeURIComponent(token)}`;
      const eventSource = new EventSource(url);
      eventSourceRef.current = eventSource;

      eventSource.onopen = () => {
        setIsConnected(true);
        setError(null);
        reconnectDelayRef.current = INITIAL_RECONNECT_DELAY; // Reset delay on successful connection
        console.log('[SSE] Connected to activity stream');
      };

      eventSource.onerror = (e) => {
        console.error('[SSE] Connection error:', e);
        setIsConnected(false);
        eventSource.close();

        // Schedule reconnect with exponential backoff
        const delay = reconnectDelayRef.current;
        reconnectDelayRef.current = Math.min(delay * 2, MAX_RECONNECT_DELAY);

        console.log(`[SSE] Reconnecting in ${delay}ms...`);
        reconnectTimeoutRef.current = setTimeout(connect, delay);
      };

      // Handle connected event
      eventSource.addEventListener('connected', (e) => {
        const data = JSON.parse(e.data);
        console.log('[SSE] Connected event:', data);
      });

      // Handle heartbeat
      eventSource.addEventListener('heartbeat', (e) => {
        // Heartbeat received, connection is alive
        console.debug('[SSE] Heartbeat received');
      });

      // Handle activity events
      eventSource.addEventListener('activity', (e) => {
        const activity = JSON.parse(e.data);

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
      console.error('[SSE] Failed to create EventSource:', err);
      setError(err.message);
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

  // Connect on mount, disconnect on unmount
  useEffect(() => {
    if (enabled && token) {
      connect();
    }

    return () => {
      disconnect();
    };
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
export function formatActivityMessage(activity) {
  const { user_name, action_type, member_name, event_type } = activity;

  const actionMessages = {
    complete: `completed a task for ${member_name}`,
    ignore: `skipped a task for ${member_name}`,
    create_event: `created a ${event_type || 'care'} event for ${member_name}`,
    update_event: `updated an event for ${member_name}`,
    delete_event: `deleted an event for ${member_name}`,
    create_member: `added new member ${member_name}`,
    update_member: `updated ${member_name}'s profile`,
    delete_member: `deleted ${member_name}`,
    complete_stage: `completed a grief stage for ${member_name}`,
    ignore_stage: `skipped a grief stage for ${member_name}`,
    undo_stage: `undid a grief stage for ${member_name}`,
    send_reminder: `sent a reminder for ${member_name}`,
    distribute_aid: `distributed financial aid to ${member_name}`,
  };

  const message = actionMessages[action_type] || `performed an action on ${member_name}`;
  return `${user_name} ${message}`;
}

export default useActivityStream;
