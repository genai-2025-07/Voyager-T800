from pathlib import Path
from typing import Dict, Any


class PromptManager:
    def __init__(self, prompts_dir: str = "prompts"):
        self.prompts_dir = Path(prompts_dir)
        
    def load_prompt(self, name: str) -> str:
        template_path = self.prompts_dir / f"{name}.txt"
        
        if not template_path.exists():
            raise FileNotFoundError(f"Prompt template '{name}' not found at {template_path}")
            
        with open(template_path, 'r', encoding='utf-8') as f:
            return f.read()
    
    def format_prompt(self, template: str, values: Dict[str, Any]) -> str:
        return template.format(**values)
    
    def get_formatted_prompt(self, name: str, values: Dict[str, Any]) -> str:
        template = self.load_prompt(name)
        return self.format_prompt(template, values)
    
    def list_available_prompts(self) -> list:
        prompt_files = list(self.prompts_dir.glob("*.txt"))
        return [f.stem for f in prompt_files]


def load_prompt(name: str) -> str:
    manager = PromptManager()
    return manager.load_prompt(name)


def format_prompt(template: str, values: Dict[str, Any]) -> str:
    manager = PromptManager()
    return manager.format_prompt(template, values)


def get_formatted_prompt(name: str, values: Dict[str, Any]) -> str:
    manager = PromptManager()
    return manager.get_formatted_prompt(name, values)


if __name__ == "__main__":
    manager = PromptManager()
    
    test_values = {
        "city": "Lviv",
        "days": 3,
        "month": "May",
        "preferences": "history and food",
        "budget": "moderate"
    }
    
    print("Available prompts:", manager.list_available_prompts())
    print("\n" + "="*50)
    
    for prompt_name in ["simple_prompt", "json_prompt", "expert_prompt"]:
        print(f"\n{prompt_name.upper()}:")
        print("-" * 30)
        formatted = manager.get_formatted_prompt(prompt_name, test_values)
        print(formatted)
        print("\n" + "="*50) 