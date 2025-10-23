import React from 'react';
import { X } from 'lucide-react';

interface ToastProps {
  id: string;
  title?: string;
  description?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

const Toast: React.FC<ToastProps> = ({ id, title, description, open, onOpenChange }) => {
  if (!open) return null;

  return (
    <div className="fixed top-4 right-4 z-50 max-w-sm w-full">
      <div className="bg-white border border-gray-200 rounded-lg shadow-lg p-4 flex items-start space-x-3">
        <div className="flex-1">
          {title && (
            <h4 className="text-sm font-semibold text-gray-900">{title}</h4>
          )}
          {description && (
            <p className="text-sm text-gray-600 mt-1">{description}</p>
          )}
        </div>
        <button
          onClick={() => onOpenChange(false)}
          className="flex-shrink-0 text-gray-400 hover:text-gray-600"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
};

export default Toast;
