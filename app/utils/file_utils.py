"""
File utility functions for handling directory creation and file I/O operations.
"""

import csv
from pathlib import Path
from typing import List, Dict, Any
from dataclasses import asdict


def ensure_directory_exists(directory_path: str) -> Path:
    """
    Ensure a directory exists, creating it if necessary.
    
    Args:
        directory_path: Path to the directory to ensure exists
        
    Returns:
        Path: Path object for the directory
    """
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def save_text_file(content: str, file_path: Path, encoding: str = 'utf-8') -> bool:
    """
    Save text content to a file.
    
    Args:
        content: Text content to save
        file_path: Path object for the output file
        encoding: File encoding (default: utf-8)
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        with open(file_path, 'w', encoding=encoding) as file:
            file.write(content)
        return True
    except Exception as e:
        print(f"Error saving file {file_path}: {e}")
        return False


def save_metadata_csv(metadata_list: List[Any], output_path: Path, fieldnames: List[str] = None) -> bool:
    """
    Save metadata to CSV file.
    
    Args:
        metadata_list: List of metadata objects to save
        output_path: Path object for the output CSV file
        fieldnames: List of field names for CSV headers (optional)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not metadata_list:
        print("No metadata to save")
        return False
    
    try:
        # Determine fieldnames if not provided
        if fieldnames is None:
            # Use the first metadata object to determine fieldnames
            first_item = metadata_list[0]
            if hasattr(first_item, '__dict__'):
                fieldnames = list(first_item.__dict__.keys())
            elif hasattr(first_item, '__slots__'):
                fieldnames = list(first_item.__slots__)
            else:
                fieldnames = list(first_item.keys()) if isinstance(first_item, dict) else []
        
        with open(output_path, 'w', newline='', encoding='utf-8') as file:
            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            
            for metadata in metadata_list:
                if hasattr(metadata, '__dict__'):
                    writer.writerow(metadata.__dict__)
                elif hasattr(metadata, '__slots__'):
                    writer.writerow({slot: getattr(metadata, slot) for slot in metadata.__slots__})
                else:
                    writer.writerow(asdict(metadata) if hasattr(metadata, '__dataclass_fields__') else metadata)
        
        print(f"Metadata saved to {output_path}")
        return True
        
    except Exception as e:
        print(f"Error saving metadata: {e}")
        return False


def read_csv_file(file_path: str, encoding: str = 'utf-8') -> List[Dict[str, str]]:
    """
    Read data from a CSV file.
    
    Args:
        file_path: Path to the CSV file
        encoding: File encoding (default: utf-8)
        
    Returns:
        List[Dict[str, str]]: List of dictionaries containing CSV data
    """
    try:
        with open(file_path, 'r', encoding=encoding) as file:
            reader = csv.DictReader(file)
            data = list(reader)
        print(f"Loaded {len(data)} records from CSV")
        return data
    
    except FileNotFoundError:
        print(f"Error: CSV file {file_path} not found")
        return []
    except Exception as e:
        print(f"Error reading CSV file: {e}")
        return [] 