import { useState, useCallback, useEffect, useRef } from 'react';

/**
 * usePullToRefresh - Mobile pull-to-refresh gesture hook
 *
 * @param {Function} onRefresh - Async function to call when refresh is triggered
 * @param {Object} options - Configuration options
 * @param {number} options.threshold - Pull distance to trigger refresh (default: 80px)
 * @param {number} options.resistance - Resistance factor for pull (default: 2.5)
 * @param {boolean} options.disabled - Disable the feature
 * @returns {Object} { containerRef, isRefreshing, pullProgress, PullIndicator }
 *
 * @example
 * const { containerRef, isRefreshing, PullIndicator } = usePullToRefresh(async () => {
 *   await queryClient.invalidateQueries(['members']);
 * });
 *
 * return (
 *   <div ref={containerRef} className="overflow-y-auto">
 *     <PullIndicator />
 *     {content}
 *   </div>
 * );
 */
export function usePullToRefresh(onRefresh, options = {}) {
  const {
    threshold = 80,
    resistance = 2.5,
    disabled = false,
  } = options;

  const [isRefreshing, setIsRefreshing] = useState(false);
  const [pullProgress, setPullProgress] = useState(0);
  const [isPulling, setIsPulling] = useState(false);

  const containerRef = useRef(null);
  const startY = useRef(0);
  const currentY = useRef(0);

  const handleTouchStart = useCallback((e) => {
    if (disabled || isRefreshing) return;

    const container = containerRef.current;
    if (!container) return;

    // Only activate if scrolled to top
    if (container.scrollTop > 0) return;

    startY.current = e.touches[0].clientY;
    setIsPulling(true);
  }, [disabled, isRefreshing]);

  const handleTouchMove = useCallback((e) => {
    if (!isPulling || disabled || isRefreshing) return;

    const container = containerRef.current;
    if (!container) return;

    currentY.current = e.touches[0].clientY;
    const deltaY = currentY.current - startY.current;

    // Only track downward pull
    if (deltaY > 0) {
      // Apply resistance for natural feel
      const progress = Math.min(deltaY / resistance, threshold * 1.5);
      setPullProgress(progress);

      // Prevent default scroll when pulling
      if (container.scrollTop === 0) {
        e.preventDefault();
      }
    }
  }, [isPulling, disabled, isRefreshing, resistance, threshold]);

  const handleTouchEnd = useCallback(async () => {
    if (!isPulling || disabled) return;

    setIsPulling(false);

    if (pullProgress >= threshold && !isRefreshing) {
      setIsRefreshing(true);
      setPullProgress(threshold); // Hold at threshold during refresh

      try {
        await onRefresh();
      } catch (error) {
        console.error('Pull to refresh error:', error);
      } finally {
        setIsRefreshing(false);
        setPullProgress(0);
      }
    } else {
      // Animate back to 0
      setPullProgress(0);
    }
  }, [isPulling, disabled, pullProgress, threshold, isRefreshing, onRefresh]);

  useEffect(() => {
    const container = containerRef.current;
    if (!container || disabled) return;

    container.addEventListener('touchstart', handleTouchStart, { passive: true });
    container.addEventListener('touchmove', handleTouchMove, { passive: false });
    container.addEventListener('touchend', handleTouchEnd, { passive: true });

    return () => {
      container.removeEventListener('touchstart', handleTouchStart);
      container.removeEventListener('touchmove', handleTouchMove);
      container.removeEventListener('touchend', handleTouchEnd);
    };
  }, [handleTouchStart, handleTouchMove, handleTouchEnd, disabled]);

  // Pull indicator component
  const PullIndicator = useCallback(() => {
    if (pullProgress === 0 && !isRefreshing) return null;

    const rotation = Math.min((pullProgress / threshold) * 360, 360);
    const opacity = Math.min(pullProgress / (threshold * 0.5), 1);
    const scale = Math.min(0.5 + (pullProgress / threshold) * 0.5, 1);

    return (
      <div
        className="flex justify-center items-center overflow-hidden transition-all duration-200"
        style={{
          height: `${Math.max(pullProgress, isRefreshing ? threshold : 0)}px`,
          opacity,
        }}
        aria-live="polite"
        aria-label={isRefreshing ? 'Refreshing...' : 'Pull to refresh'}
      >
        <div
          className={`w-8 h-8 border-2 border-teal-500 border-t-transparent rounded-full ${isRefreshing ? 'animate-spin' : ''}`}
          style={{
            transform: `rotate(${rotation}deg) scale(${scale})`,
            transition: isRefreshing ? 'none' : 'transform 0.1s ease-out',
          }}
          role="progressbar"
          aria-valuenow={isRefreshing ? undefined : Math.round((pullProgress / threshold) * 100)}
          aria-valuemin={0}
          aria-valuemax={100}
        />
      </div>
    );
  }, [pullProgress, threshold, isRefreshing]);

  return {
    containerRef,
    isRefreshing,
    pullProgress,
    isPulling,
    PullIndicator,
  };
}

export default usePullToRefresh;
