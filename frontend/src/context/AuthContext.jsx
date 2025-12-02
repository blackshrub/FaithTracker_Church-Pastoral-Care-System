import React, { createContext, useContext, useState, useEffect } from 'react';
import api, { setAuthToken, clearAuthToken } from '@/lib/api';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    checkAuth();
  }, []);

  const checkAuth = async () => {
    const token = localStorage.getItem('token');
    if (token) {
      try {
        setAuthToken(token);
        const response = await api.get('/auth/me');
        setUser(response.data);
      } catch (error) {
        localStorage.removeItem('token');
        clearAuthToken();
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

    return userData;
  };

  const logout = () => {
    localStorage.removeItem('token');
    clearAuthToken();
    setUser(null);
  };
  
  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
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