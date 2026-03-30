import { createContext, useContext, useState, useEffect, type ReactNode } from 'react';

import api, { setAuthToken, clearAuthToken } from '@/lib/api';
import type { User } from '@/types';

interface AuthContextType {
  user: User | null;
  token: string | null;
  loading: boolean;
  login: (email: string, password: string, campusId?: string | null) => Promise<User>;
  logout: () => void;
  refreshUser: () => Promise<User>;
}

interface AuthProviderProps {
  children: ReactNode;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider = ({ children }: AuthProviderProps) => {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;

    const checkAuth = async () => {
      const storedToken = localStorage.getItem('token');
      if (storedToken) {
        try {
          setAuthToken(storedToken);
          const response = await api.get('/auth/me');
          if (!cancelled) {
            setUser(response.data);
            setToken(storedToken);
          }
        } catch (_error) {
          localStorage.removeItem('token');
          clearAuthToken();
          if (!cancelled) setToken(null);
        }
      }
      if (!cancelled) setLoading(false);
    };

    checkAuth();
    return () => { cancelled = true; };
  }, []);

  const login = async (email: string, password: string, campusId: string | null = null): Promise<User> => {
    const response = await api.post('/auth/login', {
      email,
      password,
      campus_id: campusId
    });
    const { access_token, user: userData } = response.data;

    localStorage.setItem('token', access_token);
    setAuthToken(access_token);
    setUser(userData);
    setToken(access_token);

    return userData;
  };

  const logout = () => {
    localStorage.removeItem('token');
    clearAuthToken();
    setUser(null);
    setToken(null);
  };

  const refreshUser = async (): Promise<User> => {
    const response = await api.get('/auth/me');
    setUser(response.data);
    return response.data;
  };

  return (
    <AuthContext.Provider value={{ user, token, login, logout, loading, refreshUser }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = (): AuthContextType => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};
