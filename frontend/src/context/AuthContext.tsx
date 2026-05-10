import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import api from '@/lib/api';
import type { User } from '@/types';

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string, campusId?: string | null) => Promise<User>;
  logout: () => Promise<void>;
  refreshUser: () => Promise<User>;
}

interface AuthProviderProps {
  children: ReactNode;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    // Auth is now carried by an httpOnly cookie; there is no token in JS.
    // Ask the server who we are — the cookie (if present) flows via withCredentials.
    const checkAuth = async () => {
      try {
        const response = await api.get('/auth/me');
        if (!cancelled) setUser(response.data);
      } catch {
        // Either no cookie or the server rejected it.
      } finally {
        // Clear any legacy localStorage token left over from pre-cookie versions.
        localStorage.removeItem('token');
        if (!cancelled) setLoading(false);
      }
    };

    checkAuth();
    return () => {
      cancelled = true;
    };
  }, []);

  // useCallback so login/logout/refreshUser have stable identities across
  // renders — prevents downstream consumers from re-rendering whenever
  // AuthProvider's local state changes for unrelated reasons.
  const login = useCallback(
    async (email: string, password: string, campusId: string | null = null): Promise<User> => {
      const response = await api.post('/auth/login', {
        email,
        password,
        campus_id: campusId,
      });
      const { user: userData } = response.data;
      setUser(userData);
      return userData;
    },
    []
  );

  const logout = useCallback(async (): Promise<void> => {
    try {
      await api.post('/auth/logout');
    } catch {
      // If the server is unreachable we still clear local state.
    }
    localStorage.removeItem('token');
    setUser(null);
  }, []);

  const refreshUser = useCallback(async (): Promise<User> => {
    const response = await api.get('/auth/me');
    setUser(response.data);
    return response.data;
  }, []);

  // Memoize the context value so consumers only re-render when one of the
  // captured fields actually changes, not on every AuthProvider render.
  const value = useMemo(
    () => ({ user, login, logout, loading, refreshUser }),
    [user, login, logout, loading, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
