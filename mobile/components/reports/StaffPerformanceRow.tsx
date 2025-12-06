/**
 * StaffPerformanceRow - Staff performance metrics row
 *
 * Displays staff member performance with:
 * - Avatar and name
 * - Rank badge (gold/silver/bronze for top 3)
 * - Tasks completed
 * - Members contacted
 * - Active days
 */

import React, { memo } from 'react';
import { View, Text, Image } from 'react-native';
import { User, CheckCircle, Users, Calendar, Trophy, Medal, Award } from 'lucide-react-native';
import Animated, { FadeInRight } from 'react-native-reanimated';

import { colors } from '@/constants/theme';

// ============================================================================
// TYPES
// ============================================================================

interface StaffPerformanceRowProps {
  rank: number;
  userName: string;
  userPhotoUrl?: string;
  tasksCompleted: number;
  membersContacted: number;
  activeDays: number;
  index: number;
  animated?: boolean;
}

// ============================================================================
// RANK BADGE
// ============================================================================

const RankBadge = memo(function RankBadge({ rank }: { rank: number }) {
  if (rank === 1) {
    return (
      <View className="w-8 h-8 rounded-full bg-amber-100 items-center justify-center">
        <Trophy size={16} color="#f59e0b" />
      </View>
    );
  }
  if (rank === 2) {
    return (
      <View className="w-8 h-8 rounded-full bg-gray-100 items-center justify-center">
        <Medal size={16} color="#6b7280" />
      </View>
    );
  }
  if (rank === 3) {
    return (
      <View className="w-8 h-8 rounded-full bg-orange-100 items-center justify-center">
        <Award size={16} color="#ea580c" />
      </View>
    );
  }

  return (
    <View className="w-8 h-8 rounded-full bg-gray-50 items-center justify-center">
      <Text className="text-sm font-semibold text-gray-500">#{rank}</Text>
    </View>
  );
});

// ============================================================================
// STAT ITEM
// ============================================================================

interface StatItemProps {
  icon: React.ReactNode;
  value: number;
  label: string;
}

const StatItem = memo(function StatItem({ icon, value, label }: StatItemProps) {
  return (
    <View className="items-center">
      <View className="flex-row items-center gap-1 mb-0.5">
        {icon}
        <Text className="text-sm font-semibold text-gray-900">{value}</Text>
      </View>
      <Text className="text-[10px] text-gray-400">{label}</Text>
    </View>
  );
});

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const StaffPerformanceRow = memo(function StaffPerformanceRow({
  rank,
  userName,
  userPhotoUrl,
  tasksCompleted,
  membersContacted,
  activeDays,
  index,
  animated = true,
}: StaffPerformanceRowProps) {
  const isTopPerformer = rank <= 3;

  const content = (
    <View
      className={`flex-row items-center p-4 bg-white rounded-xl ${
        isTopPerformer ? 'border border-amber-100' : ''
      }`}
    >
      {/* Rank badge */}
      <RankBadge rank={rank} />

      {/* Avatar */}
      <View className="ml-3">
        {userPhotoUrl ? (
          <Image
            source={{ uri: userPhotoUrl }}
            className="w-10 h-10 rounded-full"
          />
        ) : (
          <View className="w-10 h-10 rounded-full bg-gray-100 items-center justify-center">
            <User size={20} color="#9ca3af" />
          </View>
        )}
      </View>

      {/* Name */}
      <View className="flex-1 ml-3">
        <Text className="text-sm font-semibold text-gray-900" numberOfLines={1}>
          {userName}
        </Text>
        {isTopPerformer && (
          <Text className="text-[10px] text-amber-600 font-medium mt-0.5">
            {rank === 1 ? 'Top Performer' : rank === 2 ? 'Silver' : 'Bronze'}
          </Text>
        )}
      </View>

      {/* Stats */}
      <View className="flex-row gap-4">
        <StatItem
          icon={<CheckCircle size={12} color={colors.status.success} />}
          value={tasksCompleted}
          label="Tasks"
        />
        <StatItem
          icon={<Users size={12} color={colors.primary[500]} />}
          value={membersContacted}
          label="Members"
        />
        <StatItem
          icon={<Calendar size={12} color={colors.secondary.amber} />}
          value={activeDays}
          label="Days"
        />
      </View>
    </View>
  );

  if (animated) {
    return (
      <Animated.View entering={FadeInRight.duration(300).delay(index * 80)}>
        {content}
      </Animated.View>
    );
  }

  return content;
});

export default StaffPerformanceRow;
