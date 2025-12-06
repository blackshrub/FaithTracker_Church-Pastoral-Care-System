/**
 * Skeleton Loading Components
 *
 * Production-grade shimmer loading states for better perceived performance
 * Uses NativeWind + Reanimated for smooth animations
 */

import React, { memo, useEffect } from 'react';
import { View, ViewStyle } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withRepeat,
  withTiming,
  interpolate,
  Easing,
} from 'react-native-reanimated';
import { LinearGradient } from 'expo-linear-gradient';

// ============================================================================
// BASE SKELETON
// ============================================================================

interface SkeletonProps {
  width?: number | string;
  height?: number | string;
  borderRadius?: number;
  className?: string;
  style?: ViewStyle;
}

export const Skeleton = memo(function Skeleton({
  width = '100%',
  height = 16,
  borderRadius = 8,
  className = '',
  style,
}: SkeletonProps) {
  const shimmer = useSharedValue(0);

  useEffect(() => {
    shimmer.value = withRepeat(
      withTiming(1, { duration: 1500, easing: Easing.inOut(Easing.ease) }),
      -1,
      false
    );
  }, [shimmer]);

  const animatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: interpolate(shimmer.value, [0, 1], [-200, 200]) }],
  }));

  return (
    <View
      className={`bg-gray-200 dark:bg-slate-700 overflow-hidden ${className}`}
      style={[
        {
          width: width as any,
          height: height as any,
          borderRadius,
        },
        style,
      ]}
    >
      <Animated.View style={[{ flex: 1, width: 200 }, animatedStyle]}>
        <LinearGradient
          colors={['transparent', 'rgba(255,255,255,0.3)', 'transparent']}
          start={{ x: 0, y: 0.5 }}
          end={{ x: 1, y: 0.5 }}
          style={{ flex: 1 }}
        />
      </Animated.View>
    </View>
  );
});

// ============================================================================
// PRESET SKELETONS
// ============================================================================

/**
 * Skeleton for member list item
 */
export const MemberCardSkeleton = memo(function MemberCardSkeleton() {
  return (
    <View className="flex-row items-center bg-white rounded-xl p-4 mb-3 shadow-sm">
      {/* Avatar */}
      <Skeleton width={48} height={48} borderRadius={24} className="mr-4" />

      {/* Content */}
      <View className="flex-1">
        <Skeleton width="60%" height={18} borderRadius={4} className="mb-2" />
        <Skeleton width="40%" height={14} borderRadius={4} className="mb-2" />
        <Skeleton width="30%" height={12} borderRadius={4} />
      </View>

      {/* Arrow placeholder */}
      <Skeleton width={20} height={20} borderRadius={4} />
    </View>
  );
});

/**
 * Skeleton for task card
 */
export const TaskCardSkeleton = memo(function TaskCardSkeleton() {
  return (
    <View className="flex-row items-center bg-white rounded-xl p-4 shadow-sm mb-3">
      {/* Icon */}
      <Skeleton width={40} height={40} borderRadius={8} className="mr-3" />

      {/* Content */}
      <View className="flex-1">
        <Skeleton width="70%" height={18} borderRadius={4} className="mb-2" />
        <Skeleton width="50%" height={14} borderRadius={4} />
      </View>

      {/* Action button */}
      <Skeleton width={40} height={40} borderRadius={8} />
    </View>
  );
});

/**
 * Skeleton for dashboard stats
 */
export const StatsSkeleton = memo(function StatsSkeleton() {
  return (
    <View className="flex-row bg-white/10 rounded-xl p-4">
      {[1, 2, 3].map((i) => (
        <React.Fragment key={i}>
          <View className="flex-1 items-center">
            <Skeleton width={48} height={32} borderRadius={4} className="mb-2 bg-white/20" />
            <Skeleton width={64} height={12} borderRadius={4} className="bg-white/20" />
          </View>
          {i < 3 && <View className="w-px bg-white/20 mx-2" />}
        </React.Fragment>
      ))}
    </View>
  );
});

/**
 * Skeleton for member detail header
 */
export const MemberDetailSkeleton = memo(function MemberDetailSkeleton() {
  return (
    <View className="items-center px-6 py-8">
      {/* Avatar */}
      <Skeleton width={96} height={96} borderRadius={48} className="mb-4" />

      {/* Name */}
      <Skeleton width={200} height={28} borderRadius={4} className="mb-2" />

      {/* Phone */}
      <Skeleton width={140} height={16} borderRadius={4} className="mb-4" />

      {/* Badges */}
      <View className="flex-row gap-2">
        <Skeleton width={80} height={28} borderRadius={14} />
        <Skeleton width={100} height={28} borderRadius={14} />
      </View>
    </View>
  );
});

/**
 * Skeleton for timeline event
 */
export const TimelineEventSkeleton = memo(function TimelineEventSkeleton() {
  return (
    <View className="bg-white rounded-xl p-4 mb-3 shadow-sm">
      {/* Header */}
      <View className="flex-row items-center mb-3">
        <Skeleton width={32} height={32} borderRadius={8} className="mr-3" />
        <View className="flex-1">
          <Skeleton width="60%" height={16} borderRadius={4} className="mb-1" />
          <Skeleton width="40%" height={12} borderRadius={4} />
        </View>
        <Skeleton width={60} height={24} borderRadius={12} />
      </View>

      {/* Description */}
      <Skeleton width="100%" height={14} borderRadius={4} className="mb-2" />
      <Skeleton width="80%" height={14} borderRadius={4} />
    </View>
  );
});

/**
 * Skeleton list wrapper - renders multiple skeletons
 */
interface SkeletonListProps {
  count?: number;
  SkeletonComponent: React.ComponentType;
}

export const SkeletonList = memo(function SkeletonList({
  count = 5,
  SkeletonComponent,
}: SkeletonListProps) {
  return (
    <>
      {Array.from({ length: count }).map((_, index) => (
        <SkeletonComponent key={index} />
      ))}
    </>
  );
});

/**
 * Full screen skeleton for members list
 */
export const MembersListSkeleton = memo(function MembersListSkeleton() {
  return (
    <View className="px-6 pt-4">
      <SkeletonList count={8} SkeletonComponent={MemberCardSkeleton} />
    </View>
  );
});

/**
 * Full screen skeleton for tasks list
 */
export const TasksListSkeleton = memo(function TasksListSkeleton() {
  return (
    <View className="px-6 pt-4">
      <SkeletonList count={6} SkeletonComponent={TaskCardSkeleton} />
    </View>
  );
});

/**
 * Full screen skeleton for dashboard
 */
export const DashboardSkeleton = memo(function DashboardSkeleton() {
  return (
    <View className="px-6 pt-6">
      {/* Stats */}
      <StatsSkeleton />

      {/* Tasks section */}
      <View className="mt-8">
        <Skeleton width={140} height={24} borderRadius={4} className="mb-4" />
        <SkeletonList count={4} SkeletonComponent={TaskCardSkeleton} />
      </View>
    </View>
  );
});

export default {
  Skeleton,
  MemberCardSkeleton,
  TaskCardSkeleton,
  StatsSkeleton,
  MemberDetailSkeleton,
  TimelineEventSkeleton,
  SkeletonList,
  MembersListSkeleton,
  TasksListSkeleton,
  DashboardSkeleton,
};
