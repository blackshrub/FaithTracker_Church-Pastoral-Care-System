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

import { useCallback, type ReactNode } from 'react';
import { Link, useNavigate, type LinkProps } from 'react-router-dom';

import { usePrefetch } from '@/hooks/usePrefetch';

/**
 * Check if View Transitions API is supported
 */
const supportsViewTransitions =
  typeof document !== 'undefined' && 'startViewTransition' in document;

type PrefetchType = 'member' | 'dashboard' | 'membersList';

interface LinkWithPrefetchProps extends Omit<LinkProps, 'to'> {
  to: string;
  prefetchType?: PrefetchType;
  prefetchId?: string;
  useViewTransition?: boolean;
  children: ReactNode;
  className?: string;
}

/**
 * Enhanced Link with automatic data prefetching and View Transitions
 */
export function LinkWithPrefetch({
  to,
  prefetchType,
  prefetchId,
  useViewTransition = true, // Smooth page transitions on supported browsers
  children,
  className,
  ...props
}: LinkWithPrefetchProps) {
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
  const handleClick = useCallback(
    (e: React.MouseEvent<HTMLAnchorElement>) => {
      // Only use View Transitions for same-origin navigation
      if (!useViewTransition || !supportsViewTransitions) {
        return; // Let Link handle normally
      }

      // Prevent default link behavior
      e.preventDefault();

      // Start view transition with proper async handling
      // The transition captures the current state, then we navigate
      const transition = (document as any).startViewTransition(async () => {
        // Navigate and wait for it to complete
        navigate(to);
        // Give React time to update the DOM
        await new Promise((resolve) => setTimeout(resolve, 0));
      });

      // Handle transition errors gracefully
      transition.finished.catch(() => {
        // Transition interrupted - navigation still happens, no action needed
      });
    },
    [to, useViewTransition, navigate]
  );

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
interface MemberLinkProps extends Omit<
  LinkWithPrefetchProps,
  'to' | 'prefetchType' | 'prefetchId'
> {
  memberId: string;
}

export function MemberLink({ memberId, children, className, ...props }: MemberLinkProps) {
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
interface DashboardLinkProps extends Omit<LinkWithPrefetchProps, 'to' | 'prefetchType'> {
  children: ReactNode;
}

export function DashboardLink({ children, className, ...props }: DashboardLinkProps) {
  return (
    <LinkWithPrefetch to="/dashboard" prefetchType="dashboard" className={className} {...props}>
      {children}
    </LinkWithPrefetch>
  );
}

export default LinkWithPrefetch;
