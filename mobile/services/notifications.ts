/**
 * Push Notification Service
 *
 * Handles push notifications for task reminders using Expo Notifications
 */

import * as Notifications from 'expo-notifications';
import * as Device from 'expo-device';
import Constants from 'expo-constants';
import { Platform } from 'react-native';
import { router } from 'expo-router';

import { storage, STORAGE_KEYS } from '@/lib/storage';
import api from '@/services/api';

// ============================================================================
// CONFIGURATION
// ============================================================================

// Configure how notifications appear when app is in foreground
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowAlert: true,
    shouldPlaySound: true,
    shouldSetBadge: true,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

// ============================================================================
// TYPES
// ============================================================================

export interface PushNotificationData {
  type: 'task_reminder' | 'birthday' | 'care_event' | 'general';
  memberId?: string;
  eventId?: string;
  title?: string;
  body?: string;
}

export interface ScheduledNotification {
  id: string;
  type: PushNotificationData['type'];
  title: string;
  body: string;
  scheduledTime: Date;
  data?: Record<string, any>;
}

// ============================================================================
// PERMISSION HANDLING
// ============================================================================

/**
 * Request notification permissions
 * Returns the Expo push token if permissions granted
 */
export async function requestNotificationPermissions(): Promise<string | null> {
  // Check if we're on a physical device
  if (!Device.isDevice) {
    console.warn('Push notifications require a physical device');
    return null;
  }

  // Check existing permissions
  const { status: existingStatus } = await Notifications.getPermissionsAsync();
  let finalStatus = existingStatus;

  // Request permissions if not already granted
  if (existingStatus !== 'granted') {
    const { status } = await Notifications.requestPermissionsAsync();
    finalStatus = status;
  }

  if (finalStatus !== 'granted') {
    console.warn('Notification permissions not granted');
    return null;
  }

  // Get the push token
  try {
    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    const token = await Notifications.getExpoPushTokenAsync({
      projectId,
    });

    // Store the token
    storage.set(STORAGE_KEYS.NOTIFICATION_ENABLED, true);

    return token.data;
  } catch (error) {
    console.error('Failed to get push token:', error);
    return null;
  }
}

/**
 * Check if notifications are enabled
 */
export async function areNotificationsEnabled(): Promise<boolean> {
  const { status } = await Notifications.getPermissionsAsync();
  return status === 'granted';
}

/**
 * Get the current push token
 */
export async function getPushToken(): Promise<string | null> {
  try {
    const projectId = Constants.expoConfig?.extra?.eas?.projectId;
    const token = await Notifications.getExpoPushTokenAsync({
      projectId,
    });
    return token.data;
  } catch {
    return null;
  }
}

// ============================================================================
// LOCAL NOTIFICATIONS
// ============================================================================

/**
 * Schedule a local notification
 */
export async function scheduleLocalNotification(
  title: string,
  body: string,
  triggerSeconds: number,
  data?: PushNotificationData
): Promise<string> {
  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: data as any,
      sound: true,
    },
    trigger: {
      seconds: triggerSeconds,
      type: Notifications.SchedulableTriggerInputTypes.TIME_INTERVAL,
    },
  });

  return id;
}

/**
 * Schedule a notification for a specific date/time
 */
export async function scheduleNotificationAt(
  title: string,
  body: string,
  date: Date,
  data?: PushNotificationData
): Promise<string> {
  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: data as any,
      sound: true,
    },
    trigger: {
      date,
      type: Notifications.SchedulableTriggerInputTypes.DATE,
    },
  });

  return id;
}

/**
 * Schedule a daily notification at a specific time
 */
export async function scheduleDailyNotification(
  title: string,
  body: string,
  hour: number,
  minute: number,
  data?: PushNotificationData
): Promise<string> {
  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: data as any,
      sound: true,
    },
    trigger: {
      hour,
      minute,
      type: Notifications.SchedulableTriggerInputTypes.DAILY,
    },
  });

  return id;
}

/**
 * Show an immediate notification
 */
