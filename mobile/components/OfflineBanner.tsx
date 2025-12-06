/**
 * Offline Banner Component
 *
 * Shows a banner when the device is offline
 * Includes pending operations count from offline sync queue
 * Uses NativeWind for styling
 */

import React from 'react';
import { View, Text, Pressable } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { WifiOff, RefreshCw, CloudOff } from 'lucide-react-native';
import Animated, {
  FadeInDown,
  FadeOutUp,
  useAnimatedStyle,
  useSharedValue,
  withRepeat,
  withTiming,
} from 'react-native-reanimated';

import { useOfflineSync } from '@/hooks/useOfflineSync';
import { haptics } from '@/constants/interaction';

export function OfflineBanner() {
  const { isOnline, isSyncing, pendingCount, sync } = useOfflineSync();
  const insets = useSafeAreaInsets();

  // Rotation animation for sync icon
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

  // Show banner if offline OR if there are pending operations
  const shouldShow = !isOnline || (isOnline && pendingCount > 0);

  if (!shouldShow) return null;

  const handleSync = async () => {
    if (isOnline && pendingCount > 0 && !isSyncing) {
      haptics.tap();
      await sync();
    }
  };

  // Determine banner content based on state
  const getBannerContent = () => {
    if (!isOnline) {
      return {
        Icon: WifiOff,
        message: pendingCount > 0
          ? `Offline • ${pendingCount} pending change${pendingCount > 1 ? 's' : ''}`
          : "You're offline. Changes will sync when connected.",
        bgClass: 'bg-amber-500',
        canSync: false,
      };
    }

    if (isSyncing) {
      return {
        Icon: RefreshCw,
        message: 'Syncing pending changes...',
        bgClass: 'bg-teal-500',
        canSync: false,
      };
    }

    // Online with pending operations
    return {
      Icon: CloudOff,
      message: `${pendingCount} pending change${pendingCount > 1 ? 's' : ''} • Tap to sync`,
      bgClass: 'bg-amber-500',
      canSync: true,
    };
  };

  const { Icon, message, bgClass, canSync } = getBannerContent();

  const BannerContent = (
    <View className="flex-row items-center justify-center py-2 px-4 gap-2">
      <Animated.View style={isSyncing ? spinStyle : undefined}>
        <Icon size={16} color="#ffffff" strokeWidth={2} />
      </Animated.View>
      <Text className="text-white text-sm font-medium">{message}</Text>
    </View>
  );

  return (
    <Animated.View
      entering={FadeInDown.duration(200)}
      exiting={FadeOutUp.duration(200)}
      className={`absolute left-0 right-0 ${bgClass} z-50`}
      style={{ top: insets.top }}
    >
      {canSync ? (
        <Pressable onPress={handleSync} className="active:opacity-80">
          {BannerContent}
        </Pressable>
      ) : (
        BannerContent
      )}
    </Animated.View>
  );
}

export default OfflineBanner;
