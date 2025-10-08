from PIL import Image, ImageChops, ImageEnhance
import os

def ela_from_image(image_path, dst_path, quality=90, scale=15):
    """
    Perform Error Level Analysis on an image file.
    Save ELA image to dst_path and return dst_path.
    """
    original = Image.open(image_path).convert("RGB")
    # Save recompressed version to temp at given quality
    tmp = dst_path + ".tmp.jpg"
    original.save(tmp, "JPEG", quality=quality)
    compressed = Image.open(tmp)

    # Compute difference
    diff = ImageChops.difference(original, compressed)

    # Enhance difference visually
    extrema = diff.getextrema()
    # Scale to make differences visible
    enhancer = ImageEnhance.Brightness(diff)
    ela_img = enhancer.enhance(scale)

    # Save and cleanup
    ela_img.save(dst_path)
    try:
        os.remove(tmp)
    except Exception:
        pass
    return dst_path