export async function showNotification(
  title: string,
  body: string,
  data?: PushNotificationData
): Promise<string> {
  const id = await Notifications.scheduleNotificationAsync({
    content: {
      title,
      body,
      data: data as any,
      sound: true,
    },
    trigger: null, // Immediate
  });

  return id;
}

/**
 * Cancel a scheduled notification
 */
export async function cancelNotification(notificationId: string): Promise<void> {
  await Notifications.cancelScheduledNotificationAsync(notificationId);
}

/**
 * Cancel all scheduled notifications
 */
export async function cancelAllNotifications(): Promise<void> {
  await Notifications.cancelAllScheduledNotificationsAsync();
}

/**
 * Get all scheduled notifications
 */
export async function getScheduledNotifications(): Promise<Notifications.NotificationRequest[]> {
  return Notifications.getAllScheduledNotificationsAsync();
}

// ============================================================================
// NOTIFICATION HANDLERS
// ============================================================================

/**
 * Handle notification response (when user taps notification)
 */
export function handleNotificationResponse(
  response: Notifications.NotificationResponse
): void {
  const rawData = response.notification.request.content.data;
  if (!rawData || typeof rawData !== 'object') return;

  const data = rawData as unknown as PushNotificationData;
  if (!data.type) return;

  // Navigate based on notification type
  switch (data.type) {
    case 'task_reminder':
    case 'birthday':
    case 'care_event':
      if (data.memberId) {
        router.push(`/member/${data.memberId}`);
      } else {
        router.push('/(tabs)/tasks');
      }
      break;
    case 'general':
    default:
      router.push('/(tabs)');
      break;
  }
}

/**
 * Set up notification listeners
 * Call this in your root layout
 */
export function setupNotificationListeners(): () => void {
  // Handle notification received while app is foregrounded
  const notificationListener = Notifications.addNotificationReceivedListener(
    (notification) => {
      console.log('Notification received:', notification);
    }
  );

  // Handle user tapping on notification
  const responseListener = Notifications.addNotificationResponseReceivedListener(
    (response) => {
      handleNotificationResponse(response);
    }
  );

  // Return cleanup function
  return () => {
    notificationListener.remove();
    responseListener.remove();
  };
}

// ============================================================================
// TASK REMINDER HELPERS
// ============================================================================

/**
 * Schedule a task reminder notification
 */
export async function scheduleTaskReminder(
  memberId: string,
  memberName: string,
  taskType: string,
  reminderDate: Date
): Promise<string> {
  const title = 'Task Reminder';
  const body = `Don't forget: ${taskType} for ${memberName}`;

  return scheduleNotificationAt(title, body, reminderDate, {
    type: 'task_reminder',
    memberId,
    title,
    body,
  });
}

/**
 * Schedule a birthday reminder notification
 */
export async function scheduleBirthdayReminder(
  memberId: string,
  memberName: string,
  birthdayDate: Date
): Promise<string> {
  // Schedule for 9 AM on the birthday
  const reminderDate = new Date(birthdayDate);
  reminderDate.setHours(9, 0, 0, 0);

  const title = 'Birthday Today!';
  const body = `${memberName} has a birthday today. Don't forget to wish them!`;

  return scheduleNotificationAt(title, body, reminderDate, {
    type: 'birthday',
    memberId,
    title,
    body,
  });
}

/**
 * Schedule daily task digest notification
 */
export async function scheduleDailyDigest(
  hour: number = 8,
  minute: number = 0
): Promise<string> {
  const title = 'Daily Task Summary';
  const body = 'Check your tasks for today';

  return scheduleDailyNotification(title, body, hour, minute, {
    type: 'general',
    title,
    body,
  });
}

// ============================================================================
// BADGE MANAGEMENT
// ============================================================================

/**
 * Set the app badge number
 */
export async function setBadgeCount(count: number): Promise<void> {
  await Notifications.setBadgeCountAsync(count);
}

/**
 * Clear the app badge
 */
