/**
 * Tasks Screen
 *
 * All tasks view with tabs for filtering
 * Uses NativeWind for styling
 */

import React, { useState, useCallback, useMemo, memo } from 'react';
import {
  View,
  Text,
  Pressable,
  ActivityIndicator,
  RefreshControl,
  Image,
  Linking,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import { router } from 'expo-router';
import {
  CheckSquare,
  Cake,
  Heart,
  Hospital,
  DollarSign,
  Clock,
  AlertTriangle,
  User,
  MessageCircle,
  Phone,
  UserCheck,
  Baby,
  Home,
} from 'lucide-react-native';

import { useDashboardReminders, useCompleteTask, useMarkMemberContacted } from '@/hooks/useDashboard';
import { eventTypeColors, colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';
import { formatDateToLocalTimezone } from '@/lib/dateUtils';
import { formatPhoneForWhatsApp, formatPhoneNumber, formatCurrency } from '@/lib/formatting';
import type { DashboardTask } from '@/types';

// ============================================================================
// HELPERS
// ============================================================================

function getTaskIcon(type: string) {
  switch (type) {
    case 'birthday':
      return Cake;
    case 'grief_stage':
    case 'grief_loss':
      return Heart;
    case 'accident_followup':
    case 'accident_illness':
      return Hospital;
    case 'financial_aid':
      return DollarSign;
    case 'at_risk':
      return Clock;
    case 'disconnected':
      return AlertTriangle;
    case 'childbirth':
      return Baby;
    case 'new_house':
      return Home;
    default:
      return CheckSquare;
  }
}

// Task type styling configuration
const TASK_TYPE_STYLES: Record<string, { ring: string; bg: string; text: string }> = {
  birthday: { ring: 'border-amber-400', bg: 'bg-amber-50', text: 'text-amber-600' },
  grief_stage: { ring: 'border-purple-400', bg: 'bg-purple-50', text: 'text-purple-600' },
  grief_loss: { ring: 'border-purple-400', bg: 'bg-purple-50', text: 'text-purple-600' },
  accident_followup: { ring: 'border-teal-400', bg: 'bg-teal-50', text: 'text-teal-600' },
  accident_illness: { ring: 'border-teal-400', bg: 'bg-teal-50', text: 'text-teal-600' },
  financial_aid: { ring: 'border-violet-400', bg: 'bg-violet-50', text: 'text-violet-600' },
  at_risk: { ring: 'border-amber-400', bg: 'bg-amber-50', text: 'text-amber-600' },
  disconnected: { ring: 'border-red-400', bg: 'bg-red-50', text: 'text-red-600' },
  childbirth: { ring: 'border-pink-400', bg: 'bg-pink-50', text: 'text-pink-600' },
  new_house: { ring: 'border-emerald-400', bg: 'bg-emerald-50', text: 'text-emerald-600' },
  regular_contact: { ring: 'border-blue-400', bg: 'bg-blue-50', text: 'text-blue-600' },
};

function getTaskStyles(type: string) {
  return TASK_TYPE_STYLES[type] || { ring: 'border-gray-300', bg: 'bg-gray-50', text: 'text-gray-600' };
}

function getTaskColor(type: string) {
  switch (type) {
    case 'birthday':
      return eventTypeColors.birthday;
    case 'grief_stage':
    case 'grief_loss':
      return eventTypeColors.grief_loss;
    case 'accident_followup':
    case 'accident_illness':
      return eventTypeColors.accident_illness;
    case 'financial_aid':
      return eventTypeColors.financial_aid;
    case 'at_risk':
      return colors.status.warning;
    case 'disconnected':
      return colors.status.error;
    case 'childbirth':
      return '#ec4899'; // pink-500
    case 'new_house':
      return '#10b981'; // emerald-500
    default:
      return colors.primary[500];
  }
}

// Calculate days until a date (positive = future, negative = past)
function getDaysUntil(dateStr: string | undefined): number | null {
  if (!dateStr) return null;
  const date = new Date(dateStr);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  date.setHours(0, 0, 0, 0);
  const diffTime = date.getTime() - today.getTime();
  return Math.ceil(diffTime / (1000 * 60 * 60 * 24));
}

// Get the task type from various backend fields
function getTaskType(task: DashboardTask): string {
  if (task.type) return task.type;
  if ((task as any).event_type) return (task as any).event_type;
  if ((task as any).stage) {
    const stageValue = (task as any).stage;
    if (typeof stageValue === 'string' &&
        (stageValue.includes('followup') || stageValue === 'first_followup' ||
         stageValue === 'second_followup' || stageValue === 'final_followup')) {
      return 'accident_followup';
    }
    return 'grief_stage';
  }
  if ((task as any).aid_type || (task as any).aid_amount !== undefined) {
    return 'financial_aid';
  }
  return '';
}

type TabKey = 'today' | 'upcoming' | 'overdue';

// ============================================================================
// COMPONENTS
// ============================================================================

interface TaskCardProps {
  task: DashboardTask;
  onComplete: () => void;
  onMarkContact?: () => void;
  onPress: () => void;
  activeTab: TabKey;
}

const TaskCard = memo(function TaskCard({ task, onComplete, onMarkContact, onPress, activeTab }: TaskCardProps) {
  const { t } = useTranslation();
  const taskType = getTaskType(task);
  const Icon = getTaskIcon(taskType);
  const color = getTaskColor(taskType);
  const styles = getTaskStyles(taskType);

  // Get phone info
  const phone = task.member_phone || (task as any).phone;
  const whatsappUrl = formatPhoneForWhatsApp(phone);

  // Calculate days info
  const scheduledDate = task.scheduled_date || (task as any).date || (task as any).next_distribution_date;
  const daysUntil = getDaysUntil(scheduledDate);

  // Get type-specific data
  const aidAmount = (task as any).aid_amount;
  const aidType = (task as any).aid_type;
  const stage = task.stage || (task as any).stage;
  const memberAge = task.member_age || (task as any).age;
  const daysSinceContact = task.days_since_last_contact || (task as any).days_since_last_contact;

  // Determine the type label
  const getTypeLabel = () => {
    switch (taskType) {
      case 'birthday':
        return t('tasks.types.birthday', 'Birthday');
      case 'grief_stage':
      case 'grief_loss':
        return t('tasks.types.grief', 'Grief Support');
      case 'accident_followup':
      case 'accident_illness':
        return t('tasks.types.accident', 'Accident/Illness');
      case 'financial_aid':
        return t('tasks.types.financial_aid', 'Financial Aid');
      case 'at_risk':
        return t('tasks.types.at_risk', 'At Risk');
      case 'disconnected':
        return t('tasks.types.disconnected', 'Disconnected');
      case 'childbirth':
        return t('tasks.types.childbirth', 'Childbirth');
      case 'new_house':
        return t('tasks.types.new_house', 'New House');
      case 'regular_contact':
        return t('tasks.types.regular_contact', 'Regular Contact');
      default:
        return taskType || t('tasks.types.task', 'Task');
    }
  };
  const typeLabel = getTypeLabel();

  // Get stage label for grief/accident
  const getStageLabel = () => {
    if (!stage) return null;
    const stageMap: Record<string, string> = {
      '1_week': t('tasks.stages.week1', 'Week 1'),
      '2_weeks': t('tasks.stages.week2', 'Week 2'),
      '1_month': t('tasks.stages.month1', 'Month 1'),
      '3_months': t('tasks.stages.month3', 'Month 3'),
      '6_months': t('tasks.stages.month6', 'Month 6'),
      '1_year': t('tasks.stages.year1', 'Year 1'),
      'first_followup': t('tasks.stages.firstFollowup', 'First Follow-up'),
      'second_followup': t('tasks.stages.secondFollowup', 'Second Follow-up'),
      'final_followup': t('tasks.stages.finalFollowup', 'Final Follow-up'),
    };
    return stageMap[stage] || stage;
  };
  const stageLabel = getStageLabel();

  // Handle WhatsApp
  const handleWhatsApp = useCallback(() => {
    if (whatsappUrl) {
      haptics.tap();
      Linking.openURL(whatsappUrl);
    }
  }, [whatsappUrl]);

  // Determine if this is an at-risk/disconnected member
  const isContactType = taskType === 'at_risk' || taskType === 'disconnected';

  // Determine action button text and handler
  const getActionButton = () => {
    if (isContactType && onMarkContact) {
      return {
        label: t('tasks.actions.markContact', 'Mark Contact'),
        onPress: onMarkContact,
        icon: UserCheck,
        bgClass: 'bg-blue-500',
        activeBgClass: 'active:bg-blue-600',
      };
    }
    if (taskType === 'financial_aid') {
      return {
        label: t('tasks.actions.distributed', 'Distributed'),
        onPress: onComplete,
        icon: CheckSquare,
        bgClass: 'bg-violet-500',
        activeBgClass: 'active:bg-violet-600',
      };
    }
    return {
      label: t('tasks.actions.complete', 'Complete'),
      onPress: onComplete,
      icon: CheckSquare,
      bgClass: 'bg-success-500',
      activeBgClass: 'active:bg-success-600',
    };
  };
  const actionButton = getActionButton();

  return (
    <Pressable
      className="bg-white rounded-xl p-4 shadow-sm active:opacity-95"
      onPress={onPress}
    >
      {/* Header Row: Photo + Name + Badge */}
      <View className="flex-row items-start">
        {/* Profile Photo with colored ring */}
        <View className={`rounded-full p-0.5 border-2 ${styles.ring}`}>
          {task.member_photo_url ? (
            <Image
              source={{ uri: task.member_photo_url }}
              className="w-11 h-11 rounded-full"
            />
          ) : (
            <View className="w-11 h-11 rounded-full items-center justify-center bg-gray-100">
              <User size={22} color="#9ca3af" />
            </View>
          )}
        </View>

        {/* Name and Info */}
        <View className="flex-1 ml-3">
          <View className="flex-row items-center justify-between">
            <Text className="text-base font-semibold text-gray-900 flex-1" numberOfLines={1}>
              {task.member_name}
            </Text>

            {/* Days Badge */}
            {daysUntil !== null && daysUntil > 0 && (
              <View className="bg-blue-100 px-2 py-0.5 rounded-full ml-2">
                <Text className="text-xs font-medium text-blue-700">
                  {t('tasks.info.inDays', { days: daysUntil })}
                </Text>
              </View>
            )}
            {daysUntil !== null && daysUntil < 0 && (
              <View className="bg-red-100 px-2 py-0.5 rounded-full ml-2">
                <Text className="text-xs font-medium text-red-700">
                  {t('tasks.info.daysOverdue', { days: Math.abs(daysUntil) })}
                </Text>
              </View>
            )}
          </View>

          {/* Phone Number */}
          {phone && (
            <View className="flex-row items-center mt-1">
              <Phone size={12} color="#9ca3af" />
              <Text className="text-xs text-gray-500 ml-1">
                {formatPhoneNumber(phone)}
              </Text>
            </View>
          )}

          {/* Type Label with Icon */}
          <View className="flex-row items-center mt-1.5">
            <Icon size={14} color={color} />
            <Text className={`text-[13px] ml-1.5 font-medium ${styles.text}`}>
              {typeLabel}
              {stageLabel && ` - ${stageLabel}`}
            </Text>
          </View>

          {/* Birthday: Will be X years old */}
          {taskType === 'birthday' && memberAge !== undefined && (
            <Text className="text-xs text-gray-500 mt-0.5">
              {activeTab === 'upcoming'
                ? t('tasks.info.willBeYearsOld', { age: memberAge + 1 })
                : t('tasks.info.yearsOld', { age: memberAge })}
            </Text>
          )}

          {/* Grief: Stage info */}
          {(taskType === 'grief_stage' || taskType === 'grief_loss') && stageLabel && (
            <Text className="text-xs text-gray-500 mt-0.5">
              {stageLabel} {t('tasks.info.afterMourning', 'after mourning')}
            </Text>
          )}

          {/* Financial Aid: Amount and Type */}
          {taskType === 'financial_aid' && (
            <View className="mt-0.5">
              {aidAmount && (
                <Text className="text-xs text-gray-600 font-medium">
                  {formatCurrency(aidAmount)}
                </Text>
              )}
              {aidType && (
                <Text className="text-xs text-gray-500">
                  {t(`careEvents.aidTypes.${aidType}`, aidType)}
                </Text>
              )}
            </View>
          )}

          {/* At-Risk/Disconnected: Days since contact + Age */}
          {isContactType && (
            <View className="mt-0.5">
              {daysSinceContact !== undefined && daysSinceContact > 0 && (
                <Text className="text-xs text-red-500 font-medium">
                  {t('tasks.info.daysSinceContact', { days: daysSinceContact })}
                </Text>
              )}
              {memberAge !== undefined && (
                <Text className="text-xs text-gray-500">
                  {t('tasks.info.yearsOld', { age: memberAge })}
                </Text>
              )}
            </View>
          )}

          {/* Scheduled Date */}
          {scheduledDate && !isContactType && (
            <Text className="text-xs text-gray-400 mt-0.5">
              {formatDateToLocalTimezone(scheduledDate, 'short')}
            </Text>
          )}
        </View>
      </View>

      {/* Action Buttons Row */}
      <View className="flex-row gap-2 mt-3">
        {/* WhatsApp Button */}
        {whatsappUrl && (
          <Pressable
            className="flex-1 flex-row items-center justify-center py-2.5 rounded-lg bg-green-500 active:bg-green-600"
            onPress={(e) => {
              e.stopPropagation();
              handleWhatsApp();
            }}
          >
            <MessageCircle size={16} color="white" />
            <Text className="text-white font-medium text-sm ml-1.5">
              WhatsApp
            </Text>
          </Pressable>
        )}

        {/* Complete/Mark Contact Button */}
        <Pressable
          className={`flex-1 flex-row items-center justify-center py-2.5 rounded-lg ${actionButton.bgClass} ${actionButton.activeBgClass}`}
          onPress={(e) => {
            e.stopPropagation();
            haptics.success();
            actionButton.onPress();
          }}
        >
          <actionButton.icon size={16} color="white" />
          <Text className="text-white font-medium text-sm ml-1.5">
            {actionButton.label}
          </Text>
        </Pressable>
      </View>
    </Pressable>
  );
});

// ============================================================================
// MAIN SCREEN
// ============================================================================

function TasksScreen() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const [activeTab, setActiveTab] = useState<TabKey>('today');

  const {
    data: reminders,
    isLoading,
    isRefetching,
    refetch,
  } = useDashboardReminders();

  const completeTask = useCompleteTask();
  const markContacted = useMarkMemberContacted();

  // Group tasks by tab
  const todayTasks = useMemo(() => {
    if (!reminders) return [];
    // Use today_tasks if available (unified list from backend)
    // Otherwise fall back to manual combination of individual arrays
    if (reminders.today_tasks && reminders.today_tasks.length > 0) {
      return [
        ...(reminders.birthdays_today || []),
        ...reminders.today_tasks,
      ];
    }
    return [
      ...(reminders.birthdays_today || []),
      ...(reminders.grief_today || []),
      ...(reminders.accident_followup || []),
      ...(reminders.financial_aid_due || []),
    ];
  }, [reminders]);

  const upcomingTasks = useMemo(() => {
    if (!reminders) return [];
    // Use upcoming_tasks which includes ALL upcoming tasks (birthdays, accidents, financial aid)
    // Fall back to upcoming_birthdays for backward compatibility
    return reminders.upcoming_tasks || reminders.upcoming_birthdays || [];
  }, [reminders]);

  const overdueTasks = useMemo(() => {
    if (!reminders) return [];
    return [
      ...(reminders.overdue_birthdays || []),  // Past birthdays not yet completed
      ...(reminders.at_risk_members || []),
      ...(reminders.disconnected_members || []),
    ];
  }, [reminders]);

  // Current tasks based on tab
  const currentTasks = useMemo(() => {
    switch (activeTab) {
      case 'today':
        return todayTasks;
      case 'upcoming':
        return upcomingTasks;
      case 'overdue':
        return overdueTasks;
      default:
        return [];
    }
  }, [activeTab, todayTasks, upcomingTasks, overdueTasks]);

  // Handle task completion
  const handleComplete = useCallback(
    (task: DashboardTask) => {
      const taskType = getTaskType(task);
      const eventId = task.event_id || (task as any).stage_id || (task as any).schedule_id || task.member_id;
      completeTask.mutate({ eventId, type: taskType });
    },
    [completeTask]
  );

  // Handle mark contact for at-risk/disconnected members
  const handleMarkContact = useCallback(
    (memberId: string) => {
      markContacted.mutate(memberId);
    },
    [markContacted]
  );

  // Handle task press
  const handleTaskPress = useCallback((task: DashboardTask) => {
    router.push(`/member/${task.member_id}`);
  }, []);

  const tabs: { key: TabKey; label: string; count: number }[] = [
    { key: 'today', label: t('tasks.tabs.today'), count: todayTasks.length },
    { key: 'upcoming', label: t('tasks.tabs.upcoming'), count: upcomingTasks.length },
    { key: 'overdue', label: t('tasks.tabs.overdue'), count: overdueTasks.length },
  ];

  return (
    <View className="flex-1 bg-gray-50">
      {/* Header */}
      <View
        className="bg-white px-6 pb-4 border-b border-gray-200"
        style={{ paddingTop: insets.top + 16 }}
      >
        <Text className="text-3xl font-bold text-gray-900 mb-4">
          {t('tasks.title')}
        </Text>

        {/* Tabs */}
        <View className="flex-row gap-2">
          {tabs.map((tab) => {
            const isActive = tab.key === activeTab;
            const isOverdue = tab.key === 'overdue' && tab.count > 0;
            return (
              <Pressable
                key={tab.key}
                className={`flex-row items-center px-4 py-2 rounded-full gap-1 ${
                  isActive ? 'bg-primary-500' : 'bg-gray-100'
                }`}
                onPress={() => {
                  haptics.tap();
                  setActiveTab(tab.key);
                }}
              >
                <Text
                  className={`text-sm font-medium ${
                    isActive ? 'text-white' : 'text-gray-600'
                  }`}
                >
                  {tab.label}
                </Text>
                {tab.count > 0 && (
                  <View
                    className={`min-w-5 h-5 rounded-full items-center justify-center px-1.5 ${
                      isOverdue
                        ? 'bg-warning-500'
                        : isActive
                        ? 'bg-white'
                        : 'bg-gray-200'
                    }`}
                  >
                    <Text
                      className={`text-xs font-semibold ${
                        isOverdue
                          ? 'text-white'
                          : isActive
                          ? 'text-primary-600'
                          : 'text-gray-600'
                      }`}
                    >
                      {tab.count}
                    </Text>
                  </View>
                )}
              </Pressable>
            );
          })}
        </View>
      </View>

      {/* Content */}
      {isLoading ? (
        <View className="flex-1 justify-center items-center">
          <ActivityIndicator size="large" color="#14b8a6" />
        </View>
      ) : (
        <FlashList
          data={currentTasks}
          renderItem={({ item: task, index }) => (
            <View className="mb-3">
              <TaskCard
                task={task}
                onComplete={() => handleComplete(task)}
                onMarkContact={() => handleMarkContact(task.member_id)}
                onPress={() => handleTaskPress(task)}
                activeTab={activeTab}
              />
            </View>
          )}
          keyExtractor={(task, index) => `${getTaskType(task)}-${task.member_id}-${index}`}
          contentContainerStyle={{ paddingHorizontal: 24, paddingTop: 16 }}
          ListEmptyComponent={
            <View className="items-center py-24">
              <CheckSquare size={48} color="#d1d5db" />
              <Text className="text-base font-semibold text-gray-600 mt-4">
                {t('tasks.emptyState.noTasks')}
              </Text>
              <Text className="text-sm text-gray-400 mt-1">
                {t('tasks.emptyState.noTasksDesc')}
              </Text>
            </View>
          }
          ListFooterComponent={<View className="h-24" />}
          refreshControl={
            <RefreshControl
              refreshing={isRefetching}
              onRefresh={refetch}
              tintColor="#14b8a6"
            />
          }
        />
      )}
    </View>
  );
}

export default memo(TasksScreen);
