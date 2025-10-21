"""
Image processing utilities for resizing images before passing to agent.
"""
from io import BytesIO
from PIL import Image
from typing import Tuple, Optional
import logging

logger = logging.getLogger(__name__)

# map common content-types to PIL formats
_CONTENTTYPE_TO_PIL = {
    'image/jpeg': 'JPEG',
    'image/jpg': 'JPEG',
    'image/png': 'PNG',
    'image/webp': 'WEBP',
    'image/gif': 'GIF',
}

# reverse map from PIL format to content-type
_PIL_TO_CONTENTTYPE = {
    'JPEG': 'image/jpeg',
    'PNG': 'image/png',
    'WEBP': 'image/webp',
    'GIF': 'image/gif',
}


def _infer_media_type(content_type: Optional[str], pil_format: Optional[str]) -> str:
    if content_type and content_type in _CONTENTTYPE_TO_PIL:
        return content_type
    if pil_format and pil_format in _PIL_TO_CONTENTTYPE:
        return _PIL_TO_CONTENTTYPE[pil_format]
    return 'image/jpeg'


def resize_image_for_agent(
    image_bytes: bytes,
    content_type: Optional[str] = None,
    max_size: Tuple[int, int] = (1024, 1024),
    quality: int = 90
) -> Tuple[bytes, str]:
    """
    Resize image to standardized size for agent processing, but only if the image
    exceeds max_size (width or height). If the image is already within limits,
    the original bytes are returned unchanged.

    Args:
        image_bytes: Original image bytes
        content_type: MIME type of the image (optional)
        max_size: Maximum dimensions (width, height)
        quality: JPEG quality (1-100)

    Returns:
        Tuple of (resized_image_bytes, media_type)
    """
    try:
        with Image.open(BytesIO(image_bytes)) as img:
            # Force load to access size and format reliably
            img.load()
            orig_format = img.format  # e.g., 'JPEG', 'PNG', etc.
            max_w, max_h = max_size

            # If image already within size limits, return original bytes
            if img.width <= max_w and img.height <= max_h:
                media_type = _infer_media_type(content_type, orig_format)
                logger.debug("Image within max_size (%dx%d). Skipping resize.", max_w, max_h)
                # Optionally: you could still recompress if file bytes are huge
                return image_bytes, media_type

            # Need to resize
            logger.debug(
                "Resizing image from (%d x %d) to fit within (%d x %d).",
                img.width, img.height, max_w, max_h
            )

            # Determine target format
            if content_type and content_type in _CONTENTTYPE_TO_PIL:
                target_format = _CONTENTTYPE_TO_PIL[content_type]
            else:
                target_format = orig_format or 'JPEG'

            # Convert if saving to JPEG (no alpha allowed)
            has_alpha = img.mode in ('RGBA', 'LA') or (img.mode == 'P' and 'transparency' in img.info)
            if target_format == 'JPEG' and has_alpha:
                # convert to RGB (loses alpha) since JPEG doesn't support it
                img = img.convert('RGB')
            elif img.mode == 'RGBA' and target_format in ('PNG', 'WEBP'):
                # keep alpha; Pillow will save alpha correctly for PNG/WEBP
                pass
            elif img.mode == 'P' and target_format in ('PNG', 'WEBP'):
                # palletized images: convert to RGBA if transparency exists else to RGB
                if 'transparency' in img.info:
                    img = img.convert('RGBA')
                else:
                    img = img.convert('RGB')

            # Resize maintaining aspect ratio with high-quality resampling
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

            # Save to bytes
            output = BytesIO()
            save_kwargs = {}
            if target_format == 'JPEG':
                save_kwargs['quality'] = quality
                save_kwargs['optimize'] = True
                img.save(output, format='JPEG', **save_kwargs)
            elif target_format == 'WEBP':
                # webp can accept quality param too
                save_kwargs['quality'] = quality
                img.save(output, format='WEBP', **save_kwargs)
            else:
                img.save(output, format=target_format)

            output.seek(0)
            media_type = _infer_media_type(content_type, target_format)
            return output.read(), media_type

    except Exception as e:
        logger.exception("Failed to resize image, returning original bytes. Error: %s", e)
        return image_bytes, content_type or 'image/jpeg'
