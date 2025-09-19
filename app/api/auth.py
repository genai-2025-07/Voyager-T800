"""
FastAPI router for authentication endpoints.

This module provides REST API endpoints for user authentication including
registration, login, logout, email confirmation, and token refresh.
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import logging
from typing import Dict, Any, Optional

from app.models.auth.auth import (
    SignUpRequest, SignUpResponse,
    LoginRequest, LoginResponse,
    ConfirmSignUpRequest, LogoutResponse,
    ResendConfirmationRequest, RefreshTokenRequest, RefreshTokenResponse,
    ErrorResponse
)
from app.services.cognito_service import cognito_service
from app.utils.auth_utils import decode_cognito_token, get_password_policy_description, hash_email_for_logging
from app.utils.exceptions import (
    AuthException, CognitoServiceException,
    PasswordPolicyException
)

logger = logging.getLogger(__name__)

# Security scheme for protected endpoints
security = HTTPBearer()

router = APIRouter(
    prefix="/api/auth",
    tags=["Authentication"],
    responses={
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        400: {"model": ErrorResponse, "description": "Bad Request"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"}
    }
)


def get_access_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """
    Extract and validate access token from Authorization header.
    
    Args:
        credentials: HTTP Bearer credentials from Authorization header.
        
    Returns:
        str: Valid access token.
        
    Raises:
        HTTPException: If token is missing or invalid.
    """
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token required"
        )
    
    token = credentials.credentials
    
    # Validate token format and signature
    try:
        decode_cognito_token(token, token_type="access")
        return token
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Token validation error: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid access token"
        )


@router.get("/debug")
async def debug_auth():
    """
    Debug endpoint to check router availability and list endpoints.
    
    Returns:
        Dict: Debug information including available endpoints.
    """
    return {
        "message": "Auth router is working!",
        "available_endpoints": [
            "GET /api/auth/debug",
            "GET /api/auth/health", 
            "GET /api/auth/password-policy",
            "POST /api/auth/signup",
            "POST /api/auth/confirm",
            "POST /api/auth/resend-confirmation",
            "POST /api/auth/login",
            "POST /api/auth/refresh-token",
            "POST /api/auth/logout"
        ]
    }


@router.get("/health")
async def health_check():
    """
    Health check endpoint for the authentication service.
    
    Returns:
        Dict: Service health status and basic information.
    """
    return {
        "status": "healthy",
        "service": "authentication",
        "version": "1.0.0"
    }


@router.get("/password-policy")
async def get_password_policy():
    """
    Get password policy requirements.
    
    Returns:
        Dict: Password policy description for frontend validation.
    """
    return {
        "policy": get_password_policy_description(),
        "message": "Password requirements for user registration and reset"
    }


@router.post("/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
async def signup(request: SignUpRequest):
    """
    Register a new user account.
    
    Creates a new user in AWS Cognito and sends email verification code.
    Password strength is validated by Pydantic model using centralized validator.
    
    Args:
        request: User registration data including email and password.
        
    Returns:
        SignUpResponse: Registration result with user ID and verification status.
        
    Raises:
        PasswordPolicyException: If password doesn't meet requirements.
        UserAlreadyExistsException: If user already exists.
        HTTPException: For other errors.
    """
    try:
        user_hash = hash_email_for_logging(request.email)
        logger.info(f"User signup attempt: {user_hash}")
        
        # Password validation is already done by Pydantic model
        # Register user with Cognito
        result = await cognito_service.sign_up_user(
            email=request.email,
            password=request.password
        )
        
        logger.info(f"User signup successful: {user_hash}")
        
        return SignUpResponse(
            message="User registered successfully. Please check your email for confirmation code.",
            user_sub=result.get("user_sub"),
            email_verification_required=result.get("email_verification_required", True)
        )
        
    except ValueError as e:
        # This would come from Pydantic validation
        logger.warning(f"Password validation failed: {str(e)}")
        raise PasswordPolicyException(str(e))
        
    except AuthException:
        # Re-raise auth exceptions (they already have proper HTTP status codes)
        raise
        
    except CognitoServiceException as e:
        logger.error(f"Cognito service error during signup: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {e.message}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during signup: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Registration failed due to internal error"
        )


@router.post("/confirm")
async def confirm_signup(request: ConfirmSignUpRequest):
    """
    Confirm user registration with email verification code.
    
    Activates user account using the 6-digit code sent to their email.
    
    Args:
        request: Email and confirmation code.
        
    Returns:
        Dict: Success message and confirmation status.
        
    Raises:
        UserNotFoundException: If user doesn't exist.
        InvalidConfirmationCodeException: If code is wrong or expired.
        HTTPException: For other errors.
    """
    try:
        user_hash = hash_email_for_logging(request.email)
        logger.info(f"User confirmation attempt: {user_hash}")
        
        result = await cognito_service.confirm_user(
            email=request.email,
            confirmation_code=request.confirmation_code
        )
        
        logger.info(f"User confirmation successful: {user_hash}")
        
        return {
            "message": "User confirmed successfully. You can now log in.",
            "confirmed": result.get("confirmed", True)
        }
        
    except AuthException:
        # Re-raise auth exceptions (they already have proper HTTP status codes)
        raise
        
    except CognitoServiceException as e:
        logger.error(f"Cognito service error during confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Confirmation failed: {e.message}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during confirmation: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Confirmation failed due to internal error"
        )


@router.post("/resend-confirmation")
async def resend_confirmation(request: ResendConfirmationRequest):
    """
    Resend email verification code to user.
    
    Sends a new 6-digit confirmation code to the user's email address.
    
    Args:
        request: User's email address.
        
    Returns:
        Dict: Success message.
        
    Raises:
        UserNotFoundException: If user doesn't exist.
        TooManyAttemptsException: If too many codes requested.
        HTTPException: For other errors.
    """
    try:
        user_hash = hash_email_for_logging(request.email)
        logger.info(f"Confirmation code resend attempt: {user_hash}")
        
        result = await cognito_service.resend_confirmation_code(request.email)
        
        logger.info(f"Confirmation code resent successfully: {user_hash}")
        
        return {
            "message": "Confirmation code sent to your email address."
        }
        
    except AuthException:
        # Re-raise auth exceptions (they already have proper HTTP status codes)
        raise
        
    except CognitoServiceException as e:
        logger.error(f"Cognito service error during resend confirmation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resend confirmation: {e.message}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during resend confirmation: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resend confirmation due to internal error"
        )


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """
    Authenticate user and return tokens.
    
    Validates credentials and returns access, ID, and refresh tokens.
    
    Args:
        request: User login credentials.
        
    Returns:
        LoginResponse: Authentication tokens and user information.
        
    Raises:
        InvalidCredentialsException: If email/password is wrong.
        UserNotConfirmedException: If user hasn't verified email.
        UserNotFoundException: If user doesn't exist.
        HTTPException: For other errors.
    """
    try:
        user_hash = hash_email_for_logging(request.email)
        logger.info(f"User login attempt: {user_hash}")
        
        result = await cognito_service.login_user(
            email=request.email,
            password=request.password
        )
        
        logger.info(f"User login successful: {user_hash}")
        
        return LoginResponse(
            access_token=result["access_token"],
            id_token=result["id_token"],
            refresh_token=result["refresh_token"],
            token_type=result["token_type"],
            expires_in=result["expires_in"],
            user_sub=result["user_sub"],
            email=result["email"]
        )
        
    except AuthException:
        # Re-raise auth exceptions (they already have proper HTTP status codes)
        raise
        
    except CognitoServiceException as e:
        logger.error(f"Cognito service error during login: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {e.message}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during login: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Login failed due to internal error"
        )


@router.post("/refresh-token", response_model=RefreshTokenResponse)
async def refresh_token(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token.
    
    Obtains new access and ID tokens without requiring user to re-authenticate.
    Now properly handles SECRET_HASH for confidential clients.
    
    Args:
        request: Refresh token from previous login.
        
    Returns:
        RefreshTokenResponse: New access and ID tokens.
        
    Raises:
        InvalidTokenException: If refresh token is invalid or expired.
        HTTPException: For other errors.
    """
    try:
        logger.info("Token refresh attempt")
        
        result = await cognito_service.refresh_access_token(request.refresh_token)
        
        logger.info("Token refresh successful")
        
        return RefreshTokenResponse(
            access_token=result["access_token"],
            id_token=result["id_token"],
            token_type=result["token_type"],
            expires_in=result["expires_in"]
        )
        
    except AuthException:
        # Re-raise auth exceptions (they already have proper HTTP status codes)
        raise
        
    except CognitoServiceException as e:
        logger.error(f"Cognito service error during token refresh: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {e.message}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during token refresh: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Token refresh failed due to internal error"
        )


