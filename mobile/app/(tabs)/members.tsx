/**
 * Members Screen
 *
 * List of all members with search and filter
 * Uses NativeWind for styling
 */

import React, { useState, useCallback, useMemo, memo } from 'react';
import {
  View,
  Text,
  TextInput,
  Pressable,
  RefreshControl,
  ActivityIndicator,
} from 'react-native';
import { FlashList } from '@shopify/flash-list';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import { router } from 'expo-router';
import { Search, ChevronRight, Plus } from 'lucide-react-native';
import { useDebouncedCallback } from 'use-debounce';

import { useMembers } from '@/hooks/useMembers';
import { engagementColors, colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';
import { FloatingActionButton } from '@/components/ui/FloatingActionButton';
import { MembersListSkeleton } from '@/components/ui/Skeleton';
import { EmptyMembers, EmptySearch } from '@/components/ui/EmptyState';
import { MemberAvatar } from '@/components/ui/CachedImage';
import type { MemberListItem, EngagementStatus } from '@/types';

// ============================================================================
// COMPONENTS
// ============================================================================

interface MemberCardProps {
  member: MemberListItem;
  onPress: () => void;
}

const MemberCard = memo(function MemberCard({ member, onPress }: MemberCardProps) {
  const { t } = useTranslation();

  const engagementColor = engagementColors[member.engagement_status] || colors.gray[400];

  return (
    <Pressable
      className="flex-row items-center bg-white rounded-xl p-4 mb-3 shadow-sm active:opacity-90 active:scale-[0.98]"
      onPress={onPress}
    >
      {/* Avatar - Using CachedImage for automatic disk caching */}
      <View className="mr-4">
        <MemberAvatar photoUrl={member.photo_url} size="md" />
      </View>

      {/* Content */}
      <View className="flex-1">
        <Text className="text-base font-semibold text-gray-900" numberOfLines={1}>
          {member.name}
        </Text>
        {member.phone && (
          <Text className="text-sm text-gray-500 mt-0.5" numberOfLines={1}>
            {member.phone}
          </Text>
        )}
        <View className="flex-row items-center mt-1 gap-2">
          <View
            className="flex-row items-center px-2 py-0.5 rounded-full gap-1"
            style={{ backgroundColor: `${engagementColor}20` }}
          >
            <View
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: engagementColor }}
            />
            <Text className="text-xs font-medium" style={{ color: engagementColor }}>
              {t(`members.engagement.${member.engagement_status}`)}
            </Text>
          </View>
          {member.days_since_last_contact !== undefined && member.days_since_last_contact > 0 && (
            <Text className="text-xs text-gray-400">
              {t('members.daysSinceContact', { days: member.days_since_last_contact })}
            </Text>
          )}
        </View>
      </View>

      {/* Arrow */}
      <ChevronRight size={20} color="#9ca3af" />
    </Pressable>
  );
});

const FILTER_OPTIONS: (EngagementStatus | 'all')[] = ['all', 'active', 'at_risk', 'disconnected'];

// ============================================================================
// MAIN SCREEN
// ============================================================================

