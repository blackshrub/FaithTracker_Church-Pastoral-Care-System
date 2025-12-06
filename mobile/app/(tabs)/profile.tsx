/**
 * Profile Screen
 *
 * User profile and app settings
 * Uses NativeWind for styling
 */

import React, { memo, useCallback, useState } from 'react';
import {
  View,
  Text,
  ScrollView,
  Pressable,
  Alert,
  Image,
  Switch,
  Linking,
  Platform,
  TextInput,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { useTranslation } from 'react-i18next';
import { router } from 'expo-router';
import {
  User,
  LogOut,
  Globe,
  Bell,
  BellOff,
  Info,
  ChevronRight,
  Building2,
  Shield,
  Fingerprint,
  ScanFace,
  FileText,
} from 'lucide-react-native';
import Toast from 'react-native-toast-message';

import { useAuthStore } from '@/stores/auth';
import { changeLanguage, getCurrentLanguage } from '@/lib/i18n';
import { haptics } from '@/constants/interaction';
import { useNotifications } from '@/hooks/useNotifications';
import { useBiometrics } from '@/hooks/useBiometrics';

// ============================================================================
// COMPONENTS
// ============================================================================

interface SettingsRowProps {
  icon: any;
  label: string;
  value?: string;
  onPress?: () => void;
  destructive?: boolean;
}

const SettingsRow = memo(function SettingsRow({
  icon: Icon,
  label,
  value,
  onPress,
  destructive,
}: SettingsRowProps) {
  return (
    <Pressable
      className={`flex-row items-center px-4 py-4 ${onPress ? 'active:bg-gray-50' : ''}`}
      onPress={onPress}
      disabled={!onPress}
    >
      <View
        className={`w-9 h-9 rounded-lg items-center justify-center mr-4 ${
          destructive ? 'bg-error-50' : 'bg-primary-50'
        }`}
      >
        <Icon size={20} color={destructive ? '#ef4444' : '#0d9488'} />
      </View>
      <Text
        className={`flex-1 text-base ${
          destructive ? 'text-error-500' : 'text-gray-900'
        }`}
      >
        {label}
      </Text>
      {value && <Text className="text-sm text-gray-500 mr-2">{value}</Text>}
      {onPress && <ChevronRight size={20} color="#9ca3af" />}
    </Pressable>
  );
});

// ============================================================================
// MAIN SCREEN
// ============================================================================

function ProfileScreen() {
  const { t, i18n } = useTranslation();
  const insets = useSafeAreaInsets();
  const { user, logout, saveCredentialsForBiometric, clearBiometricCredentials } = useAuthStore();
  const { isEnabled: notificationsEnabled, isLoading: notificationsLoading, requestPermissions } = useNotifications();
  const { status, isEnabled: biometricEnabled, enable: enableBiometric, disable: disableBiometric, isLoading: biometricLoading } = useBiometrics();

  // Modal state for biometric setup
  const [showBiometricSetup, setShowBiometricSetup] = useState(false);
  const [biometricPassword, setBiometricPassword] = useState('');

  // Get role display name
  const roleLabel = user?.role === 'full_admin'
    ? 'Full Admin'
    : user?.role === 'campus_admin'
    ? 'Campus Admin'
    : 'Pastor';

  // Biometric icon and label
  const BiometricIcon = status?.biometricType === 'facial' ? ScanFace : Fingerprint;
  const biometricLabel = status?.biometricType === 'facial'
    ? t('profile.faceId') || 'Face ID'
    : t('profile.touchId') || 'Touch ID';
  const showBiometricOption = status?.isAvailable;

  // Handle language change
  const handleLanguageChange = useCallback(async () => {
    const currentLang = getCurrentLanguage();
    const newLang = currentLang === 'en' ? 'id' : 'en';
    await changeLanguage(newLang);
    haptics.success();
  }, []);

  // Handle biometric toggle
  const handleBiometricToggle = useCallback(async () => {
    if (biometricEnabled) {
      // Disable biometric
      Alert.alert(
        t('profile.disableBiometric') || 'Disable Biometric Login',
        t('profile.disableBiometricConfirm') || 'Are you sure you want to disable biometric login?',
        [
          { text: t('common.cancel'), style: 'cancel' },
          {
            text: t('common.disable') || 'Disable',
            style: 'destructive',
            onPress: async () => {
              await disableBiometric();
              await clearBiometricCredentials();
              haptics.success();
              Toast.show({
                type: 'info',
                text1: t('profile.biometricDisabled') || 'Biometric Disabled',
                text2: t('profile.biometricDisabledMessage') || 'You can enable it again anytime',
              });
            },
          },
        ]
      );
    } else {
      // Enable biometric - need password to save credentials
      setShowBiometricSetup(true);
    }
  }, [biometricEnabled, disableBiometric, clearBiometricCredentials, t]);

  // Handle biometric setup confirmation
  const handleBiometricSetupConfirm = useCallback(async () => {
    if (!biometricPassword.trim()) {
      Toast.show({
        type: 'error',
        text1: t('common.error') || 'Error',
        text2: t('profile.enterPassword') || 'Please enter your password',
      });
      return;
    }

    try {
      // Save credentials for biometric login
      if (user?.email) {
        await saveCredentialsForBiometric(user.email, biometricPassword);
        await enableBiometric();
        haptics.success();
        Toast.show({
          type: 'success',
          text1: t('profile.biometricEnabled') || 'Biometric Enabled',
          text2: t('profile.biometricEnabledMessage') || 'You can now login with biometrics',
        });
      }
    } catch (error) {
      Toast.show({
        type: 'error',
        text1: t('common.error') || 'Error',
        text2: t('profile.biometricSetupFailed') || 'Failed to setup biometric login',
      });
    } finally {
      setShowBiometricSetup(false);
      setBiometricPassword('');
    }
  }, [biometricPassword, user, saveCredentialsForBiometric, enableBiometric, t]);

  // Handle notification toggle
  const handleNotificationToggle = useCallback(async () => {
    if (notificationsEnabled) {
      // Direct user to settings to disable
      Alert.alert(
        t('profile.notifications'),
        t('profile.disableNotificationsHint') || 'To disable notifications, please go to your device settings.',
        [
          { text: t('common.cancel'), style: 'cancel' },
          {
            text: t('profile.openSettings') || 'Open Settings',
            onPress: () => {
              if (Platform.OS === 'ios') {
                Linking.openURL('app-settings:');
              } else {
                Linking.openSettings();
              }
            },
          },
        ]
      );
    } else {
      // Request permissions
      const granted = await requestPermissions();
      if (granted) {
        haptics.success();
      } else {
        Alert.alert(
          t('profile.notifications'),
          t('profile.notificationsDenied') || 'Notification permissions were denied. Please enable in settings.',
          [
            { text: t('common.cancel'), style: 'cancel' },
            {
              text: t('profile.openSettings') || 'Open Settings',
              onPress: () => {
                if (Platform.OS === 'ios') {
                  Linking.openURL('app-settings:');
                } else {
                  Linking.openSettings();
                }
              },
            },
          ]
        );
      }
    }
  }, [notificationsEnabled, requestPermissions, t]);

  // Handle logout
  const handleLogout = useCallback(() => {
    Alert.alert(
      t('auth.logout'),
      t('profile.logoutConfirm'),
      [
        { text: t('common.cancel'), style: 'cancel' },
        {
          text: t('auth.logout'),
          style: 'destructive',
          onPress: async () => {
            haptics.tap();
            await logout();
            router.replace('/(auth)/login');
          },
        },
      ]
    );
  }, [t, logout]);

  return (
    <View className="flex-1 bg-gray-50">
      <ScrollView
        className="flex-1"
        contentContainerStyle={{ paddingTop: insets.top + 24 }}
        contentContainerClassName="px-6"
        showsVerticalScrollIndicator={false}
      >
        {/* Profile Header */}
        <View className="bg-white rounded-2xl p-6 items-center shadow-sm">
          <View className="mb-4">
            {user?.photo_url ? (
              <Image
                source={{ uri: user.photo_url }}
                className="w-20 h-20 rounded-full"
              />
            ) : (
              <View className="w-20 h-20 rounded-full bg-gray-100 items-center justify-center">
                <User size={40} color="#9ca3af" />
              </View>
            )}
          </View>
          <Text className="text-[22px] font-bold text-gray-900 mb-1">
            {user?.name || 'User'}
          </Text>
          <Text className="text-sm text-gray-500 mb-4">{user?.email}</Text>

          <View className="flex-row gap-2">
            <View className="flex-row items-center px-3 py-1.5 rounded-full bg-primary-50 gap-1">
              <Shield size={14} color="#0d9488" />
              <Text className="text-xs font-medium text-primary-600">{roleLabel}</Text>
            </View>
            {user?.campus_name && (
              <View className="flex-row items-center px-3 py-1.5 rounded-full bg-gray-100 gap-1">
                <Building2 size={14} color="#4b5563" />
                <Text className="text-xs font-medium text-gray-600">{user.campus_name}</Text>
              </View>
            )}
          </View>
        </View>

        {/* Settings Section */}
        <View className="mt-6">
          <Text className="text-sm font-semibold text-gray-500 mb-2 ml-1 uppercase tracking-wide">
            {t('profile.settings')}
          </Text>

          <View className="bg-white rounded-2xl shadow-sm overflow-hidden">
            <SettingsRow
              icon={Globe}
              label={t('profile.language')}
              value={i18n.language === 'en' ? 'English' : 'Bahasa Indonesia'}
              onPress={handleLanguageChange}
            />
            <View className="h-px bg-gray-100 ml-16" />
            <Pressable
              className="flex-row items-center px-4 py-4 active:bg-gray-50"
              onPress={handleNotificationToggle}
            >
              <View className="w-9 h-9 rounded-lg items-center justify-center mr-4 bg-primary-50">
                {notificationsEnabled ? (
                  <Bell size={20} color="#0d9488" />
                ) : (
                  <BellOff size={20} color="#0d9488" />
                )}
              </View>
              <Text className="flex-1 text-base text-gray-900">
                {t('profile.notifications')}
              </Text>
              <Switch
                value={notificationsEnabled}
                onValueChange={handleNotificationToggle}
                trackColor={{ false: '#e5e7eb', true: '#5eead4' }}
                thumbColor={notificationsEnabled ? '#14b8a6' : '#f4f4f5'}
                disabled={notificationsLoading}
              />
            </Pressable>
            {showBiometricOption && (
              <>
                <View className="h-px bg-gray-100 ml-16" />
                <Pressable
                  className="flex-row items-center px-4 py-4 active:bg-gray-50"
                  onPress={handleBiometricToggle}
                >
                  <View className="w-9 h-9 rounded-lg items-center justify-center mr-4 bg-primary-50">
                    <BiometricIcon size={20} color="#0d9488" />
                  </View>
                  <Text className="flex-1 text-base text-gray-900">
                    {biometricLabel}
                  </Text>
                  <Switch
                    value={biometricEnabled}
                    onValueChange={handleBiometricToggle}
                    trackColor={{ false: '#e5e7eb', true: '#5eead4' }}
                    thumbColor={biometricEnabled ? '#14b8a6' : '#f4f4f5'}
                    disabled={biometricLoading}
                  />
                </Pressable>
              </>
            )}
          </View>
        </View>

        {/* Tools Section */}
        <View className="mt-6">
          <Text className="text-sm font-semibold text-gray-500 mb-2 ml-1 uppercase tracking-wide">
            {t('profile.tools', 'Tools')}
          </Text>

          <View className="bg-white rounded-2xl shadow-sm overflow-hidden">
            <SettingsRow
              icon={FileText}
              label={t('reports.title', 'Reports')}
              onPress={() => {
                haptics.tap();
                router.push('/reports');
              }}
            />
          </View>
        </View>

        {/* About Section */}
        <View className="mt-6">
          <Text className="text-sm font-semibold text-gray-500 mb-2 ml-1 uppercase tracking-wide">
            {t('profile.about')}
          </Text>

          <View className="bg-white rounded-2xl shadow-sm overflow-hidden">
            <SettingsRow
              icon={Info}
              label={t('profile.version')}
              value="1.0.0"
            />
          </View>
        </View>

        {/* Logout */}
        <View className="mt-6">
          <View className="bg-white rounded-2xl shadow-sm overflow-hidden">
            <SettingsRow
              icon={LogOut}
              label={t('auth.logout')}
              onPress={handleLogout}
              destructive
            />
          </View>
        </View>

        {/* Footer */}
        <View className="items-center mt-12 py-6">
          <Text className="text-base font-semibold text-gray-400">FaithTracker</Text>
          <Text className="text-xs text-gray-300 mt-1">GKBJ Pastoral Care System</Text>
        </View>

        <View className="h-24" />
      </ScrollView>

      {/* Biometric Setup Modal */}
      {showBiometricSetup && (
        <Pressable
          className="absolute inset-0 bg-black/50 justify-center items-center px-6"
          onPress={() => {
            setShowBiometricSetup(false);
            setBiometricPassword('');
          }}
        >
          <Pressable
            className="bg-white rounded-2xl p-6 w-full max-w-sm"
            onPress={(e) => e.stopPropagation()}
          >
            <View className="items-center mb-4">
              <View className="w-16 h-16 rounded-full bg-primary-50 items-center justify-center mb-3">
                <BiometricIcon size={32} color="#0d9488" />
              </View>
              <Text className="text-xl font-bold text-gray-900 text-center">
                {t('profile.setupBiometric') || `Setup ${biometricLabel}`}
              </Text>
              <Text className="text-sm text-gray-500 text-center mt-2">
                {t('profile.setupBiometricHint') || 'Enter your password to enable biometric login'}
              </Text>
            </View>

            <View className="bg-gray-100 rounded-xl px-4 py-3 mb-4">
              <TextInput
                className="text-base text-gray-900"
                placeholder={t('auth.passwordPlaceholder') || 'Password'}
                placeholderTextColor="#9ca3af"
                value={biometricPassword}
                onChangeText={setBiometricPassword}
                secureTextEntry
                autoFocus
              />
            </View>

            <View className="flex-row gap-3">
              <Pressable
                className="flex-1 py-3 rounded-xl bg-gray-100 active:bg-gray-200"
                onPress={() => {
                  setShowBiometricSetup(false);
                  setBiometricPassword('');
                }}
              >
                <Text className="text-base font-semibold text-gray-600 text-center">
                  {t('common.cancel')}
                </Text>
              </Pressable>
              <Pressable
                className="flex-1 py-3 rounded-xl bg-primary-500 active:bg-primary-600"
                onPress={handleBiometricSetupConfirm}
              >
                <Text className="text-base font-semibold text-white text-center">
                  {t('common.enable') || 'Enable'}
                </Text>
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      )}
    </View>
  );
}

export default memo(ProfileScreen);
