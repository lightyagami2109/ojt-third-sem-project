"""Generate a small sample JPEG image for testing."""
from PIL import Image
import os

# Create a simple test image
img = Image.new("RGB", (100, 100), color="red")
# Add some variation to make it interesting
pixels = img.load()
for i in range(100):
    for j in range(100):
        # Create a simple pattern
        pixels[i, j] = (i % 255, j % 255, (i + j) % 255)

# Save as JPEG
output_path = os.path.join(os.path.dirname(__file__), "sample.jpg")
img.save(output_path, "JPEG", quality=85)
print(f"Generated sample image at: {output_path}")

