"""
AWS Secrets Manager integration for secure API key management.
Retrieves encrypted secrets at runtime - NO secrets in repository.
"""

import json
import logging
from typing import Dict, Optional
from functools import lru_cache

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class SecretsManager:
    """Manages retrieval of secrets from AWS Secrets Manager"""
    
    def __init__(self, region_name: str = "us-east-2"):
        self.client = boto3.client(
            service_name='secretsmanager',
            region_name=region_name
        )
    
    @lru_cache(maxsize=10)
    def get_secret(self, secret_name: str) -> Dict[str, str]:
        """
        Retrieve secret from AWS Secrets Manager.
        
        Cached to avoid repeated API calls. Cache invalidates on app restart.
        
        Args:
            secret_name: Name of the secret in Secrets Manager
            
        Returns:
            Dictionary of secret key-value pairs
            
        Raises:
            ClientError: If secret not found or access denied
        """
        try:
            logger.info(f"Retrieving secret: {secret_name}")
            
            response = self.client.get_secret_value(SecretId=secret_name)
            
            # Parse the secret string as JSON
            if 'SecretString' in response:
                secret_dict = json.loads(response['SecretString'])
                logger.info(f"Secret '{secret_name}' retrieved successfully")
                return secret_dict
            else:
                # Binary secrets not supported in this implementation
                raise ValueError(f"Secret '{secret_name}' is binary, not supported")
                
        except ClientError as e:
            error_code = e.response['Error']['Code']
            
            if error_code == 'ResourceNotFoundException':
                logger.error(f"Secret '{secret_name}' not found")
            elif error_code == 'InvalidRequestException':
                logger.error(f"Invalid request for secret '{secret_name}'")
            elif error_code == 'InvalidParameterException':
                logger.error(f"Invalid parameter for secret '{secret_name}'")
            elif error_code == 'DecryptionFailure':
                logger.error(f"Decryption failed for secret '{secret_name}'")
            elif error_code == 'InternalServiceError':
                logger.error(f"Internal service error retrieving secret '{secret_name}'")
            else:
                logger.error(f"Unknown error retrieving secret '{secret_name}': {error_code}")
            
            raise
    
    def get_api_key(self, secret_name: str, key_name: str) -> Optional[str]:
        """
        Retrieve specific API key from secret.
        
        Args:
            secret_name: Name of the secret in Secrets Manager
            key_name: Key name within the secret (e.g., 'OPENAI_API_KEY')
            
        Returns:
            API key string or None if not found
        """
        try:
            secret_dict = self.get_secret(secret_name)
            return secret_dict.get(key_name)
        except Exception as e:
            logger.error(f"Failed to retrieve API key '{key_name}' from '{secret_name}': {e}")
            return None


# Global instance
_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager(region_name: str = "us-east-2") -> SecretsManager:
    """Get or create global SecretsManager instance"""
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager(region_name=region_name)
    return _secrets_manager


def get_api_keys(secret_name: str = "voyager/api-keys") -> Dict[str, str]:
    """
    Convenience function to retrieve all API keys.
    
    Args:
        secret_name: Name of the secret containing API keys
        
    Returns:
        Dictionary with API keys:
        - OPENAI_API_KEY
        - ANTHROPIC_API_KEY
        - GROQ_API_KEY
        - GOOGLE_MAPS_API_KEY
        - OPENWEATHER_API_KEY
    """
    manager = get_secrets_manager()
    return manager.get_secret(secret_name)