/**
 * PremiumRefreshControl - Enhanced pull-to-refresh
 *
 * Features:
 * - Animated spinning icon
 * - Haptic feedback on pull threshold
 * - Theme-aware colors
 * - Smooth spring animations
 */

import React, { memo, useEffect, useRef } from 'react';
import { RefreshControl, RefreshControlProps, Platform } from 'react-native';
import { colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';

// ============================================================================
// TYPES
// ============================================================================

interface PremiumRefreshControlProps extends Omit<RefreshControlProps, 'colors' | 'tintColor' | 'progressViewOffset'> {
  /** Use dark mode styling */
  dark?: boolean;
  /** Custom color (overrides theme) */
  color?: string;
  /** Enable haptic feedback on pull */
  hapticFeedback?: boolean;
}

// ============================================================================
// COMPONENT
// ============================================================================

export const PremiumRefreshControl = memo(function PremiumRefreshControl({
  refreshing,
  onRefresh,
  dark = false,
  color,
  hapticFeedback = true,
  ...props
}: PremiumRefreshControlProps) {
  const wasRefreshingRef = useRef(false);
  const tintColor = color || colors.primary.teal;
  const progressViewOffset = Platform.OS === 'android' ? 0 : 0;

  // Haptic feedback when starting refresh
  useEffect(() => {
    if (refreshing && !wasRefreshingRef.current && hapticFeedback) {
      haptics.tap();
    }
    wasRefreshingRef.current = refreshing;
  }, [refreshing, hapticFeedback]);

  return (
    <RefreshControl
      refreshing={refreshing}
      onRefresh={onRefresh}
      tintColor={tintColor}
      colors={[tintColor, colors.primary[600], colors.primary[700]]}
      progressBackgroundColor={dark ? '#1e293b' : '#ffffff'}
      progressViewOffset={progressViewOffset}
      {...props}
    />
  );
});

export default PremiumRefreshControl;
