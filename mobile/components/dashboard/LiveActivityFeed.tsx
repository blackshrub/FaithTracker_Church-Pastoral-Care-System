/**
 * LiveActivityFeed - Real-time activity stream component
 *
 * Displays live updates from team members using SSE.
 * Shows who completed what task, with animations for new items.
 */

import React, { useState, memo, useCallback } from 'react';
import { View, Text, ScrollView, Pressable } from 'react-native';
import Animated, {
  FadeIn,
  FadeInDown,
  FadeOut,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
  withSequence,
} from 'react-native-reanimated';
import {
  Activity,
  Wifi,
  WifiOff,
  Clock,
  Check,
  X,
  RotateCcw,
  Bell,
  StopCircle,
  Trash2,
  UserPlus,
  UserMinus,
  Edit,
  CalendarPlus,
  CalendarClock,
  CalendarX,
} from 'lucide-react-native';
import { useTranslation } from 'react-i18next';

import {
  useActivityStream,
  formatActivityMessage,
  getActivityActionColor,
} from '@/hooks/useActivityStream';
import { CachedImage } from '@/components/ui/CachedImage';
import { colors } from '@/constants/theme';
import type { ActivityEvent, ActivityActionType } from '@/types';

// ============================================================================
// CONSTANTS
// ============================================================================

const API_BASE_URL = process.env.EXPO_PUBLIC_API_URL || 'http://localhost:8001/api';

// Icon mapping
const ACTION_ICONS: Record<ActivityActionType, React.ComponentType<{ size: number; color: string; strokeWidth: number }>> = {
  complete_task: Check,
  ignore_task: X,
  unignore_task: RotateCcw,
  send_reminder: Bell,
  stop_schedule: StopCircle,
  clear_ignored: Trash2,
  create_member: UserPlus,
  update_member: Edit,
  delete_member: UserMinus,
  create_care_event: CalendarPlus,
  update_care_event: CalendarClock,
  delete_care_event: CalendarX,
};

// ============================================================================
// UTILITIES
// ============================================================================

function getInitials(name: string): string {
  if (!name) return '?';
  const parts = name.trim().split(' ');
  if (parts.length >= 2) {
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }
  return name.substring(0, 2).toUpperCase();
}

function formatRelativeTime(timestamp: string): string {
  const date = new Date(timestamp);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Baru saja';
  if (diffMins < 60) return `${diffMins} menit lalu`;
  if (diffHours < 24) return `${diffHours} jam lalu`;
  if (diffDays < 7) return `${diffDays} hari lalu`;
  // Use Indonesian locale for date formatting
  return date.toLocaleDateString('id-ID', { day: 'numeric', month: 'short' });
}

// ============================================================================
// ACTIVITY ITEM COMPONENT
// ============================================================================

interface ActivityItemProps {
  activity: ActivityEvent;
  isNew: boolean;
}

const ActivityItem = memo(function ActivityItem({ activity, isNew }: ActivityItemProps) {
  const { t } = useTranslation();
  const Icon = ACTION_ICONS[activity.action_type] || Activity;
  const { bg, text } = getActivityActionColor(activity.action_type);

  // Pulse animation for new items
  const opacity = useSharedValue(isNew ? 0.5 : 1);

  React.useEffect(() => {
    if (isNew) {
      opacity.value = withRepeat(
        withSequence(
          withTiming(1, { duration: 500 }),
          withTiming(0.5, { duration: 500 })
        ),
        3, // 3 pulses
        false
      );
      // After animation, set to full opacity
      setTimeout(() => {
        opacity.value = withTiming(1, { duration: 200 });
      }, 3000);
    }
  }, [isNew]);

  const animatedStyle = useAnimatedStyle(() => ({
    opacity: opacity.value,
  }));

  const photoUrl = activity.user_photo_url
    ? activity.user_photo_url.startsWith('http')
      ? activity.user_photo_url
      : `${API_BASE_URL}${activity.user_photo_url}`
    : undefined;

  return (
    <Animated.View
      entering={FadeInDown.duration(300)}
      style={isNew ? animatedStyle : undefined}
      className={`flex-row items-start gap-3 p-3 rounded-xl ${isNew ? 'bg-teal-50' : 'bg-white'}`}
    >
      {/* Avatar */}
      {photoUrl ? (
        <CachedImage
          source={photoUrl}
          className="w-8 h-8 rounded-full"
          isAvatar
          avatarIconSize={16}
        />
      ) : (
        <View className="w-8 h-8 rounded-full bg-teal-100 items-center justify-center">
          <Text className="text-teal-700 text-xs font-semibold">
            {getInitials(activity.user_name)}
          </Text>
        </View>
      )}

      {/* Content */}
      <View className="flex-1">
        <Text className="text-sm text-gray-900">
          <Text className="font-semibold">{activity.user_name}</Text>{' '}
          <Text className="text-gray-600">
            {t(`activity.${activity.action_type}`, {
              member: activity.member_name,
              defaultValue: formatActivityMessage(activity).replace(activity.user_name + ' ', ''),
            })}
          </Text>
        </Text>
        <Text className="text-xs text-gray-500 mt-0.5">
          {formatRelativeTime(activity.timestamp)}
        </Text>
      </View>

      {/* Icon */}
      <View className={`p-1.5 rounded-full ${bg}`}>
        <Icon size={14} color={text.replace('text-', '#').replace('-700', '').replace('-600', '')} strokeWidth={2.5} />
      </View>
    </Animated.View>
  );
});

