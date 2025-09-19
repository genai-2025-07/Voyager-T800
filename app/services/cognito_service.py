import boto3
import os
import logging
import hmac
import hashlib
import base64
import jwt
import threading
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from app.utils.exceptions import (
    UserAlreadyExistsException,
    UserNotFoundException,
    InvalidCredentialsException,
    UserNotConfirmedException,
    InvalidConfirmationCodeException,
    TooManyAttemptsException,
    CognitoServiceException
)

logger = logging.getLogger(__name__)

# Import validation function from auth_utils
from app.utils.auth_utils import validate_environment

# Validate environment on module load
validate_environment()

# Environment variables
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET")


class TokenStore:
    """Thread-safe storage for refresh token username mapping."""
    
    def __init__(self):
        self._store = {}
        self._lock = threading.Lock()
    
    def store_token_user(self, refresh_token: str, username: str) -> None:
        """Store username for refresh token."""
        with self._lock:
            # Store only last 10 chars of token as key to save memory
            token_key = refresh_token[-10:] if len(refresh_token) > 10 else refresh_token
            self._store[token_key] = username
    
    def get_token_user(self, refresh_token: str) -> Optional[str]:
        """Get username for refresh token."""
        with self._lock:
            token_key = refresh_token[-10:] if len(refresh_token) > 10 else refresh_token
            return self._store.get(token_key)
    
    def remove_token_user(self, refresh_token: str) -> None:
        """Remove username mapping for refresh token."""
        with self._lock:
            token_key = refresh_token[-10:] if len(refresh_token) > 10 else refresh_token
            self._store.pop(token_key, None)


