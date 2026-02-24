# sNotes

A lightweight, distraction-free note-taking app built with Python and tkinter for Windows.

## Features

### Writing
- **Auto-save** — Notes save automatically 1 second after you stop typing
- **First-line titles** — The first line of your note becomes its title in the sidebar
- **Auto-date new notes** — New notes are pre-titled with today's date (e.g. `24 February 2026`)
- **Full undo/redo** — Ctrl+Z / Ctrl+Y for text changes; Ctrl+Z also restores a just-deleted note
- **Tab indentation** — Tab inserts an indent; Shift+Tab removes one
- **Clickable URLs** — `http://` and `https://` links open in your browser on click
- **Find in note** — Ctrl+F opens an inline find bar with match highlighting and navigation

### Organisation
- **Search** — Filters notes by title and content as you type; shows match count in the header
- **Pin notes** — Right-click → Pin to keep important notes at the top of the list
- **Sort toggle** — Switch between last-modified and A–Z order with the Date/A–Z button
- **Duplicate note** — Right-click → Duplicate to copy a note as a new one
- **Delete with confirmation** — Notes with content ask for confirmation before deletion

### Interface
- **Notion-inspired theme** — Warm, clean light theme easy on the eyes
- **Right-click context menu** — Pin/Unpin, Rename, Duplicate, Export as TXT, Delete
- **Note count** — Header shows total notes; switches to "2 of 5" when searching
- **Status bar** — Always shows time since last edit and word/character count
- **Scroll memory** — Returns to your scroll position when switching back to a note
- **Font size control** — Ctrl+= / Ctrl+- to resize the editor font; persists between sessions

### Export
- **Save as TXT** — Export the current note as a `.txt` file
- **Export all** — Export every note to a folder of your choice

## Requirements

- Python 3.6 or higher (tkinter is included with Python on Windows)
- Optional: [Pillow](https://python-pillow.org/) for the custom window icon

## Running the App

```bash
python snotes.py
```

Or double-click `snotes.py` in Windows Explorer (if `.py` files are associated with Python).

## Keyboard Shortcuts

| Shortcut | Action |
|---|---|
| Ctrl+N | New note |
| Ctrl+S | Save current note |
| Ctrl+D | Delete current note |
| Ctrl+Z | Undo text — or restore a just-deleted note |
| Ctrl+Y | Redo |
| Ctrl+F | Find in note |
| Ctrl+/ | Focus the search box |
| Ctrl+Shift+C | Copy entire note to clipboard |
| Ctrl+= / Ctrl++ | Increase editor font size |
| Ctrl+- | Decrease editor font size |
| Ctrl+0 | Reset editor font size |
| Tab | Indent |
| Shift+Tab | De-indent |
| Escape | Close find bar / clear search |
| Delete | Delete selected note (sidebar focused) |
| Double-click | Rename note (sidebar) |

## Data Storage

Notes are stored in:
```
C:\Users\YourUsername\.simple_notes\
  notes.json   — all note content
  config.json  — window size, last note, font size, sort preference
```

To back up or sync your notes, copy the `.simple_notes` folder to cloud storage (OneDrive, Dropbox, etc.) or keep it under version control.

## Troubleshooting

**App won't start:**
- Confirm Python is installed: `python --version`
- Try: `python3 snotes.py`

**Can't find my notes:**
- Notes are at `C:\Users\YourUsername\.simple_notes\notes.json`

**Icon not showing:**
- Install Pillow: `pip install pillow`
