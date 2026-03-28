# Potential Enhancements & Refinements

A collection of subtle improvements identified by reviewing the current codebase. These are roughly ordered from most impactful to most minor.

---

## UX / Interaction

### ~~1. F2 to Rename~~ ✓
~~There's no keyboard shortcut for rename. Double-click and right-click work, but F2 is the universal rename key (Explorer, VS Code, etc.) and users will reach for it instinctively.~~

### ~~2. Cursor Position in Status Bar~~ ✓
~~The status bar shows word count and time-ago but not line/column. Adding `Ln 12, Col 5` is standard in any text editor and makes the status bar far more useful, especially when writing structured content.~~

### ~~3. Find & Replace~~ ✓
~~The find bar finds but can't replace. A "Replace" input with "Replace" and "Replace All" buttons would complete the feature without much added complexity.~~

### ~~4. Case-Sensitive Toggle in Find Bar~~ ✓
~~Find is always case-insensitive. A small `Aa` toggle button in the find bar would cover the occasional need to match exact case.~~

### ~~5. Sidebar Resizable~~ ✓
~~The sidebar is fixed at 250px. Note titles are truncated at 30 chars (`title[:29] + '…'`). A drag handle on the divider between sidebar and editor would let users see more of long titles.~~

### ~~6. Window Title Reflects Current Note~~ ✓
~~The window title is always `"Notes"`. Setting it to `"Notes — {title}"` would help users identify the app from the taskbar or Alt+Tab switcher when working with multiple windows.~~

---

## Subtle Behavioural Issues

### ~~7. Undo-Delete Window Closes Silently~~ ✓
~~After deleting a note, the status bar correctly says "Ctrl+Z to undo". But `auto_save()` clears `_deleted_note = None`, so one second after you start typing anything in the replacement note, that undo window closes silently. The user has no indication it expired. Options: keep the buffer until a second manual action, or flash a brief "Undo window expired" message.~~

### ~~8. Sidebar Search Only Matches Persisted Content~~ ✓
~~`filter_notes()` searches `note_data.get('content', '')` from the in-memory store. If the current note has unsaved edits (within the 1-second auto-save window), searching won't find those live changes. This is a minor edge case but can feel like search is broken.~~

### ~~9. Duplicate Note Compounds "Copy of"~~ ✓
~~Duplicating a note named "Copy of X" produces "Copy of Copy of X". A simple check — strip a leading "Copy of " before prepending — would prevent the compounding.~~

### ~~10. Off-Screen Window Position~~ ✓
~~The geometry string (including `+x+y` position) is restored as-is. If the window was on a second monitor that's now disconnected, it will reopen off-screen. Clamping the restored position to the current display bounds would prevent this.~~

---

## Missing Persistence

### ~~11. Scroll Positions Not Persisted Across Restarts~~ ✓
~~`_scroll_positions` is an in-memory dict. When the app closes and reopens, every note scrolls back to the top. Persisting this dict (keyed by note ID) in `config.json` would restore reading position, which matters most for long notes.~~

### ~~12. Created Date Never Shown~~ ✓
~~The `created` timestamp is stored on every note but never surfaced in the UI. A tooltip on the status bar time-ago, or a line in the right-click menu ("Created 3 days ago"), would give it a home.~~

---

## Status Bar & Time Display

### ~~13. Time-Ago Rolls Into "Days" Indefinitely~~ ✓
~~After 24 hours, the status bar shows "X days ago" with no upper bound — "42 days ago", "200 days ago". Switching to an absolute date (e.g. "Mar 20") for notes older than ~7 days is more readable and conventional.~~

---

## Keyboard Shortcuts

### ~~14. No Ctrl+W / Ctrl+Q to Close~~ ✓
~~Users commonly expect Ctrl+W or Ctrl+Q to close an app (especially on Windows). Currently only the window X button triggers `on_closing`. Binding at least one of these would avoid friction.~~
