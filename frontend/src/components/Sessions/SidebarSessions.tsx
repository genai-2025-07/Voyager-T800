// src/components/Sessions/SidebarSessions.tsx
import React from 'react';
import { Plus } from 'lucide-react';
import { useSessions } from '../../contexts/SessionsContext';
import { useAuth } from '../../contexts/AuthContext';
import SessionItem from './SessionItem';

const SidebarSessions: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const { sessions, openSession, deleteSession, clearCurrentSession } = useSessions();
  const { isGuest } = useAuth();

  if (!isOpen) return null;

  return (
    <>
      <div className="fixed inset-0 bg-black/50 z-40 lg:hidden" onClick={onClose} />
      <div className={`fixed lg:static inset-y-0 left-0 w-64 bg-sidebar-background border-r border-sidebar-border shadow-lg z-50 transform transition-transform ${isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0'}`}>
        <div className="p-4 border-b border-sidebar-border flex justify-between items-center">
          <h2 className="font-bold text-sidebar-foreground">Sessions</h2>
          <button onClick={clearCurrentSession} className="text-primary hover:opacity-80 p-1 rounded-lg transition-opacity">
            <Plus size={20} />
          </button>
        </div>

        {isGuest ? (
          <div className="p-4 text-center text-sm text-muted-foreground">
            Login to save and manage sessions
          </div>
        ) : (
          <div className="overflow-y-auto h-[calc(100vh-8rem)] scrollbar-pastel">
            {sessions.length === 0 ? (
              <div className="p-4 text-center text-sm text-muted-foreground">
                No sessions yet
              </div>
            ) : (
              sessions.map(session => (
                <SessionItem
                  key={session.session_id}
                  session={session}
                  onOpen={() => { openSession(session.session_id); onClose(); }}
                  onDelete={() => deleteSession(session.session_id)}
                />
              ))
            )}
          </div>
        )}
      </div>
    </>
  );
};

export default SidebarSessions;
