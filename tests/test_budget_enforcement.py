"""
Unit tests for agent budget enforcement.
Tests that budget limits are properly enforced and errors are raised.
"""

import pytest
from unittest.mock import Mock, patch
from src.voyager.agents.budget_tracker import (
    BudgetTracker,
    BudgetExceededError,
    get_budget_tracker,
    clear_budget_tracker
)


class TestBudgetTracker:
    """Test budget tracking and enforcement"""
    
    def test_tool_call_increment(self):
        """Test tool call counter increments correctly"""
        tracker = BudgetTracker(
            max_tool_calls=5,
            max_paid_calls=3,
            per_call_timeout=30,
            session_id="test_session"
        )
        
        for i in range(5):
            tracker.increment_tool_call()
            assert tracker.tool_calls_count == i + 1
    
    def test_tool_call_budget_exceeded(self):
        """Test that exceeding tool call budget raises error"""
        tracker = BudgetTracker(
            max_tool_calls=3,
            max_paid_calls=5,
            per_call_timeout=30,
            session_id="test_session"
        )
        
        # Should succeed for first 3 calls
        tracker.increment_tool_call()
        tracker.increment_tool_call()
        tracker.increment_tool_call()
        
        # 4th call should raise error
        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.increment_tool_call()
        
        assert exc_info.value.budget_type == "tool_calls"
    
    def test_paid_call_budget_exceeded(self):
        """Test that exceeding paid call budget raises error"""
        tracker = BudgetTracker(
            max_tool_calls=10,
            max_paid_calls=2,
            per_call_timeout=30,
            session_id="test_session"
        )
        
        tracker.increment_paid_call()
        tracker.increment_paid_call()
        
        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.increment_paid_call()
        
        assert exc_info.value.budget_type == "paid_calls"
    
    def test_timeout_check(self):
        """Test timeout detection"""
        import time
        
        tracker = BudgetTracker(
            max_tool_calls=10,
            max_paid_calls=10,
            per_call_timeout=1,  # 1 second timeout
            session_id="test_session"
        )
        
        # Should not raise immediately
        tracker.check_timeout()
        
        # Wait for timeout
        time.sleep(1.1)
        
        with pytest.raises(BudgetExceededError) as exc_info:
            tracker.check_timeout()
        
        assert exc_info.value.budget_type == "timeout"
    
    def test_get_stats(self):
        """Test budget statistics reporting"""
        tracker = BudgetTracker(
            max_tool_calls=10,
            max_paid_calls=5,
            per_call_timeout=30,
            session_id="test_session"
        )
        
        tracker.increment_tool_call()
        tracker.increment_paid_call()
        
        stats = tracker.get_stats()
        
        assert stats["session_id"] == "test_session"
        assert stats["tool_calls"] == 1
        assert stats["paid_calls"] == 1
        assert stats["max_tool_calls"] == 10
        assert stats["max_paid_calls"] == 5
        assert "elapsed_seconds" in stats
    
    def test_session_tracker_management(self):
        """Test get/clear session budget trackers"""
        session_id = "test_session_123"
        
        tracker1 = get_budget_tracker(
            session_id=session_id,
            max_tool_calls=10,
            max_paid_calls=5,
            per_call_timeout=30
        )
        
        # Should return same instance
        tracker2 = get_budget_tracker(
            session_id=session_id,
            max_tool_calls=10,
            max_paid_calls=5,
            per_call_timeout=30
        )
        
        assert tracker1 is tracker2
        
        # Clear and verify new instance created
        clear_budget_tracker(session_id)
        
        tracker3 = get_budget_tracker(
            session_id=session_id,
            max_tool_calls=10,
            max_paid_calls=5,
            per_call_timeout=30
        )
        
        assert tracker3 is not tracker1