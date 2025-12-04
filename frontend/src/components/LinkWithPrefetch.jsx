/**
 * LinkWithPrefetch - Smart Link component with automatic prefetching
 *
 * Wraps React Router's Link to automatically prefetch data
 * when user hovers over the link. Makes navigation feel instant.
 *
 * Features:
 * - Automatic data prefetching on hover
 * - View Transitions API for smooth page animations
 * - Graceful degradation on older browsers
 *
 * Usage:
 * <LinkWithPrefetch to={`/members/${id}`} prefetchType="member" prefetchId={id}>
 *   View Member
 * </LinkWithPrefetch>
 */

import React, { useCallback } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { usePrefetch } from '@/hooks/usePrefetch';

/**
 * Check if View Transitions API is supported
 */
const supportsViewTransitions = typeof document !== 'undefined' && 'startViewTransition' in document;

/**
 * Enhanced Link with automatic data prefetching and View Transitions
 *
 * @param {string} to - Route path
 * @param {string} prefetchType - Type of data to prefetch: 'member' | 'dashboard' | 'membersList'
 * @param {string} prefetchId - ID to pass to prefetch function (for member)
 * @param {boolean} useViewTransition - Enable View Transitions API (default: false - causes data fetch issues)
 * @param {React.ReactNode} children - Link content
 * @param {object} props - Additional props passed to Link
 */
export function LinkWithPrefetch({
  to,
  prefetchType,
  prefetchId,
  useViewTransition = false, // Disabled by default - causes "member not found" issues
  children,
  className,
  ...props
}) {
  const navigate = useNavigate();
  const { prefetchMember, prefetchDashboard, prefetchMembersList, cancelPrefetch } = usePrefetch();

  const handleMouseEnter = useCallback(() => {
    switch (prefetchType) {
      case 'member':
        if (prefetchId) prefetchMember(prefetchId);
        break;
      case 'dashboard':
        prefetchDashboard();
        break;
      case 'membersList':
        prefetchMembersList();
        break;
      default:
        // Auto-detect from route pattern
        if (to.startsWith('/members/') && to !== '/members') {
          const id = to.split('/members/')[1];
          if (id) prefetchMember(id);
        } else if (to === '/dashboard' || to === '/') {
          prefetchDashboard();
        } else if (to === '/members') {
          prefetchMembersList();
        }
    }
  }, [prefetchType, prefetchId, to, prefetchMember, prefetchDashboard, prefetchMembersList]);

  const handleMouseLeave = useCallback(() => {
    cancelPrefetch();
  }, [cancelPrefetch]);

  /**
   * Handle click with View Transitions API
   * Creates smooth morphing animation between pages
   */
  const handleClick = useCallback((e) => {
    // Only use View Transitions for same-origin navigation
    if (!useViewTransition || !supportsViewTransitions) {
      return; // Let Link handle normally
    }

    // Prevent default link behavior
    e.preventDefault();

    // Start view transition with proper async handling
    // The transition captures the current state, then we navigate
    const transition = document.startViewTransition(async () => {
      // Navigate and wait for it to complete
      navigate(to);
      // Give React time to update the DOM
      await new Promise(resolve => setTimeout(resolve, 0));
    });

    // Handle transition errors gracefully
    transition.finished.catch(() => {
      // If transition fails, ensure navigation still happens
      console.debug('[ViewTransition] Transition interrupted');
    });
  }, [to, useViewTransition, navigate]);

  return (
    <Link
      to={to}
      className={className}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
      onClick={handleClick}
      {...props}
    >
      {children}
    </Link>
  );
}

/**
 * MemberLink - Convenience wrapper for member links
 * Automatically extracts member ID from 'to' prop
 */
export function MemberLink({ memberId, children, className, ...props }) {
  return (
    <LinkWithPrefetch
      to={`/members/${memberId}`}
      prefetchType="member"
      prefetchId={memberId}
      className={className}
      {...props}
    >
      {children}
    </LinkWithPrefetch>
  );
}

/**
 * DashboardLink - Convenience wrapper for dashboard link
 */
export function DashboardLink({ children, className, ...props }) {
  return (
    <LinkWithPrefetch
      to="/dashboard"
      prefetchType="dashboard"
      className={className}
      {...props}
    >
      {children}
    </LinkWithPrefetch>
  );
}

export default LinkWithPrefetch;
