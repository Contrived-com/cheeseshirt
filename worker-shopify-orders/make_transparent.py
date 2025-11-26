#!/usr/bin/env python3
"""
Simple image processor for converting a specific color to transparent in PNG files.
Usage: python make_transparent.py <input_file.png>
"""

import sys
import os
from pathlib import Path
from PIL import Image


# Color threshold for replacement with transparency
# Any pixel with ALL RGB values below this threshold will be made transparent
RGB_THRESHOLD = 100


def validate_png(file_path):
    """
    Validate that the file is a valid PNG file.
    
    Args:
        file_path: Path to the file to validate
        
    Returns:
        True if valid PNG, False otherwise
    """
    try:
        with Image.open(file_path) as img:
            return img.format == 'PNG'
    except Exception:
        return False


def make_color_transparent(input_path, threshold=RGB_THRESHOLD):
    """
    Replace dark colors with transparency in a PNG image.
    Any pixel where ALL RGB values are below the threshold will be made transparent.
    
    Args:
        input_path: Path to the input PNG file
        threshold: RGB threshold value (0-255). Pixels with all RGB < threshold become transparent
        
    Returns:
        Path to the output file
    """
    # Open the image
    img = Image.open(input_path)
    
    # Convert to RGBA if not already
    if img.mode != 'RGBA':
        img = img.convert('RGBA')
    
    # Get image data
    data = img.getdata()
    
    # Create new data with transparency
    new_data = []
    for item in data:
        # Get RGB values (ignore alpha if present)
        r, g, b = item[0], item[1], item[2]
        
        # Check if ALL RGB values are below the threshold (dark pixel)
        if r < threshold and g < threshold and b < threshold:
            # Make it transparent (alpha = 0)
            new_data.append((r, g, b, 0))
        else:
            # Keep the original pixel (fully opaque)
            new_data.append((r, g, b, 255))
    
    # Update image data
    img.putdata(new_data)
    
    # Generate output filename
    path_obj = Path(input_path)
    output_filename = f"{path_obj.stem}-transparent{path_obj.suffix}"
    output_path = path_obj.parent / output_filename
    
    # Save the modified image
    img.save(output_path, 'PNG')
    
    return output_path


def main():
    """Main entry point for the script."""
    # Check command line arguments
    if len(sys.argv) != 2:
        print("Usage: python make_transparent.py <input_file.png>")
        sys.exit(1)
    
    input_file = sys.argv[1]
    
    # Check if file exists
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found.")
        sys.exit(1)
    
    # Validate it's a PNG file
    if not validate_png(input_file):
        print(f"Error: File '{input_file}' is not a valid PNG file.")
        sys.exit(1)
    
    # Process the image
    try:
        output_path = make_color_transparent(input_file)
        print(f"✓ Successfully processed image!")
        print(f"  Input:  {input_file}")
        print(f"  Output: {output_path}")
        print(f"  Dark pixels replaced: RGB values < ({RGB_THRESHOLD}, {RGB_THRESHOLD}, {RGB_THRESHOLD}) → Transparent")
    except Exception as e:
        print(f"Error processing image: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

