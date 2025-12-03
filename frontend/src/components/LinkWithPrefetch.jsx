/**
 * LinkWithPrefetch - Smart Link component with automatic prefetching
 *
 * Wraps React Router's Link to automatically prefetch data
 * when user hovers over the link. Makes navigation feel instant.
 *
 * Usage:
 * <LinkWithPrefetch to={`/members/${id}`} prefetchType="member" prefetchId={id}>
 *   View Member
 * </LinkWithPrefetch>
 */

import React, { useCallback } from 'react';
import { Link } from 'react-router-dom';
import { usePrefetch } from '@/hooks/usePrefetch';

/**
 * Enhanced Link with automatic data prefetching
 *
 * @param {string} to - Route path
 * @param {string} prefetchType - Type of data to prefetch: 'member' | 'dashboard' | 'membersList'
 * @param {string} prefetchId - ID to pass to prefetch function (for member)
 * @param {React.ReactNode} children - Link content
 * @param {object} props - Additional props passed to Link
 */
export function LinkWithPrefetch({
  to,
  prefetchType,
  prefetchId,
  children,
  className,
  ...props
}) {
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

  return (
    <Link
      to={to}
      className={className}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleMouseEnter}
      onBlur={handleMouseLeave}
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
