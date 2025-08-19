from pathlib import Path
from typing import Dict, Any, Optional


class PromptManager:
    """
    Manages prompt templates for the Voyager T800 travel planning system.
    
    This class handles loading, formatting, and managing prompt templates from
    text files. It provides robust error handling for missing files and template
    variables, with intelligent fallback values for common template placeholders.
    
    Attributes:
        prompts_dir (Path): Directory containing prompt template files
    """
    
    def __init__(self, prompts_dir: Optional[str] = None):
        """
        Initialize the PromptManager with a prompts directory.
        
        Args:
            prompts_dir: Optional path to the prompts directory. If None, uses
                        the default prompts directory relative to this file.
        """
        if prompts_dir is None: 
            current_file_dir = Path(__file__).parent
            self.prompts_dir = (current_file_dir.parent.parent / "prompts").resolve()
        else:
            self.prompts_dir = Path(prompts_dir).resolve()
        
    def load_prompt(self, name: str) -> str:
        """
        Load a prompt template from a text file.
        
        This method reads a prompt template file from the prompts directory.
        The file should be named '{name}.txt' and contain the template text
        with placeholders for dynamic values.
        
        Args:
            name: The name of the prompt template file (without .txt extension)
            
        Returns:
            str: The contents of the prompt template file
            
        Raises:
            FileNotFoundError: If the prompt template file doesn't exist
            UnicodeDecodeError: If the file contains invalid UTF-8 characters
        """
        template_path = self.prompts_dir / f"{name}.txt"
        
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template '{name}' not found at {template_path}")
        
        return template_path.read_text(encoding="utf-8")
    
    def format_prompt(self, template: str, values: Dict[str, Any]) -> str:
        """
        Format a prompt template with provided values, handling missing keys gracefully.
        
        This method formats a template string by replacing placeholders with values
        from the provided dictionary. It handles missing keys by using fallback values
        or leaving the placeholder as-is, preventing KeyError exceptions.
        
        Args:
            template: The template string containing placeholders like {city}, {days}
            values: Dictionary of values to substitute into the template
            
        Returns:
            str: The formatted prompt with all available values substituted
            
        Raises:
            ValueError: If template is None or empty
            TypeError: If values is not a dictionary
        """
        if template is None:
            raise ValueError("Template cannot be None")
        
        if not isinstance(template, str):
            raise TypeError(f"Template must be a string, got {type(template).__name__}")
        
        if not template.strip():
            raise ValueError("Template cannot be empty or whitespace-only")
        
        if not isinstance(values, dict):
            raise TypeError(f"Values must be a dictionary, got {type(values).__name__}")
        
        try:
            return template.format(**values)
        except KeyError as e:
            missing_key = str(e).strip("'")
            return self._format_with_fallbacks(template, values, missing_key)
    
    def _format_with_fallbacks(self, template: str, values: Dict[str, Any], missing_key: str) -> str:
        """
        Format template with fallback values for missing keys.
        
        Args:
            template: The template string to format
            values: Dictionary of available values
            missing_key: The key that was missing from the values dictionary
            
        Returns:
            str: Template formatted with fallbacks for missing keys
        """
        fallback_values = values.copy()

        fallbacks = {
            'city': 'the destination',
            'days': 'several',
            'month': 'your preferred time',
            'preferences': 'your interests',
            'budget': 'your budget',
            'nation': 'the country',
            'special_requirements': 'any special requirements',
            'chat_history': 'previous conversation context',
            'user_input': 'your travel request'
        }
        
        if missing_key in fallbacks:
            fallback_values[missing_key] = fallbacks[missing_key]
        else:
            fallback_values[missing_key] = f'[missing: {missing_key}]'
        
        try:
            return template.format(**fallback_values)
        except KeyError as e:
            return self._replace_all_placeholders(template, fallback_values)
    
    def _replace_all_placeholders(self, template: str, values: Dict[str, Any]) -> str:
        """
        Replace all remaining placeholders with fallback values or generic placeholders.
        
        Args:
            template: The template string with remaining placeholders
            values: Dictionary of available values
            
        Returns:
            str: Template with all placeholders replaced
        """
        import re
        
        placeholder_pattern = r'\{([^}]+)\}'
        
        def replace_placeholder(match):
            key = match.group(1)
            if key in values:
                return str(values[key])
            else:
                return f'[placeholder: {key}]'
        
        return re.sub(placeholder_pattern, replace_placeholder, template)
    
    def get_formatted_prompt(self, name: str, values: Dict[str, Any]) -> str:
        """
        Load and format a prompt template with provided values.
        
        This method combines loading a prompt template and formatting it with
        the provided values. It includes comprehensive error handling for both
        loading and formatting operations, returning error messages instead of
        raising exceptions.
        
        Args:
            name: The name of the prompt template file (without .txt extension)
            values: Dictionary of values to substitute into the template
            
        Returns:
            str: The formatted prompt, or an error message if loading/formatting fails
        """
        try:
            template = self.load_prompt(name)
        except Exception as e:
            return f"[PromptManager Error] Failed to load prompt '{name}': {str(e)}"
        try:
            return self.format_prompt(template, values)
        except Exception as e:
            return f"[PromptManager Error] Failed to format prompt '{name}': {str(e)}"
    
    def list_available_prompts(self) -> list:
        """
        List all available prompt template files.
        
        This method scans the prompts directory for .txt files and returns
        a list of their names without the .txt extension.
        
        Returns:
            list: List of available prompt template names
        """
        prompt_files = list(self.prompts_dir.glob("*.txt"))
        return [f.stem for f in prompt_files]