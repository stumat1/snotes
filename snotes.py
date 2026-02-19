#!/usr/bin/env python3
"""
Simple Note Taking App
A lightweight, thoughtful note-taking application with auto-save and search.
"""

import tkinter as tk
from tkinter import ttk, messagebox, font, filedialog, simpledialog
import json
import os
from datetime import datetime
from pathlib import Path


class NoteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Notes")

        # Set up data directory
        self.data_dir = Path.home() / ".simple_notes"
        self.data_dir.mkdir(exist_ok=True)
        self.notes_file = self.data_dir / "notes.json"
        self.config_file = self.data_dir / "config.json"

        # Load notes and config
        self.notes = self.load_notes()
        self.config = self.load_config()
        self.root.geometry(self.config.get('geometry', '900x600'))
        self.current_note_id = self.config.get("last_note_id")
        self.auto_save_after_id = None
        self.displayed_note_ids = []  # Parallel list tracking note IDs shown in listbox

        # Create UI
        self.create_ui()

        # Open last note, most recent note, or create a new one
        if self.notes and self.current_note_id in self.notes:
            self.load_note(self.current_note_id)
        elif self.notes:
            most_recent = max(self.notes.items(), key=lambda x: x[1]['modified'])[0]
            self.load_note(most_recent)
        else:
            self.new_note()

        # Bind save on close
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_ui(self):
        # Configure style
        style = ttk.Style()
        style.theme_use('clam')

        # Main container
        main_container = ttk.Frame(self.root)
        main_container.pack(fill=tk.BOTH, expand=True)

        # Left sidebar for note list
        sidebar = ttk.Frame(main_container, width=250)
        sidebar.pack(side=tk.LEFT, fill=tk.BOTH, padx=(5, 0), pady=5)
        sidebar.pack_propagate(False)

        # Sidebar header
        sidebar_header = ttk.Frame(sidebar)
        sidebar_header.pack(fill=tk.X, pady=(0, 5))

        self.notes_header_label = ttk.Label(sidebar_header, text="Notes", font=('Segoe UI', 12, 'bold'))
        self.notes_header_label.pack(side=tk.LEFT)

        new_btn = ttk.Button(sidebar_header, text="+", width=3, command=self.new_note)
        new_btn.pack(side=tk.RIGHT)

        # Search box
        search_frame = ttk.Frame(sidebar)
        search_frame.pack(fill=tk.X, pady=(0, 5))

        self.search_var = tk.StringVar()
        self.search_entry = ttk.Entry(search_frame, textvariable=self.search_var)
        self.search_entry.pack(fill=tk.X)
        self.search_entry.insert(0, "Search...")
        self.search_entry.bind('<FocusIn>', lambda e: self.on_search_focus_in(e))
        self.search_entry.bind('<FocusOut>', lambda e: self.on_search_focus_out(e))
        self.search_entry.bind('<Escape>', self._clear_search)

        # Note list
        list_frame = ttk.Frame(sidebar)
        list_frame.pack(fill=tk.BOTH, expand=True)

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.note_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=scrollbar.set,
            font=('Segoe UI', 10),
            selectmode=tk.SINGLE,
            activestyle='none',
            borderwidth=0,
            highlightthickness=0
        )
        self.note_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.note_listbox.yview)

        self.note_listbox.bind('<<ListboxSelect>>', self.on_note_select)
        self.note_listbox.bind('<Double-Button-1>', self.rename_note)
        self.note_listbox.bind('<Delete>', lambda e: self.delete_note())

        # Now that listbox exists, we can set up the search trace
        self.search_var.trace_add('write', lambda *args: self.filter_notes())

        # Right side - editor
        editor_container = ttk.Frame(main_container)
        editor_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Editor toolbar
        toolbar = ttk.Frame(editor_container)
        toolbar.pack(fill=tk.X, pady=(0, 5))

        self.title_label = ttk.Label(toolbar, text="", font=('Segoe UI', 11))
        self.title_label.pack(side=tk.LEFT)

        delete_btn = ttk.Button(toolbar, text="Delete", command=self.delete_note)
        delete_btn.pack(side=tk.RIGHT, padx=(5, 0))

        save_txt_btn = ttk.Button(toolbar, text="Save TXT", command=self.export_as_txt)
        save_txt_btn.pack(side=tk.RIGHT, padx=(5, 0))

        export_all_btn = ttk.Button(toolbar, text="Export All", command=self.export_all_notes)
        export_all_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Text editor
        editor_frame = ttk.Frame(editor_container)
        editor_frame.pack(fill=tk.BOTH, expand=True)

        text_font = font.Font(family="Consolas", size=11)

        self.text_editor = tk.Text(
            editor_frame,
            wrap=tk.WORD,
            font=text_font,
            borderwidth=1,
            relief=tk.SOLID,
            padx=10,
            pady=10,
            undo=True,
            maxundo=-1
        )
        self.text_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text_scrollbar = ttk.Scrollbar(editor_frame, command=self.text_editor.yview)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_editor.config(yscrollcommand=text_scrollbar.set)

        # Bind text change to auto-save and live word count
        self.text_editor.bind('<<Modified>>', self.on_text_modified)
        self.text_editor.bind('<KeyRelease>', lambda e: self._update_status())

        # Keyboard shortcuts — bind Ctrl+N on the editor directly so "break"
        # prevents the Text widget's class binding from inserting a newline first
        self.text_editor.bind('<Control-n>', lambda e: self.new_note() or "break")
        self.root.bind('<Control-n>', lambda e: self.new_note())
        self.root.bind('<Control-s>', lambda e: self.save_current_note())
        self.root.bind('<Control-d>', lambda e: self.delete_note())

        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Populate note list
        self.update_note_list()

    def _clear_search(self, event=None):
        self.search_var.set("")
        self.text_editor.focus_set()
        return "break"

    def on_search_focus_in(self, event):
        if self.search_var.get() == "Search...":
            self.search_var.set("")

    def on_search_focus_out(self, event):
        if self.search_var.get() == "":
            self.search_var.set("Search...")

    def _rebuild_listbox(self, note_items):
        """Rebuild the listbox from (note_id, note_data) pairs and restore selection."""
        self.note_listbox.delete(0, tk.END)
        self.displayed_note_ids = []

        for note_id, note_data in note_items:
            title = note_data.get('title', 'Untitled')
            display = title if len(title) <= 30 else title[:29] + '…'
            self.note_listbox.insert(tk.END, display)
            self.displayed_note_ids.append(note_id)

        # Empty-state placeholder
        if not self.displayed_note_ids:
            searching = self.search_var.get() not in ('', 'Search...')
            msg = 'No results' if searching else 'Press + to create a note'
            self.note_listbox.insert(tk.END, msg)
            self.note_listbox.itemconfig(0, fg='#999')

        # Update header count
        count = len(self.notes)
        self.notes_header_label.config(text=f"Notes ({count})" if count else "Notes")

        # Restore selection highlight for the current note
        if self.current_note_id in self.displayed_note_ids:
            idx = self.displayed_note_ids.index(self.current_note_id)
            self.note_listbox.selection_set(idx)
            self.note_listbox.see(idx)

    def filter_notes(self):
        search_term = self.search_var.get().lower()
        if search_term == "search...":
            search_term = ""

        sorted_notes = sorted(
            self.notes.items(),
            key=lambda x: x[1]['modified'],
            reverse=True
        )

        if search_term:
            sorted_notes = [
                (note_id, note_data) for note_id, note_data in sorted_notes
                if search_term in note_data.get('title', '').lower()
                or search_term in note_data.get('content', '').lower()
            ]

        self._rebuild_listbox(sorted_notes)

    def update_note_list(self):
        sorted_notes = sorted(
            self.notes.items(),
            key=lambda x: x[1]['modified'],
            reverse=True
        )
        self._rebuild_listbox(sorted_notes)

    def on_note_select(self, event):
        selection = self.note_listbox.curselection()
        if selection:
            index = selection[0]
            if index >= len(self.displayed_note_ids):
                return  # Placeholder item
            note_id = self.displayed_note_ids[index]
            if note_id != self.current_note_id:
                self.save_current_note()
                self.load_note(note_id)

    def load_note(self, note_id):
        if note_id in self.notes:
            self.current_note_id = note_id
            note_data = self.notes[note_id]

            self.title_label.config(text=note_data.get('title', 'Untitled'))

            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', note_data.get('content', ''))

            self.text_editor.edit_modified(False)

            self.config['last_note_id'] = note_id
            self.save_config()

            self.update_note_list()
            modified = note_data.get('modified', '')
            if modified:
                self.status_bar.config(text=f"Last modified: {self._time_ago(modified)}")
            else:
                self._update_status()

    def new_note(self):
        self.save_current_note()

        note_id = datetime.now().strftime("%Y%m%d_%H%M%S")

        self.notes[note_id] = {
            'title': 'New Note',
            'content': '',
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat()
        }

        self.current_note_id = note_id
        self.load_note(note_id)
        self.text_editor.focus_set()

    def delete_note(self):
        if not self.current_note_id:
            return

        has_content = bool(self.notes.get(self.current_note_id, {}).get('content', '').strip())
        if has_content and not messagebox.askyesno("Delete Note", "Are you sure you want to delete this note?"):
            return

        if self.current_note_id in self.notes:
            del self.notes[self.current_note_id]
            self.save_notes()

            if self.notes:
                most_recent = max(self.notes.items(), key=lambda x: x[1]['modified'])[0]
                self.load_note(most_recent)
            else:
                self.new_note()

            self.status_bar.config(text="Note deleted")

    def on_text_modified(self, event):
        if self.text_editor.edit_modified():
            if self.auto_save_after_id:
                self.root.after_cancel(self.auto_save_after_id)
            self.auto_save_after_id = self.root.after(1000, self.auto_save)

    def auto_save(self):
        self.save_current_note()
        self.status_bar.config(text=f"Auto-saved  ·  {self._word_count_text()}")
        self.root.after(2000, self._update_status)

    def _word_count_text(self):
        content = self.text_editor.get('1.0', tk.END).strip()
        if not content:
            return "0 words"
        words = len(content.split())
        chars = len(content)
        return f"{words} word{'s' if words != 1 else ''}  ·  {chars} chars"

    def _update_status(self):
        self.status_bar.config(text=self._word_count_text())

    def _time_ago(self, iso_string):
        try:
            dt = datetime.fromisoformat(iso_string)
            seconds = int((datetime.now() - dt).total_seconds())
            if seconds < 60:
                return "just now"
            elif seconds < 3600:
                m = seconds // 60
                return f"{m} minute{'s' if m != 1 else ''} ago"
            elif seconds < 86400:
                h = seconds // 3600
                return f"{h} hour{'s' if h != 1 else ''} ago"
            else:
                d = seconds // 86400
                return f"{d} day{'s' if d != 1 else ''} ago"
        except Exception:
            return ""

    def save_current_note(self):
        if not self.current_note_id:
            return

        content = self.text_editor.get('1.0', tk.END).strip()

        # Don't persist empty notes — remove them silently
        if not content:
            if self.current_note_id in self.notes:
                del self.notes[self.current_note_id]
                self.save_notes()
                self.update_note_list()
            self.text_editor.edit_modified(False)
            return

        # Note may no longer exist (e.g. was just removed by delete_note)
        if self.current_note_id not in self.notes:
            self.text_editor.edit_modified(False)
            return

        lines = content.split('\n')
        title = lines[0][:50] if lines[0] else 'Untitled'
        if not title.strip():
            title = 'Untitled'

        self.notes[self.current_note_id].update({
            'title': title,
            'content': content,
            'modified': datetime.now().isoformat()
        })

        self.title_label.config(text=title)
        self.save_notes()
        self.update_note_list()
        self.text_editor.edit_modified(False)

    def rename_note(self, event=None):
        selection = self.note_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        if index >= len(self.displayed_note_ids):
            return
        note_id = self.displayed_note_ids[index]

        current_title = self.notes[note_id].get('title', 'Untitled')
        new_title = simpledialog.askstring(
            "Rename Note", "Note title:", initialvalue=current_title, parent=self.root
        )
        if not new_title or not new_title.strip():
            return

        new_title = new_title.strip()

        # Replace the first line of the editor so auto-save picks it up correctly
        if note_id == self.current_note_id:
            content = self.text_editor.get('1.0', tk.END)
            lines = content.split('\n')
            lines[0] = new_title
            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', '\n'.join(lines).rstrip('\n'))
            self.save_current_note()
        else:
            self.notes[note_id]['title'] = new_title[:50]
            self.save_notes()
            self.update_note_list()

    def export_all_notes(self):
        if not self.notes:
            messagebox.showinfo("Export All", "No notes to export.")
            return

        folder = filedialog.askdirectory(title="Choose a folder to export notes into")
        if not folder:
            return

        folder_path = Path(folder)
        saved = 0
        for note_id, note_data in self.notes.items():
            content = note_data.get('content', '').strip()
            if not content:
                continue
            title = note_data.get('title', 'Untitled')
            safe_title = "".join(c for c in title if c.isalnum() or c in ' -_').strip() or note_id
            file_path = folder_path / f"{safe_title}.txt"
            counter = 1
            while file_path.exists():
                file_path = folder_path / f"{safe_title} ({counter}).txt"
                counter += 1
            try:
                file_path.write_text(content, encoding='utf-8')
                saved += 1
            except Exception:
                pass

        self.status_bar.config(text=f"Exported {saved} note{'s' if saved != 1 else ''} to {folder_path.name}/")
        self.root.after(4000, self._update_status)

    def export_as_txt(self):
        if not self.current_note_id:
            return

        content = self.text_editor.get('1.0', tk.END).strip()
        if not content:
            messagebox.showinfo("Export", "Nothing to save — the note is empty.")
            return

        title = self.notes.get(self.current_note_id, {}).get('title', 'note')
        default_name = title[:50].strip() + ".txt"

        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=default_name,
            title="Save note as TXT"
        )

        if not file_path:
            return  # User cancelled

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            self.status_bar.config(text=f"Saved: {Path(file_path).name}")
            self.root.after(3000, self._update_status)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save file: {e}")

    def load_notes(self):
        if self.notes_file.exists():
            try:
                with open(self.notes_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                messagebox.showerror("Error", f"Failed to load notes: {e}")
                return {}
        return {}

    def save_notes(self):
        try:
            with open(self.notes_file, 'w', encoding='utf-8') as f:
                json.dump(self.notes, f, indent=2, ensure_ascii=False)
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save notes: {e}")

    def load_config(self):
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def save_config(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2)
        except Exception:
            pass

    def on_closing(self):
        self.config['geometry'] = self.root.geometry()
        self.save_config()
        self.save_current_note()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = NoteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
