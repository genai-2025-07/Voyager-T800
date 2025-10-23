import React, { createContext, useContext, useState, useCallback } from 'react';
import Toast from './toast';

interface ToastContextType {
  showToast: (title: string, description?: string) => void;
}

const ToastContext = createContext<ToastContextType | undefined>(undefined);

export const ToastProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, setToasts] = useState<Array<{
    id: string;
    title: string;
    description?: string;
    open: boolean;
  }>>([]);

  const showToast = useCallback((title: string, description?: string) => {
    const id = Math.random().toString(36).substr(2, 9);
    const newToast = {
      id,
      title,
      description,
      open: true,
    };

    setToasts(prev => [...prev, newToast]);

    // Auto-dismiss after 4 seconds
    setTimeout(() => {
      setToasts(prev => prev.map(toast => 
        toast.id === id ? { ...toast, open: false } : toast
      ));
      
      // Remove from state after animation
      setTimeout(() => {
        setToasts(prev => prev.filter(toast => toast.id !== id));
      }, 300);
    }, 4000);
  }, []);

  const dismissToast = useCallback((id: string) => {
    setToasts(prev => prev.map(toast => 
      toast.id === id ? { ...toast, open: false } : toast
    ));
    
    setTimeout(() => {
      setToasts(prev => prev.filter(toast => toast.id !== id));
    }, 300);
  }, []);

  return (
    <ToastContext.Provider value={{ showToast }}>
      {children}
      {toasts.map(toast => (
        <Toast
          key={toast.id}
          id={toast.id}
          title={toast.title}
          description={toast.description}
          open={toast.open}
          onOpenChange={(open) => !open && dismissToast(toast.id)}
        />
      ))}
    </ToastContext.Provider>
  );
};

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};