// ============================================================================
// CONNECTION STATUS BADGE
// ============================================================================

interface ConnectionBadgeProps {
  isConnected: boolean;
}

const ConnectionBadge = memo(function ConnectionBadge({ isConnected }: ConnectionBadgeProps) {
  const { t } = useTranslation();

  return (
    <Animated.View
      entering={FadeIn.duration(200)}
      className={`flex-row items-center px-2 py-1 rounded-full border ${
        isConnected ? 'border-green-300 bg-green-50' : 'border-gray-300 bg-gray-50'
      }`}
    >
      {isConnected ? (
        <>
          <Wifi size={12} color={colors.status.success} strokeWidth={2} />
          <Text className="text-[10px] ml-1 text-green-700 font-medium">
            {t('live', 'Live')}
          </Text>
        </>
      ) : (
        <>
          <WifiOff size={12} color={colors.text.secondary} strokeWidth={2} />
          <Text className="text-[10px] ml-1 text-gray-500 font-medium">
            {t('connecting', 'Connecting...')}
          </Text>
        </>
      )}
    </Animated.View>
  );
});

// ============================================================================
// EMPTY STATE
// ============================================================================

const EmptyState = memo(function EmptyState() {
  const { t } = useTranslation();

  return (
    <Animated.View
      entering={FadeIn.duration(300)}
      className="items-center justify-center py-8"
    >
      <View className="w-12 h-12 rounded-full bg-gray-100 items-center justify-center mb-3">
        <Clock size={24} color={colors.text.tertiary} strokeWidth={1.5} />
      </View>
      <Text className="text-sm text-gray-500 text-center">
        {t('dashboard.no_recent_activity', 'No recent team activity')}
      </Text>
      <Text className="text-xs text-gray-400 text-center mt-1">
        {t('dashboard.activity_will_appear', 'Activity from teammates will appear here')}
      </Text>
    </Animated.View>
  );
});

// ============================================================================
// MAIN COMPONENT
// ============================================================================

interface LiveActivityFeedProps {
  maxItems?: number;
  maxHeight?: number;
  showHeader?: boolean;
}

export const LiveActivityFeed = memo(function LiveActivityFeed({
  maxItems = 10,
  maxHeight = 400,
  showHeader = true,
}: LiveActivityFeedProps) {
  const { t } = useTranslation();
  const [newActivityIds, setNewActivityIds] = useState<Set<string>>(new Set());

  const handleActivity = useCallback((activity: ActivityEvent) => {
    // Mark as new for animation
    setNewActivityIds((prev) => new Set([...prev, activity.id]));
    // Remove "new" status after animation
    setTimeout(() => {
      setNewActivityIds((prev) => {
        const next = new Set(prev);
        next.delete(activity.id);
        return next;
      });
    }, 3000);
  }, []);

  const { isConnected, activities, error } = useActivityStream({
    enabled: true,
    maxActivities: maxItems,
    onActivity: handleActivity,
  });

  // Don't render if there's an error
  if (error) {
    return null;
  }

  return (
    <Animated.View
      entering={FadeIn.duration(300)}
      className="bg-white rounded-2xl shadow-sm border border-gray-100 overflow-hidden"
    >
      {/* Header */}
      {showHeader && (
        <View className="flex-row items-center justify-between px-4 py-3 border-b border-gray-100">
          <View className="flex-row items-center gap-2">
            <Activity size={18} color={colors.primary.teal} strokeWidth={2} />
            <Text className="text-base font-semibold text-gray-900">
              {t('dashboard.live_activity', 'Team Activity')}
            </Text>
          </View>
          <ConnectionBadge isConnected={isConnected} />
        </View>
      )}

      {/* Content */}
      <View className="px-3 py-2">
        {activities.length === 0 ? (
          <EmptyState />
        ) : (
          <ScrollView
            style={{ maxHeight }}
            showsVerticalScrollIndicator={false}
            contentContainerStyle={{ gap: 8 }}
          >
            {activities.map((activity) => (
              <ActivityItem
                key={activity.id}
                activity={activity}
                isNew={newActivityIds.has(activity.id)}
              />
            ))}
          </ScrollView>
        )}
      </View>
    </Animated.View>
  );
});

export default LiveActivityFeed;
