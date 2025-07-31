# Development Environment Setup Guide

This guide combines all team insights for setting up AI-assisted development environments, focusing on Cursor IDE and GitHub Copilot integration.

## Prerequisites

Before starting, ensure your system has:
- **Operating System**: Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)
- **Memory**: At least 4 GB RAM
- **Storage**: ~500 MB free disk space
- **Network**: Stable internet connection for AI features
- **Required Software**:
  - [Python 3.9+](https://www.python.org/downloads/)
  - [Git](https://git-scm.com/)

## Cursor IDE Setup

### Installation Process

1. **Download and Install**
   - Visit [Cursor IDE official website](https://www.cursor.sh)
   - Download the installer for your operating system
   - Run the installer and follow the setup wizard

2. **Linux-Specific Setup** (if applicable)
   ```bash
   # Make installer executable
   chmod +x cursor.AppImage
   
   # Create desktop entry
   nano ~/.local/share/applications/cursor.desktop
   ```
   
   Add desktop entry content:
   ```desktop
   [Desktop Entry]
   Name=Cursor
   Comment=AI-powered code editor
   Exec=/path/to/cursor/cursor
   Icon=/path/to/cursor/icon.png
   Terminal=false
   Type=Application
   Categories=Development;TextEditor;
   ```
   
   Update desktop database:
   ```bash
   update-desktop-database ~/.local/share/applications/
   ```

3. **Initial Configuration**
   - Open Cursor IDE
   - Sign in via GitHub account to enable repository integration
   - Complete the authentication process

### GitHub Repository Integration

**Method 1: Direct Clone in Cursor**
1. On Cursor's main screen, click **"Clone repo"**
2. Authenticate with your GitHub account
3. Select the target repository (e.g., Voyager-T800)

**Method 2: Manual Clone**
1. Open terminal and clone repository:
   ```bash
   git clone https://github.com/genai-2025-07/Voyager-T800.git
   cd Voyager-T800
   ```
2. Open the project folder in Cursor IDE

### Python Environment Setup

1. **Create Virtual Environment**
   ```bash
   python -m venv venv
   ```

2. **Activate Virtual Environment**
   ```bash
   # Mac/Linux
   source venv/bin/activate
   
   # Windows
   .\venv\Scripts\activate
   ```

3. **Install Dependencies** (if requirements.txt exists)
   ```bash
   pip install -r requirements.txt
   ```

4. **Verify Installation**
   ```bash
   python --version
   pip list
   ```

## GitHub Copilot Setup (VS Code)

### Installation

1. Open VS Code
2. Access Extensions sidebar (`Ctrl+Shift+X`)
3. Search for "GitHub Copilot"
4. Click **Install**
5. Sign in with GitHub account when prompted

### Configuration

- Access settings: `File > Preferences > Settings`
- Search for "Copilot"
- Configure suggestions, inline completions, and advanced options

### Usage Patterns

- **Automatic Suggestions**: Start typing code, press `Tab` to accept
- **Manual Trigger**: Use `Ctrl+Enter` for suggestion panel
- **Comment Prompts**: Write descriptive comments to guide generation
- **Documentation**: Type `/**` or `///` for docstring generation

## AI Assistant Testing and Usage

### Cursor IDE AI Features

**Essential Keyboard Shortcuts:**
- **`Ctrl+K` / `Cmd+K`**: AI command palette for quick actions, code generation, and editing
- **`Ctrl+L` / `Cmd+L`**: Send questions to chat interface
- **`Ctrl+I` / `Cmd+I`**: Trigger inline AI completions
- **`Tab`**: Accept generated code suggestions
- **`Ctrl+P` / `Cmd+P`**: Open files by name
- **`Ctrl+Shift+F` / `Cmd+Shift+F`**: Search through project files
- **`Ctrl+/` / `Cmd+/`**: Toggle line comments

**Testing AI Functionality:**

1. **Basic Code Generation Test**
   Create a test file and try:
   ```python
   # Write a simple number guessing game in Python
   def main():
       # AI should provide implementation suggestions
   ```

## Common Issues and Solutions

### Installation Issues

**Read-Only File System Error**
- **Problem**: `EROFS: read-only file system` when saving files
- **Solution**: Always save files within your project directory using relative paths (`./test.txt`)

**Virtual Environment Activation Problems**
- **Problem**: `command not found: source` or permission errors
- **Solution**: 
  - Verify you're in the correct directory
  - Windows: Use `.\venv\Scripts\activate`
  - Mac/Linux: Use `source venv/bin/activate`

**Missing Dependencies**
- **Problem**: `ModuleNotFoundError` when running code
- **Solution**: Run `pip install -r requirements.txt` in activated virtual environment

**Python Not Found**
- **Problem**: `python: command not found`
- **Solution**: Ensure Python is installed and added to system PATH

### GitHub Integration Issues

**Repository Access Concerns**
When connecting Cursor to GitHub, the integration may request extensive permissions including:
- Read access to actions, commit statuses, deployments, members, metadata, packages, and pages
- Read and write access to checks, code, discussions, issues, pull requests, and workflows
