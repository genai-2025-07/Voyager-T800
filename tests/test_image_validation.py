import io
import math
from unittest.mock import Mock

import pytest

from fastapi import HTTPException, UploadFile
from PIL import Image

from app.services.image_validation import validate_image
from app.config.config import settings


def _create_image_bytes(width: int, height: int, fmt: str = 'JPEG', color: tuple[int, int, int] = (200, 200, 200)) -> bytes:
    """Create an in-memory image and return its bytes in the given format."""
    img = Image.new('RGB', (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format=fmt)
    return buf.getvalue()


def _make_upload_file(data: bytes, filename: str, content_type: str) -> UploadFile:
    """Wrap raw bytes in an UploadFile-like object for testing."""
    file_obj = io.BytesIO(data)
    
    # Create a mock UploadFile with proper content_type handling
    upload = Mock(spec=UploadFile)
    upload.filename = filename
    upload.file = file_obj
    upload.content_type = content_type
    
    # Mock the read method to support chunked reading
    async def mock_read(size=-1):
        if size == -1:
            # If no size specified, return all data (for backward compatibility)
            return data
        else:
            # For chunked reading, return the requested chunk size
            chunk = file_obj.read(size)
            return chunk
    
    upload.read = mock_read
    
    # Mock the seek method
    async def mock_seek(position):
        file_obj.seek(position)
    
    upload.seek = mock_seek
    
    return upload


@pytest.mark.asyncio
async def test_validate_image_success_jpeg_small():
    # Arrange: small valid JPEG under limits
    data = _create_image_bytes(800, 600, fmt='JPEG')
    upload = _make_upload_file(data, filename='photo.jpg', content_type='image/jpeg')

    result = await validate_image(upload)

    assert result['filename'] == 'photo.jpg'
    assert result['content_type'] == 'image/jpeg'
    assert result['width'] == 800 and result['height'] == 600
    assert 0 < result['size_bytes'] < settings.image_max_size_mb * 1024 * 1024


@pytest.mark.asyncio
async def test_validate_image_wrong_type_extension():
    # Arrange: correct bytes for PNG but wrong extension and content type (pdf)
    data = _create_image_bytes(400, 300, fmt='PNG')
    upload = _make_upload_file(data, filename='document.pdf', content_type='application/pdf')

    with pytest.raises(HTTPException) as exc:
        await validate_image(upload)
    assert exc.value.status_code == 400
    assert 'Invalid file type' in str(exc.value.detail) or 'Invalid content type' in str(exc.value.detail)


@pytest.mark.asyncio
async def test_validate_image_too_large_size():
    # Arrange: Create arbitrary bytes exceeding configured size limit
    too_large_bytes = b'x' * (int(settings.image_max_size_mb * 1024 * 1024) + 10)
    upload = _make_upload_file(too_large_bytes, filename='big.jpg', content_type='image/jpeg')

    with pytest.raises(HTTPException) as exc:
        await validate_image(upload)
    assert exc.value.status_code == 400
    assert 'exceeds maximum allowed' in str(exc.value.detail)


@pytest.mark.asyncio
async def test_validate_image_too_high_resolution():
    # Arrange: dimensions exceed configured maximum resolution
    data = _create_image_bytes(settings.image_max_resolution + 100, settings.image_max_resolution + 100, fmt='JPEG')
    upload = _make_upload_file(data, filename='huge.jpg', content_type='image/jpeg')

    with pytest.raises(HTTPException) as exc:
        await validate_image(upload)
    assert exc.value.status_code == 400
    assert 'resolution' in str(exc.value.detail)


@pytest.mark.asyncio
async def test_validate_image_corrupted():
    # Arrange: bytes that are not an image but with image extension/MIME
    data = b'not-an-image' * 100
    upload = _make_upload_file(data, filename='fake.jpg', content_type='image/jpeg')

    with pytest.raises(HTTPException) as exc:
        await validate_image(upload)
    assert exc.value.status_code == 400
    assert 'File content does not match declared type' in str(exc.value.detail)


