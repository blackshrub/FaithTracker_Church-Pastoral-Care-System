/**
 * Sync Status Indicator
 *
 * Shows offline queue status with pending operations count
 * Tap to manually sync when online with pending operations
 */

import React, { memo } from 'react';
import { Pressable, View } from 'react-native';
import Animated, {
  useAnimatedStyle,
  withRepeat,
  withSequence,
  withTiming,
  useSharedValue,
  FadeIn,
  FadeOut,
} from 'react-native-reanimated';
import { WifiOff, RefreshCw, Cloud, CloudOff, Check } from 'lucide-react-native';

import { useOfflineSync } from '@/hooks/useOfflineSync';
import { colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';

interface SyncStatusIndicatorProps {
  showLabel?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

const sizeConfig = {
  sm: { icon: 16, badge: 14, container: 32 },
  md: { icon: 20, badge: 16, container: 40 },
  lg: { icon: 24, badge: 18, container: 48 },
};

export const SyncStatusIndicator = memo(function SyncStatusIndicator({
  showLabel = false,
  size = 'md',
}: SyncStatusIndicatorProps) {
  const { isOnline, isSyncing, pendingCount, sync } = useOfflineSync();
  const config = sizeConfig[size];

  // Rotation animation for syncing state
  const rotation = useSharedValue(0);

  React.useEffect(() => {
    if (isSyncing) {
      rotation.value = withRepeat(
        withTiming(360, { duration: 1000 }),
        -1, // infinite
        false
      );
    } else {
      rotation.value = withTiming(0, { duration: 200 });
    }
  }, [isSyncing]);

  const spinStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
  }));

  const handlePress = async () => {
    if (isOnline && pendingCount > 0 && !isSyncing) {
      haptics.tap();
      await sync();
    }
  };

  // Determine icon and color based on state
  const getStateConfig = () => {
    if (isSyncing) {
      return {
        Icon: RefreshCw,
        color: colors.primary.teal,
        bgColor: 'bg-teal-50',
        label: 'Syncing...',
      };
    }

    if (!isOnline) {
      return {
        Icon: WifiOff,
        color: colors.status.warning,
        bgColor: 'bg-amber-50',
        label: 'Offline',
      };
    }

    if (pendingCount > 0) {
      return {
        Icon: CloudOff,
        color: colors.status.warning,
        bgColor: 'bg-amber-50',
        label: `${pendingCount} pending`,
      };
    }

    return {
      Icon: Cloud,
      color: colors.text.secondary,
      bgColor: 'bg-gray-100',
      label: 'Synced',
    };
  };

  const { Icon, color, bgColor, label } = getStateConfig();

  // Don't show if online and no pending operations
  if (isOnline && pendingCount === 0 && !isSyncing) {
    return null;
  }

  return (
    <AnimatedPressable
      onPress={handlePress}
      disabled={!isOnline || pendingCount === 0 || isSyncing}
      entering={FadeIn.duration(200)}
      exiting={FadeOut.duration(200)}
      className={`flex-row items-center rounded-full ${bgColor} px-3 py-1.5`}
      style={{ opacity: isOnline && pendingCount > 0 && !isSyncing ? 1 : 0.8 }}
    >
      <Animated.View style={isSyncing ? spinStyle : undefined}>
        <Icon size={config.icon} color={color} strokeWidth={2} />
      </Animated.View>

      {/* Pending count badge */}
      {pendingCount > 0 && !isSyncing && (
        <View
          className="absolute -top-1 -right-1 bg-amber-500 rounded-full items-center justify-center"
          style={{
            width: config.badge,
            height: config.badge,
            minWidth: config.badge,
          }}
        >
          <Animated.Text
            entering={FadeIn.duration(150)}
            className="text-white text-[10px] font-bold"
          >
            {pendingCount > 9 ? '9+' : pendingCount}
          </Animated.Text>
        </View>
      )}

      {/* Optional label */}
      {showLabel && (
        <Animated.Text
          entering={FadeIn.duration(200)}
          className="ml-2 text-sm font-medium"
          style={{ color }}
        >
          {label}
        </Animated.Text>
      )}
    </AnimatedPressable>
  );
});

/**
 * Compact sync indicator for headers
 */
export const SyncStatusBadge = memo(function SyncStatusBadge() {
  const { isOnline, isSyncing, pendingCount, sync } = useOfflineSync();

  const rotation = useSharedValue(0);

  React.useEffect(() => {
    if (isSyncing) {
      rotation.value = withRepeat(withTiming(360, { duration: 1000 }), -1, false);
    } else {
      rotation.value = withTiming(0, { duration: 200 });
    }
  }, [isSyncing]);

  const spinStyle = useAnimatedStyle(() => ({
    transform: [{ rotate: `${rotation.value}deg` }],
  }));

  // Don't show if online and no pending operations
  if (isOnline && pendingCount === 0 && !isSyncing) {
    return null;
  }

  const handlePress = async () => {
    if (isOnline && pendingCount > 0 && !isSyncing) {
      haptics.tap();
      await sync();
    }
  };

  return (
    <Pressable
      onPress={handlePress}
      disabled={!isOnline || pendingCount === 0 || isSyncing}
      className="relative p-2"
    >
      <Animated.View style={isSyncing ? spinStyle : undefined}>
        {isSyncing ? (
          <RefreshCw size={20} color={colors.primary.teal} strokeWidth={2} />
        ) : !isOnline ? (
          <WifiOff size={20} color={colors.status.warning} strokeWidth={2} />
        ) : (
          <CloudOff size={20} color={colors.status.warning} strokeWidth={2} />
        )}
      </Animated.View>

      {/* Badge for pending count */}
      {pendingCount > 0 && !isSyncing && (
        <View className="absolute top-0 right-0 bg-amber-500 rounded-full w-4 h-4 items-center justify-center">
          <Animated.Text entering={FadeIn} className="text-white text-[9px] font-bold">
            {pendingCount > 9 ? '+' : pendingCount}
          </Animated.Text>
        </View>
      )}
    </Pressable>
  );
});

export default SyncStatusIndicator;
