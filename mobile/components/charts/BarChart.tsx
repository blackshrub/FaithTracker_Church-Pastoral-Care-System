/**
 * BarChart - Animated horizontal/vertical bar chart
 *
 * Features:
 * - Animated bars on mount
 * - Horizontal and vertical orientations
 * - Value labels on bars
 * - Touch to highlight bars
 * - Grid lines
 */

import React, { memo, useState, useEffect } from 'react';
import { View, Text, Pressable, useWindowDimensions } from 'react-native';
import Animated, {
  useSharedValue,
  useAnimatedStyle,
  withTiming,
  withDelay,
  Easing,
  interpolate,
} from 'react-native-reanimated';

import { colors } from '@/constants/theme';
import { haptics } from '@/constants/interaction';

// ============================================================================
// TYPES
// ============================================================================

interface BarChartData {
  label: string;
  value: number;
  color?: string;
}

interface BarChartProps {
  data: BarChartData[];
  height?: number;
  barColor?: string;
  showValues?: boolean;
  showLabels?: boolean;
  horizontal?: boolean;
  animated?: boolean;
  maxValue?: number;
}

// ============================================================================
// ANIMATED BAR
// ============================================================================

interface AnimatedBarProps {
  value: number;
  maxValue: number;
  color: string;
  horizontal: boolean;
  index: number;
  animated: boolean;
  isSelected: boolean;
  barHeight: number;
}

const AnimatedBar = memo(function AnimatedBar({
  value,
  maxValue,
  color,
  horizontal,
  index,
  animated,
  isSelected,
  barHeight,
}: AnimatedBarProps) {
  const progress = useSharedValue(animated ? 0 : 1);

  useEffect(() => {
    if (animated) {
      progress.value = withDelay(
        index * 100,
        withTiming(1, {
          duration: 600,
          easing: Easing.out(Easing.cubic),
        })
      );
    }
  }, [animated, index]);

  const percentage = maxValue > 0 ? (value / maxValue) * 100 : 0;

  const animatedStyle = useAnimatedStyle(() => {
    const animatedPercentage = interpolate(progress.value, [0, 1], [0, percentage]);

    if (horizontal) {
      return {
        width: `${animatedPercentage}%`,
        height: barHeight,
      };
    }
    return {
      height: `${animatedPercentage}%`,
      width: '100%',
    };
  });

  return (
    <Animated.View
      style={[
        {
          backgroundColor: color,
          borderRadius: 4,
          opacity: isSelected ? 1 : 0.85,
        },
        animatedStyle,
      ]}
    />
  );
});

// ============================================================================
// COMPONENT
// ============================================================================

export const BarChart = memo(function BarChart({
  data,
  height = 200,
  barColor = colors.primary[500],
  showValues = true,
  showLabels = true,
  horizontal = false,
  animated = true,
  maxValue: customMaxValue,
}: BarChartProps) {
  const { width: screenWidth } = useWindowDimensions();
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  const maxValue = customMaxValue || Math.max(...data.map((d) => d.value), 1);
  const barHeight = horizontal ? Math.max(24, (height - 40) / data.length) : 0;
  const barWidth = horizontal ? 0 : Math.max(20, (screenWidth - 80) / data.length - 8);

  const handleBarPress = (index: number) => {
    haptics.tap();
    setSelectedIndex(selectedIndex === index ? null : index);
  };

  if (horizontal) {
    // Horizontal bar chart
    return (
      <View style={{ height }}>
        {data.map((item, index) => (
          <Pressable
            key={index}
            onPress={() => handleBarPress(index)}
            className="mb-2"
          >
            {/* Label */}
            {showLabels && (
              <Text
                className="text-xs text-gray-600 mb-1"
                numberOfLines={1}
              >
                {item.label}
              </Text>
            )}

            {/* Bar container */}
            <View className="flex-row items-center">
              <View
                className="flex-1 bg-gray-100 rounded overflow-hidden"
                style={{ height: barHeight }}
              >
                <AnimatedBar
                  value={item.value}
                  maxValue={maxValue}
                  color={item.color || barColor}
                  horizontal={true}
                  index={index}
                  animated={animated}
                  isSelected={selectedIndex === index}
                  barHeight={barHeight}
                />
              </View>

              {/* Value */}
              {showValues && (
                <Text className="text-sm font-medium text-gray-700 ml-2 w-12 text-right">
                  {item.value.toLocaleString()}
                </Text>
              )}
            </View>
          </Pressable>
        ))}
      </View>
    );
  }

  // Vertical bar chart
  return (
    <View style={{ height }}>
      {/* Bars */}
      <View
        className="flex-row items-end justify-between px-2"
        style={{ height: height - 40 }}
      >
        {data.map((item, index) => (
          <Pressable
            key={index}
            onPress={() => handleBarPress(index)}
            className="items-center"
            style={{ width: barWidth }}
          >
            {/* Value on top */}
            {showValues && (
              <Text
                className={`text-xs mb-1 ${
                  selectedIndex === index
                    ? 'font-semibold text-gray-900'
                    : 'text-gray-500'
                }`}
              >
                {item.value.toLocaleString()}
              </Text>
            )}

            {/* Bar */}
            <View
              className="w-full bg-gray-100 rounded-t overflow-hidden"
              style={{ height: '100%' }}
            >
              <View className="flex-1 justify-end">
                <AnimatedBar
                  value={item.value}
                  maxValue={maxValue}
                  color={item.color || barColor}
                  horizontal={false}
                  index={index}
                  animated={animated}
                  isSelected={selectedIndex === index}
                  barHeight={0}
                />
              </View>
            </View>
          </Pressable>
        ))}
      </View>

      {/* Labels */}
      {showLabels && (
        <View className="flex-row justify-between px-2 mt-2">
          {data.map((item, index) => (
            <View key={index} style={{ width: barWidth }} className="items-center">
              <Text
                className={`text-[10px] text-center ${
                  selectedIndex === index ? 'font-semibold text-gray-900' : 'text-gray-500'
                }`}
                numberOfLines={2}
              >
                {item.label}
              </Text>
            </View>
          ))}
        </View>
      )}

      {/* Selected item details */}
      {selectedIndex !== null && (
        <View className="absolute bottom-0 left-0 right-0 bg-white/90 rounded-lg px-3 py-2 mx-4 border border-gray-100">
          <Text className="text-sm font-medium text-gray-900">
            {data[selectedIndex].label}: {data[selectedIndex].value.toLocaleString()}
          </Text>
        </View>
      )}
    </View>
  );
});

export default BarChart;
