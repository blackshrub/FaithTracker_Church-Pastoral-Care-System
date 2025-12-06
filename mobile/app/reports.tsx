/**
 * Reports Screen
 *
 * Monthly management reports and staff performance
 * Stack screen accessible from Profile
 *
 * Tabs:
 * - Monthly Report: KPIs, ministry highlights, insights
 * - Staff Performance: Team metrics, top performers
 * - Yearly Summary: Annual totals and trends
 */

import React, { useState, memo, useCallback } from 'react';
import { View, Text, ScrollView, Pressable, RefreshControl } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';
import {
  ArrowLeft,
  FileText,
  Users,
  Calendar,
  TrendingUp,
  CheckCircle,
  Heart,
  DollarSign,
  Hospital,
  UserPlus,
  ChevronLeft,
  ChevronRight,
  Lightbulb,
  Target,
} from 'lucide-react-native';

import { useMonthlyReport, useStaffPerformance, useYearlySummary } from '@/hooks/useReports';
import { KPICard, StaffPerformanceRow } from '@/components/reports';
import { PremiumCard } from '@/components/ui/PremiumCard';
import { Skeleton } from '@/components/ui/Skeleton';
import { colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';

// ============================================================================
// TYPES
// ============================================================================

type ReportTab = 'monthly' | 'staff' | 'yearly';

// ============================================================================
// CONSTANTS
// ============================================================================

const MONTH_NAMES = [
  'January', 'February', 'March', 'April', 'May', 'June',
  'July', 'August', 'September', 'October', 'November', 'December'
];

// ============================================================================
// MONTH SELECTOR
// ============================================================================

interface MonthSelectorProps {
  year: number;
  month: number;
  onPrevious: () => void;
  onNext: () => void;
}

const MonthSelector = memo(function MonthSelector({
  year,
  month,
  onPrevious,
  onNext,
}: MonthSelectorProps) {
  const now = new Date();
  const isCurrentMonth = year === now.getFullYear() && month === now.getMonth() + 1;

  return (
    <View className="flex-row items-center justify-center py-3 bg-white border-b border-gray-100">
      <Pressable
        onPress={onPrevious}
        className="p-2 active:opacity-60"
        hitSlop={8}
      >
        <ChevronLeft size={24} color="#6b7280" />
      </Pressable>

      <View className="px-6 items-center">
        <Text className="text-lg font-semibold text-gray-900">
          {MONTH_NAMES[month - 1]} {year}
        </Text>
      </View>

      <Pressable
        onPress={onNext}
        className={`p-2 ${isCurrentMonth ? 'opacity-30' : 'active:opacity-60'}`}
        disabled={isCurrentMonth}
        hitSlop={8}
      >
        <ChevronRight size={24} color="#6b7280" />
      </Pressable>
    </View>
  );
});

// ============================================================================
// TAB SELECTOR
// ============================================================================

interface TabSelectorProps {
  activeTab: ReportTab;
  onTabChange: (tab: ReportTab) => void;
}

const TabSelector = memo(function TabSelector({ activeTab, onTabChange }: TabSelectorProps) {
  const tabs: { id: ReportTab; label: string; icon: any }[] = [
    { id: 'monthly', label: 'Monthly', icon: FileText },
    { id: 'staff', label: 'Staff', icon: Users },
    { id: 'yearly', label: 'Yearly', icon: Calendar },
  ];

  return (
    <View className="flex-row bg-gray-100 mx-4 mt-4 rounded-xl p-1">
      {tabs.map((tab) => {
        const Icon = tab.icon;
        const isActive = activeTab === tab.id;

        return (
          <Pressable
            key={tab.id}
            onPress={() => {
              haptics.tap();
              onTabChange(tab.id);
            }}
            className={`flex-1 flex-row items-center justify-center py-2.5 rounded-lg gap-1.5 ${
              isActive ? 'bg-white shadow-sm' : ''
            }`}
          >
            <Icon size={16} color={isActive ? colors.primary.teal : '#6b7280'} />
            <Text
              className={`text-sm font-medium ${
                isActive ? 'text-primary-600' : 'text-gray-500'
              }`}
            >
              {tab.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
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
    <View className="flex-row items-center gap-2 mb-3">
      {icon}
      <Text className="text-base font-semibold text-gray-900">{title}</Text>
    </View>
  );
});

// ============================================================================
// LOADING SKELETON
// ============================================================================

const ReportSkeleton = memo(function ReportSkeleton() {
  return (
    <View className="px-4 pt-4">
      <Skeleton className="h-32 rounded-2xl mb-4" />
      <View className="flex-row gap-3 mb-4">
        <View className="flex-1">
          <Skeleton className="h-28 rounded-2xl" />
        </View>
        <View className="flex-1">
          <Skeleton className="h-28 rounded-2xl" />
        </View>
      </View>
      <Skeleton className="h-48 rounded-2xl mb-4" />
      <Skeleton className="h-32 rounded-2xl" />
    </View>
  );
});

// ============================================================================
// MONTHLY REPORT TAB
// ============================================================================

interface MonthlyReportTabProps {
  year: number;
  month: number;
}

const MonthlyReportTab = memo(function MonthlyReportTab({ year, month }: MonthlyReportTabProps) {
  const { data, isLoading, isRefetching, refetch } = useMonthlyReport({
    year,
    month,
    enabled: true,
  });

  if (isLoading) {
    return <ReportSkeleton />;
  }

  if (!data) {
    return (
      <View className="flex-1 items-center justify-center py-12">
        <FileText size={48} color="#d1d5db" />
        <Text className="text-gray-400 mt-4">No report data available</Text>
      </View>
    );
  }

  return (
    <ScrollView
      className="flex-1"
      contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
          tintColor={colors.primary.teal}
        />
      }
    >
      <Animated.View entering={FadeIn.duration(300)}>
        {/* Executive Summary */}
        <PremiumCard className="p-4 mb-4">
          <SectionHeader
            title="Executive Summary"
            icon={<TrendingUp size={18} color={colors.primary.teal} />}
          />
          <View className="flex-row flex-wrap gap-4 mt-2">
            <View className="flex-1 min-w-[100px]">
              <Text className="text-2xl font-bold text-gray-900">
                {data.executive_summary?.total_members?.toLocaleString() || 0}
              </Text>
              <Text className="text-xs text-gray-500">Total Members</Text>
            </View>
            <View className="flex-1 min-w-[100px]">
              <Text className="text-2xl font-bold text-primary-600">
                {data.executive_summary?.active_members?.toLocaleString() || 0}
              </Text>
              <Text className="text-xs text-gray-500">Active Members</Text>
            </View>
            <View className="flex-1 min-w-[100px]">
              <Text className="text-2xl font-bold text-green-600">
                {data.executive_summary?.tasks_completed?.toLocaleString() || 0}
              </Text>
              <Text className="text-xs text-gray-500">Tasks Completed</Text>
            </View>
          </View>
        </PremiumCard>

        {/* KPIs */}
        {data.kpis && (
          <PremiumCard className="p-4 mb-4">
            <SectionHeader
              title="Key Performance Indicators"
              icon={<Target size={18} color={colors.primary.teal} />}
            />
            <View className="flex-row justify-between mt-3">
              <KPICard
                label="Care Completion"
                value={data.kpis.care_completion_rate || 0}
                target={80}
                color={colors.status.success}
                size="small"
              />
              <KPICard
                label="Engagement"
                value={data.kpis.engagement_rate || 0}
                target={75}
                color={colors.primary.teal}
                size="small"
              />
              <KPICard
                label="Reach Rate"
                value={data.kpis.reach_rate || 0}
                target={90}
                color={colors.primary[500]}
                size="small"
              />
              <KPICard
                label="Birthday Care"
                value={data.kpis.birthday_completion_rate || 0}
                target={95}
                color={colors.secondary.amber}
                size="small"
              />
            </View>
          </PremiumCard>
        )}

        {/* Ministry Highlights */}
        {data.ministry_highlights && (
          <PremiumCard className="p-4 mb-4">
            <SectionHeader
              title="Ministry Highlights"
              icon={<Heart size={18} color={colors.primary.teal} />}
            />
            <View className="mt-2 gap-3">
              <View className="flex-row items-center justify-between py-2 border-b border-gray-100">
                <View className="flex-row items-center gap-2">
                  <UserPlus size={16} color={colors.status.success} />
                  <Text className="text-sm text-gray-600">New Members</Text>
                </View>
                <Text className="text-sm font-semibold text-gray-900">
                  {data.ministry_highlights.new_members || 0}
                </Text>
              </View>
              <View className="flex-row items-center justify-between py-2 border-b border-gray-100">
                <View className="flex-row items-center gap-2">
                  <Heart size={16} color="#6366f1" />
                  <Text className="text-sm text-gray-600">Active Grief Support</Text>
                </View>
                <Text className="text-sm font-semibold text-gray-900">
                  {data.ministry_highlights.grief_support_active || 0}
                </Text>
              </View>
              <View className="flex-row items-center justify-between py-2 border-b border-gray-100">
                <View className="flex-row items-center gap-2">
                  <Hospital size={16} color="#ef4444" />
                  <Text className="text-sm text-gray-600">Hospital Visits</Text>
                </View>
                <Text className="text-sm font-semibold text-gray-900">
                  {data.ministry_highlights.hospital_visits || 0}
                </Text>
              </View>
              <View className="flex-row items-center justify-between py-2">
                <View className="flex-row items-center gap-2">
                  <DollarSign size={16} color={colors.status.success} />
                  <Text className="text-sm text-gray-600">Financial Aid</Text>
                </View>
                <Text className="text-sm font-semibold text-gray-900">
                  Rp {((data.ministry_highlights.financial_aid_distributed || 0) / 1000000).toFixed(1)}M
                </Text>
              </View>
            </View>
          </PremiumCard>
        )}

        {/* Insights & Recommendations */}
        {(data.insights?.length > 0 || data.recommendations?.length > 0) && (
          <PremiumCard className="p-4">
            <SectionHeader
              title="Insights & Recommendations"
              icon={<Lightbulb size={18} color={colors.secondary.amber} />}
            />
            <View className="mt-2 gap-2">
              {data.insights?.map((insight: string, index: number) => (
                <View key={`insight-${index}`} className="flex-row items-start gap-2 py-1">
                  <View className="w-1.5 h-1.5 rounded-full bg-primary-500 mt-1.5" />
                  <Text className="flex-1 text-sm text-gray-600">{insight}</Text>
                </View>
              ))}
              {data.recommendations?.map((rec: string, index: number) => (
                <View key={`rec-${index}`} className="flex-row items-start gap-2 py-1">
                  <View className="w-1.5 h-1.5 rounded-full bg-amber-500 mt-1.5" />
                  <Text className="flex-1 text-sm text-gray-600">{rec}</Text>
                </View>
              ))}
            </View>
          </PremiumCard>
        )}
      </Animated.View>
    </ScrollView>
  );
});

// ============================================================================
// STAFF PERFORMANCE TAB
// ============================================================================

interface StaffPerformanceTabProps {
  year: number;
  month: number;
}

const StaffPerformanceTab = memo(function StaffPerformanceTab({
  year,
  month,
}: StaffPerformanceTabProps) {
  const { data, isLoading, isRefetching, refetch } = useStaffPerformance({
    year,
    month,
    enabled: true,
  });

  if (isLoading) {
    return <ReportSkeleton />;
  }

  if (!data) {
    return (
      <View className="flex-1 items-center justify-center py-12">
        <Users size={48} color="#d1d5db" />
        <Text className="text-gray-400 mt-4">No staff data available</Text>
      </View>
    );
  }

  return (
    <ScrollView
      className="flex-1"
      contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
          tintColor={colors.primary.teal}
        />
      }
    >
      <Animated.View entering={FadeIn.duration(300)}>
        {/* Team Overview */}
        {data.team_overview && (
          <PremiumCard className="p-4 mb-4">
            <SectionHeader
              title="Team Overview"
              icon={<Users size={18} color={colors.primary.teal} />}
            />
            <View className="flex-row justify-between mt-3">
              <View className="items-center flex-1">
                <Text className="text-2xl font-bold text-gray-900">
                  {data.team_overview.total_staff || 0}
                </Text>
                <Text className="text-xs text-gray-500 text-center">Staff</Text>
              </View>
              <View className="w-px h-12 bg-gray-200" />
              <View className="items-center flex-1">
                <Text className="text-2xl font-bold text-primary-600">
                  {data.team_overview.total_tasks_completed || 0}
                </Text>
                <Text className="text-xs text-gray-500 text-center">Total Tasks</Text>
              </View>
              <View className="w-px h-12 bg-gray-200" />
              <View className="items-center flex-1">
                <Text className="text-2xl font-bold text-green-600">
                  {data.team_overview.average_per_staff?.toFixed(1) || 0}
                </Text>
                <Text className="text-xs text-gray-500 text-center">Avg/Staff</Text>
              </View>
            </View>
          </PremiumCard>
        )}

        {/* Staff Leaderboard */}
        {data.staff_metrics && data.staff_metrics.length > 0 && (
          <View>
            <Text className="text-base font-semibold text-gray-900 mb-3">
              Staff Leaderboard
            </Text>
            <View className="gap-3">
              {data.staff_metrics.map((staff: any, index: number) => (
                <StaffPerformanceRow
                  key={staff.user_id || index}
                  rank={staff.rank || index + 1}
                  userName={staff.user_name}
                  userPhotoUrl={staff.user_photo_url}
                  tasksCompleted={staff.tasks_completed}
                  membersContacted={staff.members_contacted}
                  activeDays={staff.active_days}
                  index={index}
                />
              ))}
            </View>
          </View>
        )}
      </Animated.View>
    </ScrollView>
  );
});

// ============================================================================
// YEARLY SUMMARY TAB
// ============================================================================

interface YearlySummaryTabProps {
  year: number;
}

const YearlySummaryTab = memo(function YearlySummaryTab({ year }: YearlySummaryTabProps) {
  const { data, isLoading, isRefetching, refetch } = useYearlySummary({
    year,
    enabled: true,
  });

  if (isLoading) {
    return <ReportSkeleton />;
  }

  if (!data) {
    return (
      <View className="flex-1 items-center justify-center py-12">
        <Calendar size={48} color="#d1d5db" />
        <Text className="text-gray-400 mt-4">No yearly data available</Text>
      </View>
    );
  }

  return (
    <ScrollView
      className="flex-1"
      contentContainerStyle={{ padding: 16, paddingBottom: 100 }}
      refreshControl={
        <RefreshControl
          refreshing={isRefetching}
          onRefresh={refetch}
          tintColor={colors.primary.teal}
        />
      }
    >
      <Animated.View entering={FadeIn.duration(300)}>
        {/* Year Header */}
        <View className="items-center mb-4">
          <Text className="text-3xl font-bold text-gray-900">{year}</Text>
          <Text className="text-sm text-gray-500">Annual Summary</Text>
        </View>

        {/* Annual Stats */}
        <PremiumCard className="p-4 mb-4">
          <SectionHeader
            title="Annual Totals"
            icon={<TrendingUp size={18} color={colors.primary.teal} />}
          />
          <View className="flex-row flex-wrap gap-4 mt-2">
            <Animated.View entering={FadeInDown.duration(300).delay(100)} className="flex-1 min-w-[100px] items-center py-3 bg-gray-50 rounded-xl">
              <CheckCircle size={24} color={colors.status.success} />
              <Text className="text-xl font-bold text-gray-900 mt-2">
                {data.total_tasks_completed?.toLocaleString() || 0}
              </Text>
              <Text className="text-xs text-gray-500">Tasks Completed</Text>
            </Animated.View>
            <Animated.View entering={FadeInDown.duration(300).delay(200)} className="flex-1 min-w-[100px] items-center py-3 bg-gray-50 rounded-xl">
              <Users size={24} color={colors.primary.teal} />
              <Text className="text-xl font-bold text-gray-900 mt-2">
                {data.total_members_served?.toLocaleString() || 0}
              </Text>
              <Text className="text-xs text-gray-500">Members Served</Text>
            </Animated.View>
          </View>
          <View className="flex-row flex-wrap gap-4 mt-3">
            <Animated.View entering={FadeInDown.duration(300).delay(300)} className="flex-1 min-w-[100px] items-center py-3 bg-gray-50 rounded-xl">
              <Heart size={24} color="#6366f1" />
              <Text className="text-xl font-bold text-gray-900 mt-2">
                {data.total_care_events?.toLocaleString() || 0}
              </Text>
              <Text className="text-xs text-gray-500">Care Events</Text>
            </Animated.View>
            <Animated.View entering={FadeInDown.duration(300).delay(400)} className="flex-1 min-w-[100px] items-center py-3 bg-gray-50 rounded-xl">
              <DollarSign size={24} color={colors.status.success} />
              <Text className="text-xl font-bold text-gray-900 mt-2">
                {((data.total_financial_aid || 0) / 1000000).toFixed(1)}M
              </Text>
              <Text className="text-xs text-gray-500">Financial Aid</Text>
            </Animated.View>
          </View>
        </PremiumCard>

        {/* Monthly Breakdown */}
        {data.monthly_breakdown && data.monthly_breakdown.length > 0 && (
          <PremiumCard className="p-4">
            <SectionHeader
              title="Monthly Breakdown"
              icon={<Calendar size={18} color={colors.primary.teal} />}
            />
            <View className="mt-2 gap-2">
              {data.monthly_breakdown.map((month: any, index: number) => (
                <Animated.View
                  key={month.month || index}
                  entering={FadeInDown.duration(200).delay(index * 50)}
                  className="flex-row items-center justify-between py-2 border-b border-gray-50"
                >
                  <Text className="text-sm text-gray-600 w-20">
                    {MONTH_NAMES[month.month - 1]?.substring(0, 3) || `M${month.month}`}
                  </Text>
                  <View className="flex-1 flex-row items-center justify-end gap-4">
                    <Text className="text-xs text-gray-400">
                      {month.tasks_completed} tasks
                    </Text>
                    <View className="w-20">
                      <View className="h-2 bg-gray-100 rounded-full overflow-hidden">
                        <View
                          className="h-full bg-primary-500 rounded-full"
                          style={{
                            width: `${Math.min((month.tasks_completed / (data.max_monthly_tasks || 100)) * 100, 100)}%`,
                          }}
                        />
                      </View>
                    </View>
                  </View>
                </Animated.View>
              ))}
            </View>
          </PremiumCard>
        )}
      </Animated.View>
    </ScrollView>
  );
});

// ============================================================================
// MAIN SCREEN
// ============================================================================

export default function ReportsScreen() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const [activeTab, setActiveTab] = useState<ReportTab>('monthly');

  // Date state for month/year selection
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  const handlePreviousMonth = useCallback(() => {
    haptics.tap();
    if (month === 1) {
      setMonth(12);
      setYear(year - 1);
    } else {
      setMonth(month - 1);
    }
  }, [month, year]);

  const handleNextMonth = useCallback(() => {
    const currentYear = now.getFullYear();
    const currentMonth = now.getMonth() + 1;

    // Don't go beyond current month
    if (year === currentYear && month === currentMonth) {
      return;
    }

    haptics.tap();
    if (month === 12) {
      setMonth(1);
      setYear(year + 1);
    } else {
      setMonth(month + 1);
    }
  }, [month, year, now]);

  const handleBack = useCallback(() => {
    haptics.tap();
    router.back();
  }, []);

  return (
    <View className="flex-1 bg-gray-50" style={{ paddingTop: insets.top }}>
      {/* Header */}
      <View className="flex-row items-center px-4 py-3 bg-white border-b border-gray-100">
        <Pressable
          onPress={handleBack}
          className="mr-3 p-1 -ml-1 active:opacity-60"
          hitSlop={8}
        >
          <ArrowLeft size={24} color="#374151" />
        </Pressable>
        <Text className="text-lg font-semibold text-gray-900 flex-1">
          {t('reports.title', 'Reports')}
        </Text>
      </View>

      {/* Tab Selector */}
      <TabSelector activeTab={activeTab} onTabChange={setActiveTab} />

      {/* Month Selector (not shown for yearly) */}
      {activeTab !== 'yearly' && (
        <MonthSelector
          year={year}
          month={month}
          onPrevious={handlePreviousMonth}
          onNext={handleNextMonth}
        />
      )}

      {/* Tab Content */}
      {activeTab === 'monthly' && <MonthlyReportTab year={year} month={month} />}
      {activeTab === 'staff' && <StaffPerformanceTab year={year} month={month} />}
      {activeTab === 'yearly' && <YearlySummaryTab year={year} />}
    </View>
  );
}
