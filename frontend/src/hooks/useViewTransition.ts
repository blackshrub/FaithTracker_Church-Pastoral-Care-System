/**
 * useViewTransition - Hook for programmatic navigation with View Transitions API
 *
 * Provides smooth page transitions for button clicks, form submissions,
 * and other programmatic navigation scenarios.
 *
 * Usage:
 * const { navigate, isTransitioning } = useViewTransition();
 * navigate('/members/123'); // Smooth transition
 *
 * Features:
 * - Automatic fallback on unsupported browsers
 * - Respects prefers-reduced-motion
 * - Returns transition state for loading indicators
 */

import { useCallback } from 'react';
import { flushSync } from 'react-dom';
import {
  useNavigate as useRouterNavigate,
  useNavigation,
  type NavigateOptions,
} from 'react-router-dom';

/**
 * Check if View Transitions API is supported
 */
const supportsViewTransitions =
  typeof document !== 'undefined' && 'startViewTransition' in document;

/**
 * Live check for prefers-reduced-motion. Read on every transition attempt
 * (not at module load) so users who toggle the OS accessibility setting
 * mid-session — or whose system theme changes — get the right behavior.
 */
function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return Boolean(window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches);
}

export interface UseViewTransitionReturn {
  navigate: (to: string, options?: NavigateOptions) => void;
  goBack: () => void;
  isTransitioning: boolean;
  supportsViewTransitions: boolean;
}

/**
 * Hook for navigation with View Transitions.
 *
 * Delegates to React Router's `viewTransition` navigation option rather than
 * wrapping `startViewTransition()` by hand. The data router coordinates the
 * transition snapshot with React's commit (flushSync internally) so the new
 * DOM is in place before the animation runs. The previous hand-rolled version
 * called `routerNavigate` inside the transition callback, which raced React 19's
 * async commit and threw "Failed to execute 'removeChild' on 'Node'".
 */
export function useViewTransition(): UseViewTransitionReturn {
  const routerNavigate = useRouterNavigate();
  const navigation = useNavigation();

  /**
   * Navigate with View Transition animation
   */
  const navigate = useCallback(
    (to: string, options: NavigateOptions = {}): void => {
      const animate = supportsViewTransitions && !prefersReducedMotion();
      routerNavigate(to, { ...options, viewTransition: animate });
    },
    [routerNavigate]
  );

  /**
   * Navigate back. The delta form of navigate() takes no options, so the
   * transition is only applied to forward navigations that pass a path.
   */
  const goBack = useCallback((): void => {
    routerNavigate(-1);
  }, [routerNavigate]);

  return {
    navigate,
    goBack,
    // Reflects the router's in-flight navigation state (data router).
    isTransitioning: navigation.state !== 'idle',
    supportsViewTransitions,
  };
}

/**
 * Utility function to run any DOM update with View Transition
 * Useful for non-navigation state changes that should animate
 */
export function withViewTransition(updateCallback: () => void): ViewTransition | undefined {
  if (!supportsViewTransitions || prefersReducedMotion()) {
    updateCallback();
    return undefined;
  }

  // flushSync forces any React state update in the callback to commit
  // synchronously, so the new DOM exists before the transition snapshots it.
  // Without it, React 19's async commit lands mid-transition and can throw
  // "Failed to execute 'removeChild' on 'Node'".
  return document.startViewTransition(() => {
    flushSync(updateCallback);
  });
}

export default useViewTransition;
