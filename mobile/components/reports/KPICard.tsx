/**
 * KPICard - Key Performance Indicator Card
 *
 * Displays a KPI metric with:
 * - Circular progress indicator
 * - Percentage value
 * - Label
 * - Target indicator
 */

import React, { memo, useEffect } from 'react';
import { View, Text } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedProps,
  withTiming,
  Easing,
  interpolate,
} from 'react-native-reanimated';
import Svg, { Circle } from 'react-native-svg';

import { colors } from '@/constants/theme';

// ============================================================================
// TYPES
// ============================================================================

interface KPICardProps {
  label: string;
  value: number; // 0-100 percentage
  target?: number; // Target percentage (e.g., 80%)
  color?: string;
  size?: 'small' | 'medium' | 'large';
  animated?: boolean;
}

// ============================================================================
// ANIMATED CIRCLE COMPONENT
// ============================================================================

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

interface CircularProgressProps {
  progress: number;
  size: number;
  strokeWidth: number;
  color: string;
  animated: boolean;
}

const CircularProgress = memo(function CircularProgress({
  progress,
  size,
  strokeWidth,
  color,
  animated,
}: CircularProgressProps) {
  const animatedProgress = useSharedValue(animated ? 0 : progress);
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;

  useEffect(() => {
    if (animated) {
      animatedProgress.value = withTiming(progress, {
        duration: 1000,
        easing: Easing.out(Easing.cubic),
      });
    } else {
      animatedProgress.value = progress;
    }
  }, [progress, animated]);

  const animatedProps = useAnimatedProps(() => {
    const strokeDashoffset = interpolate(
      animatedProgress.value,
      [0, 100],
      [circumference, 0]
    );
    return {
      strokeDashoffset,
    };
  });

  return (
    <Svg width={size} height={size} style={{ transform: [{ rotate: '-90deg' }] }}>
      {/* Background circle */}
      <Circle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        stroke="#e5e7eb"
        strokeWidth={strokeWidth}
        fill="transparent"
      />
      {/* Progress circle */}
      <AnimatedCircle
        cx={size / 2}
        cy={size / 2}
        r={radius}
        stroke={color}
        strokeWidth={strokeWidth}
        fill="transparent"
        strokeDasharray={circumference}
        strokeLinecap="round"
        animatedProps={animatedProps}
      />
    </Svg>
  );
});

// ============================================================================
// MAIN COMPONENT
// ============================================================================

export const KPICard = memo(function KPICard({
  label,
  value,
  target = 80,
  color = colors.primary.teal,
  size = 'medium',
  animated = true,
}: KPICardProps) {
  // Size configurations
  const sizeConfig = {
    small: { circleSize: 60, strokeWidth: 5, fontSize: 'text-lg', labelSize: 'text-[10px]' },
    medium: { circleSize: 80, strokeWidth: 6, fontSize: 'text-2xl', labelSize: 'text-xs' },
    large: { circleSize: 100, strokeWidth: 8, fontSize: 'text-3xl', labelSize: 'text-sm' },
  };

  const config = sizeConfig[size];
  const isAboveTarget = value >= target;
  const displayColor = isAboveTarget ? color : colors.status.warning;

  return (
    <View className="items-center">
      <View className="relative items-center justify-center">
        <CircularProgress
          progress={Math.min(value, 100)}
          size={config.circleSize}
          strokeWidth={config.strokeWidth}
          color={displayColor}
          animated={animated}
        />
        {/* Value in center */}
        <View
          className="absolute inset-0 items-center justify-center"
          style={{ width: config.circleSize, height: config.circleSize }}
        >
          <Text className={`${config.fontSize} font-bold text-gray-900`}>
            {Math.round(value)}%
          </Text>
        </View>
      </View>

      {/* Label */}
      <Text
        className={`${config.labelSize} text-gray-600 text-center mt-2 font-medium`}
        numberOfLines={2}
      >
        {label}
      </Text>

      {/* Target indicator */}
      {target && (
        <Text className="text-[10px] text-gray-400 mt-0.5">
          Target: {target}%
        </Text>
      )}
    </View>
  );
});

export default KPICard;
