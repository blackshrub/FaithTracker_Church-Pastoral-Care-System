/**
 * PremiumCard - Card with premium micro-interactions
 *
 * Features:
 * - Press animation: scale down + shadow reduction
 * - Lift effect on long press
 * - Smooth spring animations
 * - Haptic feedback on press
 * - Configurable variants (default, elevated, outline)
 * - Stagger animation support for lists
 */

import React, { memo, useCallback } from 'react';
import { Pressable, ViewStyle, StyleProp } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withSpring,
  withTiming,
  interpolate,
  Extrapolation,
  FadeInDown,
  FadeInUp,
  Layout,
} from 'react-native-reanimated';

import { haptics } from '@/constants/interaction';
import { colors } from '@/constants/theme';

// ============================================================================
// TYPES
// ============================================================================

type CardVariant = 'default' | 'elevated' | 'outline' | 'ghost';

interface PremiumCardProps {
  children: React.ReactNode;
  variant?: CardVariant;
  onPress?: () => void;
  onLongPress?: () => void;
  disabled?: boolean;
  hapticOnPress?: boolean;
  className?: string;
  style?: StyleProp<ViewStyle>;
  // Animation props
  animateOnMount?: boolean;
  mountDelay?: number;
  // Stagger support
  index?: number;
  staggerDelay?: number;
}

// ============================================================================
// CONSTANTS
// ============================================================================

const SPRING_CONFIG = {
  damping: 15,
  stiffness: 300,
  mass: 0.5,
};

const PRESS_SCALE = 0.98;
const LIFT_TRANSLATE_Y = -2;

// Variant styles
const variantStyles: Record<CardVariant, ViewStyle> = {
  default: {
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
  elevated: {
    backgroundColor: colors.white,
    borderRadius: 16,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.1,
    shadowRadius: 12,
    elevation: 8,
    borderWidth: 0,
  },
  outline: {
    backgroundColor: 'transparent',
    borderRadius: 16,
    borderWidth: 1.5,
    borderColor: colors.gray[200],
    shadowOpacity: 0,
    elevation: 0,
  },
  ghost: {
    backgroundColor: 'transparent',
    borderRadius: 16,
    borderWidth: 0,
    shadowOpacity: 0,
    elevation: 0,
  },
};

// ============================================================================
// ANIMATED PRESSABLE
// ============================================================================

const AnimatedPressable = Animated.createAnimatedComponent(Pressable);

// ============================================================================
// COMPONENT
// ============================================================================

export const PremiumCard = memo(function PremiumCard({
  children,
  variant = 'default',
  onPress,
  onLongPress,
  disabled = false,
  hapticOnPress = true,
  className,
  style,
  animateOnMount = false,
  mountDelay = 0,
  index = 0,
  staggerDelay = 50,
}: PremiumCardProps) {
  const isPressed = useSharedValue(0);
  const isLongPressed = useSharedValue(0);

  // Handle press in
  const handlePressIn = useCallback(() => {
    isPressed.value = withSpring(1, SPRING_CONFIG);
  }, []);

  // Handle press out
  const handlePressOut = useCallback(() => {
    isPressed.value = withSpring(0, SPRING_CONFIG);
    isLongPressed.value = withSpring(0, SPRING_CONFIG);
  }, []);

  // Handle press
  const handlePress = useCallback(() => {
    if (disabled) return;
    if (hapticOnPress) {
      haptics.tap();
    }
    onPress?.();
  }, [disabled, hapticOnPress, onPress]);

  // Handle long press
  const handleLongPress = useCallback(() => {
    if (disabled) return;
    isLongPressed.value = withSpring(1, SPRING_CONFIG);
    haptics.success();
    onLongPress?.();
  }, [disabled, onLongPress]);

  // Animated styles
  const animatedStyle = useAnimatedStyle(() => {
    const scale = interpolate(
      isPressed.value,
      [0, 1],
      [1, PRESS_SCALE],
      Extrapolation.CLAMP
    );

    const translateY = interpolate(
      isLongPressed.value,
      [0, 1],
      [0, LIFT_TRANSLATE_Y],
      Extrapolation.CLAMP
    );

    const shadowOpacity = interpolate(
      isPressed.value,
      [0, 1],
      [variant === 'elevated' ? 0.1 : 0.05, 0.02],
      Extrapolation.CLAMP
    );

    const shadowRadius = interpolate(
      isLongPressed.value,
      [0, 1],
      [variant === 'elevated' ? 12 : 4, 20],
      Extrapolation.CLAMP
    );

    return {
      transform: [{ scale }, { translateY }],
      shadowOpacity,
      shadowRadius,
    };
  });

  // Calculate mount animation delay based on index
  const calculatedDelay = mountDelay + index * staggerDelay;

  // Determine entering animation
  const enteringAnimation = animateOnMount
    ? FadeInDown.duration(300).delay(calculatedDelay).springify()
    : undefined;

  const baseStyle = variantStyles[variant];

  return (
    <AnimatedPressable
      onPress={onPress ? handlePress : undefined}
      onLongPress={onLongPress ? handleLongPress : undefined}
      onPressIn={onPress || onLongPress ? handlePressIn : undefined}
      onPressOut={onPress || onLongPress ? handlePressOut : undefined}
      disabled={disabled}
      entering={enteringAnimation}
      layout={Layout.springify()}
      style={[
        baseStyle,
        {
          overflow: 'hidden',
          opacity: disabled ? 0.5 : 1,
        },
        animatedStyle,
        style,
      ]}
      className={className}
    >
      {children}
    </AnimatedPressable>
  );
});

// ============================================================================
// PRESET COMPONENTS
// ============================================================================

/**
 * Card with default styling (subtle shadow)
 */
export const Card = memo(function Card(
  props: Omit<PremiumCardProps, 'variant'>
) {
  return <PremiumCard variant="default" {...props} />;
});

/**
 * Card with elevated styling (prominent shadow)
 */
export const ElevatedCard = memo(function ElevatedCard(
  props: Omit<PremiumCardProps, 'variant'>
) {
  return <PremiumCard variant="elevated" {...props} />;
});

/**
 * Card with outline styling (border, no shadow)
 */
export const OutlineCard = memo(function OutlineCard(
  props: Omit<PremiumCardProps, 'variant'>
) {
  return <PremiumCard variant="outline" {...props} />;
});

/**
 * Ghost card (transparent, no border)
 */
export const GhostCard = memo(function GhostCard(
  props: Omit<PremiumCardProps, 'variant'>
) {
  return <PremiumCard variant="ghost" {...props} />;
});

export default PremiumCard;
