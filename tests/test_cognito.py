"""
Updated integration tests for authentication endpoints with fixes.
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock, AsyncMock

# Import your app
from app.main import app


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_cognito_service():
    """Mock the CognitoService at the router level."""
    with patch('app.api.auth.cognito_service') as mock_service:
        # Make all methods async mocks
        mock_service.sign_up_user = AsyncMock()
        mock_service.confirm_user = AsyncMock()  
        mock_service.resend_confirmation_code = AsyncMock()
        mock_service.login_user = AsyncMock()
        mock_service.refresh_access_token = AsyncMock()
        mock_service.logout_user = AsyncMock()
        
        yield mock_service


@pytest.fixture
def mock_auth_utils():
    """Mock auth utils to avoid environment validation issues in tests."""
    with patch('app.utils.auth_utils.validate_environment') as mock_validate:
        mock_validate.return_value = None
        yield mock_validate


class TestAuthenticationFlow:
    """Test the complete authentication flow with mocked service."""

    @pytest.mark.asyncio
    async def test_signup_success(self, test_client, mock_cognito_service):
        # Configure mock response
        mock_cognito_service.sign_up_user.return_value = {
            "user_sub": "test-user-sub-123",
            "email_verification_required": True
        }
        
        response = test_client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "password": "TestPass123!"
        })
        
        assert response.status_code == 201
        data = response.json()
        assert "User registered successfully" in data["message"]
        assert "user_sub" in data
        assert data["email_verification_required"] is True
        
        # Verify the service was called with correct parameters
        mock_cognito_service.sign_up_user.assert_called_once_with(
            email="test@example.com",
            password="TestPass123!"
        )

    def test_signup_weak_password(self, test_client, mock_cognito_service):
        response = test_client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "password": "weak"
        })
        
        # Should fail at Pydantic validation level
        assert response.status_code == 422
        data = response.json()
        # Check that it's a validation error about password
        error_messages = str(data)
        assert "password" in error_messages.lower()

    def test_signup_invalid_email(self, test_client, mock_cognito_service):
        response = test_client.post("/api/auth/signup", json={
            "email": "invalid-email",
            "password": "TestPass123!"
        })
        
        assert response.status_code == 422  # Pydantic validation

    @pytest.mark.asyncio 
    async def test_signup_duplicate_user(self, test_client, mock_cognito_service):
        from app.utils.exceptions import UserAlreadyExistsException
        
        # Configure mock to raise exception
        mock_cognito_service.sign_up_user.side_effect = UserAlreadyExistsException("test@example.com")
        
        response = test_client.post("/api/auth/signup", json={
            "email": "test@example.com", 
            "password": "TestPass123!"
        })
        
        assert response.status_code == 409

    @pytest.mark.asyncio
    async def test_confirm_signup_success(self, test_client, mock_cognito_service):
        mock_cognito_service.confirm_user.return_value = {"confirmed": True}
        
        response = test_client.post("/api/auth/confirm", json={
            "email": "test@example.com",
            "confirmation_code": "123456"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["confirmed"] is True
        
        # Verify service was called correctly
        mock_cognito_service.confirm_user.assert_called_once_with(
            email="test@example.com",
            confirmation_code="123456"
        )

    @pytest.mark.asyncio
    async def test_confirm_signup_invalid_code(self, test_client, mock_cognito_service):
        from app.utils.exceptions import UserNotFoundException
        
        mock_cognito_service.confirm_user.side_effect = UserNotFoundException("nonexistent@example.com")
        
        response = test_client.post("/api/auth/confirm", json={
            "email": "nonexistent@example.com",
            "confirmation_code": "123456"
        })
        
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_resend_confirmation_success(self, test_client, mock_cognito_service):
        mock_cognito_service.resend_confirmation_code.return_value = {
            "message": "Confirmation code sent"
        }
        
        response = test_client.post("/api/auth/resend-confirmation", json={
            "email": "test@example.com"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert "email address" in data["message"]

    @pytest.mark.asyncio
    async def test_login_success(self, test_client, mock_cognito_service):
        mock_cognito_service.login_user.return_value = {
            "access_token": "mock-access-token",
            "id_token": "mock-id-token", 
            "refresh_token": "mock-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "user_sub": "12345678-1234-1234-1234-123456789012",  # Real UUID format
            "email": "test@example.com"
        }
        
        response = test_client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123!"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "mock-access-token"
        assert data["user_sub"] == "12345678-1234-1234-1234-123456789012"
        assert data["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, test_client, mock_cognito_service):
        from app.utils.exceptions import InvalidCredentialsException
        
        mock_cognito_service.login_user.side_effect = InvalidCredentialsException()
        
        response = test_client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "WrongPassword!"
        })
        
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_unconfirmed_user(self, test_client, mock_cognito_service):
        from app.utils.exceptions import UserNotConfirmedException
        
        mock_cognito_service.login_user.side_effect = UserNotConfirmedException()
        
        response = test_client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123!"
        })
        
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_refresh_token_success(self, test_client, mock_cognito_service):
        mock_cognito_service.refresh_access_token.return_value = {
            "access_token": "new-access-token",
            "id_token": "new-id-token",
            "token_type": "Bearer", 
            "expires_in": 3600
        }
        
        response = test_client.post("/api/auth/refresh-token", json={
            "refresh_token": "valid-refresh-token"
        })
        
        assert response.status_code == 200
        data = response.json()
        assert data["access_token"] == "new-access-token"
        
        # Verify service was called correctly
        mock_cognito_service.refresh_access_token.assert_called_once_with("valid-refresh-token")

    @pytest.mark.asyncio
    async def test_refresh_token_invalid(self, test_client, mock_cognito_service):
        from app.utils.exceptions import CognitoServiceException
        
        mock_cognito_service.refresh_access_token.side_effect = CognitoServiceException(
            "Invalid refresh token", "InvalidParameterException"
        )
        
        response = test_client.post("/api/auth/refresh-token", json={
            "refresh_token": "invalid-token"
        })
        
        assert response.status_code == 500

    def test_logout_success(self, test_client):
        """Client-side logout doesn't use Cognito service, so no mocking needed."""
        response = test_client.post("/api/auth/logout")
        
        assert response.status_code == 200
        data = response.json()
        assert "discard your tokens" in data["message"]

    @pytest.mark.asyncio
    async def test_logout_global_success(self, test_client, mock_cognito_service):
        """Test global logout with access token."""
        mock_cognito_service.logout_user.return_value = {
            "message": "User logged out successfully"
        }
        
        # Mock token validation
        with patch('app.api.auth.decode_cognito_token') as mock_decode:
            mock_decode.return_value = {"sub": "test-user", "token_use": "access"}
            
            response = test_client.post(
                "/api/auth/logout-global",
                headers={"Authorization": "Bearer valid-access-token"}
            )
            
            assert response.status_code == 200
            data = response.json()
            assert "logged out successfully" in data["message"]


