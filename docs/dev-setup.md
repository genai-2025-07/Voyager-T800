# Developer Setup Guide

Welcome to the Voyager T800 project! This guide will help you get started with development, avoid common setup issues, and follow best practices.

---

## Prerequisites

- **Python 3.8+** (for backend and testing)
- **pip** (Python package manager)
- **Git** (for version control)

---

## Repository Structure

Refer to the main `README.md` for a detailed project structure overview.

---

## Common Setup Issues & Tips

- **Missing dependencies:**
  - Double-check for a `requirements.txt` or `package.json` in relevant subfolders.
  - If you add new dependencies, update the requirements file and notify the team.

- **Python version mismatch:**
  - Use `python --version` to check. Prefer Python 3.8 or newer.

- **Virtual environment not activated:**
  - If you see import errors, make sure your virtual environment is active.

- **Markdown preview:**
  - In VS Code, you can auto-preview `.md` files using extensions like "Markdown Preview Enhanced" or by setting up a custom keybinding.

- **Branching:**
  - Follow the branch naming conventions in the main `README.md`.

---

## Additional Resources

- See `/docs/sprints/` for weekly goals and contribution focus.
- For API keys or secrets, use environment variables and **never commit them to the repo**.
- If you encounter issues, check the README, ask your team, or open an issue.

---

Happy coding! 