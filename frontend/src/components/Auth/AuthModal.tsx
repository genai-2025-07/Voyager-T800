import React, { useState } from 'react';
import { X } from 'lucide-react';
import { useAuth } from '../../contexts/AuthContext';

const AuthModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [mode, setMode] = useState<'login' | 'signup' | 'confirm'>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmCode, setConfirmCode] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const { login, signup, confirm } = useAuth();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      if (mode === 'login') {
        await login(email, password);
        onClose();
      } else if (mode === 'signup') {
        await signup(email, password);
        setMode('confirm');
      } else if (mode === 'confirm') {
        await confirm(email, confirmCode);
        await login(email, password);
        onClose();
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'An error occurred');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-card rounded-xl shadow-2xl max-w-md w-full p-6 border border-border">
        <div className="flex justify-between items-center mb-4">
          <h2 className="text-2xl font-bold text-card-foreground">
            {mode === 'login' ? 'Login' : mode === 'signup' ? 'Sign Up' : 'Confirm Email'}
          </h2>
          <button onClick={onClose} className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded-lg hover:bg-muted">
            <X size={24} />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          {mode !== 'confirm' && (
            <>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground">Email</label>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2 bg-input border border-border rounded-lg focus:ring-2 focus:ring-primary focus:outline-none text-foreground transition-all"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1 text-foreground">Password</label>
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2 bg-input border border-border rounded-lg focus:ring-2 focus:ring-primary focus:outline-none text-foreground transition-all"
                  required
                />
              </div>
            </>
          )}

          {mode === 'confirm' && (
            <div>
              <label className="block text-sm font-medium mb-1 text-foreground">Confirmation Code</label>
              <input
                type="text"
                value={confirmCode}
                onChange={(e) => setConfirmCode(e.target.value)}
                className="w-full px-3 py-2 bg-input border border-border rounded-lg focus:ring-2 focus:ring-primary focus:outline-none text-foreground transition-all"
                required
              />
            </div>
          )}

          {error && (
            <div className="bg-destructive/10 text-destructive-foreground p-3 rounded-lg text-sm border border-destructive/20">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={loading}
            className="w-full bg-primary text-primary-foreground py-2 rounded-lg hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity font-medium shadow-sm"
          >
            {loading ? 'Processing...' : mode === 'login' ? 'Login' : mode === 'signup' ? 'Sign Up' : 'Confirm'}
          </button>
        </form>

        {mode === 'login' && (
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Don't have an account?{' '}
            <button onClick={() => setMode('signup')} className="text-primary hover:opacity-80 transition-opacity font-medium">
              Sign up
            </button>
          </p>
        )}

        {mode === 'signup' && (
          <p className="mt-4 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <button onClick={() => setMode('login')} className="text-primary hover:opacity-80 transition-opacity font-medium">
              Login
            </button>
          </p>
        )}
      </div>
    </div>
  );
};

export default AuthModal;
