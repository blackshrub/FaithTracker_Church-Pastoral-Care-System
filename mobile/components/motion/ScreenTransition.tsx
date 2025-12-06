/**
 * ScreenTransition - Animated screen wrapper
 *
 * Provides smooth enter/exit animations for screens
 * Respects reduced motion preferences
 */

import React, { memo, ReactNode } from 'react';
import { View, StyleSheet } from 'react-native';
import Animated, {
  FadeIn,
  FadeOut,
  SlideInRight,
  SlideOutLeft,
  SlideInUp,
  SlideOutDown,
  FadeInDown,
  FadeOutUp,
  withSpring,
  withTiming,
} from 'react-native-reanimated';

import { useReducedMotion } from '@/hooks/useReducedMotion';

// ============================================================================
// TYPES
// ============================================================================

type TransitionType = 'fade' | 'slide' | 'slideUp' | 'fadeSlide' | 'none';

interface ScreenTransitionProps {
  children: ReactNode;
  /** Type of transition animation */
  transition?: TransitionType;
  /** Duration in ms (ignored if reduced motion) */
  duration?: number;
  /** Delay before animation starts */
  delay?: number;
  /** Additional className */
  className?: string;
}

// ============================================================================
// ANIMATION CONFIGS
// ============================================================================

const createEntering = (type: TransitionType, duration: number, delay: number, skipAnimation: boolean) => {
  if (skipAnimation || type === 'none') {
    return undefined;
  }

  const config = { duration };
  const delayMs = delay;

  switch (type) {
    case 'fade':
      return FadeIn.duration(duration).delay(delayMs);
    case 'slide':
      return SlideInRight.duration(duration).delay(delayMs).springify().damping(20);
    case 'slideUp':
      return SlideInUp.duration(duration).delay(delayMs).springify().damping(20);
    case 'fadeSlide':
      return FadeInDown.duration(duration).delay(delayMs);
    default:
      return FadeIn.duration(duration).delay(delayMs);
  }
};

const createExiting = (type: TransitionType, duration: number, skipAnimation: boolean) => {
  if (skipAnimation || type === 'none') {
    return undefined;
  }

  switch (type) {
    case 'fade':
      return FadeOut.duration(duration);
    case 'slide':
      return SlideOutLeft.duration(duration);
    case 'slideUp':
      return SlideOutDown.duration(duration);
    case 'fadeSlide':
      return FadeOutUp.duration(duration);
    default:
      return FadeOut.duration(duration);
  }
};

// ============================================================================
// COMPONENT
// ============================================================================

export const ScreenTransition = memo(function ScreenTransition({
  children,
  transition = 'fadeSlide',
  duration = 300,
  delay = 0,
  className = '',
}: ScreenTransitionProps) {
  const reducedMotion = useReducedMotion();

  const entering = createEntering(transition, duration, delay, reducedMotion);
  const exiting = createExiting(transition, duration / 2, reducedMotion);

  return (
    <Animated.View
      entering={entering}
      exiting={exiting}
      className={`flex-1 ${className}`}
    >
      {children}
    </Animated.View>
  );
});

// ============================================================================
// STAGGER ANIMATION WRAPPER
// ============================================================================

interface StaggerChildProps {
  children: ReactNode;
  index: number;
  /** Base delay between items in ms */
  staggerDelay?: number;
  /** Duration of each item animation */
  duration?: number;
  /** Type of animation */
  type?: 'fadeIn' | 'fadeInDown' | 'fadeInUp' | 'fadeInRight';
  className?: string;
}

export const StaggerChild = memo(function StaggerChild({
  children,
  index,
  staggerDelay = 50,
  duration = 300,
  type = 'fadeInDown',
  className = '',
}: StaggerChildProps) {
  const reducedMotion = useReducedMotion();
  const delay = index * staggerDelay;

  if (reducedMotion) {
    return <View className={className}>{children}</View>;
  }

  const entering = (() => {
    switch (type) {
      case 'fadeIn':
        return FadeIn.duration(duration).delay(delay);
      case 'fadeInUp':
        return SlideInUp.duration(duration).delay(delay).springify().damping(15);
      case 'fadeInRight':
        return SlideInRight.duration(duration).delay(delay).springify().damping(15);
      case 'fadeInDown':
      default:
        return FadeInDown.duration(duration).delay(delay);
    }
  })();

  return (
    <Animated.View entering={entering} className={className}>
      {children}
    </Animated.View>
  );
});

// ============================================================================
// LOADING TRANSITION
// ============================================================================

interface LoadingTransitionProps {
  isLoading: boolean;
  loadingComponent: ReactNode;
  children: ReactNode;
  /** Duration of cross-fade */
  duration?: number;
}

export const LoadingTransition = memo(function LoadingTransition({
  isLoading,
  loadingComponent,
  children,
  duration = 200,
}: LoadingTransitionProps) {
  const reducedMotion = useReducedMotion();

  if (reducedMotion) {
    return <View style={StyleSheet.absoluteFill}>{isLoading ? loadingComponent : children}</View>;
  }

  return (
    <View style={StyleSheet.absoluteFill}>
      {isLoading ? (
        <Animated.View
          entering={FadeIn.duration(duration)}
          exiting={FadeOut.duration(duration)}
          style={StyleSheet.absoluteFill}
        >
          {loadingComponent}
        </Animated.View>
      ) : (
        <Animated.View
          entering={FadeIn.duration(duration)}
          style={StyleSheet.absoluteFill}
        >
          {children}
        </Animated.View>
      )}
    </View>
  );
});

export default ScreenTransition;
