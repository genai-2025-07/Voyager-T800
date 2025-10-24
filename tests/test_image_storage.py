"""
Unit tests for image storage with EXIF stripping.
Ensures GPS and metadata are removed before S3 upload.
"""

import pytest
from io import BytesIO
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from unittest.mock import Mock, patch, MagicMock

from src.voyager.services.image.storage_manager import ImageStorageManager


class TestImageStorageManager:
    """Test image storage with security features"""
    
    @pytest.fixture
    def storage_manager(self):
        """Create storage manager with mocked S3 client"""
        with patch('boto3.client'):
            manager = ImageStorageManager(
                s3_bucket="test-bucket",
                s3_region="us-east-2"
            )
            manager.s3_client = Mock()
            return manager
    
    def create_image_with_exif(self, include_gps=True):
        """Create test image with EXIF data including GPS"""
        from PIL import Image
        from PIL.ExifTags import TAGS
        from io import BytesIO
        
        img = Image.new('RGB', (100, 100), color='red')
        
        # Create EXIF data using Pillow's Exif class
        from PIL.Image import Exif
        exif = Exif()
        
        # Add basic EXIF tags
        exif[0x010F] = "Test Camera"  # Make
        exif[0x0110] = "Test Model"   # Model
        
        if include_gps:
            # Add GPS IFD with proper format (IFDRational)
            from PIL.TiffImagePlugin import IFDRational
            
            gps_ifd = {
                1: 'N',  # GPSLatitudeRef
                2: (IFDRational(40, 1), IFDRational(26, 1), IFDRational(46, 1)),  # GPSLatitude
                3: 'W',  # GPSLongitudeRef
                4: (IFDRational(79, 1), IFDRational(56, 1), IFDRational(55, 1)),  # GPSLongitude
            }
            exif[0x8825] = gps_ifd  # GPS IFD pointer
        
        # Save with EXIF
        output = BytesIO()
        img.save(output, format='JPEG', exif=exif)
        output.seek(0)
        return output.read()
    
    def test_exif_stripping_removes_metadata(self, storage_manager):
        """Test that EXIF data is completely removed"""
        # Create image with EXIF
        image_with_exif = self.create_image_with_exif(include_gps=True)
        
        # Strip EXIF
        stripped_bytes = storage_manager._strip_exif(image_with_exif)
        
        # Verify EXIF is gone
        img_stripped = Image.open(BytesIO(stripped_bytes))
        exif_data = img_stripped.getexif()
        
        # Should have no EXIF data
        assert len(exif_data) == 0 or all(
            tag not in exif_data for tag in [0x010F, 0x0110, 0x8825]
        )
    
    def test_exif_stripping_preserves_image_quality(self, storage_manager):
        """Test that image is not corrupted during EXIF stripping"""
        original_bytes = self.create_image_with_exif()
        
        stripped_bytes = storage_manager._strip_exif(original_bytes)
        
        # Should be able to open stripped image
        img = Image.open(BytesIO(stripped_bytes))
        assert img.size == (100, 100)
        assert img.mode == 'RGB'
    
    def test_upload_thumbnail_strips_exif(self, storage_manager):
        """Test that upload_thumbnail strips EXIF before upload"""
        image_with_exif = self.create_image_with_exif(include_gps=True)
        
        # Mock S3 upload
        storage_manager.s3_client.put_object = Mock()
        
        result = storage_manager.upload_thumbnail(
            image_bytes=image_with_exif,
            user_id="test_user",
            session_id="test_session"
        )
        
        # Verify upload was called
        assert storage_manager.s3_client.put_object.called
        
        # Verify metadata indicates EXIF was stripped
        assert result['exif_stripped'] is True
        
        # Verify S3 metadata includes exif-stripped flag
        call_kwargs = storage_manager.s3_client.put_object.call_args[1]
        assert call_kwargs['Metadata']['exif-stripped'] == 'true'
    
    def test_upload_sets_private_acl(self, storage_manager):
        """Test that uploaded images are private"""
        image_bytes = self.create_image_with_exif()
        storage_manager.s3_client.put_object = Mock()
        
        storage_manager.upload_thumbnail(
            image_bytes=image_bytes,
            user_id="test_user",
            session_id="test_session"
        )
        
        call_kwargs = storage_manager.s3_client.put_object.call_args[1]
        assert call_kwargs['ACL'] == 'private'
        assert call_kwargs['ServerSideEncryption'] == 'AES256'
    
    def test_presigned_url_generation(self, storage_manager):
        """Test presigned URL generation"""
        test_key = "user/session/test.jpg"
        expected_url = "https://s3.amazonaws.com/presigned-url"
        
        storage_manager.s3_client.generate_presigned_url = Mock(
            return_value=expected_url
        )
        
        url = storage_manager.generate_presigned_url(test_key, expiration=3600)
        
        assert url == expected_url
        storage_manager.s3_client.generate_presigned_url.assert_called_once()
        
        call_kwargs = storage_manager.s3_client.generate_presigned_url.call_args[1]
        assert call_kwargs['Params']['Key'] == test_key
        assert call_kwargs['ExpiresIn'] == 3600