class TestHealthEndpoints:
    """Test health and debug endpoints."""

    def test_health_check(self, test_client):
        response = test_client.get("/api/auth/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "authentication"

    def test_debug_endpoint(self, test_client):
        response = test_client.get("/api/auth/debug")
        
        assert response.status_code == 200
        data = response.json()
        assert "available_endpoints" in data
        assert len(data["available_endpoints"]) > 5  # Should have multiple endpoints

    def test_password_policy_endpoint(self, test_client):
        response = test_client.get("/api/auth/password-policy")
        
        assert response.status_code == 200
        data = response.json()
        assert "policy" in data
        assert "Password must contain" in data["policy"]


class TestPasswordValidation:
    """Test password validation with centralized validator."""

    def test_password_scenarios(self, test_client):
        """Test various password validation scenarios."""
        
        invalid_passwords = [
            ("Short1!", "too short"),
            ("lowercase123!", "uppercase"),
            ("UPPERCASE123!", "lowercase"),
            ("NoDigits!", "digit"),
            ("NoSpecial123", "special character")
        ]
        
        for password, expected_error in invalid_passwords:
            response = test_client.post("/api/auth/signup", json={
                "email": "test@example.com",
                "password": password
            })
            assert response.status_code == 422
            # Could check for specific error message if needed

    def test_valid_passwords(self, test_client, mock_cognito_service):
        """Test that valid passwords pass validation."""
        mock_cognito_service.sign_up_user.return_value = {
            "user_sub": "test-sub",
            "email_verification_required": True
        }
        
        valid_passwords = [
            "ValidPass123!",
            "AnotherGood1@",
            "Complex2024#"
        ]
        
        for password in valid_passwords:
            response = test_client.post("/api/auth/signup", json={
                "email": "test@example.com",
                "password": password
            })
            assert response.status_code == 201


class TestInputValidation:
    """Test input validation and edge cases."""

    def test_malformed_json(self, test_client):
        response = test_client.post(
            "/api/auth/signup",
            data="invalid json",
            headers={"Content-Type": "application/json"}
        )
        
        assert response.status_code == 422

    def test_missing_fields(self, test_client):
        # Missing password
        response = test_client.post("/api/auth/signup", json={
            "email": "test@example.com"
        })
        assert response.status_code == 422
        
        # Missing email
        response = test_client.post("/api/auth/signup", json={
            "password": "TestPass123!"
        })
        assert response.status_code == 422

    def test_empty_request_body(self, test_client):
        response = test_client.post("/api/auth/signup", json={})
        assert response.status_code == 422

    def test_confirmation_code_validation(self, test_client):
        # Code too short
        response = test_client.post("/api/auth/confirm", json={
            "email": "test@example.com",
            "confirmation_code": "123"
        })
        assert response.status_code == 422
        
        # Code too long  
        response = test_client.post("/api/auth/confirm", json={
            "email": "test@example.com",
            "confirmation_code": "1234567"
        })
        assert response.status_code == 422

    def test_email_sanitization(self, test_client, mock_cognito_service):
        """Test that emails are properly sanitized."""
        mock_cognito_service.sign_up_user.return_value = {
            "user_sub": "test-sub",
            "email_verification_required": True
        }
        
        # Test email with extra whitespace
        response = test_client.post("/api/auth/signup", json={
            "email": "  TEST@EXAMPLE.COM  ",
            "password": "TestPass123!"
        })
        
        assert response.status_code == 201
        # Verify service was called with sanitized email
        mock_cognito_service.sign_up_user.assert_called_with(
            email="test@example.com",  # Should be lowercased and trimmed
            password="TestPass123!"
        )


class TestExceptionHandling:
    """Test exception handling scenarios."""

    @pytest.mark.asyncio
    async def test_too_many_attempts_exception(self, test_client, mock_cognito_service):
        from app.utils.exceptions import TooManyAttemptsException
        
        mock_cognito_service.login_user.side_effect = TooManyAttemptsException()
        
        response = test_client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123!"
        })
        
        assert response.status_code == 429

    @pytest.mark.asyncio
    async def test_generic_cognito_error(self, test_client, mock_cognito_service):
        from app.utils.exceptions import CognitoServiceException
        
        mock_cognito_service.sign_up_user.side_effect = CognitoServiceException(
            "Generic AWS error", "InternalError"
        )
        
        response = test_client.post("/api/auth/signup", json={
            "email": "test@example.com",
            "password": "TestPass123!"
        })
        
        assert response.status_code == 500


