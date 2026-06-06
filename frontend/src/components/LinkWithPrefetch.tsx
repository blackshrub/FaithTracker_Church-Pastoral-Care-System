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
import { Link, type LinkProps } from 'react-router-dom';

import { usePrefetch } from '@/hooks/usePrefetch';

/**
 * Live check for hover-capable input. Used for onMouseEnter, NOT onFocus —
 * keyboard focus represents intentional user navigation regardless of
 * input device, so we keep prefetch on for focus on touch + keyboard
 * combos (e.g. tablet with bluetooth keyboard).
 */
function shouldSkipHoverPrefetch(): boolean {
  if (typeof window === 'undefined') return true;
  // Touch / coarse-pointer devices fire onMouseEnter as a synthesized
  // pointer event after tap, so prefetch would race the navigation
  // itself and waste mobile bandwidth.
  if (window.matchMedia?.('(hover: none)').matches) return true;
  if (window.matchMedia?.('(pointer: coarse)').matches) return true;
  // Honor Save-Data when the browser exposes it (Chromium-based).
  const conn = (navigator as unknown as { connection?: { saveData?: boolean } }).connection;
  if (conn?.saveData) return true;
  return false;
}

/** Save-Data check only — applied to focus prefetch (skip touch detection). */
function shouldSkipFocusPrefetch(): boolean {
  if (typeof window === 'undefined') return true;
  const conn = (navigator as unknown as { connection?: { saveData?: boolean } }).connection;
  return Boolean(conn?.saveData);
}

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
  const { prefetchMember, prefetchDashboard, prefetchMembersList, cancelPrefetch } = usePrefetch();

  const doPrefetch = useCallback(() => {
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

  const handleMouseEnter = useCallback(() => {
    if (shouldSkipHoverPrefetch()) return;
    doPrefetch();
  }, [doPrefetch]);

  const handleFocus = useCallback(() => {
    if (shouldSkipFocusPrefetch()) return;
    doPrefetch();
  }, [doPrefetch]);

  const handleMouseLeave = useCallback(() => {
    cancelPrefetch();
  }, [cancelPrefetch]);

  // View Transitions are delegated to React Router's `viewTransition` prop.
  // The data router coordinates the transition snapshot with React's commit
  // (flushSync + startViewTransition internally), so the DOM is fully updated
  // before the animation runs. Hand-rolling startViewTransition() around an
  // async navigate() raced React's async commit and threw "Failed to execute
  // 'removeChild'" when the reconciler unmounted nodes the transition had moved.
  return (
    <Link
      to={to}
      viewTransition={useViewTransition}
      className={className}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocus={handleFocus}
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
