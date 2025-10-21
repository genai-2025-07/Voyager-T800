// src/contexts/SessionsContext.tsx
import React, {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
} from "react";
import { apiClient } from "../api/apiClient.ts";
import { useAuth } from "./AuthContext.ts";
import type { Session, Message } from "../types.ts";

interface SessionsContextType {
  sessions: Session[];
  currentSession: Session | null;
  guestMessages: Message[];
  loadSessions: () => Promise<void>;
  createSession: () => Promise<string>;
  openSession: (sessionId: string) => Promise<void>;
  deleteSession: (sessionId: string) => Promise<void>;
  addMessageToGuest: (message: Message) => void;
  clearCurrentSession: () => void;
}

export const SessionsContext = createContext<SessionsContextType | null>(null);

export const SessionsProvider: React.FC<{ children: React.ReactNode }> = ({
  children,
}) => {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [currentSession, setCurrentSession] = useState<Session | null>(null);
  const [guestMessages, setGuestMessages] = useState<Message[]>([]);
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
      const guestSessionId = `guest-${Date.now()}`;
      return guestSessionId;
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
    } catch (error) {
      console.error("Failed to open session:", error);
    }
  };

  const deleteSession = async (sessionId: string) => {
    if (!user || isGuest) return;

    try {
      await apiClient.deleteSession(sessionId, user.sub);
      setSessions((prev) =>
        sortSessionsByStartDesc(prev.filter((s) => s.session_id !== sessionId))
      );
      if (currentSession?.session_id === sessionId) {
        setCurrentSession(null);
      }
    } catch (error) {
      console.error("Failed to delete session:", error);
    }
  };

  const addMessageToGuest = (message: Message) => {
    setGuestMessages((prev) => [...prev, message]);
  };

  const clearCurrentSession = () => {
    setCurrentSession(null);
    setGuestMessages([]);
  };

  useEffect(() => {
    if (user && !isGuest) {
      loadSessions();
    }
  }, [user, isGuest, loadSessions]);

  // Debug: log sessions whenever they change
  useEffect(() => {
    console.log("Sessions state:", sessions);
    // console.table(sessions); // optional: nicer tabular view
  }, [sessions]);

  return React.createElement(
    SessionsContext.Provider,
    {
      value: {
        sessions,
        currentSession,
        guestMessages,
        loadSessions,
        createSession,
        openSession,
        deleteSession,
        addMessageToGuest,
        clearCurrentSession,
      },
    },
    children
  );
};

export const useSessions = () => {
  const context = useContext(SessionsContext);
  if (!context)
    throw new Error("useSessions must be used within SessionsProvider");
  return context;
};
