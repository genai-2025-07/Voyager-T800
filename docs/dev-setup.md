# Development Environment Setup Guide

This guide combines all team insights for setting up AI-assisted development environments, focusing on Cursor IDE and GitHub Copilot integration.

## 1. Prerequisites

Before starting, ensure your system has:

### 1.1 Operating System
- Windows 10+, macOS 10.14+, or Linux (Ubuntu 18.04+)

### 1.2 Hardware Requirements
- **Memory**: At least 4 GB RAM
- **Storage**: ~500 MB free disk space  
- **Network**: Stable internet connection for AI features

### 1.3 Required Software
- [Python 3.12+](https://www.python.org/downloads/)  (You can refer to section 2.3.6 for installation guide)
- [Git](https://git-scm.com/)

## 2. Cursor IDE Setup

### 2.1 Installation Process

#### 2.1.1 Download and Install
1. Visit [Cursor IDE official website](https://www.cursor.sh)
2. Download the installer for your operating system
3. Run the installer and follow the setup wizard

#### 2.1.2 Linux-Specific Setup (if applicable)

**Basic AppImage Setup:**
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

**Sandbox Issues Fix:**
If your AppImage doesn't open and the logs show sandbox issues, modify the desktop entry:

```desktop
[Desktop Entry]
Name=Cursor
Comment=AI-powered code editor
Exec=/path/to/cursor/cursor --no-sandbox
Icon=/path/to/cursor/icon.png
Terminal=false
Type=Application
Categories=Development;TextEditor;
```

#### 2.1.3 Initial Configuration
1. Open Cursor IDE
2. Sign in via GitHub account to enable repository integration
3. Complete the authentication process

### 2.2 GitHub Repository Integration

#### Method 1: Direct Clone in Cursor
1. On Cursor's main screen, click **"Clone repo"**
2. Authenticate with your GitHub account
3. Select the target repository (e.g., Voyager-T800)

#### Method 2: Manual Clone
1. Open terminal and clone repository:
   ```bash
   git clone https://github.com/genai-2025-07/Voyager-T800.git
   cd Voyager-T800
   ```
2. Open the project folder in Cursor IDE

### 2.3 Python Environment Setup

#### 2.3.1 Install Poetry
```bash
pipx install poetry
```
Then confirm
```bash
poetry --version
```
If you need to install pipx & pyenv (for python3.12 usage), refer to section 2.3.6 below.
Please note that poetry creates `poetry.lock` file which includes dependency resolution to ensure reproducible builds.

#### 2.3.2 Install dependencies
```bash
poetry install --with dev
```

#### 2.3.3 Configure environment variables
```bash
cp .env.example .env
```

#### 2.3.4 Linting

ruff is added as linter for current project with settings in ruff.toml file.
You can run it manually via Makefile command
```bash
make ruff
```

If any file reformating is needed, ruff will handle it. After that add reformated files to git index and run ruff again.

Alternatively, ruff can be used as pre-commit hook
```bash
poetry run pre-commit install
```

If any file reformating is needed, pre-commit hook will handle it and prevent commiting. After that, you should commit again.

Note: sometimes pre-commit crashes merge process when resolving merge conflicts. You can temporarily disable it and enable after resolving conflicts

```bash
poetry run pre-commit uninstall

# resolve conflicts

poetry run pre-commit uninstall
```
 
#### 2.3.5 Configure environment variables
```bash
cp .env.example .env
```

#### 2.3.6 python3.12 installation guide (if not already installed)

Install pyenv
```bash
# Mac/Linux
brew install pyenv

# For windows you may use pyenv-win
```

Select python3.12 
```bash
pyenv install 3.12

# inside project folder
pyenv local 3.12
```

Verify
```bash
python --version
```

Install pipx
```bash
python3 -m pip install --user pipx

python3 -m pipx ensurepath
```

Then restart terminal and verify
```bash
pipx --version
```

## 3. GitHub Copilot Setup (VS Code)

### 3.1 Installation
1. Open VS Code
2. Access Extensions sidebar (`Ctrl+Shift+X`)
3. Search for "GitHub Copilot"
4. Click **Install**
5. Sign in with GitHub account when prompted

### 3.2 Configuration
- Access settings: `File > Preferences > Settings`
- Search for "Copilot"
- Configure suggestions, inline completions, and advanced options

### 3.3 Usage Patterns
- **Automatic Suggestions**: Start typing code, press `Tab` to accept
- **Manual Trigger**: Use `Ctrl+Enter` for suggestion panel
- **Comment Prompts**: Write descriptive comments to guide generation
- **Documentation**: Type `/**` or `///` for docstring generation

## 4. AI Assistant Testing and Usage

### 4.1 Cursor IDE AI Features

**Essential Keyboard Shortcuts:**
- **`Ctrl+K` / `Cmd+K`**: AI command palette for quick actions, code generation, and editing
- **`Ctrl+L` / `Cmd+L`**: Send questions to chat interface
- **`Ctrl+I` / `Cmd+I`**: Trigger inline AI completions
- **`Tab`**: Accept generated code suggestions
- **`Ctrl+P` / `Cmd+P`**: Open files by name
- **`Ctrl+Shift+F` / `Cmd+Shift+F`**: Search through project files
- **`Ctrl+/` / `Cmd+/`**: Toggle line comments

### 4.2 Cursor rules

We use Cursor's "Project Rules" feature to ensure code consistency, enforce best practices, and speed up development.

#### Why We Use It

*   **Context-Aware AI:** The AI has deep, built-in knowledge of our project structure, coding standards, and security requirements.
*   **Consistency:** The AI helps ensure that all code—whether written by a senior developer or a new contributor—adheres to the same patterns.
*   **Velocity:** Automate boilerplate for things like FastAPI endpoints, LangChain chains, and tests.

Cursor will automatically detect and load all the project rules located in the `.cursor/rules` directories.

#### **How It Works in Practice**

*   **While you code:** When you are editing a file (e.g., in `app/api/`), the AI automatically has the context of our API best practices. When you ask it to generate code or "chat with your files," its suggestions will already follow our standards.
*   **When you need specific help:** You can explicitly ask for guidance from our rulebook. In the chat panel, type `@` to see a list of available rules and select one. For example:
    > `@testing-guidelines Please write a pytest test for this function, making sure to mock the external service.`

The AI will then use the detailed instructions from that rule to generate a high-quality, compliant test case.

### 4.3 Testing AI Functionality

Create a test file and try:
```python
# Write a simple number guessing game in Python
def main():
    # AI should provide implementation suggestions
```

## 5. Common Issues and Solutions

### 5.1 Installation Issues

#### 5.1.1 Read-Only File System Error
- **Problem**: `EROFS: read-only file system` when saving files
- **Solution**: Always save files within your project directory using relative paths (`./test.txt`)

#### 5.1.2 AppImage Sandbox Issues
- **Problem**: Cursor AppImage fails to launch with sandbox-related errors in logs
- **Solution**: Add `--no-sandbox` flag to the Exec line in your desktop entry:
  ```desktop
  Exec=/path/to/cursor/cursor --no-sandbox
  ```

#### 5.1.3 Virtual Environment Activation Problems
- **Problem**: `command not found: source` or permission errors
- **Solution**: 
  - Verify you're in the correct directory
  - Windows: Use `.\venv\Scripts\activate`
  - Mac/Linux: Use `source venv/bin/activate`

#### 5.1.4 Missing Dependencies
- **Problem**: `ModuleNotFoundError` when running code
- **Solution**: Run `pip install -r requirements.txt` in activated virtual environment

#### 5.1.5 Python Not Found
- **Problem**: `python: command not found`
- **Solution**: Ensure Python is installed and added to system PATH

### 5.2 GitHub Integration Issues

#### 5.2.1 Repository Access Concerns
When connecting Cursor to GitHub, the integration may request extensive permissions including:
- Read access to actions, commit statuses, deployments, members, metadata, packages, and pages
- Read and write access to checks, code, discussions, issues, pull requests, and workflows

These permissions are standard for IDE integrations that provide comprehensive GitHub functionality.