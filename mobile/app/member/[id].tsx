/**
 * Member Detail Screen
 *
 * Shows member profile with tabbed care event views
 * Tabs: Timeline, Grief Support, Accident Follow-up, Financial Aid
 * Matches webapp logic exactly
 */

import React, { memo, useCallback, useMemo, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  Pressable,
  ActivityIndicator,
  Image,
  Linking,
  RefreshControl,
  Alert,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useLocalSearchParams, router } from 'expo-router';
import { useTranslation } from 'react-i18next';
import Animated, { FadeIn, FadeInDown } from 'react-native-reanimated';
import {
  ArrowLeft,
  Phone,
  MessageCircle,
  User,
  MapPin,
  Calendar,
  FileText,
  Plus,
  CheckCircle,
  XCircle,
  Clock,
  Cake,
  Heart,
  Hospital,
  DollarSign,
  Home,
  Baby,
  Edit3,
  RotateCcw,
  AlertCircle,
  Ban,
  ClipboardList,
  MoreVertical,
  Trash2,
  Users,
  Tag,
} from 'lucide-react-native';

import { useMember } from '@/hooks/useMembers';
import {
  useMemberCareEvents,
  useCompleteCareEvent,
  useIgnoreCareEvent,
  useDeleteCareEvent,
  useMemberGriefTimeline,
  useCompleteGriefStage,
  useIgnoreGriefStage,
  useUndoGriefStage,
  useMemberAccidentTimeline,
  useCompleteAccidentFollowup,
  useIgnoreAccidentFollowup,
  useUndoAccidentFollowup,
  useMemberFinancialAid,
  useMarkAidDistributed,
  useIgnoreAidPayment,
  useStopAidSchedule,
} from '@/hooks/useCareEvents';
import { colors, eventTypeColors, engagementColors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';
import { useOverlayStore } from '@/stores/overlayStore';
import { CreateCareEventSheet } from '@/components/care-events';
import type { CareEvent, GriefStage, AccidentFollowup, FinancialAidSchedule } from '@/types';
import { formatDateToLocalTimezone, formatAge } from '@/lib/dateUtils';
import { formatCurrency } from '@/lib/formatting';

// ============================================================================
// TYPES
// ============================================================================

type TabType = 'timeline' | 'grief' | 'accident' | 'financial';

// ============================================================================
// HELPERS
// ============================================================================

function getEventIcon(type: string) {
  switch (type) {
    case 'birthday':
      return Cake;
    case 'grief_loss':
    case 'grief_stage':
      return Heart;
    case 'accident_illness':
    case 'accident_followup':
      return Hospital;
    case 'financial_aid':
      return DollarSign;
    case 'regular_contact':
      return Phone;
    case 'childbirth':
      return Baby;
    case 'new_house':
      return Home;
    default:
      return Calendar;
  }
}

function getEventColor(type: string) {
  return eventTypeColors[type as keyof typeof eventTypeColors] || colors.primary[500];
}

// Use centralized date formatting with Indonesian locale
const formatDate = (dateString: string | null | undefined) =>
  formatDateToLocalTimezone(dateString, 'medium');

// ============================================================================
// TAB BUTTON COMPONENT
// ============================================================================

interface TabButtonProps {
  label: string;
  isActive: boolean;
  count?: number;
  onPress: () => void;
  icon: React.ComponentType<{ size: number; color: string }>;
}

const TabButton = memo(function TabButton({
  label,
  isActive,
  count,
  onPress,
  icon: Icon,
}: TabButtonProps) {
  return (
    <Pressable
      className={`flex-1 flex-row items-center justify-center py-3 rounded-xl gap-1.5 ${
        isActive ? 'bg-primary-500' : 'bg-gray-100'
      }`}
      onPress={() => {
        haptics.tap();
        onPress();
      }}
    >
      <Icon size={16} color={isActive ? '#ffffff' : '#6b7280'} />
      <Text
        className={`text-xs font-semibold ${isActive ? 'text-white' : 'text-gray-600'}`}
        numberOfLines={1}
      >
        {label}
      </Text>
      {count !== undefined && count > 0 && (
        <View
          className={`min-w-[18px] h-[18px] rounded-full items-center justify-center px-1 ${
            isActive ? 'bg-white/30' : 'bg-gray-300'
          }`}
        >
          <Text
            className={`text-[10px] font-bold ${isActive ? 'text-white' : 'text-gray-600'}`}
          >
            {count}
          </Text>
        </View>
      )}
    </Pressable>
  );
});

// ============================================================================
// TIMELINE CARD
// ============================================================================

interface TimelineCardProps {
  event: CareEvent;
  onComplete: () => void;
  onIgnore: () => void;
  onDelete: () => void;
}

const TimelineCard = memo(function TimelineCard({
  event,
  onComplete,
  onIgnore,
  onDelete,
}: TimelineCardProps) {
  const { t } = useTranslation();
  const [showMenu, setShowMenu] = useState(false);
  const Icon = getEventIcon(event.event_type);
  const color = getEventColor(event.event_type);

  const statusIcon = event.completed ? CheckCircle : event.ignored ? XCircle : Clock;
  const StatusIcon = statusIcon;
  const statusColor = event.completed
    ? '#22c55e'
    : event.ignored
    ? '#9ca3af'
    : '#f59e0b';

  return (
    <View className="flex-row">
      {/* Timeline Line */}
      <View className="w-10 items-center">
        <View
          className="w-7 h-7 rounded-full items-center justify-center"
          style={{ backgroundColor: color }}
        >
          <Icon size={14} color="#ffffff" />
        </View>
        <View className="flex-1 w-0.5 bg-gray-200 my-1" />
      </View>

      {/* Content */}
      <View className="flex-1 bg-white rounded-xl p-4 mb-4 ml-2 shadow-sm">
        <View className="flex-row items-center justify-between mb-1">
          <Text className="text-xs text-gray-500">{formatDate(event.event_date)}</Text>
          <View className="flex-row items-center gap-2">
            <View
              className="flex-row items-center px-2 py-0.5 rounded-full gap-1"
              style={{ backgroundColor: `${statusColor}15` }}
            >
              <StatusIcon size={12} color={statusColor} />
              <Text className="text-[11px] font-medium" style={{ color: statusColor }}>
                {event.completed
                  ? t('common.completed')
                  : event.ignored
                  ? 'Ignored'
                  : t('common.pending')}
              </Text>
            </View>
            {/* Three dots menu */}
            <Pressable
              className="p-1 active:opacity-70"
              onPress={() => {
                haptics.tap();
                setShowMenu(true);
              }}
            >
              <MoreVertical size={16} color="#9ca3af" />
            </Pressable>
          </View>
        </View>

        <Text className="text-[15px] font-semibold text-gray-900">{event.title}</Text>
        <Text className="text-[13px] text-gray-500 mt-0.5">
          {t(`careEvents.types.${event.event_type}`, event.event_type)}
        </Text>

        {event.description && (
          <Text className="text-[13px] text-gray-600 mt-1" numberOfLines={2}>
            {event.description}
          </Text>
        )}

        {event.completed && event.completed_by_user_name && (
          <Text className="text-xs text-gray-400 mt-1 italic">
            {t('careEvents.completedBy', { name: event.completed_by_user_name })}
          </Text>
        )}

        {/* Actions for pending events */}
        {!event.completed && !event.ignored && (
          <View className="flex-row mt-3 gap-2">
            <Pressable
              className="flex-row items-center px-4 py-2 rounded-lg bg-success-500 gap-1 active:opacity-90"
              onPress={() => {
                haptics.success();
                onComplete();
              }}
            >
              <CheckCircle size={16} color="#ffffff" />
              <Text className="text-[13px] font-semibold text-white">
                {t('careEvents.complete')}
              </Text>
            </Pressable>
            <Pressable
              className="flex-row items-center px-4 py-2 rounded-lg bg-gray-200 gap-1 active:opacity-90"
              onPress={() => {
                haptics.tap();
                onIgnore();
              }}
            >
              <XCircle size={16} color="#6b7280" />
              <Text className="text-[13px] font-semibold text-gray-600">
                {t('careEvents.ignore')}
              </Text>
            </Pressable>
          </View>
        )}
      </View>

      {/* Delete Menu Modal */}
      {showMenu && (
        <Pressable
          className="absolute inset-0 z-50"
          style={{ left: -100, right: -100, top: -100, bottom: -100 }}
          onPress={() => setShowMenu(false)}
        >
          <View className="absolute right-4 top-8 bg-white rounded-xl shadow-lg border border-gray-200 py-2 min-w-[140px]">
            <Pressable
              className="flex-row items-center px-4 py-3 gap-2 active:bg-gray-100"
              onPress={() => {
                setShowMenu(false);
                Alert.alert(
                  'Delete Care Event',
                  'Are you sure you want to delete this care event? This will also delete all related follow-up stages.',
                  [
                    { text: 'Cancel', style: 'cancel' },
                    {
                      text: 'Delete',
                      style: 'destructive',
                      onPress: () => {
                        haptics.warning();
                        onDelete();
                      },
                    },
                  ]
                );
              }}
            >
              <Trash2 size={16} color="#dc2626" />
              <Text className="text-sm font-medium text-red-600">Delete</Text>
            </Pressable>
          </View>
        </Pressable>
      )}
    </View>
  );
});

// ============================================================================
// GRIEF STAGE CARD
// ============================================================================

interface GriefStageCardProps {
  stage: GriefStage;
  onComplete: () => void;
  onIgnore: () => void;
  onUndo: () => void;
}

const GriefStageCard = memo(function GriefStageCard({
  stage,
  onComplete,
  onIgnore,
  onUndo,
}: GriefStageCardProps) {
  const { t } = useTranslation();

  const isPending = !stage.completed && !stage.ignored;
  const isOverdue = isPending && new Date(stage.scheduled_date) < new Date();

  const statusColor = stage.completed
    ? '#22c55e'
    : stage.ignored
    ? '#9ca3af'
    : isOverdue
    ? '#ef4444'
    : '#f59e0b';

  const StatusIcon = stage.completed
    ? CheckCircle
    : stage.ignored
    ? Ban
    : isOverdue
    ? AlertCircle
    : Clock;

  return (
    <View className="bg-white rounded-xl p-4 mb-3 shadow-sm border-l-4" style={{ borderLeftColor: statusColor }}>
      <View className="flex-row items-start justify-between">
        <View className="flex-1">
          <Text className="text-[15px] font-semibold text-gray-900">
            {t(`careEvents.griefStages.${stage.stage_type || 'unknown'}`, { defaultValue: stage.stage_type || stage.stage })}
          </Text>
          <Text className="text-xs text-gray-500 mt-0.5">
            {formatDate(stage.scheduled_date)}
          </Text>
        </View>
        <View
          className="flex-row items-center px-2 py-1 rounded-full gap-1"
          style={{ backgroundColor: `${statusColor}15` }}
        >
          <StatusIcon size={12} color={statusColor} />
          <Text className="text-[11px] font-medium" style={{ color: statusColor }}>
            {stage.completed
              ? t('common.completed')
              : stage.ignored
              ? 'Ignored'
              : isOverdue
              ? t('common.overdue')
              : t('common.pending')}
          </Text>
        </View>
      </View>

      {stage.notes && (
        <Text className="text-[13px] text-gray-600 mt-2">{stage.notes}</Text>
      )}

      {stage.completed_by_user_name && (
        <Text className="text-xs text-gray-400 mt-1 italic">
          {t('careEvents.completedBy', { name: stage.completed_by_user_name })}
        </Text>
      )}

      {/* Actions */}
      <View className="flex-row mt-3 gap-2">
        {isPending ? (
          <>
            <Pressable
              className="flex-row items-center px-3 py-2 rounded-lg bg-success-500 gap-1 active:opacity-90"
              onPress={() => {
                haptics.success();
                onComplete();
              }}
            >
              <CheckCircle size={14} color="#ffffff" />
              <Text className="text-[12px] font-semibold text-white">Complete</Text>
            </Pressable>
            <Pressable
              className="flex-row items-center px-3 py-2 rounded-lg bg-gray-200 gap-1 active:opacity-90"
              onPress={() => {
                haptics.tap();
                onIgnore();
              }}
            >
              <XCircle size={14} color="#6b7280" />
              <Text className="text-[12px] font-semibold text-gray-600">Ignore</Text>
            </Pressable>
          </>
        ) : (
          <Pressable
            className="flex-row items-center px-3 py-2 rounded-lg bg-amber-100 gap-1 active:opacity-90"
            onPress={() => {
              haptics.tap();
              onUndo();
            }}
          >
            <RotateCcw size={14} color="#d97706" />
            <Text className="text-[12px] font-semibold text-amber-700">Undo</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
});

// ============================================================================
// ACCIDENT FOLLOWUP CARD
// ============================================================================

interface AccidentFollowupCardProps {
  followup: AccidentFollowup;
  onComplete: () => void;
  onIgnore: () => void;
  onUndo: () => void;
}

const AccidentFollowupCard = memo(function AccidentFollowupCard({
  followup,
  onComplete,
  onIgnore,
  onUndo,
}: AccidentFollowupCardProps) {
  const { t } = useTranslation();

  const isPending = !followup.completed && !followup.ignored;
  const isOverdue = isPending && new Date(followup.scheduled_date) < new Date();

  const statusColor = followup.completed
    ? '#22c55e'
    : followup.ignored
    ? '#9ca3af'
    : isOverdue
    ? '#ef4444'
    : '#f59e0b';

  const StatusIcon = followup.completed
    ? CheckCircle
    : followup.ignored
    ? Ban
    : isOverdue
    ? AlertCircle
    : Clock;

  return (
    <View className="bg-white rounded-xl p-4 mb-3 shadow-sm border-l-4" style={{ borderLeftColor: statusColor }}>
      <View className="flex-row items-start justify-between">
        <View className="flex-1">
          <Text className="text-[15px] font-semibold text-gray-900">
            {t(`careEvents.accidentStages.${followup.stage_type || followup.stage}`, { defaultValue: followup.stage_type || followup.stage })}
          </Text>
          <Text className="text-xs text-gray-500 mt-0.5">
            {formatDate(followup.scheduled_date)}
          </Text>
          {followup.hospital_name && (
            <View className="flex-row items-center mt-1 gap-1">
              <Hospital size={12} color="#6b7280" />
              <Text className="text-xs text-gray-500">{followup.hospital_name}</Text>
            </View>
          )}
        </View>
        <View
          className="flex-row items-center px-2 py-1 rounded-full gap-1"
          style={{ backgroundColor: `${statusColor}15` }}
        >
          <StatusIcon size={12} color={statusColor} />
          <Text className="text-[11px] font-medium" style={{ color: statusColor }}>
            {followup.completed
              ? t('common.completed')
              : followup.ignored
              ? 'Ignored'
              : isOverdue
              ? t('common.overdue')
              : t('common.pending')}
          </Text>
        </View>
      </View>

      {followup.notes && (
        <Text className="text-[13px] text-gray-600 mt-2">{followup.notes}</Text>
      )}

      {followup.completed_by_user_name && (
        <Text className="text-xs text-gray-400 mt-1 italic">
          {t('careEvents.completedBy', { name: followup.completed_by_user_name })}
        </Text>
      )}

      {/* Actions */}
      <View className="flex-row mt-3 gap-2">
        {isPending ? (
          <>
            <Pressable
              className="flex-row items-center px-3 py-2 rounded-lg bg-success-500 gap-1 active:opacity-90"
              onPress={() => {
                haptics.success();
                onComplete();
              }}
            >
              <CheckCircle size={14} color="#ffffff" />
              <Text className="text-[12px] font-semibold text-white">Complete</Text>
            </Pressable>
            <Pressable
              className="flex-row items-center px-3 py-2 rounded-lg bg-gray-200 gap-1 active:opacity-90"
              onPress={() => {
                haptics.tap();
                onIgnore();
              }}
            >
              <XCircle size={14} color="#6b7280" />
              <Text className="text-[12px] font-semibold text-gray-600">Ignore</Text>
            </Pressable>
          </>
        ) : (
          <Pressable
            className="flex-row items-center px-3 py-2 rounded-lg bg-amber-100 gap-1 active:opacity-90"
            onPress={() => {
              haptics.tap();
              onUndo();
            }}
          >
            <RotateCcw size={14} color="#d97706" />
            <Text className="text-[12px] font-semibold text-amber-700">Undo</Text>
          </Pressable>
        )}
      </View>
    </View>
  );
});

// ============================================================================
// FINANCIAL AID CARD
// ============================================================================

interface FinancialAidCardProps {
  schedule: FinancialAidSchedule;
  isPast?: boolean;
  isUpcoming?: boolean;
  isIgnored?: boolean;
  onMarkDistributed?: () => void;
  onIgnore?: () => void;
  onStop?: () => void;
}

const FinancialAidCard = memo(function FinancialAidCard({
  schedule,
  isPast,
  isUpcoming,
  isIgnored,
  onMarkDistributed,
  onIgnore,
  onStop,
}: FinancialAidCardProps) {
  const { t } = useTranslation();

  const statusColor = isPast
    ? '#22c55e'
    : isIgnored
    ? '#9ca3af'
    : isUpcoming
    ? '#3b82f6'
    : '#f59e0b';

  return (
    <View className="bg-white rounded-xl p-4 mb-3 shadow-sm border-l-4" style={{ borderLeftColor: statusColor }}>
      <View className="flex-row items-start justify-between">
        <View className="flex-1">
          <Text className="text-[15px] font-semibold text-gray-900">
            {schedule.title || t(`careEvents.aidTypes.${schedule.aid_type}`, schedule.aid_type)}
          </Text>
          <View className="flex-row items-center mt-1 gap-1">
            <DollarSign size={12} color="#6b7280" />
            <Text className="text-sm font-medium text-gray-700">
              {formatCurrency(schedule.amount)}
            </Text>
          </View>
          <Text className="text-xs text-gray-500 mt-0.5">
            {formatDate(schedule.scheduled_date || schedule.payment_date)}
          </Text>
        </View>
        <View
          className="px-2 py-1 rounded-full"
          style={{ backgroundColor: `${statusColor}15` }}
        >
          <Text className="text-[11px] font-medium" style={{ color: statusColor }}>
            {isPast ? 'Distributed' : isIgnored ? 'Ignored' : isUpcoming ? 'Upcoming' : 'Pending'}
          </Text>
        </View>
      </View>

      {schedule.notes && (
        <Text className="text-[13px] text-gray-600 mt-2">{schedule.notes}</Text>
      )}

      {schedule.distributed_by_user_name && (
        <Text className="text-xs text-gray-400 mt-1 italic">
          Distributed by {schedule.distributed_by_user_name}
        </Text>
      )}

      {/* Actions for upcoming */}
      {isUpcoming && (
        <View className="flex-row mt-3 gap-2">
          {onMarkDistributed && (
            <Pressable
              className="flex-row items-center px-3 py-2 rounded-lg bg-success-500 gap-1 active:opacity-90"
              onPress={() => {
                haptics.success();
                onMarkDistributed();
              }}
            >
              <CheckCircle size={14} color="#ffffff" />
              <Text className="text-[12px] font-semibold text-white">Mark Distributed</Text>
            </Pressable>
          )}
          {onIgnore && (
            <Pressable
              className="flex-row items-center px-3 py-2 rounded-lg bg-gray-200 gap-1 active:opacity-90"
              onPress={() => {
                haptics.tap();
                onIgnore();
              }}
            >
              <XCircle size={14} color="#6b7280" />
              <Text className="text-[12px] font-semibold text-gray-600">Ignore</Text>
            </Pressable>
          )}
          {onStop && schedule.frequency !== 'one_time' && (
            <Pressable
              className="flex-row items-center px-3 py-2 rounded-lg bg-red-100 gap-1 active:opacity-90"
              onPress={() => {
                Alert.alert(
                  'Stop Schedule',
                  'Are you sure you want to stop this recurring financial aid?',
                  [
                    { text: 'Cancel', style: 'cancel' },
                    {
                      text: 'Stop',
                      style: 'destructive',
                      onPress: () => {
                        haptics.warning();
                        onStop();
                      },
                    },
                  ]
                );
              }}
            >
              <Ban size={14} color="#dc2626" />
              <Text className="text-[12px] font-semibold text-red-600">Stop</Text>
            </Pressable>
          )}
        </View>
      )}
    </View>
  );
});

// ============================================================================
// EMPTY STATE COMPONENT
// ============================================================================

interface EmptyStateProps {
  icon: React.ComponentType<{ size: number; color: string }>;
  title: string;
  subtitle?: string;
}

const EmptyState = memo(function EmptyState({ icon: Icon, title, subtitle }: EmptyStateProps) {
  return (
    <View className="bg-white rounded-2xl p-12 items-center shadow-sm">
      <Icon size={40} color="#d1d5db" />
      <Text className="text-sm font-medium text-gray-500 mt-4 text-center">{title}</Text>
      {subtitle && (
        <Text className="text-xs text-gray-400 mt-1 text-center">{subtitle}</Text>
      )}
    </View>
  );
});

// ============================================================================
// MAIN SCREEN
// ============================================================================

function MemberDetailScreen() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const { id } = useLocalSearchParams<{ id: string }>();

  const showBottomSheet = useOverlayStore((state) => state.showBottomSheet);

  // Active tab state
  const [activeTab, setActiveTab] = useState<TabType>('timeline');

  // Member data
  const {
    data: member,
    isLoading: memberLoading,
    refetch: refetchMember,
  } = useMember(id);

  // Care events
  const {
    data: careEvents,
    isLoading: eventsLoading,
    refetch: refetchEvents,
    isRefetching,
  } = useMemberCareEvents(id);

  // Grief timeline
  const {
    data: griefTimeline,
    isLoading: griefLoading,
    refetch: refetchGrief,
  } = useMemberGriefTimeline(id);

  // Accident timeline
  const {
    data: accidentTimeline,
    isLoading: accidentLoading,
    refetch: refetchAccident,
  } = useMemberAccidentTimeline(id);

  // Financial aid
  const {
    data: financialAid,
    isLoading: aidLoading,
    refetch: refetchAid,
  } = useMemberFinancialAid(id);

  // Mutations
  const completeCareEvent = useCompleteCareEvent();
  const ignoreCareEvent = useIgnoreCareEvent();
  const deleteCareEvent = useDeleteCareEvent();
  const completeGriefStage = useCompleteGriefStage();
  const ignoreGriefStage = useIgnoreGriefStage();
  const undoGriefStage = useUndoGriefStage();
  const completeAccidentFollowup = useCompleteAccidentFollowup();
  const ignoreAccidentFollowup = useIgnoreAccidentFollowup();
  const undoAccidentFollowup = useUndoAccidentFollowup();
  const markAidDistributed = useMarkAidDistributed();
  const ignoreAidPayment = useIgnoreAidPayment();
  const stopAidSchedule = useStopAidSchedule();

  // Sort events by date (newest first) - filter out birthday events from timeline
  const sortedEvents = useMemo(() => {
    if (!careEvents) return [];
    return [...careEvents]
      .filter(e => e.event_type !== 'birthday')
      .sort((a, b) => new Date(b.event_date).getTime() - new Date(a.event_date).getTime());
  }, [careEvents]);

  // Find upcoming birthday event (within 7 days or overdue up to 7 days)
  const upcomingBirthday = useMemo(() => {
    if (!careEvents) return null;
    const birthdayEvent = careEvents.find(e => e.event_type === 'birthday' && !e.completed);
    if (!birthdayEvent) return null;

    const eventDate = new Date(birthdayEvent.event_date);
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    const thisYearBirthday = new Date(today.getFullYear(), eventDate.getMonth(), eventDate.getDate());

    // If birthday already passed this year, check next year
    if (thisYearBirthday < today) {
      thisYearBirthday.setFullYear(today.getFullYear() + 1);
    }

    const daysUntil = Math.ceil((thisYearBirthday.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));

    // Show if within next 7 days or overdue up to 7 days
    const writeoffLimit = 7;
    if (daysUntil <= 7 && daysUntil >= -writeoffLimit) {
      return {
        event: birthdayEvent,
        daysUntil,
        isToday: daysUntil === 0,
        isOverdue: daysUntil < 0,
        daysOverdue: daysUntil < 0 ? Math.abs(daysUntil) : 0,
      };
    }
    return null;
  }, [careEvents]);

  // Past financial aid - care events with event_type === 'financial_aid' (one-time payments already given)
  const pastFinancialAidEvents = useMemo(() => {
    if (!careEvents) return [];
    return careEvents.filter((e) => e.event_type === 'financial_aid');
  }, [careEvents]);

  // Categorize financial aid schedules (for recurring/scheduled payments)
  const categorizedAid = useMemo(() => {
    if (!financialAid) return { active: [], ignored: [] };

    const active: FinancialAidSchedule[] = [];
    const ignored: FinancialAidSchedule[] = [];

    financialAid.forEach((aid) => {
      if (aid.ignored || aid.is_active === false) {
        ignored.push(aid);
      } else {
        active.push(aid);
      }
    });

    return { active, ignored };
  }, [financialAid]);

  // Check if tabs should be shown
  const hasGriefData = griefTimeline && griefTimeline.length > 0;
  const hasAccidentData = accidentTimeline && accidentTimeline.length > 0;
  const hasFinancialData = (financialAid && financialAid.length > 0) || pastFinancialAidEvents.length > 0;

  // Count pending items for each tab
  const pendingGriefCount = useMemo(() => {
    if (!griefTimeline) return 0;
    return griefTimeline.filter((s) => !s.completed && !s.ignored).length;
  }, [griefTimeline]);

  const pendingAccidentCount = useMemo(() => {
    if (!accidentTimeline) return 0;
    return accidentTimeline.filter((s) => !s.completed && !s.ignored).length;
  }, [accidentTimeline]);

  const pendingAidCount = useMemo(() => {
    if (!financialAid) return 0;
    return financialAid.filter((s) => !s.ignored && s.is_active !== false).length;
  }, [financialAid]);

  const engagementColor = member
    ? engagementColors[member.engagement_status] || colors.gray[400]
    : colors.gray[400];

  // Handle call
  const handleCall = useCallback(() => {
    if (member?.phone) {
      haptics.tap();
      Linking.openURL(`tel:${member.phone}`);
    }
  }, [member]);

  // Handle WhatsApp
  const handleWhatsApp = useCallback(() => {
    if (member?.phone) {
      haptics.tap();
      let phone = member.phone.replace(/\D/g, '');
      if (phone.startsWith('0')) {
        phone = '62' + phone.substring(1);
      }
      Linking.openURL(`whatsapp://send?phone=${phone}`);
    }
  }, [member]);

  // Handle refresh
  const handleRefresh = useCallback(() => {
    refetchMember();
    refetchEvents();
    refetchGrief();
    refetchAccident();
    refetchAid();
  }, [refetchMember, refetchEvents, refetchGrief, refetchAccident, refetchAid]);

  // Handle add care event
  const handleAddCareEvent = useCallback(() => {
    if (!member) return;
    haptics.tap();
    showBottomSheet(CreateCareEventSheet, {
      memberId: member.id,
      memberName: member.name,
      campusId: member.campus_id,
      onSuccess: () => {
        handleRefresh();
      },
    });
  }, [member, showBottomSheet, handleRefresh]);

  // Handle edit member
  const handleEditMember = useCallback(() => {
    if (!member) return;
    haptics.tap();
    router.push(`/member/edit?id=${member.id}`);
  }, [member]);

  const isLoading = memberLoading || eventsLoading || griefLoading || accidentLoading || aidLoading;

  if (isLoading) {
    return (
      <View className="flex-1 justify-center items-center bg-gray-50">
        <ActivityIndicator size="large" color="#14b8a6" />
      </View>
    );
  }

  if (!member) {
    return (
      <View className="flex-1 justify-center items-center bg-gray-50 p-6">
        <Text className="text-base text-gray-600 mb-4">Member not found</Text>
        <Pressable
          className="px-4 py-2 bg-primary-500 rounded-xl"
          onPress={() => router.back()}
        >
          <Text className="text-white font-semibold">Go Back</Text>
        </Pressable>
      </View>
    );
  }

  // Determine which tabs to show
  const tabs: { type: TabType; label: string; icon: any; count?: number; show: boolean }[] = [
    { type: 'timeline', label: 'Timeline', icon: ClipboardList, show: true },
    { type: 'grief', label: 'Grief', icon: Heart, count: pendingGriefCount, show: !!hasGriefData },
    { type: 'accident', label: 'Accident', icon: Hospital, count: pendingAccidentCount, show: !!hasAccidentData },
    { type: 'financial', label: 'Aid', icon: DollarSign, count: pendingAidCount, show: !!hasFinancialData },
  ];

  const visibleTabs = tabs.filter((tab) => tab.show);

  return (
    <View className="flex-1 bg-gray-50">
      {/* Header */}
      <View
        className="flex-row items-center px-4 pb-4 bg-white border-b border-gray-200"
        style={{ paddingTop: insets.top + 8 }}
      >
        <Pressable
          className="w-10 h-10 items-center justify-center"
          onPress={() => {
            haptics.tap();
            router.back();
          }}
        >
          <ArrowLeft size={24} color="#111827" />
        </Pressable>
        <Text className="flex-1 text-lg font-semibold text-gray-900 text-center" numberOfLines={1}>
          {member.name}
        </Text>
        <Pressable
          className="w-10 h-10 items-center justify-center active:opacity-70"
          onPress={handleEditMember}
        >
          <Edit3 size={20} color="#0d9488" />
        </Pressable>
      </View>

      <ScrollView
        className="flex-1"
        contentContainerClassName="p-6"
        showsVerticalScrollIndicator={false}
        refreshControl={
          <RefreshControl
            refreshing={isRefetching}
            onRefresh={handleRefresh}
            tintColor="#14b8a6"
          />
        }
      >
        {/* Profile Card */}
        <Animated.View
          entering={FadeInDown.delay(100).duration(400)}
          className="bg-white rounded-2xl p-6 mb-4 shadow-sm"
        >
          <View className="flex-row items-center mb-6">
            {member.photo_url ? (
              <Image
                source={{ uri: member.photo_url }}
                className="w-[72px] h-[72px] rounded-full"
              />
            ) : (
              <View className="w-[72px] h-[72px] rounded-full bg-gray-100 items-center justify-center">
                <User size={40} color="#9ca3af" />
              </View>
            )}
            <View className="flex-1 ml-4">
              <Text className="text-[22px] font-bold text-gray-900 mb-1">{member.name}</Text>
              <View
                className="flex-row items-center self-start px-3 py-1 rounded-full gap-1.5"
                style={{ backgroundColor: `${engagementColor}20` }}
              >
                <View
                  className="w-2 h-2 rounded-full"
                  style={{ backgroundColor: engagementColor }}
                />
                <Text className="text-[13px] font-medium" style={{ color: engagementColor }}>
                  {t(`members.engagement.${member.engagement_status}`)}
                </Text>
              </View>
            </View>
          </View>

          {/* Contact Buttons */}
          <View className="flex-row gap-3">
            <Pressable
              className="flex-1 flex-row items-center justify-center py-3 rounded-xl bg-primary-50 gap-1 active:opacity-80"
              onPress={handleCall}
            >
              <Phone size={20} color="#0d9488" />
              <Text className="text-sm font-semibold text-primary-600">
                {t('memberDetail.call')}
              </Text>
            </Pressable>
            <Pressable
              className="flex-1 flex-row items-center justify-center py-3 rounded-xl bg-success-50 gap-1 active:opacity-80"
              onPress={handleWhatsApp}
            >
              <MessageCircle size={20} color="#16a34a" />
              <Text className="text-sm font-semibold text-success-600">
                {t('memberDetail.whatsapp')}
              </Text>
            </Pressable>
          </View>
        </Animated.View>

        {/* Upcoming Birthday Banner */}
        {upcomingBirthday && (
          <Animated.View
            entering={FadeInDown.delay(150).duration(400)}
            className="bg-amber-50 border border-amber-200 rounded-2xl p-4 mb-4"
          >
            <View className="flex-row items-center">
              <View className="w-10 h-10 rounded-full bg-amber-100 items-center justify-center">
                <Cake size={20} color="#f59e0b" />
              </View>
              <View className="flex-1 ml-3">
                <Text className="text-sm font-semibold text-amber-800">
                  {upcomingBirthday.isToday
                    ? `Birthday Today!`
                    : upcomingBirthday.isOverdue
                    ? `Birthday was ${upcomingBirthday.daysOverdue} day${upcomingBirthday.daysOverdue !== 1 ? 's' : ''} ago`
                    : `Birthday in ${upcomingBirthday.daysUntil} day${upcomingBirthday.daysUntil !== 1 ? 's' : ''}`}
                </Text>
                <Text className="text-xs text-amber-600 mt-0.5">
                  {formatDate(upcomingBirthday.event.event_date)} - {member.name} turns {formatAge(member.birth_date)}
                </Text>
              </View>
              <Pressable
                className="px-3 py-2 bg-amber-500 rounded-lg active:opacity-80"
                onPress={() => {
                  haptics.success();
                  completeCareEvent.mutate(upcomingBirthday.event.id);
                }}
              >
                <Text className="text-xs font-semibold text-white">Complete</Text>
              </Pressable>
            </View>
          </Animated.View>
        )}

        {/* Profile Info */}
        <Animated.View
          entering={FadeInDown.delay(200).duration(400)}
          className="bg-white rounded-2xl p-6 mb-4 shadow-sm"
        >
          <Text className="text-base font-bold text-gray-900 mb-4">
            {t('memberDetail.profile')}
          </Text>

          {member.phone && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <Phone size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.phone')}
              </Text>
              <Text className="flex-1 text-sm text-gray-900">{member.phone}</Text>
            </View>
          )}

          {member.birth_date && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <Calendar size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.birthDate')}
              </Text>
              <Text className="flex-1 text-sm text-gray-900">
                {formatDate(member.birth_date)} ({formatAge(member.birth_date)})
              </Text>
            </View>
          )}

          {member.gender && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <Users size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.gender', { defaultValue: 'Gender' })}
              </Text>
              <Text className="flex-1 text-sm text-gray-900 capitalize">
                {t(`members.gender.${member.gender}`, { defaultValue: member.gender })}
              </Text>
            </View>
          )}

          {member.category && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <Tag size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.category', { defaultValue: 'Category' })}
              </Text>
              <Text className="flex-1 text-sm text-gray-900 capitalize">
                {t(`members.category.${member.category}`, { defaultValue: member.category })}
              </Text>
            </View>
          )}

          {member.marital_status && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <Heart size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.maritalStatus', { defaultValue: 'Marital Status' })}
              </Text>
              <Text className="flex-1 text-sm text-gray-900 capitalize">
                {t(`members.maritalStatus.${member.marital_status}`, { defaultValue: member.marital_status })}
              </Text>
            </View>
          )}

          {member.blood_type && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <Hospital size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.bloodType', { defaultValue: 'Blood Type' })}
              </Text>
              <Text className="flex-1 text-sm text-gray-900">{member.blood_type}</Text>
            </View>
          )}

          {member.membership_status && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <User size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.status', { defaultValue: 'Status' })}
              </Text>
              <Text className="flex-1 text-sm text-gray-900 capitalize">
                {t(`members.membershipStatus.${member.membership_status}`, { defaultValue: member.membership_status })}
              </Text>
            </View>
          )}

          {member.address && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <MapPin size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.address')}
              </Text>
              <Text className="flex-1 text-sm text-gray-900" numberOfLines={2}>
                {member.address}
              </Text>
            </View>
          )}

          {member.notes && (
            <View className="flex-row items-start py-3 border-b border-gray-100">
              <FileText size={18} color="#9ca3af" />
              <Text className="w-[90px] text-sm text-gray-500 ml-3">
                {t('memberDetail.fields.notes')}
              </Text>
              <Text className="flex-1 text-sm text-gray-900" numberOfLines={3}>
                {member.notes}
              </Text>
            </View>
          )}
        </Animated.View>

        {/* Tab Navigation */}
        {visibleTabs.length > 1 && (
          <Animated.View
            entering={FadeInDown.delay(250).duration(400)}
            className="flex-row gap-2 mb-4"
          >
            {visibleTabs.map((tab) => (
              <TabButton
                key={tab.type}
                label={tab.label}
                icon={tab.icon}
                count={tab.count}
                isActive={activeTab === tab.type}
                onPress={() => setActiveTab(tab.type)}
              />
            ))}
          </Animated.View>
        )}

        {/* Tab Content */}
        <Animated.View entering={FadeIn.duration(300)}>
          {/* Timeline Tab */}
          {activeTab === 'timeline' && (
            <View>
              <View className="flex-row items-center justify-between mb-4">
                <Text className="text-base font-bold text-gray-900">
                  {t('memberDetail.timeline')}
                </Text>
                <Pressable
                  className="flex-row items-center bg-primary-500 px-4 py-2 rounded-xl gap-1 active:opacity-90"
                  onPress={handleAddCareEvent}
                >
                  <Plus size={18} color="#ffffff" />
                  <Text className="text-sm font-semibold text-white">
                    {t('memberDetail.addCareEvent')}
                  </Text>
                </Pressable>
              </View>

              {sortedEvents.length === 0 ? (
                <EmptyState
                  icon={Calendar}
                  title={t('memberDetail.noCareEvents')}
                />
              ) : (
                <View>
                  {sortedEvents.map((event) => (
                    <TimelineCard
                      key={event.id}
                      event={event}
                      onComplete={() => completeCareEvent.mutate(event.id)}
                      onIgnore={() => ignoreCareEvent.mutate(event.id)}
                      onDelete={() => deleteCareEvent.mutate(event.id)}
                    />
                  ))}
                </View>
              )}
            </View>
          )}

          {/* Grief Tab */}
          {activeTab === 'grief' && hasGriefData && (
            <View>
              <Text className="text-base font-bold text-gray-900 mb-4">
                Grief Support Timeline
              </Text>
              <Text className="text-xs text-gray-500 mb-4">
                Auto-generated follow-up schedule for grief/loss care
              </Text>

              {griefTimeline?.map((stage) => (
                <GriefStageCard
                  key={stage.id}
                  stage={stage}
                  onComplete={() => completeGriefStage.mutate(stage.id)}
                  onIgnore={() => ignoreGriefStage.mutate(stage.id)}
                  onUndo={() => undoGriefStage.mutate(stage.id)}
                />
              ))}
            </View>
          )}

          {/* Accident Tab */}
          {activeTab === 'accident' && hasAccidentData && (
            <View>
              <Text className="text-base font-bold text-gray-900 mb-4">
                Accident/Illness Follow-up
              </Text>
              <Text className="text-xs text-gray-500 mb-4">
                3-step follow-up schedule for hospital visits
              </Text>

              {accidentTimeline?.map((followup) => (
                <AccidentFollowupCard
                  key={followup.id}
                  followup={followup}
                  onComplete={() => completeAccidentFollowup.mutate(followup.id)}
                  onIgnore={() => ignoreAccidentFollowup.mutate(followup.id)}
                  onUndo={() => undoAccidentFollowup.mutate(followup.id)}
                />
              ))}
            </View>
          )}

          {/* Financial Aid Tab */}
          {activeTab === 'financial' && hasFinancialData && (
            <View>
              {/* Past Financial Aid Given (one-time payments from care events) */}
              {pastFinancialAidEvents.length > 0 && (
                <>
                  <Text className="text-base font-bold text-gray-900 mb-3">
                    Past Financial Aid Given
                  </Text>
                  <Text className="text-xs text-gray-500 mb-3">
                    One-time financial aid that has been distributed
                  </Text>
                  {pastFinancialAidEvents.map((event) => (
                    <View
                      key={event.id}
                      className="bg-white rounded-xl p-4 mb-3 shadow-sm border-l-4"
                      style={{ borderLeftColor: event.ignored ? '#9ca3af' : '#22c55e' }}
                    >
                      <View className="flex-row items-start justify-between">
                        <View className="flex-1">
                          <Text className="text-[15px] font-semibold text-gray-900">
                            {event.title || 'Financial Aid'}
                          </Text>
                          <View className="flex-row items-center mt-1 gap-1">
                            <DollarSign size={12} color="#6b7280" />
                            <Text className="text-sm font-medium text-gray-700">
                              {formatCurrency(event.aid_amount || 0)}
                            </Text>
                          </View>
                          <Text className="text-xs text-gray-500 mt-0.5">
                            {t(`careEvents.aidTypes.${event.aid_type || 'other'}`, { defaultValue: event.aid_type || 'Other' })} • {formatDate(event.event_date)}
                          </Text>
                          {event.aid_notes && (
                            <Text className="text-xs text-gray-500 mt-1 italic">{event.aid_notes}</Text>
                          )}
                        </View>
                        <View
                          className="px-2 py-1 rounded-full"
                          style={{ backgroundColor: event.ignored ? '#f3f4f6' : '#dcfce7' }}
                        >
                          <Text
                            className="text-[11px] font-medium"
                            style={{ color: event.ignored ? '#9ca3af' : '#22c55e' }}
                          >
                            {event.ignored ? 'Ignored' : 'Given'}
                          </Text>
                        </View>
                      </View>
                    </View>
                  ))}
                </>
              )}

              {/* Upcoming Scheduled Payments (active aid schedules) */}
              {categorizedAid.active.length > 0 && (
                <>
                  <Text className={`text-base font-bold text-gray-900 mb-3 ${pastFinancialAidEvents.length > 0 ? 'mt-4' : ''}`}>
                    Upcoming Scheduled Payments
                  </Text>
                  <Text className="text-xs text-gray-500 mb-3">
                    Recurring financial aid with scheduled payments
                  </Text>
                  {categorizedAid.active.map((aid) => (
                    <FinancialAidCard
                      key={aid.id}
                      schedule={aid}
                      isUpcoming
                      onMarkDistributed={() => markAidDistributed.mutate(aid.id)}
                      onIgnore={() => ignoreAidPayment.mutate(aid.id)}
                      onStop={() => stopAidSchedule.mutate(aid.id)}
                    />
                  ))}
                </>
              )}

              {/* Ignored/Stopped Schedules */}
              {categorizedAid.ignored.length > 0 && (
                <>
                  <Text className="text-base font-bold text-gray-900 mb-3 mt-4">
                    Stopped/Ignored Schedules
                  </Text>
                  {categorizedAid.ignored.map((aid) => (
                    <FinancialAidCard
                      key={aid.id}
                      schedule={aid}
                      isIgnored
                    />
                  ))}
                </>
              )}
            </View>
          )}
        </Animated.View>

        <View className="h-24" />
      </ScrollView>
    </View>
  );
}

export default memo(MemberDetailScreen);
