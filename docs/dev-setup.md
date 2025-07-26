# Setup Process: Testing AI Assistant in Cursor IDE
### Installation of Cursor IDE

1. Download Cursor IDE installer from the official website
2. Make the installer executable:
   ```bash
   chmod +x cursor.AppImage
   ```
3. Create a Desktop Entry:
   ```bash
   nano ~/.local/share/applications/cursor.desktop
   ```
   Add the following content:
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
4. Update Desktop Database:
   ```bash
   update-desktop-database ~/.local/share/applications/
   ```
5. Cursor now appears in the applications window (tested on Debian 12)

### Connect Cursor IDE to GitHub Repository

1. On the main screen, click **Clone repo**
2. Click **Authenticate** to connect your GitHub account
3. Choose the repository **Voyager-T800**

## Testing AI Assistant Chat

### Test Prompt Used
Write a Python script that pops up a 300×200 px window with a label reading 'Count: 0' and a button labeled '+1'. Each time the button is clicked, the label should increment.

### Result
The test was successful - a working counter application appeared on the screen after running the generated code.