export async function clearBadge(): Promise<void> {
  await Notifications.setBadgeCountAsync(0);
}

/**
 * Get current badge count
 */
export async function getBadgeCount(): Promise<number> {
  return Notifications.getBadgeCountAsync();
}

// ============================================================================
// ANDROID CHANNEL SETUP
// ============================================================================

/**
 * Set up Android notification channels
 * Call this during app initialization
 */
export async function setupAndroidChannels(): Promise<void> {
  if (Platform.OS !== 'android') return;

  // Default channel for task reminders
  await Notifications.setNotificationChannelAsync('task-reminders', {
    name: 'Task Reminders',
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
    lightColor: '#14b8a6',
    sound: 'default',
  });

  // Channel for birthday reminders
  await Notifications.setNotificationChannelAsync('birthdays', {
    name: 'Birthday Reminders',
    importance: Notifications.AndroidImportance.HIGH,
    vibrationPattern: [0, 250, 250, 250],
    lightColor: '#f59e0b',
    sound: 'default',
  });

  // Channel for general notifications
  await Notifications.setNotificationChannelAsync('general', {
    name: 'General',
    importance: Notifications.AndroidImportance.DEFAULT,
    sound: 'default',
  });
}

// ============================================================================
// BACKEND TOKEN REGISTRATION
// ============================================================================

/**
 * Register push token with backend for server-sent notifications
 * Call this after successful login and when token changes
 */
export async function registerPushToken(userId: string): Promise<boolean> {
  try {
    const token = await getPushToken();
    if (!token) {
      console.warn('No push token available to register');
      return false;
    }

    // Store token locally
    storage.set(STORAGE_KEYS.PUSH_TOKEN, token);

    // Send to backend
    await api.post('/users/push-token', {
      user_id: userId,
      token,
      platform: Platform.OS,
      device_id: Device.osInternalBuildId || Device.deviceName,
    });

    console.log('Push token registered successfully');
    return true;
  } catch (error) {
    console.error('Failed to register push token:', error);
    return false;
  }
}

/**
 * Unregister push token from backend (on logout)
 */
export async function unregisterPushToken(): Promise<void> {
  try {
    const token = storage.getString(STORAGE_KEYS.PUSH_TOKEN);
    if (token) {
      await api.delete('/users/push-token', {
        data: { token },
      });
      storage.remove(STORAGE_KEYS.PUSH_TOKEN);
    }
  } catch (error) {
    console.error('Failed to unregister push token:', error);
  }
}

/**
 * Initialize push notifications
 * Call this in root layout on mount
 */
export async function initializePushNotifications(userId?: string): Promise<void> {
  // Setup Android channels
  await setupAndroidChannels();

  // Request permissions if not granted
  const enabled = await areNotificationsEnabled();
  if (!enabled) {
    // Don't automatically request - let user opt-in via settings
    console.log('Push notifications not enabled');
    return;
  }

  // Register token with backend if user is logged in
  if (userId) {
    await registerPushToken(userId);
  }

  // Schedule daily digest if enabled
  const digestEnabled = storage.getBoolean('daily_digest_enabled');
  if (digestEnabled) {
    const notifications = await getScheduledNotifications();
    const hasDigest = notifications.some(
      (n) => (n.content.data as any)?.type === 'general'
    );
    if (!hasDigest) {
      await scheduleDailyDigest(8, 0); // 8 AM
    }
  }
}

export default {
  requestNotificationPermissions,
  areNotificationsEnabled,
  getPushToken,
  scheduleLocalNotification,
  scheduleNotificationAt,
  scheduleDailyNotification,
  showNotification,
  cancelNotification,
  cancelAllNotifications,
  getScheduledNotifications,
  setupNotificationListeners,
  scheduleTaskReminder,
  scheduleBirthdayReminder,
  scheduleDailyDigest,
  setBadgeCount,
  clearBadge,
  getBadgeCount,
  setupAndroidChannels,
  registerPushToken,
  unregisterPushToken,
  initializePushNotifications,
};
