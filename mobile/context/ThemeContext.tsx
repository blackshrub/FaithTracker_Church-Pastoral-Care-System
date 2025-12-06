/**
 * ThemeContext - Dark/Light mode management
 *
 * Features:
 * - System preference detection
 * - Manual theme toggle
 * - Persistent preference storage
 * - Real-time system preference updates
 */

import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from 'react';
import { useColorScheme, Appearance } from 'react-native';

// Use centralized storage (works in both Expo Go and production)
import { storage } from '@/lib/storage';

// ============================================================================
// TYPES
// ============================================================================

export type ThemeMode = 'light' | 'dark' | 'system';
export type ResolvedTheme = 'light' | 'dark';

interface ThemeContextValue {
  /** Current theme mode setting */
  mode: ThemeMode;
  /** Resolved theme (what's actually displayed) */
  theme: ResolvedTheme;
  /** Whether dark mode is active */
  isDark: boolean;
  /** Whether light mode is active */
  isLight: boolean;
  /** Set theme mode */
  setMode: (mode: ThemeMode) => void;
  /** Toggle between light and dark */
  toggle: () => void;
}

// ============================================================================
// STORAGE
// ============================================================================

const THEME_KEY = 'theme:mode';

function getStoredTheme(): ThemeMode {
  const stored = storage.getString(THEME_KEY);
  if (stored === 'light' || stored === 'dark' || stored === 'system') {
    return stored;
  }
  return 'system';
}

function storeTheme(mode: ThemeMode): void {
  storage.set(THEME_KEY, mode);
}

// ============================================================================
// CONTEXT
// ============================================================================

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

// ============================================================================
// PROVIDER
// ============================================================================

interface ThemeProviderProps {
  children: React.ReactNode;
}

export function ThemeProvider({ children }: ThemeProviderProps) {
  const systemColorScheme = useColorScheme();
  const [mode, setModeState] = useState<ThemeMode>(() => getStoredTheme());

  // Listen for system theme changes
  useEffect(() => {
    const subscription = Appearance.addChangeListener(({ colorScheme }) => {
      // Force re-render when system theme changes (only affects 'system' mode)
      if (mode === 'system') {
        // This triggers a re-render through the context value change
        setModeState((prev) => prev);
      }
    });

    return () => subscription.remove();
  }, [mode]);

  // Resolve the actual theme based on mode and system preference
  const theme: ResolvedTheme = useMemo(() => {
    if (mode === 'system') {
      return systemColorScheme === 'dark' ? 'dark' : 'light';
    }
    return mode;
  }, [mode, systemColorScheme]);

  // Set mode and persist
  const setMode = useCallback((newMode: ThemeMode) => {
    setModeState(newMode);
    storeTheme(newMode);
  }, []);

  // Toggle between light and dark (sets explicit preference, not system)
  const toggle = useCallback(() => {
    const newMode = theme === 'dark' ? 'light' : 'dark';
    setMode(newMode);
  }, [theme, setMode]);

  const value = useMemo<ThemeContextValue>(
    () => ({
      mode,
      theme,
      isDark: theme === 'dark',
      isLight: theme === 'light',
      setMode,
      toggle,
    }),
    [mode, theme, setMode, toggle]
  );

  return (
    <ThemeContext.Provider value={value}>
      {children}
    </ThemeContext.Provider>
  );
}

// ============================================================================
// HOOK
// ============================================================================

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);
  if (!context) {
    throw new Error('useTheme must be used within a ThemeProvider');
  }
  return context;
}

// ============================================================================
// UTILITY HOOK FOR THEMED COLORS
// ============================================================================

interface ThemedColors {
  background: string;
  surface: string;
  surfaceElevated: string;
  text: string;
  textSecondary: string;
  textTertiary: string;
  border: string;
  borderLight: string;
  icon: string;
  iconMuted: string;
}

/**
 * Returns theme-aware semantic colors
 */
export function useThemedColors(): ThemedColors {
  const { isDark } = useTheme();

  return useMemo(
    () => ({
      // Backgrounds
      background: isDark ? '#0f172a' : '#f9fafb',
      surface: isDark ? '#1e293b' : '#ffffff',
      surfaceElevated: isDark ? '#334155' : '#ffffff',
      // Text
      text: isDark ? '#f1f5f9' : '#111827',
      textSecondary: isDark ? '#94a3b8' : '#6b7280',
      textTertiary: isDark ? '#64748b' : '#9ca3af',
      // Borders
      border: isDark ? '#334155' : '#e5e7eb',
      borderLight: isDark ? '#1e293b' : '#f3f4f6',
      // Icons
      icon: isDark ? '#f1f5f9' : '#374151',
      iconMuted: isDark ? '#64748b' : '#9ca3af',
    }),
    [isDark]
  );
}

export default ThemeContext;
