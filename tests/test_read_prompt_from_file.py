import pytest
import os
import platform
from app.utils.read_prompt_from_file import load_prompt_from_file

def test_load_valid_prompt_file(tmp_path):
    # Create a temporary test file with trailing whitespace
    test_content = "Test prompt content\n\n"
    test_file = tmp_path / "test_prompt.txt"
    test_file.write_text(test_content, encoding="utf-8")
    
    # Test reading valid file
    result = load_prompt_from_file(str(test_file))
    assert result == test_content.strip()  # Перевірка, що strip() працює

def test_file_not_found():
    # Test non-existent file
    with pytest.raises(FileNotFoundError, match=r"Prompt file not found: nonexistent_file\.txt"):
        load_prompt_from_file("nonexistent_file.txt")

def test_invalid_file_path():
    # Test empty path
    with pytest.raises(FileNotFoundError, match=r"Prompt file not found: "):
        load_prompt_from_file("")
    
    # Test invalid type
    with pytest.raises(TypeError, match=r"file_path must be a string, got (NoneType|int)"):
        load_prompt_from_file(None)
    with pytest.raises(TypeError, match=r"file_path must be a string, got int"):
        load_prompt_from_file(123)

@pytest.mark.skipif(platform.system() == "Windows", reason="os.chmod behavior differs on Windows")
def test_permission_error(tmp_path):
    # Create a file without read permissions
    test_file = tmp_path / "no_permission.txt"
    test_file.write_text("Test content", encoding="utf-8")
    os.chmod(test_file, 0o000)  # Remove all permissions
    
    try:
        with pytest.raises(IOError, match=r"Error reading prompt file .*/no_permission\.txt"):
            load_prompt_from_file(str(test_file))
    finally:
        # Cleanup: restore permissions for deletion
        os.chmod(test_file, 0o666)

def test_empty_file(tmp_path):
    # Test empty file
    test_file = tmp_path / "empty.txt"
    test_file.write_text("", encoding="utf-8")
    
    result = load_prompt_from_file(str(test_file))
    assert result == ""

def test_non_utf8_encoding(tmp_path):
    # Test file with latin-1 encoding
    test_content = "Test with special chars: café"
    test_file = tmp_path / "latin1.txt"
    test_file.write_text(test_content, encoding="latin-1")
    
    # Should raise UnicodeDecodeError since we use utf-8
    with pytest.raises(UnicodeDecodeError):
        load_prompt_from_file(str(test_file))