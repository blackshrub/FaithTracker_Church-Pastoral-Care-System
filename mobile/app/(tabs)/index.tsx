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
} from 'lucide-react-native';

import { useAuthStore } from '@/stores/auth';
import { useDashboardReminders, useCompleteTask } from '@/hooks/useDashboard';
import { useOverlayStore } from '@/stores/overlayStore';
import { CreateCareEventSheet } from '@/components/care-events/CreateCareEventSheet';
import { MemberAvatar } from '@/components/ui/CachedImage';
import { gradients, eventTypeColors, colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';
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
    case 'disconnected':
      return Users;
    default:
      return CheckSquare;
  }
}

function getTaskColor(type: string) {
  const config = EVENT_TYPE_CONFIG.find(c => c.key === type);
  return config?.color || colors.primary[500];
}

// ============================================================================
// COMPONENTS
// ============================================================================

interface TaskCardProps {
  task: DashboardTask;
  onComplete: () => void;
  onPress: () => void;
}

const TaskCard = memo(function TaskCard({ task, onComplete, onPress }: TaskCardProps) {
  const { t } = useTranslation();
  // Backend uses different fields depending on task source:
  // - upcoming_tasks/today_tasks: has "type" field
  // - birthdays_today/overdue_birthdays: has "event_type" field (from care_events)
  // - grief_today: has "stage" field (from grief_support collection)
  // - accident_followup: has "stage" field (from accident_followups collection)
  // - financial_aid_due: has "aid_type" field (from financial_aid_schedules collection)
  const getTaskType = () => {
    if (task.type) return task.type;
    if ((task as any).event_type) return (task as any).event_type;
    // For grief/accident stages without explicit type, detect from stage or collection fields
    if ((task as any).stage) {
      // Check if it's an accident followup (has specific stage names)
      const stageValue = (task as any).stage;
      if (typeof stageValue === 'string' &&
          (stageValue.includes('followup') || stageValue === 'first_followup' ||
           stageValue === 'second_followup' || stageValue === 'final_followup')) {
        return 'accident_followup';
      }
      // Otherwise it's grief support
      return 'grief_stage';
    }
    // For financial aid schedules
    if ((task as any).aid_type || (task as any).aid_amount !== undefined) {
      return 'financial_aid';
    }
    return '';
  };
  const taskType = getTaskType();
  const Icon = getTaskIcon(taskType);
  const color = getTaskColor(taskType);

  // Determine the type label based on task type
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

  return (
    <Pressable
      className="flex-row items-center bg-white rounded-xl p-4 shadow-sm active:opacity-90 active:scale-[0.98]"
      onPress={onPress}
    >
      {/* Profile Photo or Icon */}
      {task.member_photo_url ? (
        <Image
          source={{ uri: task.member_photo_url }}
          className="w-10 h-10 rounded-full"
        />
      ) : (
        <View
          className="w-10 h-10 rounded-full items-center justify-center bg-gray-100"
        >
          <User size={20} color="#9ca3af" />
        </View>
      )}

      {/* Content */}
      <View className="flex-1 ml-3">
        <Text className="text-base font-semibold text-gray-900" numberOfLines={1}>
          {task.member_name}
        </Text>
        <Text className="text-sm text-gray-500 mt-0.5">
          {typeLabel}
          {task.stage && ` - ${t(`careEvents.griefStages.${task.stage}`, task.stage)}`}
        </Text>
      </View>

      {/* Complete Button */}
      <Pressable
        className="w-10 h-10 rounded-lg bg-success-50 items-center justify-center active:bg-success-100"
        onPress={(e) => {
          e.stopPropagation();
          haptics.success();
          onComplete();
        }}
      >
        <CheckSquare size={18} color="#22c55e" />
      </Pressable>
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
      const eventId = task.event_id || task.stage_id || task.member_id;
      completeTask.mutate({ eventId, type: task.type });
    },
    [completeTask]
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
                  key={`${task.type}-${task.member_id}-${index}`}
                  task={task}
                  onComplete={() => handleComplete(task)}
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
