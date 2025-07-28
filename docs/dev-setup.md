1. Installing and Configuring Cursor IDE
    1.1 Check that your system meets the requirements for Cursor IDE:
        Available for Windows 10 or later, macOS 10.14 or later, and Linux (Ubuntu 18.04+); 
        requires at least 4 GB RAM, ~500 MB of free disk space, and a stable internet connection for AI features.
    1.2 Download and install Cursor IDE.
    1.3 Sign in via GitHub to enable repository integration.
    1.4 Open the project directory in Cursor.
    1.5 Verify that AI code suggestions (autocompletion) are working:  
        Try typing a Python function definition (e.g., `def test_func():`) and check that autocompletion popups appear with code suggestions.

2. Cloning the Repository
    2.1 Create a directory on your computer to store your projects, if you haven't already.
    2.2 Open a terminal and run the following command to clone the repository from GitHub:
        git clone https://github.com/genai-2025-07/Voyager-T800.git
    2.3 Change into the newly created project directory:
        cd Voyager-T800

3. Setting Up the Python Environment
    3.1 Create a virtual environment (venv) inside the project directory:
        python -m venv venv
    3.2 Activate the virtual environment:"
        # On Mac/Linux
        source venv/bin/activate
        # On Windows
        .\venv\Scripts\activate
    3.3 (If there is a requirements.txt file) Install the required libraries:
        pip install -r requirements.txt
    3.4 Ensure Python and all required libraries are working correctly by running:
        python --version
        pip list

4. Creating a Branch for the Task
    4.1 Create and switch to a new branch using the following naming convention:
        issue-<task-number>-<short-description>
    For example, to create and switch to a branch for task 12 "add-login":
        git checkout -b issue-12-add-login
    4.2 Ensure you are working in your own branch (not on main).
    4.3 Commit all your changes only to this branch.

5. Test AI-Assisted Code Completions
   5.1 Create a simple Python test file to check autocompletion. For example, try prompting Cursor with:
        # Write a simple number guessing game in Python
        def main():
            # Cursor should suggest code to implement the game logic here
   5.2 Confirm that Cursor provides code autocompletion suggestions as you type, especially for Python code.
   5.3 Make sure the suggestions are relevant and help you complete the Python function or script.
   5.4 Run your test script to ensure there are no errors.
   5.5 Verify that the test game works as expected (e.g., the guessing game runs and responds to input).

**Common Setup Issues & Solutions:**
    - **Read-Only File System Error:**  
    If you encounter an error such as `Unable to write file '/test.txt' ... EROFS: read-only file system`, this usually means you're attempting to save a file outside your project directory (for example, in `/`).  
    **Solution:** Always save files within your project folder using a relative path like `test.txt` or `./test.txt`.
    - **Virtual Environment Activation Problems:**  
    If activating the virtual environment fails (e.g., `command not found: source` or permission errors), double-check that you are in the correct directory and that the virtual environment was created successfully. On Windows, use `.\venv\Scripts\activate`; on Mac/Linux, use `source venv/bin/activate`.
    - **Missing Dependencies:**  
    If you see `ModuleNotFoundError` or similar import errors, ensure you have run `pip install -r requirements.txt` inside your activated virtual environment.
    - **Python Not Found:**  
    If running `python` or `python3` gives a "command not found" error, make sure Python is installed and added to your system's PATH.

**Pro Tip for Using Cursor IDE:**  
    - `Cmd+K` / `Ctrl+K`: Open the AI command palette for quick actions.
    - `Cmd+I` / `Ctrl+I`: Trigger inline AI code completions.
    - `Cmd+P` / `Ctrl+P`: Open files by name.
    - `Cmd+Shift+F` / `Ctrl+Shift+F`: Search through all files in the project.
    - `Cmd+/` / `Ctrl+/`: Add or remove line comments.