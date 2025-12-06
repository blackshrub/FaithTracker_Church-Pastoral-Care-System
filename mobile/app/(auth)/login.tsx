/**
 * Login Screen
 *
 * Email/password authentication with campus selection
 * Uses NativeWind for styling where supported
 * Supports biometric authentication (Face ID / Touch ID)
 */

import React, { useState, useCallback, useEffect, useMemo } from 'react';
import {
  View,
  Text,
  TextInput,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Pressable,
  TouchableOpacity,
  ScrollView,
  Modal,
} from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';
import { LinearGradient } from 'expo-linear-gradient';
import { useTranslation } from 'react-i18next';
import { router } from 'expo-router';
import { Mail, Lock, LogIn, Fingerprint, ScanFace, Play, Building2, ChevronDown, Check } from 'lucide-react-native';
import Animated, { FadeInDown, FadeInUp } from 'react-native-reanimated';

import { useAuthStore } from '@/stores/auth';
import api, { getErrorMessage } from '@/services/api';
import { gradients } from '@/constants/theme';
import { haptics } from '@/constants/interaction';
import { useBiometrics } from '@/hooks/useBiometrics';
import { USE_MOCK_DATA } from '@/services/mockApi';
import { API_ENDPOINTS } from '@/constants/api';

interface Campus {
  id: string;
  campus_name: string;
  church_name?: string;
  is_active?: boolean;
}

