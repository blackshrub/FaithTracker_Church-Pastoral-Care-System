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
import { useNavigate as useRouterNavigate } from 'react-router-dom';

/**
 * Check if View Transitions API is supported
 */
const supportsViewTransitions =
  typeof document !== 'undefined' && 'startViewTransition' in document;

/**
 * Check if user prefers reduced motion
 */
const prefersReducedMotion =
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)')?.matches;

/**
 * Hook for navigation with View Transitions
 */
export function useViewTransition() {
  const routerNavigate = useRouterNavigate();
  const [isTransitioning, setIsTransitioning] = useState(false);

  /**
   * Navigate with View Transition animation
   * @param {string} to - Destination path
   * @param {object} options - Navigation options (replace, state)
   */
  const navigate = useCallback(
    (to, options = {}) => {
      // Skip transitions if not supported or user prefers reduced motion
      if (!supportsViewTransitions || prefersReducedMotion) {
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
  const goBack = useCallback(() => {
    if (!supportsViewTransitions || prefersReducedMotion) {
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
 *
 * @param {Function} updateCallback - Function that updates the DOM
 * @returns {ViewTransition|undefined}
 */
export function withViewTransition(updateCallback) {
  if (!supportsViewTransitions || prefersReducedMotion) {
    updateCallback();
    return undefined;
  }

  return document.startViewTransition(updateCallback);
}

export default useViewTransition;
