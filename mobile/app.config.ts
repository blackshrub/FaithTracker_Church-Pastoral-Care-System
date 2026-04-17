/**
 * Expo App Configuration
 *
 * Dynamic configuration with deep linking, notifications, and app metadata
 */

import { ExpoConfig, ConfigContext } from 'expo/config';

export default ({ config }: ConfigContext): ExpoConfig => ({
  ...config,
  name: 'FaithTracker',
  slug: 'faithtracker-mobile',
  version: '1.0.0',
  orientation: 'portrait',
  icon: './assets/icon.png',
  userInterfaceStyle: 'automatic',
  splash: {
    image: './assets/splash.png',
    resizeMode: 'contain',
    backgroundColor: '#115e59',
  },
  assetBundlePatterns: ['**/*'],
  ios: {
    supportsTablet: true,
    bundleIdentifier: 'com.gkbj.faithtracker',
    infoPlist: {
      NSCameraUsageDescription: 'FaithTracker needs camera access to take profile photos.',
      NSPhotoLibraryUsageDescription: 'FaithTracker needs photo library access to select profile photos.',
      NSFaceIDUsageDescription: 'FaithTracker uses Face ID for secure login.',
    },
  },
  android: {
    adaptiveIcon: {
      foregroundImage: './assets/adaptive-icon.png',
      backgroundColor: '#115e59',
    },
    package: 'com.gkbj.faithtracker',
    permissions: [
      'android.permission.CAMERA',
      'android.permission.READ_EXTERNAL_STORAGE',
      'android.permission.WRITE_EXTERNAL_STORAGE',
      'android.permission.USE_BIOMETRIC',
      'android.permission.USE_FINGERPRINT',
    ],
  },
  web: {
    favicon: './assets/favicon.png',
    bundler: 'metro',
  },
  plugins: [
    'expo-router',
    'expo-font',
    'expo-secure-store',
    [
      'expo-notifications',
      {
        icon: './assets/notification-icon.png',
        color: '#14b8a6',
        sounds: ['./assets/notification.wav'],
      },
    ],
    [
      'expo-image-picker',
      {
        photosPermission: 'FaithTracker needs access to your photos to set profile pictures.',
        cameraPermission: 'FaithTracker needs access to your camera to take profile photos.',
      },
    ],
    [
      'expo-local-authentication',
      {
        faceIDPermission: 'FaithTracker uses Face ID for secure authentication.',
      },
    ],
  ],
  experiments: {
    // Typed routes: makes `router.push('/member/[id]')` type-checked at build time.
    typedRoutes: true,
    // React Compiler: auto-memoizes components + callbacks at build time.
    // Removes the need for most useMemo/useCallback. Supported by React 19
    // and babel-preset-expo 54+ (which pulls in babel-plugin-react-compiler).
    reactCompiler: true,
  },
  scheme: 'faithtracker',
  extra: {
    eas: {
      projectId: 'your-eas-project-id', // Replace with actual EAS project ID
    },
  },
});
