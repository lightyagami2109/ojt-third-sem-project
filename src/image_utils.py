"""Image processing utilities: hashing, perceptual hashing, rendition generation."""
import hashlib
from io import BytesIO
from PIL import Image
from typing import Tuple, Optional
from src.settings import settings


def compute_content_hash(data: bytes) -> str:
    """Compute SHA256 hash of image data (for idempotency)."""
    return hashlib.sha256(data).hexdigest()


def compute_phash(image: Image.Image, hash_size: int = None) -> str:
    """
    Compute perceptual hash (aHash) of an image.
    
    aHash (Average Hash):
    1. Resize image to hash_size x hash_size
    2. Convert to grayscale
    3. Compute average pixel value
    4. Create hash: 1 if pixel > average, 0 otherwise
    5. Return as hex string
    
    Args:
        image: PIL Image object
        hash_size: Size for hash computation (default from settings)
        
    Returns:
        Hex string of perceptual hash
    """
    if hash_size is None:
        hash_size = settings.PHASH_SIZE
    
    # Resize and convert to grayscale
    img = image.resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    img = img.convert("L")  # Grayscale
    
    # Compute average pixel value
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    
    # Create hash bits
    bits = []
    for pixel in pixels:
        bits.append(1 if pixel > avg else 0)
    
    # Convert bits to integer, then to hex
    hash_int = 0
    for bit in bits:
        hash_int = (hash_int << 1) | bit
    
    # Return as hex string (pad to ensure consistent length)
    return format(hash_int, f"0{hash_size * hash_size // 4}x")


def hamming_distance(hash1: str, hash2: str) -> int:
    """
    Compute Hamming distance between two perceptual hashes.
    
    Args:
        hash1: Hex string of first hash
        hash2: Hex string of second hash
        
    Returns:
        Hamming distance (number of differing bits)
    """
    # Convert hex strings to integers
    int1 = int(hash1, 16)
    int2 = int(hash2, 16)
    
    # XOR and count set bits
    xor = int1 ^ int2
    distance = bin(xor).count("1")
    
    return distance


def is_near_duplicate(phash1: str, phash2: str, threshold: int = None) -> bool:
    """
    Check if two perceptual hashes represent near-duplicate images.
    
    Args:
        phash1: First perceptual hash (hex)
        phash2: Second perceptual hash (hex)
        threshold: Maximum hamming distance (default from settings)
        
    Returns:
        True if hamming distance <= threshold
    """
    if threshold is None:
        threshold = settings.PHASH_HAMMING_THRESHOLD
    
    distance = hamming_distance(phash1, phash2)
    return distance <= threshold


def generate_rendition_bytes(
    image: Image.Image,
    preset: str,
    width: int,
    height: int,
    quality: int = 85
) -> Tuple[bytes, int, int]:
    """
    Generate rendition bytes for a given preset.
    
    Args:
        image: PIL Image object
        preset: Preset name
        width: Target width
        height: Target height
        quality: JPEG quality (1-100)
        
    Returns:
        Tuple of (bytes, actual_width, actual_height)
    """
    # Resize image maintaining aspect ratio
    # Use thumbnail to preserve aspect ratio
    img_copy = image.copy()
    img_copy.thumbnail((width, height), Image.Resampling.LANCZOS)
    
    actual_width, actual_height = img_copy.size
    
    # Convert to RGB if necessary (for JPEG)
    if img_copy.mode != "RGB":
        img_copy = img_copy.convert("RGB")
    
    # Save to bytes
    output = BytesIO()
    img_copy.save(output, format="JPEG", quality=quality, optimize=True)
    output.seek(0)
    
    return output.read(), actual_width, actual_height


def open_image_from_bytes(data: bytes) -> Image.Image:
    """
    Open PIL Image from bytes.
    
    Args:
        data: Image bytes
        
    Returns:
        PIL Image object
        
    Raises:
        ValueError: If image cannot be opened
    """
    try:
        return Image.open(BytesIO(data))
    except Exception as e:
        raise ValueError(f"Invalid image data: {str(e)}")


def compute_quality_metric(width: int, height: int, size_bytes: int) -> float:
    """
    Compute a simple quality metric (dimension-to-size ratio).
    
    Higher ratio = better quality (more bytes per pixel).
    
    Args:
        width: Image width
        height: Image height
        size_bytes: File size in bytes
        
    Returns:
        Quality metric (bytes per pixel)
    """
    if width == 0 or height == 0:
        return 0.0
    
    pixels = width * height
    return size_bytes / pixels if pixels > 0 else 0.0

