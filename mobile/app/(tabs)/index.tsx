/**
 * Today Screen (Dashboard)
 *
 * Main dashboard showing today's tasks, stats, and quick actions
 * Uses NativeWind for styling (LinearGradient uses style prop)
 */

import React, { useMemo, useCallback, memo } from 'react';
import {
  View,
  Text,
  RefreshControl,
  Pressable,
  ActivityIndicator,
  StyleSheet,
  ScrollView,
  Image,
  Linking,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import { router } from 'expo-router';
import { LinearGradient } from 'expo-linear-gradient';
import Animated, { FadeInDown } from 'react-native-reanimated';
import {
  Sun,
  CloudSun,
  Sunset,
  Moon,
  Users,
  User,
  CheckSquare,
  ChevronRight,
  Cake,
  Heart,
  Hospital,
  DollarSign,
  Plus,
  Baby,
  Home,
  Phone,
  MessageCircle,
  Clock,
  AlertTriangle,
  UserCheck,
} from 'lucide-react-native';

import { useAuthStore } from '@/stores/auth';
import { useDashboardReminders, useCompleteTask, useMarkMemberContacted } from '@/hooks/useDashboard';
import { useOverlayStore } from '@/stores/overlayStore';
import { CreateCareEventSheet } from '@/components/care-events/CreateCareEventSheet';
import { MemberAvatar } from '@/components/ui/CachedImage';
import { gradients, eventTypeColors, colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';
import { formatPhoneForWhatsApp, formatPhoneNumber, formatCurrency } from '@/lib/formatting';
import { formatDateToLocalTimezone } from '@/lib/dateUtils';
import type { DashboardTask, EventType } from '@/types';

// ============================================================================
// CONSTANTS
// ============================================================================

const EVENT_TYPE_CONFIG: {
  key: EventType;
  icon: React.ComponentType<any>;
  color: string;
  hasGriefRelationship?: boolean;
  hasHospitalName?: boolean;
  hasAidFields?: boolean;
}[] = [
  { key: 'birthday', icon: Cake, color: eventTypeColors.birthday },
  { key: 'childbirth', icon: Baby, color: '#ec4899' },
  { key: 'grief_loss', icon: Heart, color: eventTypeColors.grief_loss, hasGriefRelationship: true },
  { key: 'new_house', icon: Home, color: '#8b5cf6' },
  { key: 'accident_illness', icon: Hospital, color: eventTypeColors.accident_illness, hasHospitalName: true },
  { key: 'financial_aid', icon: DollarSign, color: eventTypeColors.financial_aid, hasAidFields: true },
  { key: 'regular_contact', icon: Phone, color: '#6366f1' },
];

// ============================================================================
// HELPERS
// ============================================================================

function useGreeting() {
  const { t } = useTranslation();

  return useMemo(() => {
    const hour = new Date().getHours();
    if (hour >= 5 && hour < 12) {
      return { text: t('dashboard.greeting.morning'), icon: Sun };
    }
    if (hour >= 12 && hour < 17) {
      return { text: t('dashboard.greeting.afternoon'), icon: CloudSun };
    }
    if (hour >= 17 && hour < 21) {
      return { text: t('dashboard.greeting.evening'), icon: Sunset };
    }
    return { text: t('dashboard.greeting.night'), icon: Moon };
  }, [t]);
}

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
    case 'childbirth':
      return Baby;
    case 'new_house':
      return Home;
    case 'regular_contact':
      return Phone;
    case 'at_risk':
      return Clock;
    case 'disconnected':
      return AlertTriangle;
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
      return '#ec4899';
    case 'new_house':
      return '#10b981';
    default:
      return colors.primary[500];
  }
}

// Calculate days until a date
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

// ============================================================================
// COMPONENTS
// ============================================================================

interface TaskCardProps {
  task: DashboardTask;
  onComplete: () => void;
  onMarkContact?: () => void;
  onPress: () => void;
}

