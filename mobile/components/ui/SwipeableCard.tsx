/**
 * SwipeableCard - Card with swipe-to-reveal actions
 *
 * Features:
 * - Swipe right to reveal "Complete" action (green)
 * - Swipe left to reveal "Ignore" action (gray)
 * - Full swipe triggers action automatically
 * - Haptic feedback at threshold and on action
 * - Smooth spring animations
 * - Reset on release if not past threshold
 */

import React, { memo, useCallback, useRef } from 'react';
import { View, Text, Dimensions, StyleProp, ViewStyle } from 'react-native';
import { Gesture, GestureDetector } from 'react-native-gesture-handler';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  runOnJS,
  interpolate,
  Extrapolation,
} from 'react-native-reanimated';
import { Check, X } from 'lucide-react-native';

import { haptics } from '@/constants/interaction';
import { colors } from '@/constants/theme';

// ============================================================================
// CONSTANTS
// ============================================================================

const SCREEN_WIDTH = Dimensions.get('window').width;
const ACTION_THRESHOLD = SCREEN_WIDTH * 0.25; // 25% of screen width
const FULL_SWIPE_THRESHOLD = SCREEN_WIDTH * 0.5; // 50% triggers action
const SPRING_CONFIG = {
  damping: 20,
  stiffness: 200,
  mass: 0.5,
};

// ============================================================================
// TYPES
// ============================================================================

interface SwipeableCardProps {
  children: React.ReactNode;
  onSwipeComplete?: () => void;
  onSwipeIgnore?: () => void;
  completeLabel?: string;
  ignoreLabel?: string;
  disabled?: boolean;
  style?: StyleProp<ViewStyle>;
  className?: string;
}

// ============================================================================
// COMPONENT
// ============================================================================