class CognitoService:
    """
    Service class for AWS Cognito User Pool operations.
    
    Provides methods for user registration, authentication, and account management
    using AWS Cognito Identity Provider. Handles both public and confidential
    client configurations with proper SECRET_HASH support.
    
    Attributes:
        cognito_client: Boto3 Cognito Identity Provider client
        user_pool_id: AWS Cognito User Pool ID
        client_id: AWS Cognito App Client ID  
        client_secret: AWS Cognito App Client Secret (optional)
        token_store: Thread-safe storage for refresh token mappings
    """
    
    def __init__(self):
        """
        Initialize CognitoService with AWS configuration.
        
        Creates boto3 client and validates required configuration.
        """
        self.cognito_client = boto3.client("cognito-idp", region_name=AWS_REGION)
        self.user_pool_id = COGNITO_USER_POOL_ID
        self.client_id = COGNITO_CLIENT_ID
        self.client_secret = COGNITO_CLIENT_SECRET
        self.token_store = TokenStore()

    def _calculate_secret_hash(self, username: str) -> Optional[str]:
        """
        Calculate SECRET_HASH for Cognito requests when client secret is configured.
        
        AWS Cognito requires a SECRET_HASH when the app client is configured with
        a client secret. This hash is calculated using HMAC-SHA256.
        
        Args:
            username (str): Username (typically email) for the user.
            
        Returns:
            Optional[str]: Base64-encoded SECRET_HASH if client secret is configured,
                          None if no client secret is set.
                          
        Note:
            The message for HMAC is username + client_id concatenated.
        """
        if not self.client_secret:
            return None
            
        message = username + self.client_id
        dig = hmac.new(
            str(self.client_secret).encode('utf-8'),
            msg=str(message).encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()
        return base64.b64encode(dig).decode()

    def _extract_user_sub_from_id_token(self, id_token: str) -> str:
        """
        Extract user_sub from ID token without verification.
        
        Args:
            id_token (str): JWT ID token from Cognito.
            
        Returns:
            str: User sub from token payload.
        """
        try:
            # Decode without verification to extract claims
            payload = jwt.decode(id_token, options={"verify_signature": False})
            return payload.get("sub", "")
        except Exception as e:
            logger.warning(f"Failed to extract user_sub from ID token: {e}")
            return ""

    def _handle_cognito_error(self, error: ClientError, email: str = None) -> None:
        """
        Handle AWS Cognito ClientError exceptions and convert to application exceptions.
        
        Maps common Cognito error codes to appropriate custom exceptions
        with user-friendly messages while preserving error context.
        
        Args:
            error (ClientError): Boto3 ClientError from Cognito operation.
            email (str, optional): User email for logging context (hashed for privacy).
            
        Raises:
            Custom exceptions based on Cognito error code:
            - UserAlreadyExistsException: User already registered
            - UserNotFoundException: User doesn't exist
            - InvalidCredentialsException: Wrong password or user disabled
            - UserNotConfirmedException: Account needs email verification
            - InvalidConfirmationCodeException: Wrong or expired verification code
            - TooManyAttemptsException: Rate limit exceeded
            - CognitoServiceException: Other Cognito errors
        """
        error_code = error.response['Error']['Code']
        error_message = error.response['Error']['Message']
        
        # Log with hashed email for privacy
        user_context = f"user_{hash(email) % 10000}" if email else "unknown"
        logger.error(f"Cognito error for {user_context}: {error_code} - {error_message}")
        
        error_mapping = {
            'UsernameExistsException': lambda: UserAlreadyExistsException(email or "unknown"),
            'UserNotFoundException': lambda: UserNotFoundException(email or "unknown"),
            'NotAuthorizedException': lambda: InvalidCredentialsException(),
            'UserNotConfirmedException': lambda: UserNotConfirmedException(),
            'CodeMismatchException': lambda: InvalidConfirmationCodeException(),
            'ExpiredCodeException': lambda: InvalidConfirmationCodeException(),
            'TooManyRequestsException': lambda: TooManyAttemptsException(),
            'TooManyFailedAttemptsException': lambda: TooManyAttemptsException(),
        }
        
        if error_code in error_mapping:
            raise error_mapping[error_code]()
        else:
            raise CognitoServiceException(f"Cognito error: {error_message}", error_code)

    async def sign_up_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Register a new user in AWS Cognito User Pool.
        
        Creates a new user account with email as username. The user will need
        to verify their email address before they can sign in.
        
        Args:
            email (str): User's email address (used as username).
            password (str): User's password (must meet Cognito password policy).
            
        Returns:
            Dict[str, Any]: Registration result containing:
                - user_sub: Unique user identifier
                - email_verification_required: Whether email verification is needed
                
        Raises:
            UserAlreadyExistsException: If user already exists
            CognitoServiceException: For other Cognito errors
        """
        try:
            logger.info(f"Attempting to sign up user: {hash(email) % 10000}")
            
            # Prepare request parameters
            request_params = {
                "ClientId": self.client_id,
                "Username": email,
                "Password": password,
                "UserAttributes": [
                    {"Name": "email", "Value": email}
                ],
                "ClientMetadata": {
                    "source": "api_signup"
                }
            }
            
            # Add SECRET_HASH if client secret is configured
            if self.client_secret:
                request_params["SecretHash"] = self._calculate_secret_hash(email)
                logger.debug("SECRET_HASH added to signup request")
            
            response = self.cognito_client.sign_up(**request_params)
            
            logger.info(f"User signed up successfully")
            return {
                "user_sub": response.get("UserSub"),
                "email_verification_required": not response.get("UserConfirmed", False)
            }
            
        except ClientError as e:
            self._handle_cognito_error(e, email)

    async def confirm_user(self, email: str, confirmation_code: str) -> Dict[str, Any]:
        """
        Confirm user registration with email verification code.
        
        Validates the confirmation code sent to user's email and activates
        their account for sign-in.
        
        Args:
            email (str): User's email address.
            confirmation_code (str): 6-digit verification code from email.
            
        Returns:
            Dict[str, Any]: Confirmation result with success status.
            
        Raises:
            UserNotFoundException: If user doesn't exist
            InvalidConfirmationCodeException: If code is wrong or expired
            CognitoServiceException: For other Cognito errors
        """
        try:
            logger.info(f"Attempting to confirm user: {hash(email) % 10000}")
            
            # Prepare request parameters
            request_params = {
                "ClientId": self.client_id,
                "Username": email,
                "ConfirmationCode": confirmation_code
            }
            
            # Add SECRET_HASH if client secret is configured
            if self.client_secret:
                request_params["SecretHash"] = self._calculate_secret_hash(email)
            
            response = self.cognito_client.confirm_sign_up(**request_params)
            
            logger.info("User confirmed successfully")
            return {"confirmed": True}
            
        except ClientError as e:
            self._handle_cognito_error(e, email)

    async def resend_confirmation_code(self, email: str) -> Dict[str, Any]:
        """
        Resend email verification code to user.
        
        Triggers Cognito to send a new confirmation code to the user's email.
        Useful when the original code expires or gets lost.
        
        Args:
            email (str): User's email address.
            
        Returns:
            Dict[str, Any]: Success message.
            
        Raises:
            UserNotFoundException: If user doesn't exist
            TooManyAttemptsException: If too many codes requested
            CognitoServiceException: For other Cognito errors
        """
        try:
            logger.info(f"Resending confirmation code")
            
            # Prepare request parameters
            request_params = {
                "ClientId": self.client_id,
                "Username": email
            }
            
            # Add SECRET_HASH if client secret is configured
            if self.client_secret:
                request_params["SecretHash"] = self._calculate_secret_hash(email)
            
            response = self.cognito_client.resend_confirmation_code(**request_params)
            
            logger.info("Confirmation code resent successfully")
            return {"message": "Confirmation code sent"}
            
        except ClientError as e:
            self._handle_cognito_error(e, email)

    async def login_user(self, email: str, password: str) -> Dict[str, Any]:
        """
        Authenticate user and return JWT tokens.
        
        Performs username/password authentication against Cognito User Pool
        and returns access, ID, and refresh tokens upon successful login.
        
        Args:
            email (str): User's email address.
            password (str): User's password.
            
        Returns:
            Dict[str, Any]: Authentication result containing:
                - access_token: JWT access token for API authorization
                - id_token: JWT ID token with user claims  
                - refresh_token: Token for refreshing access token
                - expires_in: Token expiration time in seconds
                - token_type: Token type ("Bearer")
                - user_sub: Unique user identifier
                - email: User's email address
                
        Raises:
            InvalidCredentialsException: If email/password is wrong
            UserNotConfirmedException: If user hasn't verified email
            UserNotFoundException: If user doesn't exist
            TooManyAttemptsException: If too many failed attempts
            CognitoServiceException: For other Cognito errors
        """
        try:
            logger.info(f"Attempting to login user")
            
            # Prepare authentication parameters
            auth_parameters = {
                "USERNAME": email,
                "PASSWORD": password
            }
            
            # Add SECRET_HASH if client secret is configured
            if self.client_secret:
                auth_parameters["SECRET_HASH"] = self._calculate_secret_hash(email)
            
            response = self.cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="USER_PASSWORD_AUTH",
                AuthParameters=auth_parameters
            )
            
            auth_result = response["AuthenticationResult"]
            
            # Extract real user_sub from ID token
            user_sub = self._extract_user_sub_from_id_token(auth_result["IdToken"])
            
            # Store username for refresh token (for SECRET_HASH calculation)
            if self.client_secret:
                self.token_store.store_token_user(auth_result["RefreshToken"], email)
            
            logger.info("User logged in successfully")
            return {
                "access_token": auth_result["AccessToken"],
                "id_token": auth_result["IdToken"],
                "refresh_token": auth_result["RefreshToken"],
                "expires_in": auth_result["ExpiresIn"],
                "token_type": "Bearer",
                "user_sub": user_sub,
                "email": email
            }
            
        except ClientError as e:
            self._handle_cognito_error(e, email)

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """
        Refresh access token using refresh token.
        
        Uses a valid refresh token to obtain new access and ID tokens
        without requiring the user to re-enter credentials. Now properly
        handles SECRET_HASH for confidential clients.
        
        Args:
            refresh_token (str): Valid refresh token from previous login.
            
        Returns:
            Dict[str, Any]: New tokens containing:
                - access_token: New JWT access token
                - id_token: New JWT ID token
                - expires_in: Token expiration time in seconds
                - token_type: Token type ("Bearer")
                
        Raises:
            InvalidTokenException: If refresh token is invalid or expired
            CognitoServiceException: For other Cognito errors
        """
        try:
            logger.info("Attempting to refresh access token")
            
            # Prepare authentication parameters
            auth_parameters = {
                "REFRESH_TOKEN": refresh_token
            }
            
            # Add SECRET_HASH if client secret is configured
            if self.client_secret:
                username = self.token_store.get_token_user(refresh_token)
                if username:
                    auth_parameters["SECRET_HASH"] = self._calculate_secret_hash(username)
                    logger.debug("SECRET_HASH added to refresh request")
                else:
                    logger.warning("No username found for refresh token - SECRET_HASH not added")
            
            response = self.cognito_client.initiate_auth(
                ClientId=self.client_id,
                AuthFlow="REFRESH_TOKEN_AUTH",
                AuthParameters=auth_parameters
            )
            
            auth_result = response["AuthenticationResult"]
            
            logger.info("Access token refreshed successfully")
            return {
                "access_token": auth_result["AccessToken"],
                "id_token": auth_result["IdToken"],
                "expires_in": auth_result["ExpiresIn"],
                "token_type": "Bearer"
            }
            
        except ClientError as e:
            self._handle_cognito_error(e)

    async def logout_user(self, access_token: str) -> Dict[str, Any]:
        """
        Log out user by invalidating all tokens globally.
        
        Performs global sign out which invalidates all tokens for the user
        across all devices and sessions.
        
        Args:
            access_token (str): Valid access token for the user.
            
        Returns:
            Dict[str, Any]: Success message.
            
        Raises:
            InvalidTokenException: If access token is invalid
            CognitoServiceException: For other Cognito errors
        """
        try:
            logger.info("Attempting to logout user")
            
            self.cognito_client.global_sign_out(
                AccessToken=access_token
            )
            logger.info("User logged out successfully")
            return {"message": "User logged out successfully"}
            
        except ClientError as e:
            self._handle_cognito_error(e)


# Create singleton instance
cognito_service = CognitoService()