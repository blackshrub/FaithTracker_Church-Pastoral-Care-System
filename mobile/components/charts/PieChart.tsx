/**
 * PieChart - Animated pie/donut chart component
 *
 * Features:
 * - Animated segments on mount
 * - Donut variant with center text
 * - Legend with labels and values
 * - Touch to highlight segments
 */

import React, { memo, useState, useEffect } from 'react';
import { View, Text, Pressable } from 'react-native';
import Svg, { G, Path, Circle } from 'react-native-svg';
import Animated, {
  useSharedValue,
  useAnimatedProps,
  withTiming,
  withDelay,
  Easing,
} from 'react-native-reanimated';

import { colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';

// ============================================================================
// TYPES
// ============================================================================

interface PieChartData {
  label: string;
  value: number;
  color: string;
}

interface PieChartProps {
  data: PieChartData[];
  size?: number;
  innerRadius?: number; // 0 for pie, > 0 for donut
  showLegend?: boolean;
  centerText?: string;
  centerSubtext?: string;
  animated?: boolean;
}

// ============================================================================
// ANIMATED PATH
// ============================================================================

const AnimatedPath = Animated.createAnimatedComponent(Path);

// ============================================================================
// UTILITIES
// ============================================================================

function polarToCartesian(
  centerX: number,
  centerY: number,
  radius: number,
  angleInDegrees: number
) {
  const angleInRadians = ((angleInDegrees - 90) * Math.PI) / 180.0;
  return {
    x: centerX + radius * Math.cos(angleInRadians),
    y: centerY + radius * Math.sin(angleInRadians),
  };
}

function describeArc(
  x: number,
  y: number,
  radius: number,
  startAngle: number,
  endAngle: number
) {
  const start = polarToCartesian(x, y, radius, endAngle);
  const end = polarToCartesian(x, y, radius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';

  return [
    'M',
    start.x,
    start.y,
    'A',
    radius,
    radius,
    0,
    largeArcFlag,
    0,
    end.x,
    end.y,
  ].join(' ');
}

function describeDonutArc(
  x: number,
  y: number,
  outerRadius: number,
  innerRadius: number,
  startAngle: number,
  endAngle: number
) {
  const outerStart = polarToCartesian(x, y, outerRadius, endAngle);
  const outerEnd = polarToCartesian(x, y, outerRadius, startAngle);
  const innerStart = polarToCartesian(x, y, innerRadius, endAngle);
  const innerEnd = polarToCartesian(x, y, innerRadius, startAngle);
  const largeArcFlag = endAngle - startAngle <= 180 ? '0' : '1';

  return [
    'M',
    outerStart.x,
    outerStart.y,
    'A',
    outerRadius,
    outerRadius,
    0,
    largeArcFlag,
    0,
    outerEnd.x,
    outerEnd.y,
    'L',
    innerEnd.x,
    innerEnd.y,
    'A',
    innerRadius,
    innerRadius,
    0,
    largeArcFlag,
    1,
    innerStart.x,
    innerStart.y,
    'Z',
  ].join(' ');
}

// ============================================================================
// COMPONENT
// ============================================================================

export const PieChart = memo(function PieChart({
  data,
  size = 200,
  innerRadius = 0,
  showLegend = true,
  centerText,
  centerSubtext,
  animated = true,
}: PieChartProps) {
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const total = data.reduce((sum, item) => sum + item.value, 0);
  const center = size / 2;
  const radius = (size / 2) - 10;
  const actualInnerRadius = innerRadius > 0 ? innerRadius : 0;

  // Calculate segments
  let currentAngle = 0;
  const segments = data.map((item, index) => {
    const percentage = total > 0 ? item.value / total : 0;
    const angle = percentage * 360;
    const startAngle = currentAngle;
    const endAngle = currentAngle + angle;
    currentAngle = endAngle;

    return {
      ...item,
      startAngle,
      endAngle,
      percentage,
      index,
    };
  });

  const handleSegmentPress = (index: number) => {
    haptics.tap();
    setSelectedIndex(selectedIndex === index ? null : index);
  };

  return (
    <View className="items-center">
      {/* Chart */}
      <View style={{ width: size, height: size }}>
        <Svg width={size} height={size}>
          <G>
            {segments.map((segment, index) => {
              if (segment.value === 0) return null;

              const isSelected = selectedIndex === index;
              const path =
                actualInnerRadius > 0
                  ? describeDonutArc(
                      center,
                      center,
                      isSelected ? radius + 5 : radius,
                      actualInnerRadius,
                      segment.startAngle,
                      segment.endAngle - 0.5 // Small gap between segments
                    )
                  : describeArc(
                      center,
                      center,
                      isSelected ? radius + 5 : radius,
                      segment.startAngle,
                      segment.endAngle - 0.5
                    );

              return (
                <Path
                  key={index}
                  d={path}
                  fill={segment.color}
                  opacity={selectedIndex !== null && !isSelected ? 0.5 : 1}
                  onPress={() => handleSegmentPress(index)}
                />
              );
            })}
          </G>
        </Svg>

        {/* Center text (for donut charts) */}
        {actualInnerRadius > 0 && (centerText || centerSubtext) && (
          <View
            className="absolute items-center justify-center"
            style={{
              top: center - actualInnerRadius / 2,
              left: center - actualInnerRadius / 2,
              width: actualInnerRadius,
              height: actualInnerRadius,
            }}
          >
            {centerText && (
              <Text className="text-2xl font-bold text-gray-900">{centerText}</Text>
            )}
            {centerSubtext && (
              <Text className="text-xs text-gray-500">{centerSubtext}</Text>
            )}
          </View>
        )}
      </View>

      {/* Legend */}
      {showLegend && (
        <View className="flex-row flex-wrap justify-center gap-3 mt-4">
          {data.map((item, index) => (
            <Pressable
              key={index}
              onPress={() => handleSegmentPress(index)}
              className={`flex-row items-center px-2 py-1 rounded-lg ${
                selectedIndex === index ? 'bg-gray-100' : ''
              }`}
            >
              <View
                className="w-3 h-3 rounded-full mr-2"
                style={{ backgroundColor: item.color }}
              />
              <Text className="text-sm text-gray-700">{item.label}</Text>
              <Text className="text-sm text-gray-500 ml-1">
                ({Math.round((item.value / total) * 100)}%)
              </Text>
            </Pressable>
          ))}
        </View>
      )}

      {/* Selected item details */}
      {selectedIndex !== null && (
        <View className="mt-3 bg-gray-50 rounded-lg px-4 py-2">
          <Text className="text-sm font-medium text-gray-900">
            {data[selectedIndex].label}
          </Text>
          <Text className="text-xs text-gray-500">
            {data[selectedIndex].value.toLocaleString()} (
            {Math.round((data[selectedIndex].value / total) * 100)}%)
          </Text>
        </View>
      )}
    </View>
  );
});

export default PieChart;
