"""
Image validation service for Voyager-T800.

This module provides image validation functionality to ensure uploaded images
meet security and quality requirements before processing.

Validation checks:
- File type: jpg, jpeg, png, webp (by MIME type and magic bytes)
- File size: maximum 5 MB
- Resolution: maximum 4096×4096 pixels
- Image integrity: file can be opened and decoded

All validation errors are logged for debugging and raise HTTPException
with appropriate status codes and user-friendly messages.
"""

import io
import logging

from typing import Dict

from fastapi import HTTPException, UploadFile
from PIL import Image, UnidentifiedImageError

from app.config.config import settings


logger = logging.getLogger(__name__)


# Magic bytes for image format detection
MAGIC_BYTES = {
    'image/jpeg': [b'\xff\xd8\xff'],
    'image/png': [b'\x89\x50\x4e\x47\x0d\x0a\x1a\x0a'],
    'image/webp': [b'RIFF', b'WEBP'],
}


async def validate_image(file: UploadFile) -> Dict[str, any]:
    """
    Validate an uploaded image file.

    This function performs validation on an uploaded image:
    1. Checks file extension
    2. Checks MIME type (Content-Type header)
    3. Validates file size
    4. Verifies magic bytes (actual file content)
    5. Validates image can be opened and decoded
    6. Checks resolution limits

    Args:
        file: FastAPI UploadFile object containing the uploaded image

    Returns:
        dict: Image metadata including:
            - filename: Original filename
            - content_type: MIME type
            - size_bytes: File size in bytes
            - width: Image width in pixels
            - height: Image height in pixels

    Raises:
        HTTPException:
            - 400: Validation failed (wrong type, too large, invalid resolution)
            - 500: Unexpected processing error

    """
    try:
        # Step 1: Validate filename and extension
        filename = file.filename or 'unknown'
        if not filename or filename == 'unknown':
            logger.warning('Image uploaded without filename')
            raise HTTPException(status_code=400, detail='Image filename is required.')

        # Get allowed types from config
        allowed_extensions = {f'.{ext}' for ext in settings.image_allowed_types}
        allowed_content_types = {f'image/{ext}' for ext in settings.image_allowed_types}
        # Handle jpg/jpeg mapping
        if 'jpg' in settings.image_allowed_types:
            allowed_content_types.add('image/jpg')
        
        file_extension = None
        if '.' in filename:
            file_extension = '.' + filename.rsplit('.', 1)[1].lower()

        if file_extension not in allowed_extensions:
            logger.warning(f'Invalid file extension: {file_extension} for file {filename}')
            raise HTTPException(
                status_code=400,
                detail=f'Invalid file type. Allowed types: {", ".join(settings.image_allowed_types)}',
            )

        # Step 2: Validate MIME type from Content-Type header
        content_type = file.content_type
        if content_type not in allowed_content_types:
            logger.warning(f'Invalid content type: {content_type} for file {filename}')
            raise HTTPException(
                status_code=400,
                detail=f'Invalid content type "{content_type}". Allowed types: {", ".join(settings.image_allowed_types)}',
            )

        # Step 3: Read file content into memory
        # Note: For very large files, consider streaming validation
        file_content = await file.read()
        file_size = len(file_content)

        # Validate file size
        max_size_bytes = settings.image_max_size_mb * 1024 * 1024
        if file_size > max_size_bytes:
            size_mb = file_size / (1024 * 1024)
            logger.warning(f'File too large: {size_mb:.2f} MB for file {filename}')
            raise HTTPException(
                status_code=400,
                detail=f'Image size {size_mb:.2f} MB exceeds maximum allowed {settings.image_max_size_mb} MB',
            )

        if file_size == 0:
            logger.warning(f'Empty file uploaded: {filename}')
            raise HTTPException(status_code=400, detail='Uploaded file is empty.')

        # Step 4: Validate magic bytes (actual file content)
        magic_bytes_valid = _validate_magic_bytes(file_content, content_type)
        if not magic_bytes_valid:
            logger.warning(f'Magic bytes validation failed for {filename} (claimed type: {content_type})')
            raise HTTPException(
                status_code=400,
                detail='File content does not match declared type. Possible file corruption or spoofing.',
            )

        # Step 5: Validate image can be opened and get dimensions
        try:
            image = Image.open(io.BytesIO(file_content))
            width, height = image.size
            image_format = image.format  # PIL detected format

            logger.info(f'Image opened successfully: {filename} ({width}x{height}, format: {image_format})')

        except UnidentifiedImageError:
            logger.warning(f'Cannot identify image format for {filename}')
            raise HTTPException(status_code=400, detail='Invalid or corrupted image file.')
        except Exception as e:
            logger.error(f'Error opening image {filename}: {str(e)}')
            raise HTTPException(status_code=400, detail='Cannot process image. File may be corrupted.')

        # Step 6: Validate resolution
        if width > settings.image_max_resolution or height > settings.image_max_resolution:
            logger.warning(f'Resolution too high: {width}x{height} for file {filename}')
            raise HTTPException(
                status_code=400,
                detail=f'Image resolution {width}x{height} exceeds maximum allowed {settings.image_max_resolution}x{settings.image_max_resolution}',
            )

        # Step 7: Reset file pointer for potential future reads
        await file.seek(0)

        # All validation passed - return metadata
        logger.info(
            f'Image validation successful: {filename} '
            f'({width}x{height}, {file_size} bytes, {content_type})'
        )

        return {
            'filename': filename,
            'content_type': content_type,
            'size_bytes': file_size,
            'width': width,
            'height': height,
        }

    except HTTPException:
        # Re-raise validation errors
        raise
    except Exception as e:
        # Catch any unexpected errors
        logger.error(f'Unexpected error during image validation: {str(e)}', exc_info=True)
        raise HTTPException(status_code=500, detail='An unexpected error occurred during image validation.')


def _validate_magic_bytes(file_content: bytes, content_type: str) -> bool:
    """
    Validate file magic bytes match the declared content type.

    This prevents file type spoofing by checking the actual file content
    against known magic byte signatures.

    Args:
        file_content: Raw file bytes
        content_type: Declared MIME type

    Returns:
        bool: True if magic bytes match content type, False otherwise
    """
    if content_type not in MAGIC_BYTES:
        logger.warning(f'No magic bytes defined for content type: {content_type}')
        return False

    magic_signatures = MAGIC_BYTES[content_type]

    # For WEBP, we need to check both RIFF and WEBP markers
    if content_type == 'image/webp':
        has_riff = file_content.startswith(b'RIFF')
        has_webp = b'WEBP' in file_content[:16]  # WEBP signature is within first 16 bytes
        return has_riff and has_webp

    # For other formats, check if file starts with any of the magic bytes
    for magic in magic_signatures:
        if file_content.startswith(magic):
            return True

    return False

