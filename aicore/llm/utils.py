from typing import Union
from pathlib import Path
import base64
import re


def parse_content(text :str):
    # Regex to match starting patterns (``` + word without space or \n``` + word)
    start_pattern = r"```(\S*)|\n```(\S*)"

    # Regex to match ending patterns (``` or \n```)
    end_pattern = r"```|\n```"

    # Find all start matches
    start_matches = list(re.finditer(start_pattern, text))

    # Find all end matches
    end_matches = list(re.finditer(end_pattern, text))

    # If there are no start or end matches, return None
    if not start_matches:
        return text

    if not end_matches:
        first_start = start_matches[0].end()
        return text[first_start:]

    elif not start_matches or not end_matches:
        # TODO: log here warning that failed to parse
        return text

    # Get the first start match and the last end match
    first_start = start_matches[0].end()
    last_end = end_matches[-1].start()

    # Extract the content between the first start and the last end
    content_between = text[first_start:last_end]

    return content_between


def image_to_base64(image_path: Union[Path, str, bytes]) -> str:
    """
    Encode the image to base64.
    
    Args:
        image_path: Can be a file path (str or Path) or an already encoded base64 string
        
    Returns:
        Base64 encoded string of the image
    """
    # Check if input is already a base64 string
    if isinstance(image_path, str) and is_base64(image_path):
        return image_path
    
    # Handle file paths
    try:
        if isinstance(image_path, (str, Path)):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        # Handle if bytes were directly passed
        elif isinstance(image_path, bytes):
            return base64.b64encode(image_path).decode('utf-8')
        else:
            print(f"Error: Unsupported input type {type(image_path)}")
            return None
    except FileNotFoundError:
        print(f"Error: The file {image_path} was not found.")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def is_base64(s: str) -> bool:
    """Check if a string is base64 encoded."""
    # Check if the string matches base64 pattern
    pattern = r'^[A-Za-z0-9+/]+={0,2}$'
    if not re.match(pattern, s):
        return False
    
    # Try to decode it
    try:
        # Additional check for valid base64 by trying to decode
        base64.b64decode(s)
        return True
    except:
        return False