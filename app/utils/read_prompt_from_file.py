"""
Utility for loading prompt templates from text files.
Provides a function to read and return the contents of a prompt file as a string.
"""

def load_prompt_from_file(file_path: str) -> str:
    """
    Reads a prompt from a file and returns its content as a string.
    
    Args:
        file_path (str): Path to the prompt file (.txt).
        
    Returns:
        str: Content of the prompt file.
        
    Raises:
        TypeError: If file_path is not a string.
        FileNotFoundError: If the file does not exist.
        IOError: If there's an error reading the file.
    """
    if not isinstance(file_path, str):
        raise TypeError(f"file_path must be a string, got {type(file_path).__name__}")
    try:
        with open(file_path, 'r', encoding='utf-8') as file:
            return file.read().strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Prompt file not found: {file_path}")
    except IOError as e:
        raise IOError(f"Error reading prompt file {file_path}: {e}")
