# Image Handling Documentation

This document describes the image upload and validation system for Voyager-T800, including accepted formats, size limits, resolution constraints, and usage guidelines.

## Accepted Image Formats

### Supported File Types

| Format | Extensions | MIME Type | Description |
|--------|------------|-----------|-------------|
| **JPEG** | `.jpg`, `.jpeg` | `image/jpeg` | Standard compressed image format |
| **PNG** | `.png` | `image/png` | Lossless compressed format with transparency |
| **WebP** | `.webp` | `image/webp` | Modern format with superior compression |

### Format Validation

Images are validated using multiple methods for security:

1. **File Extension Check**: Verifies the file extension matches allowed types
2. **MIME Type Validation**: Checks the `Content-Type` header
3. **Magic Bytes Verification**: Validates actual file content against known signatures
4. **PIL Integrity Check**: Ensures the file can be opened and decoded as an image

## Size and Resolution Limits

### File Size Limits

- **Maximum Size**: 3.75 MB (3,932,160 bytes)
- **Minimum Size**: 1 byte (empty files are rejected)
- **Recommended**: Under 2 MB for optimal performance

### Resolution Limits

- **Maximum Dimensions**: 4096 × 4096 pixels
- **Minimum Dimensions**: 200 × 200 pixels (for UX quality)
- **Recommended**: 1920 × 1080 or smaller for faster processing

### Configuration

These limits are configurable via environment variables in `app/config/config.py`:

```python
# Image Upload & Validation Configuration
image_max_size_mb: int = Field(default=3.75)
image_max_resolution: int = Field(default=4096)
image_allowed_types: list[str] = Field(default=['jpg', 'jpeg', 'png', 'webp'])
```

## Validation Process

### Client-Side Validation (Frontend)

Performed in `app/frontend/chat_interface.py` before sending to backend:

1. **Extension Check**: Validates file extension against allowed types
2. **Size Check**: Ensures file size ≤ 3.75 MB
3. **Resolution Check**: Verifies dimensions ≤ 4096×4096 and ≥ 200×200
4. **PIL Validation**: Confirms file can be opened as an image

**Benefits**: Fast feedback, reduces unnecessary network calls

### Server-Side Validation (Backend)

Performed in `app/services/image_validation.py` for comprehensive security:

1. **MIME Type Validation**: Checks `Content-Type` header
2. **Magic Bytes Verification**: Prevents file type spoofing
3. **File Size Validation**: Server-side size verification
4. **Image Integrity**: PIL-based format and corruption detection
5. **Resolution Validation**: Server-side dimension checking

**Benefits**: Security, prevents malicious uploads, definitive validation

## API Endpoints

### Upload Image

**Endpoint**: `POST /api/v1/images/upload`

**Request**: Multipart form data with image file

**Response** (Success):
```json
{
  "image_id": "img_a1b2c3d4e5f6",
  "filename": "vacation.jpg",
  "content_type": "image/jpeg",
  "size_bytes": 2048000,
  "width": 1920,
  "height": 1080,
  "uploaded_at": "2025-01-15T10:30:00Z",
  "success": true
}
```

**Response** (Validation Error):
```json
{
  "detail": "Image size 4.00 MB exceeds maximum allowed 3.75 MB"
}
```

### Validate Image

**Endpoint**: `POST /api/v1/images/validate`

**Request**: Multipart form data with image file

**Response** (Valid):
```json
{
  "valid": true,
  "message": "Image is valid and meets all requirements",
  "metadata": {
    "filename": "test.jpg",
    "content_type": "image/jpeg",
    "size_bytes": 1024000,
    "width": 1024,
    "height": 768
  }
}
```

## Error Handling

### Common Validation Errors

| Error | Cause | Solution |
|-------|-------|----------|
| `Unsupported image file type` | Wrong file extension | Use .jpg, .jpeg, .png, or .webp |
| `Image is too large` | File exceeds 3.75 MB | Compress or resize image |
| `Image resolution exceeds 4096×4096` | Dimensions too high | Resize image to smaller dimensions |
| `Image is too small` | Dimensions below 200×200 | Use higher resolution image |
| `Invalid content type` | MIME type mismatch | Ensure file is actually an image |
| `File content does not match declared type` | Magic bytes don't match | File may be corrupted or spoofed |

### Error Response Format

All validation errors return HTTP 400 with descriptive messages:

```json
{
  "detail": "Human-readable error message"
}
```

## Security Considerations

### File Type Spoofing Prevention

- **Magic Bytes Validation**: Checks actual file content, not just extension
- **MIME Type Verification**: Validates Content-Type header
- **PIL Integrity Check**: Ensures file can be processed as intended format

### Size Limits

- **Prevents DoS**: Large file uploads can consume server resources
- **Performance**: Smaller files process faster
- **Storage**: Limits temporary storage requirements

### Resolution Limits

- **Memory Protection**: Prevents excessive memory usage during processing
- **Processing Time**: Large images take longer to analyze
- **Storage Efficiency**: Reasonable dimensions for travel planning context

## Troubleshooting

### Common Issues

**"Image validation failed" but file looks fine**:
- Check file size is under 3.75 MB
- Verify image dimensions are under 4096×4096
- Ensure file isn't corrupted

**"Unsupported file type" error**:
- Confirm file extension is .jpg, .jpeg, .png, or .webp
- Check file isn't renamed (e.g., .pdf renamed to .jpg)

**"File content does not match declared type"**:
- File may be corrupted
- Try re-saving the image in a supported format
- Verify the file is actually an image


## Changelog

### v1.0.0 (2025-10-01)
- Initial image validation system
- Support for JPEG, PNG, WebP formats
- 3.75 MB size limit, 4096×4096 resolution limit
- Client-side and server-side validation
- Comprehensive error handling
