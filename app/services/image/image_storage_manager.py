"""
Image Storage Manager
Handles S3 uploads, pre-signed URL generation, and metadata management
"""

import boto3
import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Optional, Tuple
from io import BytesIO
from PIL import Image
import hashlib
import logging

logger = logging.getLogger(__name__)


class ImageStorageManager:
    """Manages image storage in S3 and secure retrieval"""
    
    def __init__(
        self,
        s3_bucket: str,
        s3_region: str = "us-east-2",
        url_expiration_seconds: int = 3600,
        max_thumbnail_size: Tuple[int, int] = (400, 400),
        thumbnail_quality: int = 85
    ):
        """
        Initialize storage manager
        
        Args:
            s3_bucket: S3 bucket name for storing thumbnails
            s3_region: AWS region
            url_expiration_seconds: How long pre-signed URLs remain valid
            max_thumbnail_size: Max dimensions for thumbnails (width, height)
            thumbnail_quality: JPEG quality for thumbnails (1-100)
        """
        self.s3_bucket = s3_bucket
        self.s3_region = s3_region
        self.url_expiration = url_expiration_seconds
        self.max_thumbnail_size = max_thumbnail_size
        self.thumbnail_quality = thumbnail_quality
        
        # Initialize AWS clients
        self.s3_client = boto3.client(
            's3',
            config=boto3.session.Config(
                signature_version="s3v4",
                region_name=s3_region,
            )
        )
        
    def _generate_image_key(
        self,
        user_id: str,
        session_id: str,
        file_extension: str = "jpg"
    ) -> str:
        """
        Generate unique S3 key for image
        
        Format: {user_id}/{session_id}/{timestamp}-{uuid}.{ext}
        """
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"{user_id}/{session_id}/{timestamp}-{unique_id}.{file_extension}"
    
    def _resize_image(self, image_bytes: bytes, max_size: Tuple[int, int]) -> bytes:
        """
        Resize image maintaining aspect ratio
        
        Args:
            image_bytes: Original image bytes
            max_size: Maximum (width, height)
            
        Returns:
            Resized image bytes
        """
        img = Image.open(BytesIO(image_bytes))
        
        # Convert RGBA to RGB if necessary
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Resize maintaining aspect ratio
        img.thumbnail(max_size, Image.Resampling.LANCZOS)
        
        # Save to bytes
        output = BytesIO()
        img.save(output, format='JPEG', quality=self.thumbnail_quality, optimize=True)
        output.seek(0)
        
        return output.read()
    
    def _calculate_content_hash(self, content: bytes) -> str:
        """Calculate SHA256 hash of content for integrity"""
        return hashlib.sha256(content).hexdigest()
    
    def upload_thumbnail(
        self,
        image_bytes: bytes,
        user_id: str,
        session_id: str,
        original_filename: Optional[str] = None,
        mime_type: str = "image/jpeg"
    ) -> Dict[str, any]:
        """
        Upload thumbnail to S3 and return metadata
        
        Args:
            image_bytes: Original image bytes
            user_id: User identifier
            session_id: Session/conversation identifier
            original_filename: Original filename (optional)
            mime_type: MIME type
            
        Returns:
            Dictionary with:
            - s3_key: S3 object key
            - s3_bucket: Bucket name
            - content_hash: SHA256 hash
            - size_bytes: File size
            - upload_timestamp: ISO format timestamp
            - original_filename: Original filename if provided
            - mime_type: Content type
        """
        # Resize image to thumbnail
        logger.info("upploading thumbnail")
        thumbnail_bytes = self._resize_image(image_bytes, self.max_thumbnail_size)
        
        # Generate unique key
        file_ext = mime_type.split('/')[-1] if '/' in mime_type else 'jpg'
        s3_key = self._generate_image_key(user_id, session_id, file_ext)
        
        # Calculate hash for integrity
        content_hash = self._calculate_content_hash(thumbnail_bytes)
        
        # Upload to S3
        self.s3_client.put_object(
            Bucket=self.s3_bucket,
            Key=s3_key,
            Body=thumbnail_bytes,
            ContentType=mime_type,
            Metadata={
                'original-filename': original_filename or 'unknown',
                'user-id': user_id,
                'session-id': session_id,
                'content-hash': content_hash
            },
            # Security settings
            ServerSideEncryption='AES256',
            # Prevent public access
            ACL='private'
        )
        logger.info("finished upploading thumbnail")
        # Return metadata for DynamoDB
        return {
            's3_key': s3_key,
            's3_bucket': self.s3_bucket,
            's3_region': self.s3_region,
            'content_hash': content_hash,
            'size_bytes': len(thumbnail_bytes),
            'upload_timestamp': datetime.utcnow().isoformat(),
            'original_filename': original_filename,
            'mime_type': mime_type
        }
    
    def generate_presigned_url(
        self,
        s3_key: str,
        expiration: Optional[int] = None
    ) -> str:
        """
        Generate secure pre-signed URL for image retrieval
        
        Args:
            s3_key: S3 object key
            expiration: URL expiration in seconds (overrides default)
            
        Returns:
            Pre-signed URL string
        """
        expiration = expiration or self.url_expiration
        
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': self.s3_bucket,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            return url
        except Exception:
            logger.exception("Failed to generate pre-signed URL for key '%s' in bucket '%s'.", s3_key, self.s3_bucket)
            return ""
    
    def get_image_metadata(self, s3_key: str) -> Dict[str, any]:
        """
        Retrieve image metadata from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            Metadata dictionary
        """
        try:
            response = self.s3_client.head_object(
                Bucket=self.s3_bucket,
                Key=s3_key
            )
            
            return {
                'content_type': response.get('ContentType'),
                'content_length': response.get('ContentLength'),
                'last_modified': response.get('LastModified').isoformat(),
                'metadata': response.get('Metadata', {})
            }
        except Exception:
            logger.exception("Failed to retrieve metadata for key '%s' in bucket '%s'.", s3_key, self.s3_bucket)
            return {}
    
    def delete_image(self, s3_key: str) -> bool:
        """
        Delete image from S3
        
        Args:
            s3_key: S3 object key
            
        Returns:
            True if successful
        """
        try:
            self.s3_client.delete_object(
                Bucket=self.s3_bucket,
                Key=s3_key
            )
            return True
        except Exception:
            logger.exception("Failed to delete image with key '%s' from bucket '%s'.", s3_key, self.s3_bucket)
            return False
    
    def enrich_history_with_urls(
        self,
        messages: list,
        image_key_field: str = 's3_key'
    ) -> list:
        """
        Add pre-signed URLs to messages containing images
        
        Args:
            messages: List of message dictionaries from DynamoDB
            image_key_field: Field name containing S3 key
            
        Returns:
            Messages with added 'image_url' field
        """
        enriched_messages = []
        
        for msg in messages:
            enriched_msg = msg.copy()
            
            # If message has an image, generate fresh URL
            if image_key_field in msg and msg[image_key_field]:
                try:
                    enriched_msg['image_url'] = self.generate_presigned_url(
                        msg[image_key_field]
                    )
                    enriched_msg['image_url_expires_at'] = (
                        datetime.utcnow() + timedelta(seconds=self.url_expiration)
                    ).isoformat()
                except Exception as e:
                    # Handle missing or inaccessible images gracefully
                    enriched_msg['image_url'] = None
                    enriched_msg['image_error'] = str(e)
            
            enriched_messages.append(enriched_msg)
        
        return enriched_messages

