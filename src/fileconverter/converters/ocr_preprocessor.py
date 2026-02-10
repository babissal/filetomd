"""OCR image preprocessing pipeline to improve text extraction accuracy."""

from PIL import Image, ImageFilter

# Tunable constants
MIN_WIDTH_FOR_UPSCALE = 1000
UPSCALE_FACTOR = 2
DENOISE_STRENGTH = 10
CLAHE_CLIP_LIMIT = 2.0
CLAHE_TILE_SIZE = 8
ADAPTIVE_BLOCK_SIZE = 11
ADAPTIVE_C = 2
MIN_DESKEW_ANGLE = 0.5
MAX_DESKEW_ANGLE = 15.0
SHARPEN_RADIUS = 2
SHARPEN_PERCENT = 150
SHARPEN_THRESHOLD = 3


def preprocess_for_ocr(image: Image.Image) -> Image.Image:
    """Apply preprocessing pipeline to improve OCR accuracy.

    Pipeline: grayscale -> upscale -> denoise -> CLAHE -> binarize -> deskew -> sharpen.
    Falls back to Pillow-only pipeline if OpenCV is unavailable.

    Args:
        image: Input PIL Image (any mode).

    Returns:
        Preprocessed PIL Image (grayscale).
    """
    try:
        import cv2  # noqa: F401
    except ImportError:
        return _preprocess_pillow_only(image)

    # Grayscale
    img = image.convert("L")

    # Upscale small images
    img = _upscale_if_small(img)

    # OpenCV steps (operate on numpy arrays)
    import numpy as np
    arr = np.array(img)

    arr = _denoise(arr)
    arr = _apply_clahe(arr)
    arr = _binarize(arr)
    arr = _deskew(arr)

    # Back to PIL for sharpening
    img = Image.fromarray(arr)
    img = _sharpen(img)

    return img


def _preprocess_pillow_only(image: Image.Image) -> Image.Image:
    """Fallback pipeline using only Pillow (no OpenCV).

    Pipeline: grayscale -> upscale -> contrast -> sharpen.
    """
    from PIL import ImageEnhance

    img = image.convert("L")
    img = _upscale_if_small(img)

    # Boost contrast
    enhancer = ImageEnhance.Contrast(img)
    img = enhancer.enhance(2.0)

    img = _sharpen(img)
    return img


def _upscale_if_small(image: Image.Image) -> Image.Image:
    """Upscale image by UPSCALE_FACTOR if width is below MIN_WIDTH_FOR_UPSCALE."""
    if image.width < MIN_WIDTH_FOR_UPSCALE:
        new_size = (image.width * UPSCALE_FACTOR, image.height * UPSCALE_FACTOR)
        return image.resize(new_size, Image.LANCZOS)
    return image


def _denoise(arr):
    """Apply non-local means denoising."""
    import cv2
    return cv2.fastNlMeansDenoising(arr, None, DENOISE_STRENGTH)


def _apply_clahe(arr):
    """Apply Contrast Limited Adaptive Histogram Equalization."""
    import cv2
    clahe = cv2.createCLAHE(
        clipLimit=CLAHE_CLIP_LIMIT,
        tileGridSize=(CLAHE_TILE_SIZE, CLAHE_TILE_SIZE),
    )
    return clahe.apply(arr)


def _binarize(arr):
    """Apply adaptive thresholding for binarization."""
    import cv2
    return cv2.adaptiveThreshold(
        arr, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, ADAPTIVE_BLOCK_SIZE, ADAPTIVE_C,
    )


def _deskew(arr):
    """Correct skew using minAreaRect on contours.

    Only applies corrections between MIN_DESKEW_ANGLE and MAX_DESKEW_ANGLE degrees.
    """
    import cv2
    import numpy as np

    # Find contours on inverted image (text = white)
    inverted = cv2.bitwise_not(arr)
    coords = np.column_stack(np.where(inverted > 0))

    if len(coords) < 10:
        return arr

    rect = cv2.minAreaRect(coords)
    angle = rect[2]

    # minAreaRect returns angles in [-90, 0); adjust to get skew
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    # Only correct if within bounds
    if abs(angle) < MIN_DESKEW_ANGLE or abs(angle) > MAX_DESKEW_ANGLE:
        return arr

    h, w = arr.shape
    center = (w // 2, h // 2)
    rotation_matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    rotated = cv2.warpAffine(
        arr, rotation_matrix, (w, h),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )
    return rotated


def _sharpen(image: Image.Image) -> Image.Image:
    """Apply unsharp mask sharpening."""
    return image.filter(
        ImageFilter.UnsharpMask(
            radius=SHARPEN_RADIUS,
            percent=SHARPEN_PERCENT,
            threshold=SHARPEN_THRESHOLD,
        )
    )
