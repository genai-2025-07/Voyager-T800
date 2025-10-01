"""
Image upload and validation endpoints.
"""

import logging
import uuid

from datetime import UTC, datetime

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.image_validation import validate_image


logger = logging.getLogger(__name__)
router = APIRouter(prefix='/images', tags=['images'])


class ImageUploadResponse(BaseModel):
    """Response model for successful image upload."""

    image_id: str
    filename: str
    content_type: str
    size_bytes: int
    width: int
    height: int
    uploaded_at: str
    success: bool = True


class ImageValidationError(BaseModel):
    """Response model for image validation errors."""

    error: str
    detail: str
    success: bool = False


@router.post('/upload', response_model=ImageUploadResponse)
async def upload_image(file: UploadFile = File(...)):
    """
    Upload and validate an image file.

    This endpoint validates the uploaded image for:
    - File type (jpg, jpeg, png, webp)
    - File size (max 5 MB)
    - Resolution (max 4096×4096 px)

    Args:
        file: The uploaded image file

    Returns:
        ImageUploadResponse with image metadata

    Raises:
        HTTPException: If validation fails (400) or processing error occurs (500)

    """
    try:
        logger.info(f'Received image upload request: {file.filename}')

        # Validate the image using the validation service
        validation_result = await validate_image(file)

        # Generate unique image ID
        image_id = f'img_{uuid.uuid4().hex}'

        # Prepare response with image metadata
        response = ImageUploadResponse(
            image_id=image_id,
            filename=validation_result['filename'],
            content_type=validation_result['content_type'],
            size_bytes=validation_result['size_bytes'],
            width=validation_result['width'],
            height=validation_result['height'],
            uploaded_at=datetime.now(UTC).isoformat(),
        )

        logger.info(
            f'Image uploaded successfully: {image_id} '
            f'({validation_result["width"]}x{validation_result["height"]}, '
            f'{validation_result["size_bytes"]} bytes)'
        )

        return response

    except HTTPException:
        # Re-raise validation errors from the service layer
        raise
    except Exception as e:
        logger.error(f'Unexpected error during image upload: {str(e)}', exc_info=True)
        raise HTTPException(status_code=500, detail='Failed to process image upload. Please try again.')


@router.post('/validate')
async def validate_image_endpoint(file: UploadFile = File(...)):
    """
    Validate an image without storing it.

    This endpoint is useful for pre-flight validation before uploading.
    It performs the same checks as /upload but doesn't persist the image.

    Args:
        file: The image file to validate

    Returns:
        dict: Validation result with image metadata

    Raises:
        HTTPException: If validation fails (400)

    """
    try:
        logger.info(f'Received image validation request: {file.filename}')

        # Validate the image
        validation_result = await validate_image(file)

        logger.info(
            f'Image validation successful: {file.filename} '
            f'({validation_result["width"]}x{validation_result["height"]})'
        )

        return {
            'valid': True,
            'message': 'Image is valid and meets all requirements',
            'metadata': validation_result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Unexpected error during image validation: {str(e)}', exc_info=True)
        raise HTTPException(status_code=500, detail='Failed to validate image. Please try again.')

