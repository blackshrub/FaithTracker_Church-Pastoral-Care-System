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

import { useCallback, useState } from 'react';
import { useNavigate as useRouterNavigate, type NavigateOptions } from 'react-router-dom';

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
  navigate: (to: string, options?: NavigateOptions) => ViewTransition | undefined;
  goBack: () => ViewTransition | undefined;
  isTransitioning: boolean;
  supportsViewTransitions: boolean;
}

/**
 * Hook for navigation with View Transitions
 */
export function useViewTransition(): UseViewTransitionReturn {
  const routerNavigate = useRouterNavigate();
  const [isTransitioning, setIsTransitioning] = useState(false);

  /**
   * Navigate with View Transition animation
   */
  const navigate = useCallback(
    (to: string, options: NavigateOptions = {}): ViewTransition | undefined => {
      // Skip transitions if not supported or user prefers reduced motion
      if (!supportsViewTransitions || prefersReducedMotion()) {
        routerNavigate(to, options);
        return;
      }

      setIsTransitioning(true);

      // Start view transition
      const transition = document.startViewTransition(() => {
        routerNavigate(to, options);
      });

      // Clean up after transition completes
      transition.finished.finally(() => {
        setIsTransitioning(false);
      });

      return transition;
    },
    [routerNavigate]
  );

  /**
   * Navigate back with View Transition
   */
  const goBack = useCallback((): ViewTransition | undefined => {
    if (!supportsViewTransitions || prefersReducedMotion()) {
      routerNavigate(-1);
      return;
    }

    setIsTransitioning(true);

    const transition = document.startViewTransition(() => {
      routerNavigate(-1);
    });

    transition.finished.finally(() => {
      setIsTransitioning(false);
    });

    return transition;
  }, [routerNavigate]);

  return {
    navigate,
    goBack,
    isTransitioning,
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

  return document.startViewTransition(updateCallback);
}

export default useViewTransition;