export default function LoginScreen() {
  const { t } = useTranslation();
  const insets = useSafeAreaInsets();
  const { login, loginWithBiometrics, hasSavedCredentials } = useAuthStore();
  const { status, isEnabled, authenticate, refresh } = useBiometrics();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [campusId, setCampusId] = useState('');
  const [campuses, setCampuses] = useState<Campus[]>([]);
  const [loadingCampuses, setLoadingCampuses] = useState(true);
  const [showCampusPicker, setShowCampusPicker] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [isDemoLoading, setIsDemoLoading] = useState(false);
  const [isBiometricLoading, setIsBiometricLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load campuses on mount
  useEffect(() => {
    loadCampuses();
  }, []);

  const loadCampuses = async () => {
    try {
      if (USE_MOCK_DATA) {
        // Mock campuses for demo mode
        setCampuses([
          { id: 'campus-1', campus_name: 'Demo Campus', church_name: 'Demo Church' },
        ]);
        setCampusId('campus-1');
      } else {
        const response = await api.get(API_ENDPOINTS.CAMPUSES.LIST);
        const data = response.data;
        const campusList = Array.isArray(data) ? data : (data?.campuses || []);
        setCampuses(campusList.filter((c: Campus) => c.is_active !== false));
      }
    } catch (err) {
      console.warn('Failed to load campuses:', err);
      setCampuses([]);
    } finally {
      setLoadingCampuses(false);
    }
  };

  // Get selected campus name
  const selectedCampus = useMemo(() => {
    return campuses.find(c => c.id === campusId);
  }, [campuses, campusId]);

  // Show biometric prompt on mount if enabled and available
  useEffect(() => {
    const checkBiometric = async () => {
      await refresh();
      if (isEnabled && status?.isAvailable && hasSavedCredentials()) {
        handleBiometricLogin();
      }
    };
    checkBiometric();
  }, []);

  // Handle biometric login
  const handleBiometricLogin = useCallback(async () => {
    if (!isEnabled || !status?.isAvailable) return;

    setIsBiometricLoading(true);
    setError(null);

    try {
      const success = await authenticate();
      if (success) {
        const result = await loginWithBiometrics();
        if (result) {
          haptics.success();
          router.replace('/(tabs)');
        } else {
          setError(t('auth.biometricFailed', { defaultValue: 'Biometric login failed. Please use email and password.' }));
        }
      }
    } catch (err) {
      const message = getErrorMessage(err);
      setError(message);
      haptics.error();
    } finally {
      setIsBiometricLoading(false);
    }
  }, [isEnabled, status, authenticate, loginWithBiometrics, t]);

  // Handle demo login (mock mode)
  const handleDemoLogin = useCallback(async () => {
    setIsDemoLoading(true);
    setError(null);

    try {
      await login('demo@faithtracker.app', 'demo123');
      haptics.success();
      router.replace('/(tabs)');
    } catch (err) {
      const message = getErrorMessage(err);
      setError(message);
      haptics.error();
    } finally {
      setIsDemoLoading(false);
    }
  }, [login]);

  const handleLogin = useCallback(async () => {
    if (!email.trim() || !password.trim()) {
      setError(t('auth.loginError', { defaultValue: 'Please enter email and password' }));
      haptics.error();
      return;
    }

    if (!USE_MOCK_DATA && !campusId) {
      setError(t('auth.selectCampus', { defaultValue: 'Please select a campus' }));
      haptics.error();
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      await login(email.trim(), password, campusId || undefined);
      haptics.success();
      router.replace('/(tabs)');
    } catch (err) {
      const message = getErrorMessage(err);
      setError(message);
      haptics.error();
    } finally {
      setIsLoading(false);
    }
  }, [email, password, campusId, login, t]);

  // Determine biometric icon based on type
  const BiometricIcon = status?.biometricType === 'facial' ? ScanFace : Fingerprint;
  const biometricLabel = status?.biometricType === 'facial'
    ? t('auth.faceId', { defaultValue: 'Face ID' })
    : t('auth.touchId', { defaultValue: 'Touch ID' });
  const showBiometric = isEnabled && status?.isAvailable && hasSavedCredentials();

  const isAnyLoading = isLoading || isDemoLoading || isBiometricLoading;

  return (
    <LinearGradient
      colors={[gradients.header.start, gradients.header.mid, gradients.header.end]}
      style={{ flex: 1 }}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
        style={{ flex: 1 }}
      >
        <ScrollView
          contentContainerStyle={{ flexGrow: 1 }}
          keyboardShouldPersistTaps="handled"
        >
          <View
            className="flex-1 px-6 justify-between"
            style={{ paddingTop: insets.top + 32 }}
          >
            {/* Logo & Title */}
            <Animated.View
              entering={FadeInDown.delay(100).duration(500)}
              className="items-center mb-8"
            >
              <View className="w-20 h-20 rounded-2xl bg-white items-center justify-center mb-6 shadow-lg">
                <Text className="text-3xl font-bold text-teal-600">FT</Text>
              </View>
              <Text className="text-3xl font-bold text-white text-center mb-1">
                {t('auth.welcome', { defaultValue: 'Welcome' })}
              </Text>
              <Text className="text-base text-teal-100 text-center">
                {t('auth.subtitle', { defaultValue: 'Sign in to continue' })}
              </Text>
            </Animated.View>

            {/* Login Form */}
            <Animated.View
              entering={FadeInUp.delay(300).duration(500)}
              className="gap-4"
            >
              {/* Demo Login Button - Primary action for demo mode */}
              {USE_MOCK_DATA && (
                <TouchableOpacity
                  className="min-h-14 rounded-xl bg-white justify-center items-center shadow-md active:opacity-80"
                  onPress={handleDemoLogin}
                  disabled={isAnyLoading}
                  activeOpacity={0.8}
                >
                  {isDemoLoading ? (
                    <ActivityIndicator color="#0d9488" size="small" />
                  ) : (
                    <View className="flex-row items-center justify-center">
                      <Play size={20} color="#0d9488" />
                      <Text className="text-base font-semibold text-teal-600 ml-2">Demo Login</Text>
                    </View>
                  )}
                </TouchableOpacity>
              )}

              {/* Divider - only show if mock mode */}
              {USE_MOCK_DATA && (
                <View className="flex-row items-center my-2">
                  <View className="flex-1 h-px bg-white/30" />
                  <Text className="mx-4 text-white/60 text-sm">or</Text>
                  <View className="flex-1 h-px bg-white/30" />
                </View>
              )}

              {/* Campus Selector */}
              {!USE_MOCK_DATA && (
                <TouchableOpacity
                  className="flex-row items-center bg-white rounded-xl px-4 min-h-14 shadow-sm"
                  onPress={() => setShowCampusPicker(true)}
                  disabled={loadingCampuses || isAnyLoading}
                  activeOpacity={0.8}
                >
                  <Building2 size={20} color="#9ca3af" />
                  {loadingCampuses ? (
                    <Text className="flex-1 text-base text-gray-400 py-4 ml-3">
                      {t('auth.loadingCampuses', { defaultValue: 'Loading campuses...' })}
                    </Text>
                  ) : (
                    <Text className={`flex-1 text-base py-4 ml-3 ${selectedCampus ? 'text-gray-900' : 'text-gray-400'}`}>
                      {selectedCampus?.campus_name || t('auth.selectCampusPlaceholder', { defaultValue: 'Select campus' })}
                    </Text>
                  )}
                  <ChevronDown size={20} color="#9ca3af" />
                </TouchableOpacity>
              )}

              {/* Email Input */}
              <View className="flex-row items-center bg-white rounded-xl px-4 min-h-14 shadow-sm">
                <Mail size={20} color="#9ca3af" />
                <TextInput
                  className="flex-1 text-base text-gray-900 py-4 ml-3"
                  placeholder={t('auth.emailPlaceholder', { defaultValue: 'Email address' })}
                  placeholderTextColor="#9ca3af"
                  value={email}
                  onChangeText={setEmail}
                  keyboardType="email-address"
                  autoCapitalize="none"
                  autoCorrect={false}
                  editable={!isAnyLoading}
                />
              </View>

              {/* Password Input */}
              <View className="flex-row items-center bg-white rounded-xl px-4 min-h-14 shadow-sm">
                <Lock size={20} color="#9ca3af" />
                <TextInput
                  className="flex-1 text-base text-gray-900 py-4 ml-3"
                  placeholder={t('auth.passwordPlaceholder', { defaultValue: 'Password' })}
                  placeholderTextColor="#9ca3af"
                  value={password}
                  onChangeText={setPassword}
                  secureTextEntry
                  editable={!isAnyLoading}
                />
              </View>

              {/* Error Message */}
              {error && (
                <Animated.View
                  entering={FadeInDown.duration(200)}
                  className="bg-red-50 rounded-lg p-3 border border-red-200"
                >
                  <Text className="text-sm text-red-600 text-center">{error}</Text>
                </Animated.View>
              )}

              {/* Login Button */}
              <TouchableOpacity
                className={`mt-2 min-h-14 rounded-xl bg-teal-600 justify-center items-center shadow-md active:opacity-80 ${isAnyLoading ? 'opacity-60' : ''}`}
                onPress={handleLogin}
                disabled={isAnyLoading}
                activeOpacity={0.8}
              >
                {isLoading ? (
                  <ActivityIndicator color="white" size="small" />
                ) : (
                  <View className="flex-row items-center justify-center">
                    <LogIn size={20} color="white" />
                    <Text className="text-base font-semibold text-white ml-2">
                      {t('auth.loginButton', { defaultValue: 'Sign In' })}
                    </Text>
                  </View>
                )}
              </TouchableOpacity>

              {/* Biometric Login Button */}
              {showBiometric && (
                <Animated.View entering={FadeInUp.delay(400).duration(300)}>
                  <Pressable
                    className="flex-row items-center justify-center mt-4 py-4 rounded-xl bg-white/10 active:bg-white/20"
                    onPress={handleBiometricLogin}
                    disabled={isAnyLoading}
                  >
                    {isBiometricLoading ? (
                      <ActivityIndicator color="white" size="small" />
                    ) : (
                      <>
                        <BiometricIcon size={24} color="white" />
                        <Text className="text-base font-semibold text-white ml-3">
                          {t('auth.loginWith', { defaultValue: 'Login with' })} {biometricLabel}
                        </Text>
                      </>
                    )}
                  </Pressable>
                </Animated.View>
              )}
            </Animated.View>

            {/* Footer */}
            <Animated.View
              entering={FadeInUp.delay(500).duration(500)}
              className="items-center"
              style={{ paddingBottom: insets.bottom + 24 }}
            >
              <Text className="text-xs text-teal-200">
                GKBJ Pastoral Care System
              </Text>
            </Animated.View>
          </View>
        </ScrollView>
      </KeyboardAvoidingView>

      {/* Campus Picker Modal */}
      <Modal
        visible={showCampusPicker}
        transparent
        animationType="slide"
        onRequestClose={() => setShowCampusPicker(false)}
      >
        <Pressable
          className="flex-1 bg-black/50 justify-end"
          onPress={() => setShowCampusPicker(false)}
        >
          <Pressable
            className="bg-white rounded-t-3xl"
            style={{ paddingBottom: insets.bottom + 16 }}
            onPress={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <View className="flex-row items-center justify-between px-6 py-4 border-b border-gray-100">
              <Text className="text-lg font-semibold text-gray-900">
                {t('auth.selectCampusTitle', { defaultValue: 'Select Campus' })}
              </Text>
              <TouchableOpacity onPress={() => setShowCampusPicker(false)}>
                <Text className="text-teal-600 font-medium">
                  {t('common.done', { defaultValue: 'Done' })}
                </Text>
              </TouchableOpacity>
            </View>

            {/* Campus List */}
            <ScrollView className="max-h-80">
              {campuses.length === 0 ? (
                <View className="py-8 items-center">
                  <Text className="text-gray-500">
                    {t('auth.noCampuses', { defaultValue: 'No campuses available' })}
                  </Text>
                </View>
              ) : (
                campuses.map((campus) => (
                  <TouchableOpacity
                    key={campus.id}
                    className={`flex-row items-center px-6 py-4 border-b border-gray-50 ${
                      campusId === campus.id ? 'bg-teal-50' : ''
                    }`}
                    onPress={() => {
                      setCampusId(campus.id);
                      setShowCampusPicker(false);
                      haptics.tap();
                    }}
                  >
                    <Building2 size={20} color={campusId === campus.id ? '#0d9488' : '#9ca3af'} />
                    <View className="flex-1 ml-3">
                      <Text className={`text-base ${campusId === campus.id ? 'text-teal-700 font-medium' : 'text-gray-900'}`}>
                        {campus.campus_name}
                      </Text>
                      {campus.church_name && (
                        <Text className="text-sm text-gray-500">{campus.church_name}</Text>
                      )}
                    </View>
                    {campusId === campus.id && (
                      <Check size={20} color="#0d9488" />
                    )}
                  </TouchableOpacity>
                ))
              )}
            </ScrollView>
          </Pressable>
        </Pressable>
      </Modal>
    </LinearGradient>
  );
}
