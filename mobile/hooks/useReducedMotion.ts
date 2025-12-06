/**
 * useReducedMotion - Accessibility hook for motion preferences
 *
 * Respects user's system preference for reduced motion.
 * Use this to conditionally disable or simplify animations.
 */

import { useEffect, useState } from 'react';
import { AccessibilityInfo } from 'react-native';

/**
 * Hook to check if reduced motion is preferred
 * @returns true if user prefers reduced motion
 */
export function useReducedMotion(): boolean {
  const [reducedMotion, setReducedMotion] = useState(false);

  useEffect(() => {
    // Get initial value
    AccessibilityInfo.isReduceMotionEnabled().then(setReducedMotion);

    // Listen for changes
    const subscription = AccessibilityInfo.addEventListener(
      'reduceMotionChanged',
      setReducedMotion
    );

    return () => {
      subscription.remove();
    };
  }, []);

  return reducedMotion;
}

/**
 * Get animation duration based on reduced motion preference
 * @param normalDuration - Duration in ms for normal motion
 * @param reducedDuration - Duration in ms for reduced motion (default: 0)
 */
export function useAnimationDuration(
  normalDuration: number,
  reducedDuration: number = 0
): number {
  const reducedMotion = useReducedMotion();
  return reducedMotion ? reducedDuration : normalDuration;
}

/**
 * Get animation config for Reanimated based on reduced motion
 * Returns simplified or skipped animations when reduced motion is enabled
 */
export function useAnimationConfig() {
  const reducedMotion = useReducedMotion();

  return {
    /** Whether to skip animations entirely */
    skipAnimations: reducedMotion,
    /** Duration multiplier (0 for instant, 1 for normal) */
    durationMultiplier: reducedMotion ? 0 : 1,
    /** Get adjusted duration */
    getDuration: (ms: number) => (reducedMotion ? 0 : ms),
    /** Get adjusted delay */
    getDelay: (ms: number) => (reducedMotion ? 0 : ms),
  };
}

export default useReducedMotion;
