"""
Cancellation manager for handling stop requests during streaming.

This module provides thread-safe cancellation tokens that allow
the frontend to stop generation mid-stream.
"""

import logging
from threading import Lock
from typing import Dict, Set

logger = logging.getLogger(__name__)


class CancellationManager:
    """
    Manages cancellation tokens for streaming operations.
    
    Thread-safe implementation that allows checking and setting
    cancellation flags across different threads.
    """
    
    def __init__(self):
        self._cancelled_sessions: Set[str] = set()
        self._lock = Lock()
    
    def cancel(self, session_id: str) -> bool:
        """
        Mark a session as cancelled.
        
        Args:
            session_id: Session to cancel
            
        Returns:
            True if newly cancelled, False if already cancelled
        """
        with self._lock:
            if session_id in self._cancelled_sessions:
                return False
            self._cancelled_sessions.add(session_id)
            logger.info(f"Session {session_id} marked for cancellation")
            return True
    
    def is_cancelled(self, session_id: str) -> bool:
        """
        Check if a session is cancelled.
        
        Args:
            session_id: Session to check
            
        Returns:
            True if cancelled, False otherwise
        """
        with self._lock:
            return session_id in self._cancelled_sessions
    
    def clear(self, session_id: str) -> bool:
        """
        Clear cancellation flag for a session.
        
        Args:
            session_id: Session to clear
            
        Returns:
            True if was cancelled and cleared, False if wasn't cancelled
        """
        with self._lock:
            if session_id in self._cancelled_sessions:
                self._cancelled_sessions.remove(session_id)
                logger.info(f"Cancellation cleared for session {session_id}")
                return True
            return False
    
    def cleanup_old_sessions(self, active_sessions: Set[str]):
        """
        Remove cancellation flags for sessions that no longer exist.
        
        Args:
            active_sessions: Set of currently active session IDs
        """
        with self._lock:
            old_sessions = self._cancelled_sessions - active_sessions
            for session_id in old_sessions:
                self._cancelled_sessions.discard(session_id)
            if old_sessions:
                logger.info(f"Cleaned up {len(old_sessions)} old cancellation flags")


# Global cancellation manager instance
_cancellation_manager = CancellationManager()


def get_cancellation_manager() -> CancellationManager:
    """Get the global cancellation manager instance."""
    return _cancellation_manager