const TaskCard = memo(function TaskCard({ task, onComplete, onMarkContact, onPress }: TaskCardProps) {
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

  // Get stage label
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

  // Determine if contact type
  const isContactType = taskType === 'at_risk' || taskType === 'disconnected';

  // Action button config
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
      {/* Header Row */}
      <View className="flex-row items-start">
        {/* Avatar with ring */}
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

        {/* Info */}
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

          {/* Phone */}
          {phone && (
            <View className="flex-row items-center mt-1">
              <Phone size={12} color="#9ca3af" />
              <Text className="text-xs text-gray-500 ml-1">
                {formatPhoneNumber(phone)}
              </Text>
            </View>
          )}

          {/* Type with icon */}
          <View className="flex-row items-center mt-1.5">
            <Icon size={14} color={color} />
            <Text className={`text-[13px] ml-1.5 font-medium ${styles.text}`}>
              {typeLabel}
              {stageLabel && ` - ${stageLabel}`}
            </Text>
          </View>

          {/* Birthday age */}
          {taskType === 'birthday' && memberAge !== undefined && (
            <Text className="text-xs text-gray-500 mt-0.5">
              {t('tasks.info.yearsOld', { age: memberAge })}
            </Text>
          )}

          {/* Grief info */}
          {(taskType === 'grief_stage' || taskType === 'grief_loss') && stageLabel && (
            <Text className="text-xs text-gray-500 mt-0.5">
              {stageLabel} {t('tasks.info.afterMourning', 'after mourning')}
            </Text>
          )}

          {/* Financial aid */}
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

          {/* At-risk/Disconnected */}
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

          {/* Date */}
          {scheduledDate && !isContactType && (
            <Text className="text-xs text-gray-400 mt-0.5">
              {formatDateToLocalTimezone(scheduledDate, 'short')}
            </Text>
          )}
        </View>
      </View>

      {/* Action Buttons */}
      <View className="flex-row gap-2 mt-3">
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

// Quick Add Care Event Button
interface QuickAddButtonProps {
  icon: React.ComponentType<any>;
  label: string;
  color: string;
  onPress: () => void;
}

const QuickAddButton = memo(function QuickAddButton({ icon: Icon, label, color, onPress }: QuickAddButtonProps) {
  return (
    <Pressable
      className="items-center active:opacity-80"
      onPress={onPress}
    >
      <View
        className="w-14 h-14 rounded-2xl items-center justify-center mb-2"
        style={{ backgroundColor: `${color}15` }}
      >
        <Icon size={24} color={color} />
      </View>
      <Text className="text-xs text-gray-600 text-center" numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
});

// ============================================================================
// MAIN SCREEN
// ============================================================================

function TodayScreen() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const { user } = useAuthStore();
  const greeting = useGreeting();
  const GreetingIcon = greeting.icon;

  // Overlay store for care event creation
  const { showBottomSheet } = useOverlayStore();

  const {
    data: reminders,
    isLoading,
    isRefetching,
    refetch,
  } = useDashboardReminders();

  const completeTask = useCompleteTask();
  const markContacted = useMarkMemberContacted();

  // Combine all today's tasks
  const todayTasks = useMemo(() => {
    if (!reminders) return [];
    return [
      ...(reminders.birthdays_today || []),
      ...(reminders.grief_today || []),
      ...(reminders.accident_followup || []),
      ...(reminders.financial_aid_due || []),
    ];
  }, [reminders]);

  // Count overdue items
  const overdueCount = useMemo(() => {
    if (!reminders) return 0;
    return (reminders.at_risk_members?.length || 0) + (reminders.disconnected_members?.length || 0);
  }, [reminders]);

  // Get user name
  const userName = user?.name || '';

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

  // Handle task press - navigate to member
  const handleTaskPress = useCallback((task: DashboardTask) => {
    router.push(`/member/${task.member_id}`);
  }, []);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    refetch();
  }, [refetch]);

  // Open care event creation overlay
  const handleOpenQuickAdd = useCallback((initialEventType?: EventType) => {
    haptics.tap();
    if (!user?.campus_id) return;

    showBottomSheet(CreateCareEventSheet, {
      campusId: user.campus_id,
      initialEventType,
      onSuccess: () => refetch(),
    });
  }, [user?.campus_id, showBottomSheet, refetch]);

  if (isLoading) {
    return (
      <View className="flex-1 justify-center items-center bg-gray-50 dark:bg-slate-900">
        <ActivityIndicator size="large" color="#14b8a6" />
      </View>
    );
  }

  return (
    <View className="flex-1 bg-gray-50 dark:bg-slate-900">
      {/* Fixed Header */}
      <LinearGradient
        colors={[gradients.header.start, gradients.header.mid, gradients.header.end]}
        style={[styles.headerGradient, { paddingTop: insets.top + 12 }]}
      >
        {/* Greeting */}
        <View className="flex-row items-center mb-1">
          <GreetingIcon size={18} color="#99f6e4" />
          <Text className="text-sm text-teal-200 font-medium ml-2">{greeting.text}</Text>
        </View>
        <Text className="text-2xl font-bold text-white mb-4">{userName}</Text>

        {/* Stats Row */}
        <View style={styles.statsContainer}>
          <View className="flex-1 items-center">
            <Text className="text-xl font-bold text-white">{todayTasks.length}</Text>
            <Text className="text-xs text-teal-200">{t('dashboard.stats.todayTasks')}</Text>
          </View>
          <View style={styles.statsDivider} />
          <View className="flex-1 items-center">
            <Text className={`text-xl font-bold ${overdueCount > 0 ? 'text-amber-400' : 'text-white'}`}>
              {overdueCount}
            </Text>
            <Text className="text-xs text-teal-200">{t('dashboard.stats.overdueTasks')}</Text>
          </View>
          <View style={styles.statsDivider} />
          <View className="flex-1 items-center">
            <Text className="text-xl font-bold text-white">{reminders?.total_members || 0}</Text>
            <Text className="text-xs text-teal-200">{t('dashboard.stats.totalMembers')}</Text>
          </View>
        </View>
      </LinearGradient>

      {/* Content */}
      <ScrollView
        className="flex-1"
        contentContainerStyle={styles.scrollContent}
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={handleRefresh}
            tintColor="#14b8a6"
          />
        }
      >
        {/* Quick Add Care Event */}
        <Animated.View
          entering={FadeInDown.delay(200).duration(400)}
          className="mb-6"
        >
          <View className="flex-row justify-between items-center mb-3">
            <Text className="text-lg font-bold text-gray-900 dark:text-white">
              {t('dashboard.sections.quickActions')}
            </Text>
            <Pressable
              className="flex-row items-center bg-teal-500 rounded-full px-3 py-1.5 active:bg-teal-600"
              onPress={() => handleOpenQuickAdd()}
            >
              <Plus size={14} color="#ffffff" />
              <Text className="text-xs font-semibold text-white ml-1">
                {t('careEvents.create')}
              </Text>
            </Pressable>
          </View>

          <View className="bg-white rounded-2xl p-4 shadow-sm">
            <ScrollView horizontal showsHorizontalScrollIndicator={false}>
              <View className="flex-row gap-5">
                {EVENT_TYPE_CONFIG.map((config) => (
                  <QuickAddButton
                    key={config.key}
                    icon={config.icon}
                    label={t(`careEvents.types.${config.key}`)}
                    color={config.color}
                    onPress={() => handleOpenQuickAdd(config.key)}
                  />
                ))}
              </View>
            </ScrollView>
          </View>
        </Animated.View>

        {/* Today's Tasks */}
        <Animated.View
          entering={FadeInDown.delay(300).duration(400)}
          className="mb-6"
        >
          <Text className="text-lg font-bold text-gray-900 mb-3">
            {t('dashboard.sections.todayTasks')}
          </Text>

          {todayTasks.length === 0 ? (
            <View className="items-center py-10 bg-white rounded-2xl shadow-sm">
              <CheckSquare size={40} color="#d1d5db" />
              <Text className="text-base font-semibold text-gray-600 mt-3">
                {t('dashboard.emptyState.noTasks')}
              </Text>
              <Text className="text-sm text-gray-400 mt-1">
                {t('dashboard.emptyState.allCaughtUp')}
              </Text>
            </View>
          ) : (
            <View className="gap-3">
              {todayTasks.map((task, index) => (
                <TaskCard
                  key={`${getTaskType(task)}-${task.member_id}-${index}`}
                  task={task}
                  onComplete={() => handleComplete(task)}
                  onMarkContact={() => handleMarkContact(task.member_id)}
                  onPress={() => handleTaskPress(task)}
                />
              ))}
            </View>
          )}
        </Animated.View>

        {/* Navigation Actions */}
        <Animated.View
          entering={FadeInDown.delay(400).duration(400)}
          className="mb-6"
        >
          <View className="gap-3">
            <Pressable
              className="flex-row items-center bg-white rounded-xl p-4 shadow-sm active:opacity-90 active:scale-[0.98]"
              onPress={() => {
                haptics.tap();
                router.push('/(tabs)/members');
              }}
            >
              <View className="w-11 h-11 rounded-xl bg-teal-50 items-center justify-center">
                <Users size={22} color="#0d9488" />
              </View>
              <View className="flex-1 ml-3">
                <Text className="text-base font-semibold text-gray-900">
                  {t('dashboard.quickActions.members')}
                </Text>
                <Text className="text-sm text-gray-500">
                  {t('dashboard.quickActions.membersDesc')}
                </Text>
              </View>
              <ChevronRight size={20} color="#9ca3af" />
            </Pressable>

            <Pressable
              className="flex-row items-center bg-white rounded-xl p-4 shadow-sm active:opacity-90 active:scale-[0.98]"
              onPress={() => {
                haptics.tap();
                router.push('/(tabs)/tasks');
              }}
            >
              <View className="w-11 h-11 rounded-xl bg-amber-50 items-center justify-center">
                <CheckSquare size={22} color="#d97706" />
              </View>
              <View className="flex-1 ml-3">
                <Text className="text-base font-semibold text-gray-900">
                  {t('dashboard.quickActions.tasks')}
                </Text>
                <Text className="text-sm text-gray-500">
                  {t('dashboard.quickActions.tasksDesc')}
                </Text>
              </View>
              <ChevronRight size={20} color="#9ca3af" />
            </Pressable>
          </View>
        </Animated.View>

        {/* Bottom padding for tab bar */}
        <View style={{ height: 100 }} />
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  headerGradient: {
    paddingHorizontal: 20,
    paddingBottom: 16,
  },
  statsContainer: {
    flexDirection: 'row',
    backgroundColor: 'rgba(255, 255, 255, 0.1)',
    borderRadius: 16,
    paddingVertical: 12,
    paddingHorizontal: 8,
  },
  statsDivider: {
    width: 1,
    backgroundColor: 'rgba(255, 255, 255, 0.2)',
    marginHorizontal: 8,
  },
  scrollContent: {
    paddingHorizontal: 20,
    paddingTop: 20,
  },
});

export default memo(TodayScreen);
