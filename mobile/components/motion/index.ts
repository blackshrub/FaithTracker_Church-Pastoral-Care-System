/**
 * Motion Components
 *
 * Premium animation system for FaithTracker mobile
 */

// Premium motion presets and timing
export {
  // V10 - Latest production-grade presets
  PMotionV10,
  V10_EASING,
  V10_DURATION,
  V10_CONFIG,
  // V9 - Apple-friendly shared axis
  PMotionV9,
  V9_EASING,
  V9_DURATION,
  // V5 - Bentley-grade transitions
  PMotionV5,
  TAB_TRANSITION_V5,
  phasedEnter,
  phasedExit,
  getTabTransitionConfigV5,
  // V2 Compatible
  PMotion,
  TAB_TRANSITION,
  getTabTransitionConfig,
  // Constants
  MOTION_DURATION,
  MOTION_EASING,
  MOTION_SPRING,
  // Timing helpers
  standardTiming,
  decelerateTiming,
  accelerateTiming,
  gentleSpring,
  responsiveSpring,
  sharedSpring,
  overshootSpring,
  iosTiming,
  // Global motion delay
  GLOBAL_MOTION_DELAY,
  getGlobalMotionDelay,
  setGlobalMotionDelay,
  // Visited screens tracker
  shouldSkipEnteringAnimation,
  clearVisitedScreen,
  clearAllVisitedScreens,
} from './premium-motion';

// Screen transition wrapper
export {
  ScreenTransition,
  StaggerChild,
  LoadingTransition,
} from './ScreenTransition';
