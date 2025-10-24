"""
Budget tracking and enforcement for agent tool calls.
Prevents runaway costs by limiting tool and LLM invocations.
"""

import logging
import time
from typing import Optional
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class BudgetExceededError(Exception):
    """Raised when agent exceeds budget limits"""
    def __init__(self, message: str, budget_type: str):
        super().__init__(message)
        self.budget_type = budget_type


class BudgetTracker:
    """Tracks and enforces per-request budget limits"""
    
    def __init__(
        self,
        max_tool_calls: int,
        max_paid_calls: int,
        per_call_timeout: int,
        session_id: str
    ):
        self.max_tool_calls = max_tool_calls
        self.max_paid_calls = max_paid_calls
        self.per_call_timeout = per_call_timeout
        self.session_id = session_id
        
        # Counters
        self.tool_calls_count = 0
        self.paid_calls_count = 0
        self.start_time = time.time()
        
    def increment_tool_call(self) -> None:
        """Increment tool call counter and check limit"""
        self.tool_calls_count += 1
        logger.info(
            f"Tool call {self.tool_calls_count}/{self.max_tool_calls} "
            f"for session {self.session_id}"
        )
        
        if self.tool_calls_count > self.max_tool_calls:
            error_msg = (
                f"Tool call budget exceeded: {self.tool_calls_count}/{self.max_tool_calls} "
                f"for session {self.session_id}"
            )
            logger.warning(error_msg)
            raise BudgetExceededError(error_msg, "tool_calls")
    
    def increment_paid_call(self) -> None:
        """Increment LLM API call counter and check limit"""
        self.paid_calls_count += 1
        logger.info(
            f"Paid call {self.paid_calls_count}/{self.max_paid_calls} "
            f"for session {self.session_id}"
        )
        
        if self.paid_calls_count > self.max_paid_calls:
            error_msg = (
                f"Paid call budget exceeded: {self.paid_calls_count}/{self.max_paid_calls} "
                f"for session {self.session_id}"
            )
            logger.warning(error_msg)
            raise BudgetExceededError(error_msg, "paid_calls")
    
    def check_timeout(self) -> None:
        """Check if total execution time exceeded"""
        elapsed = time.time() - self.start_time
        if elapsed > self.per_call_timeout:
            error_msg = (
                f"Request timeout exceeded: {elapsed:.2f}s/{self.per_call_timeout}s "
                f"for session {self.session_id}"
            )
            logger.warning(error_msg)
            raise BudgetExceededError(error_msg, "timeout")
    
    def get_stats(self) -> dict:
        """Get current budget usage statistics"""
        elapsed = time.time() - self.start_time
        return {
            "session_id": self.session_id,
            "tool_calls": self.tool_calls_count,
            "max_tool_calls": self.max_tool_calls,
            "paid_calls": self.paid_calls_count,
            "max_paid_calls": self.max_paid_calls,
            "elapsed_seconds": round(elapsed, 2),
            "timeout_seconds": self.per_call_timeout
        }


# Session-based budget tracker storage
_session_budgets: dict[str, BudgetTracker] = {}


def get_budget_tracker(
    session_id: str,
    max_tool_calls: int,
    max_paid_calls: int,
    per_call_timeout: int
) -> BudgetTracker:
    """Get or create budget tracker for session"""
    if session_id not in _session_budgets:
        _session_budgets[session_id] = BudgetTracker(
            max_tool_calls=max_tool_calls,
            max_paid_calls=max_paid_calls,
            per_call_timeout=per_call_timeout,
            session_id=session_id
        )
    return _session_budgets[session_id]


def clear_budget_tracker(session_id: str) -> None:
    """Clear budget tracker after request completes"""
    if session_id in _session_budgets:
        del _session_budgets[session_id]