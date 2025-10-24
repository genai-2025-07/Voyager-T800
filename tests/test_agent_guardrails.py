"""
Integration smoke test for agent with guardrails.
Tests end-to-end flow with mocked AWS services.
"""

import pytest
from typing import Optional
from unittest.mock import Mock, patch, MagicMock
from moto import mock_aws
import boto3

from src.voyager.agents.budget_tracker import BudgetExceededError, BudgetTracker


class TestBudgetTrackerIntegration:
    """Integration tests for budget tracker"""
    
    def test_budget_tracker_lifecycle(self):
        """Test full lifecycle of budget tracker"""
        from src.voyager.agents.budget_tracker import (
            get_budget_tracker, 
            clear_budget_tracker
        )
        
        session_id = "test_session_lifecycle"
        
        # Create tracker
        tracker = get_budget_tracker(
            session_id=session_id,
            max_tool_calls=5,
            max_paid_calls=3,
            per_call_timeout=30
        )
        
        # Increment counters
        tracker.increment_tool_call()
        tracker.increment_paid_call()
        
        # Check stats
        stats = tracker.get_stats()
        assert stats["tool_calls"] == 1
        assert stats["paid_calls"] == 1
        
        # Get same tracker (should be cached)
        tracker2 = get_budget_tracker(
            session_id=session_id,
            max_tool_calls=5,
            max_paid_calls=3,
            per_call_timeout=30
        )
        assert tracker2 is tracker
        
        # Clear tracker
        clear_budget_tracker(session_id)
        
        # Get new tracker (should be fresh)
        tracker3 = get_budget_tracker(
            session_id=session_id,
            max_tool_calls=5,
            max_paid_calls=3,
            per_call_timeout=30
        )
        assert tracker3 is not tracker
        assert tracker3.tool_calls_count == 0
    
    def test_multiple_sessions_isolated(self):
        """Test that different sessions have isolated budgets"""
        from src.voyager.agents.budget_tracker import get_budget_tracker
        
        session1 = "session_1"
        session2 = "session_2"
        
        tracker1 = get_budget_tracker(
            session_id=session1,
            max_tool_calls=10,
            max_paid_calls=10,
            per_call_timeout=30
        )
        
        tracker2 = get_budget_tracker(
            session_id=session2,
            max_tool_calls=10,
            max_paid_calls=10,
            per_call_timeout=30
        )
        
        # Increment session 1 only
        tracker1.increment_tool_call()
        tracker1.increment_tool_call()
        
        # Session 2 should be unaffected
        assert tracker1.tool_calls_count == 2
        assert tracker2.tool_calls_count == 0


class TestSecretsManagerIntegration:
    """Integration tests for Secrets Manager with moto"""
    
    @pytest.fixture(autouse=True)
    def mock_secretsmanager(self):
        """Setup mock Secrets Manager"""
        with mock_aws():
            yield
    
    def test_secrets_manager_get_secret(self):
        """Test retrieving secret from mocked Secrets Manager"""
        from src.voyager.utils.secrets import SecretsManager
        
        # Create mock secret
        client = boto3.client('secretsmanager', region_name='us-east-2')
        client.create_secret(
            Name='voyager/api-keys',
            SecretString='{"OPENAI_API_KEY": "test-key-123", "ANTHROPIC_API_KEY": "test-claude-key"}'
        )
        
        # Test retrieval
        manager = SecretsManager(region_name='us-east-2')
        secret = manager.get_secret('voyager/api-keys')
        
        assert secret['OPENAI_API_KEY'] == 'test-key-123'
        assert secret['ANTHROPIC_API_KEY'] == 'test-claude-key'
    
    def test_secrets_manager_get_api_key(self):
        """Test retrieving specific API key"""
        from src.voyager.utils.secrets import SecretsManager
        
        # Create mock secret
        client = boto3.client('secretsmanager', region_name='us-east-2')
        client.create_secret(
            Name='voyager/api-keys',
            SecretString='{"GOOGLE_MAPS_API_KEY": "AIza-test-123"}'
        )
        
        # Test retrieval
        manager = SecretsManager(region_name='us-east-2')
        api_key = manager.get_api_key('voyager/api-keys', 'GOOGLE_MAPS_API_KEY')
        
        assert api_key == 'AIza-test-123'
    
    def test_secrets_manager_missing_secret(self):
        """Test handling of missing secret"""
        from src.voyager.utils.secrets import SecretsManager
        from botocore.exceptions import ClientError
        
        manager = SecretsManager(region_name='us-east-2')
        
        with pytest.raises(ClientError):
            manager.get_secret('non-existent-secret')


