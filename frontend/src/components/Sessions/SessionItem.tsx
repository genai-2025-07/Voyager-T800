// src/components/Sessions/SessionItem.tsx
import React, { useState } from 'react';
import { Trash2 } from 'lucide-react';
import type { Session } from '../../types';

const SessionItem: React.FC<{ session: Session; onOpen: () => void; onDelete: () => void }> = ({ session, onOpen, onDelete }) => {
  const [showConfirm, setShowConfirm] = useState(false);

  return (
    <div className="border-b border-sidebar-border p-3 hover:bg-sidebar-accent cursor-pointer group transition-colors">
      <div onClick={onOpen} className="flex-1">
        <div className="font-medium text-sm truncate text-sidebar-foreground">{session.summary || 'New Conversation'}</div>
        <div className="text-xs text-muted-foreground mt-1">
          {new Date(session.started_at).toLocaleDateString()}
        </div>
      </div>
      
      <button
        onClick={(e) => { e.stopPropagation(); setShowConfirm(true); }}
        className="opacity-0 group-hover:opacity-100 text-destructive hover:opacity-80 p-1 mt-2 transition-opacity"
      >
        <Trash2 size={16} />
      </button>

      {showConfirm && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4" onClick={() => setShowConfirm(false)}>
          <div className="bg-card rounded-lg p-6 max-w-sm border border-border shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="font-bold mb-2 text-card-foreground">Delete Session?</h3>
            <p className="text-sm text-muted-foreground mb-4">This action cannot be undone.</p>
            <div className="flex gap-2">
              <button
                onClick={() => { onDelete(); setShowConfirm(false); }}
                className="flex-1 bg-destructive text-destructive-foreground py-2 rounded-lg hover:opacity-90 transition-opacity font-medium"
              >
                Delete
              </button>
              <button
                onClick={() => setShowConfirm(false)}
                className="flex-1 border border-border py-2 rounded-lg hover:bg-muted transition-colors font-medium"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SessionItem;
