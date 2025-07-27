# Development Setup Guide

This document lists known setup issues and tips that may be helpful.

## Installation and Setup

### Prerequisites:
- [Cursor](https://www.cursor.so/) (for macOS)
- [Python 3.9+](https://www.python.org/downloads/)
- [Git](https://git-scm.com/)

### Cursor Installation:
1. Visit the official [Cursor webpage](https://cursor.com/), create an account or log in if you already have one.
2. Download Cursor for desktop from the [downloads page](https://cursor.com/downloads).
3. After installation, Cursor will be ready for use.

### Repository Setup:
There are two options for how to start working with the git repo.

1. You can manually copy the repo using the following command:

   ```bash git clone https://github.com/genai-2025-07/Voyager-T800.git ```

   After that, open the project folder in Cursor.

2. On the main window of Cursor, you can select the "Clone repo" option, and after connecting your GitHub account, perform repo cloning.

## Issues and tips

### Setup Issues
The process of setup was smooth and quick, no issues were encountered.
The only thing that was a bit confusing was the GitHub connection through the Cursor webpage. When you click the button to connect, it suggests you install Cursor on your GitHub profile or organization, providing the following rights:
- Read access to actions, commit statuses, deployments, members, metadata, packages, and pages.
- Read and write access to checks, code, discussions, issues, pull requests, and workflows.

Not sure if this kind of access should be approved, especially if working on a special project.
Though when I was logging in through the desktop application, it did not ask me for such access.

### Tips
1. By selecting code and pressing Cmd+K, you can ask the model what this part of the code is doing. This can be pretty useful for understanding new code.
2. If you go to Preferences > Cursor Settings > Rules & Memories, you can provide guidance to the AI that will be followed every time you interact with it.