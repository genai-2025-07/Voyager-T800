"""
Pydantic models for authentication requests and responses.

This module defines the data models used for authentication API endpoints,
including request validation, response formatting, and centralized password validation.
All models use Pydantic for automatic validation and serialization.
"""

from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional

# Import centralized password validation
from app.utils.auth_utils import verify_password_strength, get_password_policy_description, sanitize_email


class SignUpRequest(BaseModel):
    """
    Request model for user registration.
    
    Validates user registration data including email format and password strength
    using centralized validation logic.
    
    Attributes:
        email (EmailStr): User's email address (must be valid email format).
        password (str): User's password with strength validation.
    
    Password Requirements:
        Uses centralized password policy from auth_utils.
        Default requirements:
        - Minimum 8 characters
        - At least one uppercase letter (A-Z)
        - At least one lowercase letter (a-z)
        - At least one digit (0-9)
        - At least one special character
        
    Raises:
        ValidationError: If email is invalid or password doesn't meet requirements.
    """
    email: EmailStr
    password: str = Field(..., min_length=8, description="Password must contain at least 8 characters, an uppercase letter, a lowercase letter, a digit, and a special character")
    
    @validator('email')
    def sanitize_email_input(cls, v):
        """Sanitize email input."""
        if isinstance(v, str):
            return sanitize_email(v)
        return v
    
    @validator('password')
    def validate_password_strength(cls, v):
        """
        Validate password using centralized password policy.
        
        Args:
            v (str): Password value to validate.
            
        Returns:
            str: Validated password.
            
        Raises:
            ValueError: If password doesn't meet requirements.
        """
        verify_password_strength(v)
        return v


class ConfirmSignUpRequest(BaseModel):
    """
    Request model for confirming user registration.
    
    Used to verify user's email address with the confirmation code
    sent during registration.
    
    Attributes:
        email (EmailStr): User's email address.
        confirmation_code (str): 6-digit verification code from email.
    """
    email: EmailStr
    confirmation_code: str = Field(..., min_length=6, max_length=6, description="6-digit confirmation code")
    
    @validator('email')
    def sanitize_email_input(cls, v):
        """Sanitize email input."""
        if isinstance(v, str):
            return sanitize_email(v)
        return v


class LoginRequest(BaseModel):
    """
    Request model for user authentication.
    
    Handles user login with email and password, with optional
    "remember me" functionality for extended sessions.
    
    Attributes:
        email (EmailStr): User's email address.
        password (str): User's password.
        remember_me (Optional[bool]): Whether to extend session duration.
    """
    email: EmailStr
    password: str
    remember_me: Optional[bool] = False
    
    @validator('email')
    def sanitize_email_input(cls, v):
        """Sanitize email input."""
        if isinstance(v, str):
            return sanitize_email(v)
        return v


class ResendConfirmationRequest(BaseModel):
    """
    Request model for resending confirmation code.
    
    Used when user needs a new verification code sent to their email,
    typically when the original code expires or gets lost.
    
    Attributes:
        email (EmailStr): User's email address.
    """
    email: EmailStr
    
    @validator('email')
    def sanitize_email_input(cls, v):
        """Sanitize email input."""
        if isinstance(v, str):
            return sanitize_email(v)
        return v


class RefreshTokenRequest(BaseModel):
    """
    Request model for refreshing access tokens.
    
    Used to obtain new access and ID tokens using a valid refresh token
    without requiring the user to re-authenticate.
    
    Attributes:
        refresh_token (str): Valid refresh token from previous login.
    
    Example:
        >>> request = RefreshTokenRequest(refresh_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...")
    
    Note:
        Refresh tokens typically have longer expiration times (e.g., 30 days)
        compared to access tokens (e.g., 1 hour).
    """
    refresh_token: str


class SignUpResponse(BaseModel):
    """
    Response model for successful user registration.
    
    Returns confirmation that user was created and whether email
    verification is required.
    
    Attributes:
        message (str): Success message.
        user_sub (Optional[str]): Unique user identifier from Cognito.
        email_verification_required (bool): Whether user needs to verify email.
    
    Example:
        >>> response = SignUpResponse(
        ...     message="User registered successfully",
        ...     user_sub="12345678-1234-1234-1234-123456789012",
        ...     email_verification_required=True
        ... )
    """
    message: str
    user_sub: Optional[str] = None
    email_verification_required: bool = True


class LoginResponse(BaseModel):
    """
    Response model for successful authentication.
    
    Contains all tokens and user information returned after successful login.
    
    Attributes:
        access_token (str): JWT access token for API authorization.
        id_token (str): JWT ID token containing user claims.
        refresh_token (str): Token for refreshing access token.
        token_type (str): Token type (always "Bearer").
        expires_in (int): Access token expiration time in seconds.
        user_sub (str): Unique user identifier.
        email (str): User's email address.
    
    Example:
        >>> response = LoginResponse(
        ...     access_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
        ...     id_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
        ...     refresh_token="eyJ0eXAiOiJKV1QiLCJhbGciOiJSUzI1NiJ9...",
        ...     token_type="Bearer",
        ...     expires_in=3600,
        ...     user_sub="12345678-1234-1234-1234-123456789012",
        ...     email="user@example.com"
        ... )
    
    Note:
        The access_token should be included in the Authorization header
        as "Bearer {access_token}" for authenticated requests.
    """
    access_token: str
    id_token: str
    refresh_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds
    user_sub: str
    email: str


class RefreshTokenResponse(BaseModel):
    """
    Response model for successful token refresh.
    
    Contains new tokens obtained from refresh token operation.
    Note that refresh token is not returned as it remains the same.
    
    Attributes:
        access_token (str): New JWT access token.
        id_token (str): New JWT ID token.
        token_type (str): Token type (always "Bearer").
        expires_in (int): New access token expiration time in seconds.
    """
    access_token: str
    id_token: str
    token_type: str = "Bearer"
    expires_in: int  # seconds


class LogoutResponse(BaseModel):
    """
    Response model for successful logout.
    
    Simple confirmation that user has been logged out and tokens invalidated.
    
    Attributes:
        message (str): Success message.
    
    Example:
        >>> response = LogoutResponse(message="User logged out successfully")
    """
    message: str


class ErrorResponse(BaseModel):
    """
    Response model for API errors.
    
    Standardized error response format for all authentication endpoints.
    
    Attributes:
        error (str): Error type or category.
        message (str): Human-readable error description.
        details (Optional[dict]): Additional error context or validation details.
    
    Example:
        >>> response = ErrorResponse(
        ...     error="ValidationError",
        ...     message="Password does not meet requirements",
        ...     details={"field": "password", "policy": get_password_policy_description()}
        ... )
    """
    error: str
    message: str
    details: Optional[dict] = None