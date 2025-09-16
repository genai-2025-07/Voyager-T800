import os
import jwt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from fastapi import HTTPException, status
import requests
import json
import threading
import re
from jose import JWTError, jwt as jose_jwt
import logging

logger = logging.getLogger(__name__)

# Configuration
COGNITO_REGION = os.getenv("AWS_REGION", "us-east-1")
COGNITO_USER_POOL_ID = os.getenv("COGNITO_USER_POOL_ID")
COGNITO_CLIENT_ID = os.getenv("COGNITO_CLIENT_ID")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "RS256")


class PasswordValidator:
    """
    Centralized password validation with configurable policies.
    """
    
    # Default password policy
    DEFAULT_POLICY = {
        'min_length': 8,
        'require_uppercase': True,
        'require_lowercase': True,
        'require_digits': True,
        'require_special': True,
        'special_chars': r'[^A-Za-z0-9]'
    }
    
    def __init__(self, policy: Optional[Dict] = None):
        """
        Initialize with password policy.
        
        Args:
            policy: Custom password policy dict, uses defaults if None
        """
        self.policy = {**self.DEFAULT_POLICY, **(policy or {})}
    
    def validate(self, password: str) -> bool:
        """
        Validate password against policy.
        
        Args:
            password (str): Password to validate.
            
        Returns:
            bool: True if password meets all requirements.
            
        Raises:
            ValueError: If password doesn't meet any requirement.
        """
        errors = []
        
        # Check length
        if len(password) < self.policy['min_length']:
            errors.append(f"Password must be at least {self.policy['min_length']} characters long")
        
        # Check uppercase
        if self.policy['require_uppercase'] and not re.search(r'[A-Z]', password):
            errors.append("Password must contain at least one uppercase letter")
        
        # Check lowercase
        if self.policy['require_lowercase'] and not re.search(r'[a-z]', password):
            errors.append("Password must contain at least one lowercase letter")
        
        # Check digits
        if self.policy['require_digits'] and not re.search(r'\d', password):
            errors.append("Password must contain at least one digit")
        
        # Check special characters
        if self.policy['require_special'] and not re.search(self.policy['special_chars'], password):
            errors.append("Password must contain at least one special character")
        
        if errors:
            raise ValueError("; ".join(errors))
        
        return True
    
    def get_policy_description(self) -> str:
        """Get human-readable password policy description."""
        desc = [f"At least {self.policy['min_length']} characters"]
        
        if self.policy['require_uppercase']:
            desc.append("at least one uppercase letter")
        if self.policy['require_lowercase']:
            desc.append("at least one lowercase letter")
        if self.policy['require_digits']:
            desc.append("at least one digit")
        if self.policy['require_special']:
            desc.append("at least one special character")
        
        return "Password must contain: " + ", ".join(desc) + "."


# Global password validator instance
password_validator = PasswordValidator()


def verify_password_strength(password: str) -> bool:
    """
    Verify that password meets security strength requirements.
    
    Uses centralized password validator for consistency across the application.
    
    Args:
        password (str): Password string to validate.
        
    Returns:
        bool: True if password meets all requirements.
        
    Raises:
        ValueError: If password doesn't meet any of the requirements,
            with specific message indicating what's missing.
    """
    return password_validator.validate(password)


def get_password_policy_description() -> str:
    """Get password policy description for user feedback."""
    return password_validator.get_policy_description()


def validate_environment() -> None:
    """
    Validate that all required environment variables are present.
    
    Raises:
        ValueError: If any required environment variables are missing.
    """
    required_vars = [
        "AWS_REGION",
        "COGNITO_USER_POOL_ID", 
        "COGNITO_CLIENT_ID"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var) or os.getenv(var).strip() == ""]
    
    if missing_vars:
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    
    logger.info("Environment validation passed")


