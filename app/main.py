#!/usr/bin/env python3

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from app.models.llms.basic_workflow.cli import start_cli

def main():
    try:
        start_cli()
        
    except KeyboardInterrupt:
        print("\n👋 Application interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"❌ Failed to start Voyager T800: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
