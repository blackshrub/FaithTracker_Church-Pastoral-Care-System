/**
 * Internationalization (i18n) Setup
 *
 * Uses i18next with react-i18next for translations.
 * Supports English and Indonesian languages.
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';
import { NativeModules, Platform } from 'react-native';

// Import translation files
import en from '@/locales/en.json';
import id from '@/locales/id.json';

// Use centralized storage (works in both Expo Go and production)
import { storage } from '@/lib/storage';

const LANGUAGE_KEY = 'i18n-user-language';

// Get device language without expo-localization
function getDeviceLanguage(): string {
  try {
    const locale =
      Platform.OS === 'ios'
        ? NativeModules.SettingsManager?.settings?.AppleLocale ||
          NativeModules.SettingsManager?.settings?.AppleLanguages?.[0]
        : NativeModules.I18nManager?.localeIdentifier;
    return locale?.substring(0, 2) || 'en';
  } catch {
    return 'en';
  }
}

// Get saved language or detect from device
function getInitialLanguage(): string {
  const saved = storage.getString(LANGUAGE_KEY);
  if (saved) return saved;

  // Detect device language
  const deviceLang = getDeviceLanguage();
  return deviceLang === 'id' ? 'id' : 'en';
}

// Save language preference
export function setLanguage(lang: string) {
  storage.set(LANGUAGE_KEY, lang);
  i18n.changeLanguage(lang);
}

// Aliases for backward compatibility
export const changeLang = setLanguage;
export const changeLanguage = setLanguage;

// Get current language
export function getLanguage(): string {
  return i18n.language || 'en';
}

// Alias for backward compatibility
export const getCurrentLanguage = getLanguage;

// Initialize i18n (called once on app start)
export async function initializeI18n(): Promise<void> {
  const lng = getInitialLanguage();

  await i18n.use(initReactI18next).init({
    resources: {
      en: { translation: en },
      id: { translation: id },
    },
    lng,
    fallbackLng: 'en',
    interpolation: {
      escapeValue: false, // React already escapes
    },
    react: {
      useSuspense: false, // Disable suspense for faster initial render
    },
  });
}

export default i18n;
