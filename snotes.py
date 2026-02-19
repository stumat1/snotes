#!/usr/bin/env python3
"""
Simple Note Taking App
A lightweight, thoughtful note-taking application with auto-save and search.
"""

import tkinter as tk
from tkinter import ttk, messagebox, font
import json
import os
from datetime import datetime
from pathlib import Path


class NoteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Notes")
        self.root.geometry("900x600")

        # Set up data directory
        self.data_dir = Path.home() / ".simple_notes"
        self.data_dir.mkdir(exist_ok=True)
        self.notes_file = self.data_dir / "notes.json"
        self.config_file = self.data_dir / "config.json"

        # Load notes and config
        self.notes = self.load_notes()
        self.config = self.load_config()
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

        ttk.Label(sidebar_header, text="Notes", font=('Segoe UI', 12, 'bold')).pack(side=tk.LEFT)

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

        # Now that listbox exists, we can set up the search trace
        self.search_var.trace('w', lambda *args: self.filter_notes())

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

        # Keyboard shortcuts
        self.root.bind('<Control-n>', lambda e: self.new_note())
        self.root.bind('<Control-s>', lambda e: self.save_current_note())

        # Status bar
        self.status_bar = ttk.Label(self.root, text="Ready", relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # Populate note list
        self.update_note_list()

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
            self.note_listbox.insert(tk.END, title)
            self.displayed_note_ids.append(note_id)

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

        if messagebox.askyesno("Delete Note", "Are you sure you want to delete this note?"):
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
        self.save_current_note()
        self.root.destroy()


def main():
    root = tk.Tk()
    app = NoteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
