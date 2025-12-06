/**
 * Create Care Event Sheet
 *
 * Multi-step bottom sheet for creating care events
 * Matches webapp form fields exactly
 *
 * Flow when member is provided: type -> form
 * Flow when no member: member -> type -> form
 * Flow with initialEventType: (member if needed) -> form
 */

import React, { useState, useCallback, useMemo, useEffect, useRef } from 'react';
import {
  View,
  Text,
  Pressable,
  ScrollView,
  TextInput,
  Platform,
  KeyboardAvoidingView,
  ActivityIndicator,
  Keyboard,
  Dimensions,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import {
  X,
  ChevronLeft,
  Calendar,
  Cake,
  Heart,
  Hospital,
  DollarSign,
  Phone,
  Baby,
  Home,
  Check,
  ChevronDown,
  Search,
  Users,
  ChevronRight,
} from 'lucide-react-native';
import * as Haptics from 'expo-haptics';
import Toast from 'react-native-toast-message';
import DateTimePicker from '@react-native-community/datetimepicker';

import { eventTypeColors } from '@/constants/theme';
import {
  EVENT_TYPES,
  GRIEF_RELATIONSHIPS,
  AID_TYPES,
  type EventType,
  type GriefRelationship,
  type AidType,
} from '@/constants/api';
import { useCreateCareEvent } from '@/hooks/useCareEvents';
import { useMembers } from '@/hooks/useMembers';
import type { CreateCareEventRequest } from '@/types';
import type { CreateCareEventPayload, OverlayComponentProps } from '@/stores/overlayStore';

// ============================================================================
// CONSTANTS
// ============================================================================

const EVENT_TYPE_CONFIG: Record<EventType, { icon: any; color: string }> = {
  birthday: { icon: Cake, color: eventTypeColors.birthday },
  grief_loss: { icon: Heart, color: eventTypeColors.grief_loss },
  accident_illness: { icon: Hospital, color: eventTypeColors.accident_illness },
  financial_aid: { icon: DollarSign, color: eventTypeColors.financial_aid },
  regular_contact: { icon: Phone, color: eventTypeColors.regular_contact },
  childbirth: { icon: Baby, color: eventTypeColors.childbirth },
  new_house: { icon: Home, color: eventTypeColors.new_house },
};

// Event types shown in the form (excluding birthday which is auto-created)
const FORM_EVENT_TYPES: EventType[] = [
  'childbirth',
  'grief_loss',
  'new_house',
  'accident_illness',
  'financial_aid',
  'regular_contact',
];

type ScheduleFrequency = 'one_time' | 'weekly' | 'monthly' | 'annually';

const SCHEDULE_FREQUENCIES: { value: ScheduleFrequency; label: string }[] = [
  { value: 'one_time', label: 'One-time Payment (already given)' },
  { value: 'weekly', label: 'Weekly Schedule (future payments)' },
  { value: 'monthly', label: 'Monthly Schedule (future payments)' },
  { value: 'annually', label: 'Annual Schedule (future payments)' },
];

const DAYS_OF_WEEK = [
  { value: 'monday', label: 'Monday' },
  { value: 'tuesday', label: 'Tuesday' },
  { value: 'wednesday', label: 'Wednesday' },
  { value: 'thursday', label: 'Thursday' },
  { value: 'friday', label: 'Friday' },
  { value: 'saturday', label: 'Saturday' },
  { value: 'sunday', label: 'Sunday' },
];

const MONTHS = [
  { value: 1, label: 'January' },
  { value: 2, label: 'February' },
  { value: 3, label: 'March' },
  { value: 4, label: 'April' },
  { value: 5, label: 'May' },
  { value: 6, label: 'June' },
  { value: 7, label: 'July' },
  { value: 8, label: 'August' },
  { value: 9, label: 'September' },
  { value: 10, label: 'October' },
  { value: 11, label: 'November' },
  { value: 12, label: 'December' },
];

type Step = 'member' | 'type' | 'form';

// ============================================================================
// HELPER COMPONENTS
// ============================================================================

interface PickerProps {
  label: string;
  value: string;
  onPress: () => void;
}

function Picker({ label, value, onPress }: PickerProps) {
  return (
    <Pressable
      onPress={onPress}
      className="flex-row items-center justify-between bg-gray-50 border border-gray-200 rounded-xl px-4 py-3.5"
    >
      <Text className="text-gray-900">{value || label}</Text>
      <ChevronDown size={18} color="#9ca3af" />
    </Pressable>
  );
}

interface OptionSelectorProps {
  options: { value: string | number; label: string }[];
  selectedValue: string | number | null;
  onSelect: (value: any) => void;
  onClose: () => void;
  title: string;
}

function OptionSelector({ options, selectedValue, onSelect, onClose, title }: OptionSelectorProps) {
  const insets = useSafeAreaInsets();

  return (
    <View className="bg-white" style={{ minHeight: 300 }}>
      <View className="flex-row items-center px-5 py-4 border-b border-gray-200">
        <Pressable onPress={onClose} className="p-1" hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}>
          <ChevronLeft size={22} color="#4b5563" />
        </Pressable>
        <Text className="flex-1 text-lg font-bold text-gray-900 ml-2">{title}</Text>
      </View>
      <ScrollView
        style={{ maxHeight: 400 }}
        contentContainerStyle={{ padding: 16, paddingBottom: insets.bottom + 16 }}
        showsVerticalScrollIndicator={true}
      >
        {options.map((option) => (
          <Pressable
            key={option.value}
            onPress={() => {
              onSelect(option.value);
              onClose();
            }}
            className={`flex-row items-center px-4 py-4 rounded-xl mb-2 ${
              selectedValue === option.value ? 'bg-primary-50 border border-primary-200' : 'bg-gray-50'
            }`}
          >
            <Text
              className={`flex-1 text-base ${
                selectedValue === option.value ? 'text-primary-700 font-semibold' : 'text-gray-900'
              }`}
            >
              {option.label}
            </Text>
            {selectedValue === option.value && <Check size={18} color="#0d9488" />}
          </Pressable>
        ))}
      </ScrollView>
    </View>
  );
}

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export function CreateCareEventSheet({
  payload,
  onClose,
}: OverlayComponentProps<CreateCareEventPayload>) {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const createMutation = useCreateCareEvent();

  // Determine initial step based on payload
  const needsMemberSelection = !payload?.memberId;
  const hasInitialEventType = !!payload?.initialEventType;

  // Member selection state
  const [selectedMember, setSelectedMember] = useState<{ id: string; name: string } | null>(
    payload?.memberId && payload?.memberName
      ? { id: payload.memberId, name: payload.memberName }
      : null
  );
  const [memberSearch, setMemberSearch] = useState('');

  // Fetch members for selection
  const { data: membersData, isLoading: membersLoading } = useMembers({ search: memberSearch });
  const members = useMemo(() => {
    if (!membersData?.pages) return [];
    return membersData.pages.flatMap((page) => page.members);
  }, [membersData]);

  // Form state - determine initial step
  const getInitialStep = (): Step => {
    if (needsMemberSelection) return 'member';
    if (hasInitialEventType) return 'form';
    return 'type';
  };

  const [step, setStep] = useState<Step>(getInitialStep());
  const [eventType, setEventType] = useState<EventType | null>(payload?.initialEventType || null);
  const [eventDate, setEventDate] = useState(new Date());
  const [description, setDescription] = useState('');
  const [showDatePicker, setShowDatePicker] = useState(false);

  // Option selector state
  const [showOptionSelector, setShowOptionSelector] = useState<string | null>(null);

  // Type-specific fields
  const [griefRelationship, setGriefRelationship] = useState<GriefRelationship>('other');
  const [hospitalName, setHospitalName] = useState('');

  // Financial aid fields
  const [aidTitle, setAidTitle] = useState('');
  const [aidType, setAidType] = useState<AidType>('education');
  const [aidAmount, setAidAmount] = useState('');
  const [scheduleFrequency, setScheduleFrequency] = useState<ScheduleFrequency>('one_time');
  const [paymentDate, setPaymentDate] = useState(new Date());
  const [showPaymentDatePicker, setShowPaymentDatePicker] = useState(false);
  const [dayOfWeek, setDayOfWeek] = useState('monday');
  const [dayOfMonth, setDayOfMonth] = useState('1');
  const [startMonth, setStartMonth] = useState(new Date().getMonth() + 1);
  const [startYear, setStartYear] = useState(new Date().getFullYear());
  const [endMonth, setEndMonth] = useState<number | null>(null);
  const [endYear, setEndYear] = useState<number | null>(null);
  const [monthOfYear, setMonthOfYear] = useState(1);
  const [scheduleEndDate, setScheduleEndDate] = useState<Date | null>(null);
  const [showEndDatePicker, setShowEndDatePicker] = useState(false);

  // Generate year options
  const yearOptions = useMemo(() => {
    const currentYear = new Date().getFullYear();
    return Array.from({ length: 10 }, (_, i) => ({
      value: currentYear + i,
      label: (currentYear + i).toString(),
    }));
  }, []);

  const handleSelectMember = useCallback((member: { id: string; name: string }) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setSelectedMember(member);
    // Go to type selection or form if event type is pre-selected
    if (hasInitialEventType) {
      setStep('form');
    } else {
      setStep('type');
    }
  }, [hasInitialEventType]);

  const handleSelectType = useCallback((type: EventType) => {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    setEventType(type);
    setStep('form');
  }, []);

  const handleBack = useCallback(() => {
    if (showOptionSelector) {
      setShowOptionSelector(null);
      return;
    }
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);

    // Navigate back based on current step
    if (step === 'form') {
      // Go back to type selection or member if no type was pre-selected
      if (hasInitialEventType && needsMemberSelection) {
        setStep('member');
      } else {
        setStep('type');
      }
    } else if (step === 'type') {
      // Go back to member selection if needed
      if (needsMemberSelection) {
        setStep('member');
      }
    }
  }, [showOptionSelector, step, hasInitialEventType, needsMemberSelection]);

  const handleDateChange = useCallback((_: any, selectedDate?: Date) => {
    setShowDatePicker(Platform.OS === 'ios');
    if (selectedDate) {
      setEventDate(selectedDate);
    }
  }, []);

  const handlePaymentDateChange = useCallback((_: any, selectedDate?: Date) => {
    setShowPaymentDatePicker(Platform.OS === 'ios');
    if (selectedDate) {
      setPaymentDate(selectedDate);
    }
  }, []);

  const handleEndDateChange = useCallback((_: any, selectedDate?: Date) => {
    setShowEndDatePicker(Platform.OS === 'ios');
    if (selectedDate) {
      setScheduleEndDate(selectedDate);
    }
  }, []);

  const handleSubmit = useCallback(async () => {
    if (!eventType || !selectedMember?.id || !payload?.campusId) return;

    // Validate financial aid
    if (eventType === 'financial_aid') {
      if (!aidTitle.trim()) {
        Toast.show({
          type: 'error',
          text1: 'Title Required',
          text2: 'Please enter an aid name/title',
        });
        return;
      }
      if (!aidAmount || parseFloat(aidAmount) <= 0) {
        Toast.show({
          type: 'error',
          text1: 'Amount Required',
          text2: 'Please enter a valid amount',
        });
        return;
      }
    }

    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);

    const request: CreateCareEventRequest = {
      member_id: selectedMember.id,
      campus_id: payload.campusId,
      event_type: eventType,
      event_date: eventType === 'financial_aid'
        ? (scheduleFrequency === 'one_time' ? paymentDate.toISOString().split('T')[0] : new Date().toISOString().split('T')[0])
        : eventDate.toISOString().split('T')[0],
      title: eventType === 'financial_aid' ? aidTitle : t(`careEvents.types.${eventType}`),
      description: description || undefined,
    };

    // Type-specific fields
    if (eventType === 'grief_loss') {
      request.grief_relationship = griefRelationship;
    } else if (eventType === 'accident_illness') {
      if (hospitalName) request.hospital_name = hospitalName;
    } else if (eventType === 'financial_aid') {
      request.aid_type = aidType;
      request.aid_amount = parseFloat(aidAmount);

      // Add scheduling fields to request (extend type as needed)
      const extendedRequest = request as any;
      extendedRequest.schedule_frequency = scheduleFrequency;

      if (scheduleFrequency === 'one_time') {
        extendedRequest.payment_date = paymentDate.toISOString().split('T')[0];
      } else if (scheduleFrequency === 'weekly') {
        extendedRequest.day_of_week = dayOfWeek;
        if (scheduleEndDate) {
          extendedRequest.schedule_end_date = scheduleEndDate.toISOString().split('T')[0];
        }
      } else if (scheduleFrequency === 'monthly') {
        extendedRequest.start_month = startMonth;
        extendedRequest.start_year = startYear;
        extendedRequest.day_of_month = parseInt(dayOfMonth) || 1;
        if (endMonth) extendedRequest.end_month = endMonth;
        if (endYear) extendedRequest.end_year = endYear;
      } else if (scheduleFrequency === 'annually') {
        extendedRequest.month_of_year = monthOfYear;
        if (endYear) {
          extendedRequest.schedule_end_date = `${endYear}-12-31`;
        }
      }
    }

    try {
      await createMutation.mutateAsync(request);
      Toast.show({
        type: 'success',
        text1: t('notifications.eventCreated'),
      });
      payload.onSuccess?.();
      onClose();
    } catch (error) {
      Toast.show({
        type: 'error',
        text1: t('common.error'),
        text2: t('notifications.createError', 'Failed to create event'),
      });
    }
  }, [
    eventType,
    selectedMember,
    payload?.campusId,
    payload?.onSuccess,
    eventDate,
    description,
    griefRelationship,
    hospitalName,
    aidTitle,
    aidType,
    aidAmount,
    scheduleFrequency,
    paymentDate,
    dayOfWeek,
    dayOfMonth,
    startMonth,
    startYear,
    endMonth,
    endYear,
    monthOfYear,
    scheduleEndDate,
    createMutation,
    t,
    onClose,
  ]);

  // ============================================================================
  // RENDER TYPE SELECTOR
  // ============================================================================

  // ============================================================================
  // RENDER MEMBER SELECTOR
  // ============================================================================

  const renderMemberSelector = () => (
    <>
      {/* Header */}
      <View className="flex-row items-center px-5 py-4 border-b border-gray-200">
        <View className="flex-1">
          <Text className="text-xl font-bold text-gray-900">
            {t('careEvents.create')}
          </Text>
          <Text className="text-sm text-gray-500 mt-1">
            {hasInitialEventType
              ? t(`careEvents.types.${payload?.initialEventType}`)
              : t('members.selectMember', 'Select a member')}
          </Text>
        </View>
        <Pressable
          onPress={onClose}
          className="p-2"
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <X size={22} color="#9ca3af" />
        </Pressable>
      </View>

      <View className="px-5 pt-4">
        {/* Search */}
        <View className="flex-row items-center bg-gray-100 rounded-xl px-4 py-3 mb-4">
          <Search size={18} color="#9ca3af" />
          <TextInput
            className="flex-1 ml-3 text-base text-gray-900"
            placeholder={t('members.searchPlaceholder', 'Search members...')}
            placeholderTextColor="#9ca3af"
            value={memberSearch}
            onChangeText={setMemberSearch}
          />
        </View>

        {/* Member list */}
        <ScrollView
          style={{ maxHeight: 350 }}
          showsVerticalScrollIndicator
          contentContainerStyle={{ paddingBottom: insets.bottom + 16 }}
        >
          {membersLoading ? (
            <View className="items-center py-8">
              <ActivityIndicator color="#14b8a6" />
            </View>
          ) : members.length === 0 ? (
            <View className="items-center py-8">
              <Users size={32} color="#d1d5db" />
              <Text className="text-gray-500 mt-2">
                {t('emptyState.noMembers', 'No members found')}
              </Text>
            </View>
          ) : (
            members.slice(0, 15).map((member) => (
              <Pressable
                key={member.id}
                className="flex-row items-center bg-gray-50 rounded-xl p-4 mb-2 active:bg-gray-100"
                onPress={() => handleSelectMember({ id: member.id, name: member.name })}
              >
                <View className="w-10 h-10 rounded-full bg-teal-100 items-center justify-center">
                  <Text className="text-lg font-semibold text-teal-700">
                    {member.name.charAt(0).toUpperCase()}
                  </Text>
                </View>
                <View className="flex-1 ml-3">
                  <Text className="text-base font-medium text-gray-900">{member.name}</Text>
                  {member.phone && (
                    <Text className="text-sm text-gray-500">{member.phone}</Text>
                  )}
                </View>
                <ChevronRight size={18} color="#9ca3af" />
              </Pressable>
            ))
          )}
        </ScrollView>
      </View>
    </>
  );

  // ============================================================================
  // RENDER TYPE SELECTOR
  // ============================================================================

  const renderTypeSelector = () => (
    <>
      {/* Header */}
      <View className="flex-row items-center px-5 py-4 border-b border-gray-200">
        {needsMemberSelection && (
          <Pressable
            onPress={handleBack}
            className="p-1 mr-2"
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <ChevronLeft size={22} color="#4b5563" />
          </Pressable>
        )}
        <View className="flex-1">
          <Text className="text-xl font-bold text-gray-900">
            {t('careEvents.create')}
          </Text>
          <Text className="text-sm text-gray-500 mt-1">
            {selectedMember?.name || payload?.memberName}
          </Text>
        </View>
        <Pressable
          onPress={onClose}
          className="p-2"
          hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
        >
          <X size={22} color="#9ca3af" />
        </Pressable>
      </View>

      {/* Event type grid */}
      <View className="flex-row flex-wrap px-4 pt-5 pb-10">
        {FORM_EVENT_TYPES.map((type) => {
          const config = EVENT_TYPE_CONFIG[type];
          const Icon = config.icon;
          return (
            <Pressable
              key={type}
              onPress={() => handleSelectType(type)}
              className="w-1/3 items-center py-4 px-2 active:opacity-70"
            >
              <View
                className="w-14 h-14 rounded-2xl items-center justify-center"
                style={{ backgroundColor: config.color + '15' }}
              >
                <Icon size={28} color={config.color} />
              </View>
              <Text className="text-gray-700 font-medium text-sm text-center mt-2">
                {t(`careEvents.types.${type}`)}
              </Text>
            </Pressable>
          );
        })}
      </View>
    </>
  );

  // ============================================================================
  // RENDER FORM
  // ============================================================================

  const renderForm = () => {
    const config = eventType ? EVENT_TYPE_CONFIG[eventType] : null;
    const TypeIcon = config?.icon;

    // Handle option selector overlay
    if (showOptionSelector) {
      let options: { value: string | number; label: string }[] = [];
      let selectedValue: string | number | null = null;
      let onSelect: (value: any) => void = () => {};
      let title = '';

      switch (showOptionSelector) {
        case 'aidType':
          options = AID_TYPES.map(type => ({ value: type, label: t(`careEvents.aidTypes.${type}`, type) }));
          selectedValue = aidType;
          onSelect = setAidType;
          title = t('careEvents.form.aidType');
          break;
        case 'scheduleFrequency':
          options = SCHEDULE_FREQUENCIES.map(f => ({ value: f.value, label: f.label }));
          selectedValue = scheduleFrequency;
          onSelect = setScheduleFrequency;
          title = 'Payment Type';
          break;
        case 'dayOfWeek':
          options = DAYS_OF_WEEK;
          selectedValue = dayOfWeek;
          onSelect = setDayOfWeek;
          title = 'Day of Week';
          break;
        case 'startMonth':
          options = MONTHS;
          selectedValue = startMonth;
          onSelect = setStartMonth;
          title = 'Start Month';
          break;
        case 'startYear':
          options = yearOptions;
          selectedValue = startYear;
          onSelect = setStartYear;
          title = 'Start Year';
          break;
        case 'endMonth':
          options = [{ value: 0, label: 'No end date' }, ...MONTHS];
          selectedValue = endMonth || 0;
          onSelect = (v) => setEndMonth(v === 0 ? null : v);
          title = 'End Month';
          break;
        case 'endYear':
          options = [{ value: 0, label: 'No end date' }, ...yearOptions];
          selectedValue = endYear || 0;
          onSelect = (v) => setEndYear(v === 0 ? null : v);
          title = 'End Year';
          break;
        case 'monthOfYear':
          options = MONTHS;
          selectedValue = monthOfYear;
          onSelect = setMonthOfYear;
          title = 'Month of Year';
          break;
        case 'griefRelationship':
          options = GRIEF_RELATIONSHIPS.map(rel => ({
            value: rel,
            label: t(`careEvents.relationships.${rel}`, rel),
          }));
          selectedValue = griefRelationship;
          onSelect = setGriefRelationship;
          title = t('careEvents.form.relationship');
          break;
      }

      return (
        <OptionSelector
          options={options}
          selectedValue={selectedValue}
          onSelect={onSelect}
          onClose={() => setShowOptionSelector(null)}
          title={title}
        />
      );
    }

    return (
      <>
        {/* Header with back button */}
        <View className="flex-row items-center px-5 py-4 border-b border-gray-200">
          <Pressable
            onPress={handleBack}
            className="p-1"
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <ChevronLeft size={22} color="#4b5563" />
          </Pressable>
          <View className="flex-1 ml-2">
            <View className="flex-row items-center gap-2">
              {config && TypeIcon && (
                <View
                  className="w-8 h-8 rounded-lg items-center justify-center"
                  style={{ backgroundColor: config.color + '15' }}
                >
                  <TypeIcon size={18} color={config.color} />
                </View>
              )}
              <Text className="text-lg font-bold text-gray-900">
                {eventType ? t(`careEvents.types.${eventType}`) : ''}
              </Text>
            </View>
            <Text className="text-sm text-gray-500">
              {selectedMember?.name || payload?.memberName}
            </Text>
          </View>
          <Pressable
            onPress={onClose}
            className="p-2"
            hitSlop={{ top: 8, bottom: 8, left: 8, right: 8 }}
          >
            <X size={22} color="#9ca3af" />
          </Pressable>
        </View>

        <ScrollView
          style={{ maxHeight: 500 }}
          contentContainerClassName="px-5 py-5"
          showsVerticalScrollIndicator={true}
          keyboardShouldPersistTaps="handled"
          bounces={true}
        >
          {/* Event Date - NOT for financial_aid */}
          {eventType !== 'financial_aid' && (
            <View className="mb-5">
              <Text className="text-gray-700 font-semibold mb-2">
                {t('careEvents.form.eventDate')}
              </Text>
              <Pressable
                onPress={() => setShowDatePicker(true)}
                className="flex-row items-center bg-gray-50 border border-gray-200 rounded-xl px-4 py-3.5"
              >
                <Calendar size={18} color="#9ca3af" />
                <Text className="text-gray-900 ml-2">
                  {eventDate.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' })}
                </Text>
              </Pressable>
              {showDatePicker && (
                <DateTimePicker
                  value={eventDate}
                  mode="date"
                  display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                  onChange={handleDateChange}
                />
              )}
            </View>
          )}

          {/* Description */}
          <View className="mb-5">
            <Text className="text-gray-700 font-semibold mb-2">
              {t('careEvents.form.description')}
            </Text>
            <TextInput
              value={description}
              onChangeText={setDescription}
              placeholder="Additional details..."
              placeholderTextColor="#9ca3af"
              className="bg-gray-50 border border-gray-200 rounded-xl px-4 py-3 text-base text-gray-900 min-h-[80px]"
              multiline
              numberOfLines={3}
              textAlignVertical="top"
            />
          </View>

          {/* ================================================================ */}
          {/* GRIEF LOSS FIELDS */}
          {/* ================================================================ */}
          {eventType === 'grief_loss' && (
            <View className="mb-5 p-4 bg-purple-50 rounded-xl border border-purple-200">
              <Text className="text-sm font-medium text-purple-900 mb-3">
                A 6-stage grief support timeline will be auto-generated
              </Text>
              <Text className="text-gray-700 font-semibold mb-2">
                {t('careEvents.form.relationship')}
              </Text>
              <Picker
                label="Select relationship"
                value={t(`careEvents.relationships.${griefRelationship}`, griefRelationship)}
                onPress={() => setShowOptionSelector('griefRelationship')}
              />
            </View>
          )}

          {/* ================================================================ */}
          {/* ACCIDENT/ILLNESS FIELDS */}
          {/* ================================================================ */}
          {eventType === 'accident_illness' && (
            <View className="mb-5 p-4 bg-blue-50 rounded-xl border border-blue-200">
              <Text className="text-gray-700 font-semibold mb-2">
                {t('careEvents.form.hospitalName')}
              </Text>
              <TextInput
                value={hospitalName}
                onChangeText={setHospitalName}
                placeholder="e.g., RSU Jakarta, Ciputra Hospital"
                placeholderTextColor="#9ca3af"
                className="bg-white border border-gray-200 rounded-xl px-4 py-3 text-base text-gray-900"
              />
            </View>
          )}

          {/* ================================================================ */}
          {/* FINANCIAL AID FIELDS */}
          {/* ================================================================ */}
          {eventType === 'financial_aid' && (
            <View className="p-4 bg-green-50 rounded-xl border border-green-200 mb-5">
              <Text className="font-bold text-green-900 mb-4">Financial Aid Details</Text>

              {/* Aid Title */}
              <View className="mb-4">
                <Text className="text-gray-700 font-semibold mb-2">Aid Name/Title *</Text>
                <TextInput
                  value={aidTitle}
                  onChangeText={setAidTitle}
                  placeholder="e.g., Monthly Education Support"
                  placeholderTextColor="#9ca3af"
                  className="bg-white border border-gray-200 rounded-xl px-4 py-3 text-base text-gray-900"
                />
              </View>

              {/* Aid Type */}
              <View className="mb-4">
                <Text className="text-gray-700 font-semibold mb-2">Aid Type *</Text>
                <Picker
                  label="Select aid type"
                  value={t(`careEvents.aidTypes.${aidType}`, aidType)}
                  onPress={() => setShowOptionSelector('aidType')}
                />
              </View>

              {/* Amount */}
              <View className="mb-4">
                <Text className="text-gray-700 font-semibold mb-2">Amount (Rp) *</Text>
                <TextInput
                  value={aidAmount}
                  onChangeText={setAidAmount}
                  placeholder="1500000"
                  placeholderTextColor="#9ca3af"
                  className="bg-white border border-gray-200 rounded-xl px-4 py-3 text-base text-gray-900"
                  keyboardType="numeric"
                />
              </View>

              {/* Payment Type / Schedule */}
              <View className="border-t border-green-200 pt-4 mt-2">
                <Text className="font-bold text-green-800 mb-3">Payment Type</Text>

                <View className="mb-4">
                  <Text className="text-gray-700 font-semibold mb-2">Frequency</Text>
                  <Picker
                    label="Select frequency"
                    value={SCHEDULE_FREQUENCIES.find(f => f.value === scheduleFrequency)?.label || ''}
                    onPress={() => setShowOptionSelector('scheduleFrequency')}
                  />
                </View>

                {/* One-time Payment Fields */}
                {scheduleFrequency === 'one_time' && (
                  <View className="mb-4">
                    <Text className="text-gray-700 font-semibold mb-2">Payment Date</Text>
                    <Pressable
                      onPress={() => setShowPaymentDatePicker(true)}
                      className="flex-row items-center bg-white border border-gray-200 rounded-xl px-4 py-3.5"
                    >
                      <Calendar size={18} color="#9ca3af" />
                      <Text className="text-gray-900 ml-2">
                        {paymentDate.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' })}
                      </Text>
                    </Pressable>
                    <Text className="text-xs text-gray-500 mt-1">Date when aid was given</Text>
                    {showPaymentDatePicker && (
                      <DateTimePicker
                        value={paymentDate}
                        mode="date"
                        display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                        onChange={handlePaymentDateChange}
                      />
                    )}
                  </View>
                )}

                {/* Weekly Schedule Fields */}
                {scheduleFrequency === 'weekly' && (
                  <View className="p-3 bg-blue-50 rounded-xl">
                    <View className="mb-4">
                      <Text className="text-gray-700 font-semibold mb-2 text-sm">Day of Week</Text>
                      <Picker
                        label="Select day"
                        value={DAYS_OF_WEEK.find(d => d.value === dayOfWeek)?.label || ''}
                        onPress={() => setShowOptionSelector('dayOfWeek')}
                      />
                    </View>
                    <View>
                      <Text className="text-gray-700 font-semibold mb-2 text-sm">End Date (optional)</Text>
                      <Pressable
                        onPress={() => setShowEndDatePicker(true)}
                        className="flex-row items-center bg-white border border-gray-200 rounded-xl px-4 py-3.5"
                      >
                        <Calendar size={18} color="#9ca3af" />
                        <Text className="text-gray-900 ml-2">
                          {scheduleEndDate
                            ? scheduleEndDate.toLocaleDateString('id-ID', { day: 'numeric', month: 'short', year: 'numeric' })
                            : 'No end date'}
                        </Text>
                      </Pressable>
                      {showEndDatePicker && (
                        <DateTimePicker
                          value={scheduleEndDate || new Date()}
                          mode="date"
                          display={Platform.OS === 'ios' ? 'spinner' : 'default'}
                          onChange={handleEndDateChange}
                        />
                      )}
                    </View>
                  </View>
                )}

                {/* Monthly Schedule Fields */}
                {scheduleFrequency === 'monthly' && (
                  <View className="p-3 bg-purple-50 rounded-xl">
                    <View className="flex-row gap-3 mb-4">
                      <View className="flex-1">
                        <Text className="text-gray-700 font-semibold mb-2 text-sm">Start Month</Text>
                        <Picker
                          label="Month"
                          value={MONTHS.find(m => m.value === startMonth)?.label || ''}
                          onPress={() => setShowOptionSelector('startMonth')}
                        />
                      </View>
                      <View className="flex-1">
                        <Text className="text-gray-700 font-semibold mb-2 text-sm">Start Year</Text>
                        <Picker
                          label="Year"
                          value={startYear.toString()}
                          onPress={() => setShowOptionSelector('startYear')}
                        />
                      </View>
                    </View>
                    <View className="mb-4">
                      <Text className="text-gray-700 font-semibold mb-2 text-sm">Day of Month</Text>
                      <TextInput
                        value={dayOfMonth}
                        onChangeText={setDayOfMonth}
                        placeholder="13"
                        placeholderTextColor="#9ca3af"
                        className="bg-white border border-gray-200 rounded-xl px-4 py-3 text-base text-gray-900"
                        keyboardType="numeric"
                        maxLength={2}
                      />
                    </View>
                    <View className="flex-row gap-3">
                      <View className="flex-1">
                        <Text className="text-gray-700 font-semibold mb-2 text-sm">End Month</Text>
                        <Picker
                          label="No end"
                          value={endMonth ? MONTHS.find(m => m.value === endMonth)?.label || '' : 'No end date'}
                          onPress={() => setShowOptionSelector('endMonth')}
                        />
                      </View>
                      <View className="flex-1">
                        <Text className="text-gray-700 font-semibold mb-2 text-sm">End Year</Text>
                        <Picker
                          label="No end"
                          value={endYear ? endYear.toString() : 'No end date'}
                          onPress={() => setShowOptionSelector('endYear')}
                        />
                      </View>
                    </View>
                  </View>
                )}

                {/* Annual Schedule Fields */}
                {scheduleFrequency === 'annually' && (
                  <View className="p-3 bg-orange-50 rounded-xl">
                    <View className="flex-row gap-3">
                      <View className="flex-1">
                        <Text className="text-gray-700 font-semibold mb-2 text-sm">Month of Year *</Text>
                        <Picker
                          label="Month"
                          value={MONTHS.find(m => m.value === monthOfYear)?.label || ''}
                          onPress={() => setShowOptionSelector('monthOfYear')}
                        />
                      </View>
                      <View className="flex-1">
                        <Text className="text-gray-700 font-semibold mb-2 text-sm">End Year</Text>
                        <Picker
                          label="No end"
                          value={endYear ? endYear.toString() : 'No end date'}
                          onPress={() => setShowOptionSelector('endYear')}
                        />
                      </View>
                    </View>
                  </View>
                )}
              </View>
            </View>
          )}
        </ScrollView>

        {/* Submit button */}
        <View
          className="px-5 pt-4 border-t border-gray-200"
          style={{ paddingBottom: insets.bottom + 16 }}
        >
          <Pressable
            onPress={handleSubmit}
            disabled={createMutation.isPending}
            className={`flex-row items-center justify-center py-4 rounded-xl ${
              createMutation.isPending ? 'bg-gray-300' : 'bg-primary-500 active:opacity-90'
            }`}
          >
            {createMutation.isPending ? (
              <Text className="text-white font-semibold text-base">
                {t('common.loading')}
              </Text>
            ) : (
              <>
                <Check size={18} color="#ffffff" />
                <Text className="text-white font-semibold text-base ml-2">
                  Save Care Event
                </Text>
              </>
            )}
          </Pressable>
        </View>
      </>
    );
  };

  // Calculate max height for the bottom sheet (screen height - status bar - some margin)
  const screenHeight = Dimensions.get('window').height;
  const maxSheetHeight = screenHeight * 0.85;

  return (
    <KeyboardAvoidingView
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
      className="w-full"
      keyboardVerticalOffset={Platform.OS === 'ios' ? 10 : 0}
    >
      <View
        className="bg-white rounded-t-3xl shadow-2xl"
        style={{ maxHeight: maxSheetHeight }}
      >
        {/* Handle bar */}
        <View className="items-center pt-3 pb-2">
          <View className="w-10 h-1 bg-gray-300 rounded-full" />
        </View>

        {step === 'member' && renderMemberSelector()}
        {step === 'type' && renderTypeSelector()}
        {step === 'form' && renderForm()}
      </View>
    </KeyboardAvoidingView>
  );
}

export default CreateCareEventSheet;
