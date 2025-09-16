"""
Custom exception classes for authentication and authorization errors.

This module defines a hierarchy of exceptions for handling various authentication
scenarios in the application. All authentication exceptions inherit from AuthException
which extends FastAPI's HTTPException.
"""

from fastapi import HTTPException
from typing import Optional


class AuthException(HTTPException):
    """
    Base authentication exception.
    
    Extends FastAPI's HTTPException to provide consistent error handling
    for all authentication-related errors in the application.
    
    Args:
        status_code (int): HTTP status code for the error response.
        detail (str): Human-readable error message.
        headers (Optional[dict], optional): Additional HTTP headers. Defaults to None.
    """
    def __init__(self, status_code: int, detail: str, headers: Optional[dict] = None):
        super().__init__(status_code=status_code, detail=detail, headers=headers)


class UserAlreadyExistsException(AuthException):
    """
    Raised when attempting to register a user that already exists.
    
    This exception is thrown during user registration when the email
    address is already associated with an existing account.
    
    Args:
        email (str): The email address that already exists.
        
    HTTP Status: 409 Conflict
    
    Example:
        >>> raise UserAlreadyExistsException("user@example.com")
    """
    def __init__(self, email: str):
        super().__init__(
            status_code=409,
            detail=f"User with email {email} already exists"
        )


class UserNotFoundException(AuthException):
    """
    Raised when attempting to perform operations on a non-existent user.
    
    This exception is thrown when trying to authenticate, confirm, or
    perform other operations on a user that doesn't exist in the system.
    
    Args:
        email (str): The email address that was not found.
        
    HTTP Status: 404 Not Found
    
    Example:
        >>> raise UserNotFoundException("nonexistent@example.com")
    """
    def __init__(self, email: str):
        super().__init__(
            status_code=404,
            detail=f"User with email {email} not found"
        )


class InvalidCredentialsException(AuthException):
    """
    Raised when user provides incorrect login credentials.
    
    This exception is thrown during authentication when the provided
    email/password combination is invalid, or when the user account
    is disabled or locked.
    
    HTTP Status: 401 Unauthorized
    
    Example:
        >>> raise InvalidCredentialsException()
    """
    def __init__(self):
        super().__init__(
            status_code=401,
            detail="Invalid email or password"
        )


class UserNotConfirmedException(AuthException):
    """
    Raised when user attempts to sign in before confirming their account.
    
    This exception is thrown when a user tries to authenticate but hasn't
    yet verified their email address through the confirmation code.
    
    HTTP Status: 400 Bad Request
    
    Example:
        >>> raise UserNotConfirmedException()
    """
    def __init__(self):
        super().__init__(
            status_code=400,
            detail="User account not confirmed. Please check your email for confirmation code."
        )


class InvalidConfirmationCodeException(AuthException):
    """
    Raised when user provides an incorrect or expired confirmation code.
    
    This exception is thrown during account confirmation when the provided
    verification code is invalid, expired, or has already been used.
    
    HTTP Status: 400 Bad Request
    
    Example:
        >>> raise InvalidConfirmationCodeException()
    """
    def __init__(self):
        super().__init__(
            status_code=400,
            detail="Invalid or expired confirmation code"
        )


class TokenExpiredException(AuthException):
    """
    Raised when a JWT token has expired.
    
    This exception is thrown when attempting to use an access token
    or ID token that has passed its expiration time.
    
    HTTP Status: 401 Unauthorized
    Headers: WWW-Authenticate: Bearer (prompts client to refresh token)
    
    Example:
        >>> raise TokenExpiredException()
    """
    def __init__(self):
        super().__init__(
            status_code=401,
            detail="Token has expired",
            headers={"WWW-Authenticate": "Bearer"}
        )


class InvalidTokenException(AuthException):
    """
    Raised when a JWT token is malformed or invalid.
    
    This exception is thrown when a token fails signature verification,
    has invalid format, or contains invalid claims.
    
    HTTP Status: 401 Unauthorized
    Headers: WWW-Authenticate: Bearer (prompts client to provide valid token)
    
    Example:
        >>> raise InvalidTokenException()
    """
    def __init__(self):
        super().__init__(
            status_code=401,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"}
        )


class TooManyAttemptsException(AuthException):
    """
    Raised when rate limits are exceeded for authentication operations.
    
    This exception is thrown when a user or IP address exceeds the allowed
    number of authentication attempts within a time window, such as too many
    failed login attempts or too many confirmation code requests.
    
    HTTP Status: 429 Too Many Requests
    
    Example:
        >>> raise TooManyAttemptsException()
    """
    def __init__(self):
        super().__init__(
            status_code=429,
            detail="Too many failed attempts. Please try again later."
        )


class PasswordPolicyException(AuthException):
    """
    Raised when a password doesn't meet security requirements.
    
    This exception is thrown during registration or password reset when
    the provided password doesn't satisfy the configured password policy
    (length, complexity, etc.).
    
    Args:
        message (str): Specific message describing which policy requirement failed.
        
    HTTP Status: 400 Bad Request
    
    Example:
        >>> raise PasswordPolicyException("Password must contain at least one uppercase letter")
    """
    def __init__(self, message: str):
        super().__init__(
            status_code=400,
            detail=f"Password does not meet requirements: {message}"
        )


class CognitoServiceException(Exception):
    """
    Exception for AWS Cognito service errors.
    
    This exception represents errors that occur when communicating with
    AWS Cognito service that don't map to specific application errors.
    Unlike other exceptions in this module, this doesn't inherit from
    HTTPException as it's meant for internal error handling.
    
    Args:
        message (str): Error message describing what went wrong.
        error_code (Optional[str], optional): AWS Cognito error code if available.
        
    Attributes:
        message (str): The error message.
        error_code (Optional[str]): AWS error code.
        
    Example:
        >>> raise CognitoServiceException("Service temporarily unavailable", "ServiceUnavailable")
    """
    def __init__(self, message: str, error_code: Optional[str] = None):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)