import traceback
from typing import Union
from pathlib import Path
import base64
import httpx
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
        image_path: Can be a file path (str or Path), a URL, or an already encoded base64 string.

    Returns:
        Base64 encoded string of the image.
    """

    # If the string already IS base64, return it
    if isinstance(image_path, str) and is_base64(image_path):
        return image_path

    try:
        # Handle file paths
        if isinstance(image_path, (str, Path)):
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')

        # Handle raw bytes
        elif isinstance(image_path, bytes):
            return base64.b64encode(image_path).decode('utf-8')

        else:
            raise TypeError(f"Unsupported input type: {type(image_path)}")

    except (FileNotFoundError, OSError):
        # ----- TODO COMPLETED: check if it's a URL -----
        if isinstance(image_path, str) and image_path.startswith(("http://", "https://")):
            try:
                response = httpx.get(image_path, timeout=10)
                response.raise_for_status()

                return image_path

            except Exception as e:
                raise ValueError(f"Input looks like a URL but could not be fetched: {e}")

        # Not a file and not a URL → raise
        raise FileNotFoundError(
            f"'{image_path}' is neither a valid file path nor a reachable URL."
        )

    except Exception as e:
        print(traceback.format_exc())
        raise RuntimeError(f"Unexpected error while converting image to base64: {e}")

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
    except Exception:
        return False

def detect_image_type(b64 :str)->str:
    data = base64.b64decode(b64.split(",")[-1])

    # PNG
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"

    # JPEG
    elif data.startswith(b"\xff\xd8\xff"):
        return "jpeg"

    # GIF
    elif data.startswith(b"GIF8"):
        return "gif"

    # WEBP (RIFFxxxxWEBP)
    elif data.startswith(b"RIFF") and data[8:12] == b"WEBP":
        return "webp"

    raise ValueError("Unkown Image Type - supported types are ['png', 'jpeg', 'git', 'webp']")
