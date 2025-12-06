/**
 * AnimatedTabBar - Premium animated tab bar with sliding indicator
 *
 * Features:
 * - Sliding indicator that follows active tab
 * - Scale animation on active tab icon
 * - Haptic feedback on tab press
 * - Smooth spring animations
 * - Respects reduced motion preference
 */

import React, { useEffect, memo } from 'react';
import { View, Pressable, useWindowDimensions, AccessibilityInfo } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  interpolate,
  interpolateColor,
  runOnJS,
  useAnimatedReaction,
} from 'react-native-reanimated';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import type { BottomTabBarProps } from '@react-navigation/bottom-tabs';

import { colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';

// ============================================================================
// CONSTANTS
// ============================================================================

const TAB_BAR_HEIGHT = 65;
const INDICATOR_HEIGHT = 3;
const ICON_SIZE = 24;
const SPRING_CONFIG = {
  damping: 15,
  stiffness: 150,
  mass: 0.5,
};

// ============================================================================
// ANIMATED TAB BUTTON
// ============================================================================

interface TabButtonProps {
  route: {
    key: string;
    name: string;
  };
  descriptor: {
    options: {
      tabBarIcon?: (props: { focused: boolean; color: string; size: number }) => React.ReactNode;
      tabBarLabel?: string | ((props: { focused: boolean; color: string }) => React.ReactNode);
      title?: string;
      tabBarAccessibilityLabel?: string;
    };
  };
  isFocused: boolean;
  onPress: () => void;
  onLongPress: () => void;
  tabWidth: number;
}

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

const TabButton = memo(function TabButton({
  route,
  descriptor,
  isFocused,
  onPress,
  onLongPress,
  tabWidth,
}: TabButtonProps) {
  const scale = useSharedValue(1);
  const isPressed = useSharedValue(false);
  const [reducedMotion, setReducedMotion] = React.useState(false);

  // Check for reduced motion preference
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReducedMotion);
    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setReducedMotion
    );
    return () => subscription?.remove();
  }, []);

  // Animate scale when focused changes
  useEffect(() => {
    if (reducedMotion) {
      scale.value = isFocused ? 1.1 : 1;
    } else {
      scale.value = withSpring(isFocused ? 1.1 : 1, SPRING_CONFIG);
    }
  }, [isFocused, reducedMotion]);

  const animatedIconStyle = useAnimatedStyle(() => ({
    transform: [{ scale: scale.value }],
  }));

  const animatedContainerStyle = useAnimatedStyle(() => ({
    opacity: interpolate(
      isPressed.value ? 1 : 0,
      [0, 1],
      [1, 0.7]
    ),
  }));

  const handlePressIn = () => {
    isPressed.value = true;
    if (!reducedMotion) {
      scale.value = withSpring(0.9, { damping: 20, stiffness: 400 });
    }
  };

  const handlePressOut = () => {
    isPressed.value = false;
    if (!reducedMotion) {
      scale.value = withSpring(isFocused ? 1.1 : 1, SPRING_CONFIG);
    }
  };

  const handlePress = () => {
    haptics.tap();
    onPress();
  };

  const { options } = descriptor;
  const label =
    typeof options.tabBarLabel === 'function'
      ? options.tabBarLabel({ focused: isFocused, color: isFocused ? colors.primary[600] : colors.gray[400] })
      : options.tabBarLabel !== undefined
      ? options.tabBarLabel
      : options.title !== undefined
      ? options.title
      : route.name;

  const iconColor = isFocused ? colors.primary[600] : colors.gray[400];

  return (
    <AnimatedPressable
      accessibilityRole="button"
      accessibilityState={{ selected: isFocused }}
      accessibilityLabel={options.tabBarAccessibilityLabel}
      onPress={handlePress}
      onLongPress={onLongPress}
      onPressIn={handlePressIn}
      onPressOut={handlePressOut}
      style={[
        {
          flex: 1,
          alignItems: 'center',
          justifyContent: 'center',
          paddingTop: 8,
          paddingBottom: 4,
          width: tabWidth,
        },
        animatedContainerStyle,
      ]}
    >
      <Animated.View style={animatedIconStyle}>
        {options.tabBarIcon?.({
          focused: isFocused,
          color: iconColor,
          size: ICON_SIZE,
        })}
      </Animated.View>
      <Animated.Text
        style={[
          {
            fontSize: 11,
            fontWeight: isFocused ? '600' : '500',
            marginTop: 4,
            color: iconColor,
          },
        ]}
      >
        {typeof label === 'string' ? label : ''}
      </Animated.Text>
    </AnimatedPressable>
  );
});

// ============================================================================
// ANIMATED TAB BAR
// ============================================================================

export function AnimatedTabBar({ state, descriptors, navigation }: BottomTabBarProps) {
  const { width } = useWindowDimensions();
  const insets = useSafeAreaInsets();
  const [reducedMotion, setReducedMotion] = React.useState(false);

  const tabCount = state.routes.length;
  const tabWidth = width / tabCount;
  const indicatorPosition = useSharedValue(state.index * tabWidth);

  // Check for reduced motion preference
  useEffect(() => {
    AccessibilityInfo.isReduceMotionEnabled().then(setReducedMotion);
    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setReducedMotion
    );
    return () => subscription?.remove();
  }, []);

  // Animate indicator position when tab changes
  useEffect(() => {
    const targetPosition = state.index * tabWidth;
    if (reducedMotion) {
      indicatorPosition.value = targetPosition;
    } else {
      indicatorPosition.value = withSpring(targetPosition, SPRING_CONFIG);
    }
  }, [state.index, tabWidth, reducedMotion]);

  const indicatorStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: indicatorPosition.value }],
  }));

  return (
    <View
      style={{
        backgroundColor: colors.white,
        borderTopWidth: 1,
        borderTopColor: colors.gray[100],
        paddingBottom: insets.bottom,
        // Shadow
        shadowColor: '#000',
        shadowOffset: { width: 0, height: -2 },
        shadowOpacity: 0.05,
        shadowRadius: 8,
        elevation: 8,
      }}
    >
      {/* Sliding Indicator */}
      <View style={{ height: INDICATOR_HEIGHT, position: 'relative' }}>
        <Animated.View
          style={[
            {
              position: 'absolute',
              top: 0,
              width: tabWidth * 0.4,
              height: INDICATOR_HEIGHT,
              backgroundColor: colors.primary[600],
              borderBottomLeftRadius: INDICATOR_HEIGHT,
              borderBottomRightRadius: INDICATOR_HEIGHT,
              marginLeft: tabWidth * 0.3,
            },
            indicatorStyle,
          ]}
        />
      </View>

      {/* Tab Buttons */}
      <View style={{ flexDirection: 'row', height: TAB_BAR_HEIGHT }}>
        {state.routes.map((route, index) => {
          const descriptor = descriptors[route.key];
          const isFocused = state.index === index;

          const onPress = () => {
            const event = navigation.emit({
              type: 'tabPress',
              target: route.key,
              canPreventDefault: true,
            });

            if (!isFocused && !event.defaultPrevented) {
              navigation.navigate(route.name);
            }
          };

          const onLongPress = () => {
            navigation.emit({
              type: 'tabLongPress',
              target: route.key,
            });
          };

          return (
            <TabButton
              key={route.key}
              route={route}
              descriptor={descriptor}
              isFocused={isFocused}
              onPress={onPress}
              onLongPress={onLongPress}
              tabWidth={tabWidth}
            />
          );
        })}
      </View>
    </View>
  );
}

export default AnimatedTabBar;