class ThreadSafeJWKSClient:
    """Thread-safe client for fetching and caching AWS Cognito public keys."""
    
    def __init__(self):
        self._public_keys = None
        self._keys_last_updated = None
        self._lock = threading.Lock()
        self._cache_duration = timedelta(hours=24)
    
    def get_cognito_public_keys(self) -> Dict[str, Any]:
        """
        Fetch and cache Cognito public keys from JWKS endpoint.
        
        Keys are cached for 24 hours to reduce API calls and improve performance.
        Thread-safe implementation prevents race conditions.
        
        Returns:
            Dict[str, Any]: Dictionary mapping key IDs to their public key data.
            
        Raises:
            HTTPException: If unable to fetch public keys from Cognito.
        """
        with self._lock:
            # Check if cached keys are still valid
            if self._public_keys and self._keys_last_updated:
                if datetime.now() - self._keys_last_updated < self._cache_duration:
                    return self._public_keys
            
            # Fetch new keys
            try:
                jwks_url = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}/.well-known/jwks.json"
                response = requests.get(jwks_url, timeout=10)
                response.raise_for_status()
                
                keys = response.json()["keys"]
                self._public_keys = {key["kid"]: key for key in keys}
                self._keys_last_updated = datetime.now()
                
                logger.info("Successfully fetched and cached Cognito public keys")
                return self._public_keys
                
            except Exception as e:
                logger.error(f"Failed to fetch Cognito public keys: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to fetch authentication keys"
                )


# Global JWKS client instance
jwks_client = ThreadSafeJWKSClient()


def decode_cognito_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """
    Decode and validate AWS Cognito JWT token with signature verification.
    
    This function performs comprehensive token validation including:
    - Signature verification using Cognito public keys
    - Token type validation (access vs id)
    - Issuer verification
    - Audience verification (for ID tokens)
    
    Args:
        token (str): JWT token string to decode and validate.
        token_type (str, optional): Type of token - 'access' or 'id'. Defaults to "access".
    
    Returns:
        Dict[str, Any]: Decoded and validated token payload containing user claims.
        
    Raises:
        HTTPException: 
            - 401 if token is invalid, expired, or fails validation
            - 500 if unable to fetch public keys for verification
    """
    try:
        # Decode header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        kid = unverified_header.get("kid")
        
        if not kid:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: missing key ID"
            )
        
        # Get public keys for verification
        public_keys = jwks_client.get_cognito_public_keys()
        
        if kid not in public_keys:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: key not found"
            )
        
        # Get the public key for this token
        public_key = public_keys[kid]
        
        # Construct the public key for verification
        key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(public_key))
        
        # Decode and verify token
        payload = jwt.decode(
            token,
            key,
            algorithms=[JWT_ALGORITHM],
            audience=COGNITO_CLIENT_ID if token_type == "id" else None,
            options={"verify_aud": token_type == "id"}
        )
        
        # Additional validation for token type
        if token_type == "access":
            if payload.get("token_use", "").lower() != "access":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: wrong token type"
                )
        elif token_type == "id":
            if payload.get("token_use", "").lower() != "id":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid token: wrong token type"
                )
        
        # Verify issuer
        expected_iss = f"https://cognito-idp.{COGNITO_REGION}.amazonaws.com/{COGNITO_USER_POOL_ID}"
        if payload.get("iss") != expected_iss:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token: wrong issuer"
            )
        
        return payload
        
    except JWTError as e:
        logger.error(f"JWT decode error: {type(e).__name__}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    except Exception as e:
        logger.exception("Token validation error")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token validation failed"
        )


def sanitize_email(email: str) -> str:
    """
    Sanitize email input to prevent injection attacks.
    
    Args:
        email (str): Raw email input.
        
    Returns:
        str: Sanitized email.
    """
    if not email:
        return ""

    email = email.strip().lower()
    
    # Remove all non-printable ASCII characters
    email = re.sub(r'[^\x20-\x7E]', '', email)
    
    return email


def hash_email_for_logging(email: str) -> str:
    """
    Create a hash of email for logging purposes while maintaining privacy.
    
    Args:
        email (str): Email to hash.
        
    Returns:
        str: Hash suitable for logging (e.g., "user_1234").
    """
    if not email:
        return "unknown"
    
    return f"user_{hash(email) % 10000}"
