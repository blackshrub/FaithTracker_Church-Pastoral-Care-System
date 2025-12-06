/**
 * Tabs Layout
 *
 * Main tab navigation with premium animated tab bar
 *
 * Tabs:
 * - Today (Dashboard)
 * - Members
 * - Tasks
 * - Analytics
 * - Profile
 */

import { Tabs } from 'expo-router';
import { useTranslation } from 'react-i18next';
import { Home, Users, CheckSquare, BarChart3, User } from 'lucide-react-native';

import { AnimatedTabBar } from '@/components/ui/AnimatedTabBar';
import { colors } from '@/constants/theme';

export default function TabsLayout() {
  const { t } = useTranslation();

  return (
    <Tabs
      tabBar={(props) => <AnimatedTabBar {...props} />}
      screenOptions={{
        headerShown: false,
        // Performance optimizations
        lazy: false, // Pre-mount all tabs
        freezeOnBlur: true, // Freeze inactive tabs (90% CPU reduction)
        animation: 'none', // Instant switching
      }}
    >
      <Tabs.Screen
        name="index"
        options={{
          title: t('common.today'),
          tabBarIcon: ({ color, size }) => (
            <Home size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="members"
        options={{
          title: t('members.title'),
          tabBarIcon: ({ color, size }) => (
            <Users size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="tasks"
        options={{
          title: t('tasks.title'),
          tabBarIcon: ({ color, size }) => (
            <CheckSquare size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="analytics"
        options={{
          title: t('analytics.title', 'Analytics'),
          tabBarIcon: ({ color, size }) => (
            <BarChart3 size={size} color={color} />
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: t('profile.title'),
          tabBarIcon: ({ color, size }) => (
            <User size={size} color={color} />
          ),
        }}
      />
    </Tabs>
  );
}