export const SwipeableCard = memo(function SwipeableCard({
  children,
  onSwipeComplete,
  onSwipeIgnore,
  completeLabel = 'Complete',
  ignoreLabel = 'Ignore',
  disabled = false,
  style,
  className,
}: SwipeableCardProps) {
  const translateX = useSharedValue(0);
  const isActive = useSharedValue(false);
  const hasTriggeredHaptic = useRef(false);

  // Reset haptic trigger
  const resetHapticTrigger = useCallback(() => {
    hasTriggeredHaptic.current = false;
  }, []);

  // Trigger haptic at threshold
  const triggerThresholdHaptic = useCallback(() => {
    if (!hasTriggeredHaptic.current) {
      hasTriggeredHaptic.current = true;
      haptics.tap();
    }
  }, []);

  // Handle complete action
  const handleComplete = useCallback(() => {
    haptics.success();
    onSwipeComplete?.();
  }, [onSwipeComplete]);

  // Handle ignore action
  const handleIgnore = useCallback(() => {
    haptics.tap();
    onSwipeIgnore?.();
  }, [onSwipeIgnore]);

  // Pan gesture handler
  const panGesture = Gesture.Pan()
    .enabled(!disabled)
    .onStart(() => {
      isActive.value = true;
      runOnJS(resetHapticTrigger)();
    })
    .onUpdate((event) => {
      translateX.value = event.translationX;

      // Trigger haptic when crossing threshold
      if (Math.abs(event.translationX) >= ACTION_THRESHOLD) {
        runOnJS(triggerThresholdHaptic)();
      }
    })
    .onEnd((event) => {
      isActive.value = false;

      // Full swipe right - complete
      if (event.translationX >= FULL_SWIPE_THRESHOLD && onSwipeComplete) {
        translateX.value = withTiming(SCREEN_WIDTH, { duration: 200 }, () => {
          runOnJS(handleComplete)();
        });
        return;
      }

      // Full swipe left - ignore
      if (event.translationX <= -FULL_SWIPE_THRESHOLD && onSwipeIgnore) {
        translateX.value = withTiming(-SCREEN_WIDTH, { duration: 200 }, () => {
          runOnJS(handleIgnore)();
        });
        return;
      }

      // Reset to original position
      translateX.value = withSpring(0, SPRING_CONFIG);
    });

  // Animated styles for the card
  const cardAnimatedStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: translateX.value }],
  }));

  // Animated styles for the complete action (right)
  const completeActionStyle = useAnimatedStyle(() => {
    const opacity = interpolate(
      translateX.value,
      [0, ACTION_THRESHOLD],
      [0, 1],
      Extrapolation.CLAMP
    );

    const scale = interpolate(
      translateX.value,
      [0, ACTION_THRESHOLD, FULL_SWIPE_THRESHOLD],
      [0.5, 1, 1.1],
      Extrapolation.CLAMP
    );

    return {
      opacity,
      transform: [{ scale }],
    };
  });

  // Animated styles for the ignore action (left)
  const ignoreActionStyle = useAnimatedStyle(() => {
    const opacity = interpolate(
      translateX.value,
      [0, -ACTION_THRESHOLD],
      [0, 1],
      Extrapolation.CLAMP
    );

    const scale = interpolate(
      translateX.value,
      [0, -ACTION_THRESHOLD, -FULL_SWIPE_THRESHOLD],
      [0.5, 1, 1.1],
      Extrapolation.CLAMP
    );

    return {
      opacity,
      transform: [{ scale }],
    };
  });

  // Background color animation
  const backgroundStyle = useAnimatedStyle(() => {
    const rightProgress = interpolate(
      translateX.value,
      [0, ACTION_THRESHOLD],
      [0, 1],
      Extrapolation.CLAMP
    );

    const leftProgress = interpolate(
      translateX.value,
      [0, -ACTION_THRESHOLD],
      [0, 1],
      Extrapolation.CLAMP
    );

    return {
      backgroundColor:
        rightProgress > 0
          ? `rgba(16, 185, 129, ${rightProgress * 0.15})` // Green
          : leftProgress > 0
          ? `rgba(107, 114, 128, ${leftProgress * 0.15})` // Gray
          : 'transparent',
    };
  });

  return (
    <View className={className} style={[{ position: 'relative', overflow: 'hidden' }, style]}>
      {/* Background with action indicators */}
      <Animated.View
        style={[
          {
            position: 'absolute',
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            flexDirection: 'row',
            alignItems: 'center',
            justifyContent: 'space-between',
            paddingHorizontal: 20,
            borderRadius: 16,
          },
          backgroundStyle,
        ]}
      >
        {/* Complete action (left side, revealed on swipe right) */}
        <Animated.View
          style={[
            {
              alignItems: 'center',
              justifyContent: 'center',
            },
            completeActionStyle,
          ]}
        >
          <View className="w-12 h-12 rounded-full bg-green-500 items-center justify-center shadow-lg">
            <Check size={24} color="white" strokeWidth={3} />
          </View>
          <Text className="text-green-600 text-xs font-semibold mt-1">
            {completeLabel}
          </Text>
        </Animated.View>

        {/* Ignore action (right side, revealed on swipe left) */}
        <Animated.View
          style={[
            {
              alignItems: 'center',
              justifyContent: 'center',
            },
            ignoreActionStyle,
          ]}
        >
          <View className="w-12 h-12 rounded-full bg-gray-400 items-center justify-center shadow-lg">
            <X size={24} color="white" strokeWidth={3} />
          </View>
          <Text className="text-gray-500 text-xs font-semibold mt-1">
            {ignoreLabel}
          </Text>
        </Animated.View>
      </Animated.View>

      {/* Card content */}
      <GestureDetector gesture={panGesture}>
        <Animated.View
          style={[
            {
              backgroundColor: colors.white,
              borderRadius: 16,
              shadowColor: '#000',
              shadowOffset: { width: 0, height: 1 },
              shadowOpacity: 0.05,
              shadowRadius: 4,
              elevation: 2,
              borderWidth: 1,
              borderColor: colors.gray[100],
            },
            cardAnimatedStyle,
          ]}
        >
          {children}
        </Animated.View>
      </GestureDetector>
    </View>
  );
});

export default SwipeableCard;
