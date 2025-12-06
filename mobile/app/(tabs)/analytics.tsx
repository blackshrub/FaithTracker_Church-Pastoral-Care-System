/**
 * Analytics Screen
 *
 * Dashboard with charts showing:
 * - Member demographics (age, gender, category)
 * - Engagement status distribution
 * - Care events by type
 * - Financial aid summary
 */

import React, { useState, memo, useCallback } from 'react';
import { View, Text, ScrollView, RefreshControl, Pressable } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import Animated, { FadeInDown, FadeIn } from 'react-native-reanimated';
import {
  BarChart3,
  Users,
  Heart,
  DollarSign,
  TrendingUp,
  Calendar,
} from 'lucide-react-native';
import { useTranslation } from 'react-i18next';

import { useAnalytics, TimeRange } from '@/hooks/useAnalytics';
import { PieChart, BarChart } from '@/components/charts';
import { PremiumCard } from '@/components/ui/PremiumCard';
import { Skeleton } from '@/components/ui/Skeleton';
import { colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';

// ============================================================================
// CONSTANTS
// ============================================================================

const TIME_RANGES: { value: TimeRange; label: string }[] = [
  { value: 'all', label: 'All Time' },
  { value: 'year', label: 'This Year' },
  { value: '6months', label: '6 Months' },
  { value: '3months', label: '3 Months' },
  { value: 'month', label: 'This Month' },
];

const ENGAGEMENT_COLORS = {
  active: colors.status.success,
  at_risk: colors.status.warning,
  disconnected: colors.status.error,
};

const EVENT_TYPE_COLORS: Record<string, string> = {
  birthday: '#F59E0B',
  grief_loss: '#6366F1',
  accident_illness: '#EF4444',
  financial_aid: '#10B981',
  regular_contact: '#3B82F6',
  childbirth: '#EC4899',
  new_house: '#8B5CF6',
};

// ============================================================================
// TIME RANGE SELECTOR
// ============================================================================

interface TimeRangeSelectorProps {
  value: TimeRange;
  onChange: (value: TimeRange) => void;
}

const TimeRangeSelector = memo(function TimeRangeSelector({
  value,
  onChange,
}: TimeRangeSelectorProps) {
  return (
    <ScrollView
      horizontal
      showsHorizontalScrollIndicator={false}
      className="mb-4"
      contentContainerStyle={{ paddingHorizontal: 16, gap: 8 }}
    >
      {TIME_RANGES.map((range) => (
        <Pressable
          key={range.value}
          onPress={() => {
            haptics.tap();
            onChange(range.value);
          }}
          className={`px-4 py-2 rounded-full ${
            value === range.value
              ? 'bg-teal-500'
              : 'bg-gray-100'
          }`}
        >
          <Text
            className={`text-sm font-medium ${
              value === range.value ? 'text-white' : 'text-gray-600'
            }`}
          >
            {range.label}
          </Text>
        </Pressable>
      ))}
    </ScrollView>
  );
});

// ============================================================================
// STAT CARD
// ============================================================================

interface StatCardProps {
  title: string;
  value: string | number;
  subtitle?: string;
  icon: React.ReactNode;
  color: string;
  index: number;
}

const StatCard = memo(function StatCard({
  title,
  value,
  subtitle,
  icon,
  color,
  index,
}: StatCardProps) {
  return (
    <Animated.View
      entering={FadeInDown.duration(300).delay(index * 100)}
      className="flex-1 min-w-[140px]"
    >
      <PremiumCard className="p-4">
        <View
          className="w-10 h-10 rounded-full items-center justify-center mb-3"
          style={{ backgroundColor: `${color}20` }}
        >
          {icon}
        </View>
        <Text className="text-2xl font-bold text-gray-900">
          {typeof value === 'number' ? value.toLocaleString() : value}
        </Text>
        <Text className="text-sm text-gray-500 mt-1">{title}</Text>
        {subtitle && (
          <Text className="text-xs text-gray-400 mt-0.5">{subtitle}</Text>
        )}
      </PremiumCard>
    </Animated.View>
  );
});

// ============================================================================
// SECTION HEADER
// ============================================================================

interface SectionHeaderProps {
  title: string;
  icon: React.ReactNode;
}

const SectionHeader = memo(function SectionHeader({ title, icon }: SectionHeaderProps) {
  return (
    <View className="flex-row items-center gap-2 mb-3 px-4">
      {icon}
      <Text className="text-lg font-semibold text-gray-900">{title}</Text>
    </View>
  );
});

// ============================================================================
// LOADING SKELETON
// ============================================================================

const AnalyticsSkeleton = memo(function AnalyticsSkeleton() {
  return (
    <View className="flex-1 px-4">
      {/* Stats row skeleton */}
      <View className="flex-row gap-3 mb-6">
        <View className="flex-1">
          <Skeleton className="h-32 rounded-2xl" />
        </View>
        <View className="flex-1">
          <Skeleton className="h-32 rounded-2xl" />
        </View>
      </View>

      {/* Chart skeleton */}
      <Skeleton className="h-64 rounded-2xl mb-6" />
      <Skeleton className="h-48 rounded-2xl mb-6" />
      <Skeleton className="h-48 rounded-2xl" />
    </View>
  );
});

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export default function AnalyticsScreen() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const [timeRange, setTimeRange] = useState<TimeRange>('all');

  const { data, isLoading, isRefetching, refetch } = useAnalytics({
    timeRange,
    enabled: true,
  });

  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  // Prepare chart data
  const engagementData = data?.member_stats
    ? [
        { label: 'Active', value: data.member_stats.active, color: ENGAGEMENT_COLORS.active },
        { label: 'At Risk', value: data.member_stats.at_risk, color: ENGAGEMENT_COLORS.at_risk },
        { label: 'Disconnected', value: data.member_stats.disconnected, color: ENGAGEMENT_COLORS.disconnected },
      ]
    : [];

  const genderData = data?.demographics?.gender_distribution?.map((item) => ({
    label: item.gender === 'M' ? 'Male' : item.gender === 'F' ? 'Female' : 'Unknown',
    value: item.count,
    color: item.gender === 'M' ? '#3B82F6' : item.gender === 'F' ? '#EC4899' : '#9CA3AF',
  })) || [];

  const ageData = data?.demographics?.age_distribution?.map((item) => ({
    label: item.range,
    value: item.count,
  })) || [];

  const eventsData = data?.events_by_type?.filter(item => item.type).map((item) => ({
    label: (item.type || 'other').replace('_', ' ').replace(/\b\w/g, (l) => l.toUpperCase()),
    value: item.count,
    color: EVENT_TYPE_COLORS[item.type] || colors.gray[400],
  })) || [];

  const categoryData = data?.demographics?.category_distribution?.slice(0, 6).map((item) => ({
    label: item.category || 'Other',
    value: item.count,
  })) || [];

  return (
    <View className="flex-1 bg-gray-50 dark:bg-slate-900" style={{ paddingTop: insets.top }}>
      {/* Header */}
      <View className="px-4 py-4 bg-white dark:bg-slate-800 border-b border-gray-100 dark:border-slate-700">
        <View className="flex-row items-center gap-2">
          <BarChart3 size={24} color={colors.primary.teal} strokeWidth={2} />
          <Text className="text-xl font-bold text-gray-900 dark:text-white">
            {t('analytics.title', 'Analytics')}
          </Text>
        </View>
      </View>

      {/* Time Range Selector */}
      <View className="py-3 bg-white dark:bg-slate-800">
        <TimeRangeSelector value={timeRange} onChange={setTimeRange} />
      </View>

      {/* Content */}
      <ScrollView
        className="flex-1"
        contentContainerStyle={{ paddingBottom: 100 }}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={handleRefresh}
            tintColor={colors.primary.teal}
          />
        }
      >
        {isLoading ? (
          <AnalyticsSkeleton />
        ) : (
          <Animated.View entering={FadeIn.duration(300)}>
            {/* Stats Overview */}
            <View className="px-4 py-4">
              <View className="flex-row gap-3 mb-3">
                <StatCard
                  title="Total Members"
                  value={data?.member_stats?.total || 0}
                  icon={<Users size={20} color={colors.primary.teal} />}
                  color={colors.primary.teal}
                  index={0}
                />
                <StatCard
                  title="Active"
                  value={data?.member_stats?.active || 0}
                  subtitle={`${Math.round(((data?.member_stats?.active || 0) / (data?.member_stats?.total || 1)) * 100)}%`}
                  icon={<Heart size={20} color={colors.status.success} />}
                  color={colors.status.success}
                  index={1}
                />
              </View>
              <View className="flex-row gap-3">
                <StatCard
                  title="New This Month"
                  value={data?.member_stats?.new_this_month || 0}
                  icon={<TrendingUp size={20} color={colors.primary[500]} />}
                  color={colors.primary[500]}
                  index={2}
                />
                <StatCard
                  title="Financial Aid"
                  value={`${((data?.financial?.total_distributed || 0) / 1000000).toFixed(1)}M`}
                  subtitle="Distributed"
                  icon={<DollarSign size={20} color={colors.status.success} />}
                  color={colors.status.success}
                  index={3}
                />
              </View>
            </View>

            {/* Engagement Distribution */}
            {engagementData.length > 0 && (
              <View className="mb-6">
                <SectionHeader
                  title="Engagement Status"
                  icon={<Heart size={18} color={colors.primary.teal} />}
                />
                <PremiumCard className="mx-4 p-4">
                  <PieChart
                    data={engagementData}
                    size={180}
                    innerRadius={50}
                    centerText={data?.member_stats?.total?.toString() || '0'}
                    centerSubtext="Total"
                  />
                </PremiumCard>
              </View>
            )}

            {/* Gender Distribution */}
            {genderData.length > 0 && (
              <View className="mb-6">
                <SectionHeader
                  title="Gender Distribution"
                  icon={<Users size={18} color={colors.primary.teal} />}
                />
                <PremiumCard className="mx-4 p-4">
                  <PieChart
                    data={genderData}
                    size={160}
                    innerRadius={40}
                  />
                </PremiumCard>
              </View>
            )}

            {/* Age Distribution */}
            {ageData.length > 0 && (
              <View className="mb-6">
                <SectionHeader
                  title="Age Distribution"
                  icon={<Calendar size={18} color={colors.primary.teal} />}
                />
                <PremiumCard className="mx-4 p-4">
                  <BarChart
                    data={ageData}
                    height={180}
                    barColor={colors.primary[500]}
                  />
                </PremiumCard>
              </View>
            )}

            {/* Care Events by Type */}
            {eventsData.length > 0 && (
              <View className="mb-6">
                <SectionHeader
                  title="Care Events by Type"
                  icon={<Heart size={18} color={colors.primary.teal} />}
                />
                <PremiumCard className="mx-4 p-4">
                  <BarChart
                    data={eventsData}
                    height={200}
                    horizontal
                  />
                </PremiumCard>
              </View>
            )}

            {/* Category Distribution */}
            {categoryData.length > 0 && (
              <View className="mb-6">
                <SectionHeader
                  title="Member Categories"
                  icon={<Users size={18} color={colors.primary.teal} />}
                />
                <PremiumCard className="mx-4 p-4">
                  <BarChart
                    data={categoryData}
                    height={180}
                    barColor={colors.secondary.amber}
                  />
                </PremiumCard>
              </View>
            )}
          </Animated.View>
        )}
      </ScrollView>
    </View>
  );
}