class TestImageStorageIntegration:
    """Integration tests for image storage with mocked S3"""
    
    @pytest.fixture(autouse=True)
    def mock_s3_service(self):
        """Setup mock S3"""
        with mock_aws():
            yield
    
    @pytest.fixture
    def s3_bucket(self):
        """Create mock S3 bucket"""
        client = boto3.client('s3', region_name='us-east-2')
        bucket_name = 'test-voyager-thumbnails'
        client.create_bucket(
            Bucket=bucket_name,
            CreateBucketConfiguration={'LocationConstraint': 'us-east-2'}
        )
        return bucket_name
    
    def test_upload_thumbnail_with_exif_strip(self, s3_bucket):
        """Test thumbnail upload with EXIF stripping"""
        from src.voyager.services.image.storage_manager import ImageStorageManager
        from PIL import Image
        from io import BytesIO
        
        # Create test image
        img = Image.new('RGB', (100, 100), color='red')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)
        
        # Upload thumbnail
        manager = ImageStorageManager(
            s3_bucket=s3_bucket,
            s3_region='us-east-2'
        )
        
        result = manager.upload_thumbnail(
            image_bytes=img_bytes.read(),
            user_id='test_user',
            session_id='test_session',
            original_filename='test.jpg'
        )
        
        # Verify result
        assert result['s3_bucket'] == s3_bucket
        assert result['s3_key'].startswith('test_user/test_session/')
        assert result['exif_stripped'] is True
        assert 'content_hash' in result
        
        # Verify S3 upload
        client = boto3.client('s3', region_name='us-east-2')
        response = client.head_object(
            Bucket=s3_bucket,
            Key=result['s3_key']
        )
        
        assert response['ServerSideEncryption'] == 'AES256'
        assert response['Metadata']['exif-stripped'] == 'true'
    
    def test_generate_presigned_url(self, s3_bucket):
        """Test presigned URL generation"""
        from src.voyager.services.image.storage_manager import ImageStorageManager
        
        # Create test object
        client = boto3.client('s3', region_name='us-east-2')
        test_key = 'test_user/test_session/test.jpg'
        client.put_object(
            Bucket=s3_bucket,
            Key=test_key,
            Body=b'test image data'
        )
        
        # Generate presigned URL
        manager = ImageStorageManager(
            s3_bucket=s3_bucket,
            s3_region='us-east-2',
            url_expiration_seconds=3600
        )
        
        url = manager.generate_presigned_url(test_key)
        
        assert url is not None
        assert s3_bucket in url
        assert test_key in url
    
    def test_delete_image(self, s3_bucket):
        """Test image deletion"""
        from src.voyager.services.image.storage_manager import ImageStorageManager
        
        # Create test object
        client = boto3.client('s3', region_name='us-east-2')
        test_key = 'test_user/test_session/delete_me.jpg'
        client.put_object(
            Bucket=s3_bucket,
            Key=test_key,
            Body=b'test image data'
        )
        
        # Delete via manager
        manager = ImageStorageManager(
            s3_bucket=s3_bucket,
            s3_region='us-east-2'
        )
        
        result = manager.delete_image(test_key)
        assert result is True
        
        # Verify deletion
        from botocore.exceptions import ClientError
        with pytest.raises(ClientError):
            client.head_object(Bucket=s3_bucket, Key=test_key)


class TestGuardrailsConfig:
    """Test guardrails configuration loading"""
    
    def test_guardrails_settings_defaults(self):
        """Test that guardrails settings load with correct defaults"""
        from src.voyager.config.guardrails import guardrails_settings
        
        assert guardrails_settings.MAX_TOOL_CALLS == 15
        assert guardrails_settings.MAX_PAID_CALLS == 10
        assert guardrails_settings.PER_CALL_TIMEOUT == 30
        assert guardrails_settings.PRESIGNED_URL_TTL == 3600
        assert guardrails_settings.MONTHLY_BUDGET_USD == 100