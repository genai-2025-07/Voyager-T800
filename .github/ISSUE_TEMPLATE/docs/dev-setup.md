1. Installing and Configuring Cursor IDE
1.1 Download and install Cursor IDE.
1.2 Sign in via GitHub to enable repository integration.
1.3 Open the project directory in Cursor.
1.4 Verify that AI code suggestions (autocompletion) are working in the editor.

2. Cloning the Repository
2.1 Create a local directory for your projects.
2.2 Clone the repository from GitHub to your computer.
2.3 Navigate into the project directory.

3. Setting Up the Python Environment
3.1 Create a virtual environment (venv) inside the project directory.
3.2 Activate the virtual environment.
3.3 Ensure Python and all required libraries are working correctly.

4. Creating a Branch for the Task
4.1 Create a new branch named in the format:
    issue-<task-number>-<short-description>.
4.2 Make sure you are working in your own branch, not on main.
4.3 Commit all your changes only to this branch.

5. Test AI-Assisted Code Completions
   5.1 Create a simple test game file using a prompt.
   5.2 Check that Cursor provides code autocompletion suggestions.
   5.3 Ensure suggestions work as expected for Python code.
   5.4 Run your scripts to confirm there are no errors.
   5.5 Verify that the test game functions correctly.

**Setup issue:**
If you see an error like `Unable to write file '/test.txt' ... EROFS: read-only file system`, it means you're trying to save a file outside your project directory (e.g., in `/`). Always save files inside your project folder using a relative path like `test.txt` or `./test.txt`.

**Pro Tip for Using Cursor IDE:**  
Press `Cmd+K` (Mac) or `Ctrl+K` (Windows/Linux) to quickly open the command palette for accessing commands, settings, and actions.  
You can also use this shortcut to modify code and text directly within the editor.