class TestSecretHashHandling:
    """Test SECRET_HASH functionality with confidential clients."""

    @pytest.mark.asyncio
    async def test_refresh_token_with_secret_hash(self, test_client, mock_cognito_service):
        """Test that refresh token works with SECRET_HASH stored username."""
        
        # First, simulate login to store username for refresh token
        mock_cognito_service.login_user.return_value = {
            "access_token": "access-token",
            "id_token": "id-token",
            "refresh_token": "refresh-token-123", 
            "token_type": "Bearer",
            "expires_in": 3600,
            "user_sub": "real-user-sub",
            "email": "test@example.com"
        }
        
        # Login first
        login_response = test_client.post("/api/auth/login", json={
            "email": "test@example.com",
            "password": "TestPass123!"
        })
        assert login_response.status_code == 200
        
        # Now test refresh
        mock_cognito_service.refresh_access_token.return_value = {
            "access_token": "new-access-token",
            "id_token": "new-id-token",
            "token_type": "Bearer",
            "expires_in": 3600
        }
        
        refresh_response = test_client.post("/api/auth/refresh-token", json={
            "refresh_token": "refresh-token-123"
        })
        
        assert refresh_response.status_code == 200
        data = refresh_response.json()
        assert data["access_token"] == "new-access-token"


# Test configuration
@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Set up test environment with proper environment variables."""
    test_env_vars = {
        "TESTING": "true",
        "AWS_REGION": "us-east-2",
        "COGNITO_USER_POOL_ID": "us-east-2_TestPool123",
        "COGNITO_CLIENT_ID": "test-client-id", 
        "COGNITO_CLIENT_SECRET": "test-client-secret",
        "JWT_ALGORITHM": "RS256",
        "JWT_SECRET_KEY": "test-secret-key-for-testing-only"
    }
    
    original_values = {}
    for key, value in test_env_vars.items():
        original_values[key] = os.environ.get(key)
        os.environ[key] = value
    
    yield
    
    # Restore original values
    for key, original_value in original_values.items():
        if original_value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = original_value


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])