@router.post("/logout", response_model=LogoutResponse)
async def logout():
    """
    Log out user (client-side logout).
    
    Returns success message. Client should discard tokens locally.
    For server-side token invalidation, use POST /api/auth/logout-global with access token.
    
    Returns:
        LogoutResponse: Success message.
        
    Note:
        This is a client-side logout. Client should discard all tokens.
        For server-side token invalidation, additional endpoint would be needed.
    """
    try:
        logger.info("Client-side logout requested")
        
        return LogoutResponse(
            message="Logged out successfully. Please discard your tokens."
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during logout: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Logout failed due to internal error"
        )


@router.post("/logout-global", response_model=LogoutResponse)
async def logout_global(access_token: str = Depends(get_access_token)):
    """
    Log out user globally (server-side logout).
    
    Invalidates all user tokens across all devices and sessions.
    Requires valid access token for authentication.
    
    Args:
        access_token: Valid access token from Authorization header.
        
    Returns:
        LogoutResponse: Success message.
        
    Raises:
        InvalidTokenException: If access token is invalid.
        HTTPException: For other errors.
    """
    try:
        logger.info("Global logout requested")
        
        result = await cognito_service.logout_user(access_token)
        
        logger.info("Global logout successful")
        
        return LogoutResponse(
            message=result["message"]
        )
        
    except AuthException:
        # Re-raise auth exceptions (they already have proper HTTP status codes)
        raise
        
    except CognitoServiceException as e:
        logger.error(f"Cognito service error during global logout: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Global logout failed: {e.message}"
        )
        
    except Exception as e:
        logger.error(f"Unexpected error during global logout: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Global logout failed due to internal error"
        )