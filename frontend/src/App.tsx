import React, { useState, useEffect } from 'react';
import { AuthProvider } from './contexts/AuthContext';
import { SessionsProvider } from './contexts/SessionsContext';
import Header from './components/Header/Header';
import SidebarSessions from './components/Sessions/SidebarSessions';
import ChatWindow from './components/Chat/ChatWindow';
import AuthModal from './components/Auth/AuthModal';

const App: React.FC = () => {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [authModalOpen, setAuthModalOpen] = useState(false);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setAuthModalOpen(false);
        setSidebarOpen(false);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, []);

  useEffect(() => {
    const onResize = () => {
      if (window.innerWidth >= 1024) {
        setSidebarOpen(false);
      }
    };
    window.addEventListener('resize', onResize);
    return () => window.removeEventListener('resize', onResize);
  }, []);

  return (
    <AuthProvider>
      <SessionsProvider>
        <div className="h-screen flex flex-col bg-background">
          <Header
            onToggleSidebar={() => setSidebarOpen((v) => !v)}
            onOpenAuth={() => setAuthModalOpen(true)}
          />

          <div className="flex flex-1 overflow-hidden" role="main">
            <SidebarSessions
              isOpen={sidebarOpen}
              onClose={() => setSidebarOpen(false)}
            />

            <main className="flex-1 overflow-hidden">
              <ChatWindow />
            </main>
          </div>

          {authModalOpen && (
            <AuthModal onClose={() => setAuthModalOpen(false)} />
          )}
        </div>
      </SessionsProvider>
    </AuthProvider>
  );
};

export default App;
