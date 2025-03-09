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


def image_to_base64(image_path :Union[Path, str])->str:
    """Encode the image to base64."""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')    
    except FileNotFoundError:
        print(f"Error: The file {image_path} was not found.")
        return None
    except Exception as e:  # Added general exception handling
        print(f"Error: {e}")
        return None