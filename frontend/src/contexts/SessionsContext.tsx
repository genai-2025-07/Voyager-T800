// src/contexts/SessionsContext.tsx
import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { apiClient } from '../api/apiClient.ts';
import { useAuth } from './AuthContext.ts';
import type { Session, Message } from '../types.ts'

interface SessionsContextType {
  sessions: Session[];
  currentSession: Session | null;
  guestMessages: Message[];
  guestSessionId: string | null;
  loadSessions: () => Promise<void>;
  createSession: () => Promise<string>;
  openSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  addMessageToGuest: (message: Message) => void;
  updateLastGuestMessage: (contentOrUpdater: string | ((prevContent: string) => string)) => void;
  clearCurrentSession: () => void;
}

export const SessionsContext = createContext<SessionsContextType | null>(null);

export const SessionsProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [guestMessages, setGuestMessages] = useState<Message[]>([]);
  const [guestSessionId, setGuestSessionId] = useState<string | null>(null);
  const { user, isGuest } = useAuth();

  // Helper: sort sessions by started_at descending (most recent first)
  const sortSessionsByStartDesc = (arr: Session[]) =>
    arr
      .slice()
      .sort(
        (a, b) =>
          new Date(b.started_at).getTime() - new Date(a.started_at).getTime()
      );


  const loadSessions = useCallback(async () => {
    if (!user || isGuest) return;
    
    try {
      const data = await apiClient.listSessions(user.sub);
      setSessions(sortSessionsByStartDesc(data.sessions || []));
    } catch (error) {
      console.error("Failed to load sessions:", error);
    }
  }, [user, isGuest]);

  const createSession = async () => {
    if (!user || isGuest) {
      // For guests, reuse existing session ID within the same page session
      // or create a new one if this is the first message
      if (guestSessionId) {
        return guestSessionId;
      }
      
      const newGuestSessionId = `guest-${Date.now()}-${Math.random().toString(36).substring(7)}`;
      setGuestSessionId(newGuestSessionId);
      return newGuestSessionId;
    }
    
    const data = await apiClient.createSession(user.sub);
    await loadSessions();
    return data.session_id;
  };

  const openSession = async (sessionId: string) => {
    if (!user || isGuest) return;
    
    try {
      const data = await apiClient.getSession(sessionId, user.sub);
      setCurrentSession(data);
      // Save current session ID to localStorage for persistence across page refreshes
      localStorage.setItem('currentSessionId', sessionId);
    } catch (error) {
      console.error('Failed to open session:', error);
    }
  };

  const deleteSession = async (sessionId: string) => {
    if (!user || isGuest) return;
    
    try {
      await apiClient.deleteSession(sessionId, user.sub);
      setSessions(prev => prev.filter(s => s.session_id !== sessionId));
      if (currentSession?.session_id === sessionId) {
        setCurrentSession(null);
      }
    } catch (error) {
      console.error('Failed to delete session:', error);
    }
  };

  const addMessageToGuest = (message: Message) => {
    setGuestMessages(prev => [...prev, message]);
  };

const updateLastGuestMessage = (contentOrUpdater: string | ((prevContent: string) => string)) => {
  setGuestMessages(prev => {
    if (prev.length === 0) return prev;
    const updated = [...prev];
    const lastIdx = updated.length - 1;
    const lastMsg = updated[lastIdx];
    const prevContent = lastMsg?.content ?? "";

    const newContent =
      typeof contentOrUpdater === "function"
        ? (contentOrUpdater as (pc: string) => string)(prevContent)
        : contentOrUpdater;

    updated[lastIdx] = { ...lastMsg, content: newContent };
    return updated;
  });
};



  const clearCurrentSession = () => {
    setCurrentSession(null);
    setGuestMessages([]);
    setGuestSessionId(null);
    // Clear current session ID from localStorage
    localStorage.removeItem('currentSessionId');
  };

  useEffect(() => {
    if (user && !isGuest) {
      loadSessions();
    }
  }, [user, isGuest, loadSessions]);

  // Restore current session after page refresh
  useEffect(() => {
    if (user && !isGuest && sessions.length > 0 && !currentSession) {
      const savedSessionId = localStorage.getItem('currentSessionId');
      if (savedSessionId) {
        // Check if the saved session still exists
        const sessionExists = sessions.some(s => s.session_id === savedSessionId);
        if (sessionExists) {
          openSession(savedSessionId);
        } else {
          // Session no longer exists, clear the saved ID
          localStorage.removeItem('currentSessionId');
        }
      }
    }
  }, [user, isGuest, sessions, currentSession, openSession]);

  return React.createElement(
    SessionsContext.Provider,
    {
      value: {
        sessions,
        currentSession,
        guestMessages,
        guestSessionId,
        loadSessions,
        createSession,
        openSession,
        deleteSession,
        addMessageToGuest,
        updateLastGuestMessage,
        clearCurrentSession,
      },
    },
    children
  );
};

export const useSessions = () => {
  const context = useContext(SessionsContext);
  if (!context) throw new Error('useSessions must be used within SessionsProvider');
  return context;
};