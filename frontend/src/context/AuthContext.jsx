import { createContext, useContext, useState, useEffect } from 'react';

import api, { setAuthToken, clearAuthToken } from '@/lib/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const storedToken = localStorage.getItem('token');
    if (storedToken) {
      try {
        setAuthToken(storedToken);
        const response = await api.get('/auth/me');
        setUser(response.data);
        setToken(storedToken);
      } catch (_error) {
        localStorage.removeItem('token');
        clearAuthToken();
        setToken(null);
      }
    }
    setLoading(false);
  };

  const login = async (email, password, campusId = null) => {
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

  const refreshUser = async () => {
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

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};