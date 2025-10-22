import React, { useState } from 'react';
import { Menu, LogOut } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const Header: React.FC<{ onToggleSidebar: () => void; onOpenAuth: () => void }> = ({ onToggleSidebar, onOpenAuth }) => {
  const { user, isGuest, logout } = useAuth();
  const [showLogoutMenu, setShowLogoutMenu] = useState(false);

  return (
    <header className="bg-primary text-primary-foreground p-4 flex items-center justify-between shadow-md border-b border-border">
      <div className="flex items-center gap-3">
        {!isGuest && (
          <button onClick={onToggleSidebar} className="hover:bg-primary/80 p-2 rounded-lg transition-colors">
            <Menu size={24} />
          </button>
        )}
        <h1 className="text-xl font-bold">Voyager-T800</h1>
      </div>

      <div className="flex items-center gap-3">
        {isGuest ? (
          <button onClick={onOpenAuth} className="bg-secondary text-secondary-foreground px-4 py-2 rounded-lg hover:opacity-90 font-medium transition-opacity shadow-sm">
            Login / Sign Up
          </button>
        ) : (
          <div className="relative">
            <button
              onClick={() => setShowLogoutMenu(!showLogoutMenu)}
              className="flex items-center gap-2 hover:bg-primary/80 px-3 py-2 rounded-lg transition-colors"
            >
              <span className="text-sm">{user?.email}</span>
              <LogOut size={18} />
            </button>
            
            {showLogoutMenu && (
              <div className="absolute right-0 mt-2 bg-card text-card-foreground rounded-lg shadow-lg py-2 min-w-[160px] border border-border">
                <button
                  onClick={() => { logout(); setShowLogoutMenu(false); }}
                  className="w-full text-left px-4 py-2 hover:bg-muted transition-colors rounded-md mx-1"
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
};

export default Header;
