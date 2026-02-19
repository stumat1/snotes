# Simple Note Taking App

A lightweight, thoughtful note-taking application built with Python and tkinter for Windows.

## Features

- **Auto-save** - Your notes are automatically saved as you type (after 1 second of inactivity)
- **Search** - Quickly find notes by searching titles and content
- **Clean Interface** - Distraction-free writing experience with a sidebar for navigation
- **Persistent State** - Remembers your last note when you reopen the app
- **File-based Storage** - Notes stored as JSON in your home directory (`~/.simple_notes/`)
- **First-line Titles** - The first line of your note automatically becomes its title
- **Keyboard-friendly** - Full undo/redo support (Ctrl+Z, Ctrl+Y)

## Requirements

- Python 3.6 or higher (Python comes with tkinter on Windows)

## Installation

1. Save `note_app.py` to your preferred location
2. That's it! No additional packages needed.

## Usage

### Running the App

```bash
python note_app.py
```

Or simply double-click `note_app.py` in Windows Explorer.

### Creating a New Note

- Click the **+** button in the top-right of the sidebar
- Or just start typing in an empty note

### Searching Notes

- Type in the search box at the top of the sidebar
- Search looks through both titles and content
- Clear the search to see all notes

### Deleting a Note

- Select the note you want to delete
- Click the **Delete** button in the toolbar

### Tips

- **First line is the title**: Whatever you write on the first line becomes the note title in the sidebar
- **Auto-save**: Your notes save automatically - no need to press Ctrl+S
- **Quick access**: Notes are sorted by most recently modified at the top

## Data Storage

Notes are stored in:
```
Windows: C:\Users\YourUsername\.simple_notes\notes.json
```

You can:
- Back up this folder to preserve your notes
- Sync it with cloud storage (Dropbox, OneDrive, etc.)
- Version control it with git

## Keyboard Shortcuts

- **Ctrl+Z** - Undo
- **Ctrl+Y** - Redo
- **Ctrl+A** - Select all
- **Ctrl+C** - Copy
- **Ctrl+V** - Paste
- **Ctrl+X** - Cut

## Customization

The code is clean and easy to modify. Some ideas:

- Change the font in the `create_ui()` method (look for `text_font`)
- Adjust the auto-save delay (currently 1000ms in `on_text_modified()`)
- Modify the window size (default 900x600)
- Change the sidebar width (currently 250px)

## Troubleshooting

**App won't start:**
- Make sure Python is installed: `python --version`
- On some systems, try: `python3 note_app.py`

**Can't find my notes:**
- Notes are stored in `~/.simple_notes/notes.json`
- On Windows: `C:\Users\YourUsername\.simple_notes\`

**Text is too small/large:**
- Edit the `text_font = font.Font(family="Consolas", size=11)` line
- Change the `size=11` to your preferred size

## Why Python + tkinter?

- ✅ No compilation needed - runs immediately
- ✅ Native Windows look and feel
- ✅ Works great with VS Code
- ✅ No external dependencies to install
- ✅ Lightweight and fast
- ✅ Easy to read and modify the code

## License

Free to use and modify as you wish!