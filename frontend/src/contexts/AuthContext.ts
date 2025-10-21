import React, { createContext, useContext, useState, useEffect } from 'react';
import { apiClient } from '../api/apiClient';
import type { User } from '../types.ts'

interface AuthContextType {
  user: User | null;
  isGuest: boolean;
  login: (email: string, password: string) => Promise<void>;
  signup: (email: string, password: string) => Promise<{ needsConfirmation: boolean }>;
  confirm: (email: string, code: string) => Promise<void>;
  logout: () => void;
  logoutGlobal: () => Promise<void>;
  refreshToken: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{children: React.ReactNode}> = ({ children }) => {
  const [user, setUser] = useState<User | null>(null);
  const [isGuest, setIsGuest] = useState(true);

  useEffect(() => {
    const userStr = localStorage.getItem('user');
    const refreshToken = localStorage.getItem('refreshToken');
    
    if (userStr && refreshToken) {
      const userData = JSON.parse(userStr);
      setUser(userData);
      setIsGuest(false);
      
      if (userData.expiresAt < Date.now()) {
        refreshTokenFn();
      }
    }
  }, []);

  const refreshTokenFn = async () => {
    try {
      const refreshToken = localStorage.getItem('refreshToken');
      if (!refreshToken) throw new Error('No refresh token');
      
      const data = await apiClient.refreshToken(refreshToken);
      const newUser = {
        sub: data.user_sub || user?.sub || '',
        email: data.email || user?.email || '',
        accessToken: data.access_token,
        idToken: data.id_token,
        expiresAt: Date.now() + (data.expires_in * 1000),
      };
      
      setUser(newUser);
      localStorage.setItem('user', JSON.stringify(newUser));
    } catch (error) {
      logout();
    }
  };

  const login = async (email: string, password: string) => {
    const data = await apiClient.login(email, password);
    const userData: User = {
      sub: data.user_sub,
      email: data.email,
      accessToken: data.access_token,
      idToken: data.id_token,
      expiresAt: Date.now() + (data.expires_in * 1000),
    };
    
    setUser(userData);
    setIsGuest(false);
    localStorage.setItem('user', JSON.stringify(userData));
    localStorage.setItem('refreshToken', data.refresh_token);
  };

  const signup = async (email: string, password: string) => {
    await apiClient.signup(email, password);
    return { needsConfirmation: true };
  };

  const confirm = async (email: string, code: string) => {
    await apiClient.confirm(email, code);
  };

  const logout = () => {
    setUser(null);
    setIsGuest(true);
    localStorage.removeItem('user');
    localStorage.removeItem('refreshToken');
  };

  const logoutGlobal = async () => {
    await apiClient.logoutGlobal();
    logout();
  };

  return React.createElement(
    AuthContext.Provider,
    { value: { user, isGuest, login, signup, confirm, logout, logoutGlobal, refreshToken: refreshTokenFn } },
    children
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};