function MembersScreen() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();

  const [searchQuery, setSearchQuery] = useState('');
  const [debouncedSearch, setDebouncedSearch] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<EngagementStatus | 'all'>('all');

  // Debounce search
  const debouncedSetSearch = useDebouncedCallback((value: string) => {
    setDebouncedSearch(value);
  }, 500);

  const handleSearchChange = useCallback(
    (text: string) => {
      setSearchQuery(text);
      debouncedSetSearch(text);
    },
    [debouncedSetSearch]
  );

  // Build filters
  const filters = useMemo(() => {
    const f: any = {};
    if (debouncedSearch) {
      f.search = debouncedSearch;
    }
    if (selectedFilter !== 'all') {
      f.engagement_status = selectedFilter;
    }
    return f;
  }, [debouncedSearch, selectedFilter]);

  const {
    data,
    isLoading,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    refetch,
    isRefetching,
  } = useMembers(filters);

  // Flatten members from all pages
  const members = useMemo(() => {
    if (!data?.pages) return [];
    return data.pages.flatMap((page) => page.members);
  }, [data]);

  // Handle member press
  const handleMemberPress = useCallback((member: MemberListItem) => {
    haptics.tap();
    router.push(`/member/${member.id}`);
  }, []);

  // Handle load more
  const handleLoadMore = useCallback(() => {
    if (hasNextPage && !isFetchingNextPage) {
      fetchNextPage();
    }
  }, [hasNextPage, isFetchingNextPage, fetchNextPage]);

  // Render member item
  const renderMember = useCallback(
    ({ item }: { item: MemberListItem }) => (
      <MemberCard member={item} onPress={() => handleMemberPress(item)} />
    ),
    [handleMemberPress]
  );

  // Render footer (loading indicator)
  const renderFooter = useCallback(() => {
    if (!isFetchingNextPage) return <View className="h-24" />;
    return (
      <View className="py-6 items-center">
        <ActivityIndicator size="small" color="#14b8a6" />
      </View>
    );
  }, [isFetchingNextPage]);

  // Render empty state
  const renderEmpty = useCallback(() => {
    if (isLoading) return null;
    // Show different empty state based on search
    if (debouncedSearch || selectedFilter !== 'all') {
      return <EmptySearch />;
    }
    return (
      <EmptyMembers
        onAction={() => {
          haptics.tap();
          router.push('/member/add');
        }}
      />
    );
  }, [isLoading, debouncedSearch, selectedFilter]);

  // Handle add member
  const handleAddMember = useCallback(() => {
    haptics.tap();
    router.push('/member/add');
  }, []);

  return (
    <View className="flex-1 bg-gray-50">
      {/* Header */}
      <View
        className="bg-white px-6 pb-4 border-b border-gray-200"
        style={{ paddingTop: insets.top + 16 }}
      >
        <Text className="text-3xl font-bold text-gray-900 mb-4">
          {t('members.title')}
        </Text>

        {/* Search Bar */}
        <View className="flex-row items-center bg-gray-100 rounded-xl px-4 h-11 mb-4">
          <Search size={20} color="#9ca3af" />
          <TextInput
            className="flex-1 text-base text-gray-900 ml-3"
            placeholder={t('members.searchPlaceholder')}
            placeholderTextColor="#9ca3af"
            value={searchQuery}
            onChangeText={handleSearchChange}
            autoCapitalize="none"
            autoCorrect={false}
          />
        </View>

        {/* Filter Pills */}
        <View className="flex-row gap-2">
          {FILTER_OPTIONS.map((filter) => {
            const isActive = filter === selectedFilter;
            return (
              <Pressable
                key={filter}
                className={`px-4 py-2 rounded-full ${
                  isActive ? 'bg-primary-500' : 'bg-gray-100'
                }`}
                onPress={() => {
                  haptics.tap();
                  setSelectedFilter(filter);
                }}
              >
                <Text
                  className={`text-sm font-medium ${
                    isActive ? 'text-white' : 'text-gray-600'
                  }`}
                >
                  {t(`members.filters.${filter}`)}
                </Text>
              </Pressable>
            );
          })}
        </View>
      </View>

      {/* Members List */}
      {isLoading ? (
        <MembersListSkeleton />
      ) : (
        <FlashList
          data={members}
          renderItem={renderMember}
          keyExtractor={(item) => item.id}
          contentContainerStyle={{ paddingHorizontal: 24, paddingTop: 16 }}
          onEndReached={handleLoadMore}
          onEndReachedThreshold={0.5}
          ListFooterComponent={renderFooter}
          ListEmptyComponent={renderEmpty}
          refreshControl={
            <RefreshControl
              refreshing={isRefetching}
              onRefresh={refetch}
              tintColor="#14b8a6"
            />
          }
        />
      )}

      {/* Floating Action Button */}
      <FloatingActionButton
        icon={Plus}
        onPress={handleAddMember}
        position="bottom-right"
      />
    </View>
  );
}

export default memo(MembersScreen);
