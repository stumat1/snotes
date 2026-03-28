#!/usr/bin/env python3
"""
Simple Note Taking App
A lightweight, thoughtful note-taking application with auto-save and search.
"""

import sys
import tkinter as tk
from tkinter import ttk, messagebox, font, filedialog, simpledialog
import json
import re
import uuid
import webbrowser
from datetime import datetime
from pathlib import Path

# Enable per-monitor DPI awareness on Windows to prevent blurry fonts
try:
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()  # fallback for older Windows
    except Exception:
        pass

URL_RE = re.compile(r'https?://[^\s<>"{}|\\^`\[\]]+')

# ---------------------------------------------------------------------------
# Single-instance lock
# ---------------------------------------------------------------------------
_lock_fh = None  # kept alive for the process lifetime; releasing it drops the OS lock


def _acquire_single_instance_lock(lock_path: Path) -> bool:
    """Return True if this is the only running instance, False if another is open."""
    global _lock_fh
    try:
        if sys.platform == 'win32':
            import msvcrt
            _lock_fh = open(lock_path, 'w')
            try:
                msvcrt.locking(_lock_fh.fileno(), msvcrt.LK_NBLCK, 1)
                return True
            except OSError:
                _lock_fh.close()
                _lock_fh = None
                return False
        else:
            import fcntl
            _lock_fh = open(lock_path, 'w')
            try:
                fcntl.flock(_lock_fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return True
            except OSError:
                _lock_fh.close()
                _lock_fh = None
                return False
    except Exception:
        return True  # can't determine — allow startup

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
C = {
    'bg':       '#fafaf8',   # main background (warm white)
    'sidebar':  '#f0efed',   # sidebar (slightly darker)
    'surface':  '#e8e7e4',   # inputs, surface cards
    'surface2': '#d4d3d0',   # hover states, dividers
    'text':     '#37352f',   # primary text (warm near-black)
    'subtext':  '#787672',   # secondary text
    'muted':    '#9b9a97',   # placeholder / disabled
    'accent':   '#5b8dd9',   # primary accent (blue)
    'accent_h': '#4070b8',   # accent hover
    'red':      '#c7382a',   # danger (delete button text)
    'select':   '#d3e3f3',   # text selection background
}


class _Tooltip:
    """Minimal hover tooltip for a tkinter widget."""
    def __init__(self, widget, text_fn):
        self._widget = widget
        self._text_fn = text_fn
        self._tip = None
        widget.bind('<Enter>', self._show)
        widget.bind('<Leave>', self._hide)

    def _show(self, _):
        text = self._text_fn()
        if not text:
            return
        x = self._widget.winfo_rootx() + 10
        y = self._widget.winfo_rooty() - 28
        self._tip = tk.Toplevel(self._widget)
        self._tip.wm_overrideredirect(True)
        self._tip.wm_geometry(f"+{x}+{y}")
        tk.Label(self._tip, text=text, bg='#fffde7', fg=C['text'],
                 font=('Segoe UI', 9), relief=tk.FLAT, padx=6, pady=3).pack()

    def _hide(self, _):
        if self._tip:
            self._tip.destroy()
            self._tip = None


class NoteApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Notes")
        self.root.configure(bg=C['bg'])

        # Set up data directory
        self.data_dir = Path.home() / ".simple_notes"
        self.data_dir.mkdir(exist_ok=True)
        self.notes_file = self.data_dir / "notes.json"
        self.config_file = self.data_dir / "config.json"

        # Load notes and config
        self.notes = self.load_notes()
        self.config = self.load_config()
        min_w, min_h = 1100, 700
        w, h = min_w, min_h
        saved = self.config.get('geometry', '')
        if saved:
            try:
                sw, sh = (int(x) for x in saved.split('+')[0].split('x'))
                w, h = max(sw, min_w), max(sh, min_h)
            except Exception:
                pass
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")
        self.root.minsize(min_w, min_h)
        self.current_note_id = self.config.get("last_note_id")
        self.auto_save_after_id = None
        self.displayed_note_ids = []  # Parallel list tracking note IDs shown in listbox
        self._hovered_idx = None
        self._deleted_note = None     # (note_id, note_data) held for undo-delete
        self.editor_font_size = self.config.get('editor_font_size', 11)
        self._find_matches = []
        self._find_idx = -1
        self._find_case_sensitive = False
        self.sort_mode = self.config.get('sort_mode', 'modified')
        self._scroll_positions = self.config.get('scroll_positions', {})
        self.sidebar_width = self.config.get('sidebar_width', 250)
        self._drag_start_x = 0
        self._drag_start_width = self.sidebar_width

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

    # ------------------------------------------------------------------
    # Style setup
    # ------------------------------------------------------------------

    def _setup_styles(self):
        style = ttk.Style()
        style.theme_use('clam')

        style.configure('TFrame', background=C['bg'])
        style.configure('TLabel', background=C['bg'], foreground=C['text'])

        style.configure('TButton',
                        background=C['surface'],
                        foreground=C['text'],
                        borderwidth=0,
                        focusthickness=0,
                        padding=(10, 5))
        style.map('TButton',
                  background=[('active', C['surface2']), ('pressed', C['surface2'])],
                  relief=[('pressed', 'flat'), ('!pressed', 'flat')])
        style.configure('Compact.TButton',
                        background=C['surface'],
                        foreground=C['text'],
                        borderwidth=0,
                        focusthickness=0,
                        padding=(4, 5))
        style.map('Compact.TButton',
                  background=[('active', C['surface2']), ('pressed', C['surface2'])],
                  relief=[('pressed', 'flat'), ('!pressed', 'flat')])

        style.configure('Accent.TButton',
                        background=C['accent'],
                        foreground=C['bg'],
                        borderwidth=0,
                        focusthickness=0,
                        padding=(10, 5))
        style.map('Accent.TButton',
                  background=[('active', C['accent_h']), ('pressed', C['accent_h'])],
                  relief=[('pressed', 'flat'), ('!pressed', 'flat')])

        style.configure('Danger.TButton',
                        background=C['surface'],
                        foreground=C['red'],
                        borderwidth=0,
                        focusthickness=0,
                        padding=(10, 5))
        style.map('Danger.TButton',
                  background=[('active', C['surface2']), ('pressed', C['surface2'])],
                  relief=[('pressed', 'flat'), ('!pressed', 'flat')])

        style.configure('Vertical.TScrollbar',
                        background=C['surface'],
                        troughcolor=C['bg'],
                        borderwidth=0,
                        arrowsize=0)
        style.map('Vertical.TScrollbar',
                  background=[('active', C['surface2'])])

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def create_ui(self):
        self._setup_styles()

        # Main container
        main_container = tk.Frame(self.root, bg=C['bg'])
        main_container.pack(fill=tk.BOTH, expand=True)

        # ── Left sidebar ──────────────────────────────────────────────
        self.sidebar = tk.Frame(main_container, bg=C['sidebar'], width=self.sidebar_width)
        self.sidebar.pack(side=tk.LEFT, fill=tk.BOTH)
        self.sidebar.pack_propagate(False)
        sidebar = self.sidebar  # local alias for the rest of create_ui

        # Inner padding frame
        inner = tk.Frame(sidebar, bg=C['sidebar'])
        inner.pack(fill=tk.BOTH, expand=True, padx=12, pady=10)

        # Sidebar header
        sidebar_header = tk.Frame(inner, bg=C['sidebar'])
        sidebar_header.pack(fill=tk.X, pady=(0, 8))

        self.notes_header_label = tk.Label(
            sidebar_header, text="Notes",
            font=('Segoe UI', 13, 'bold'),
            bg=C['sidebar'], fg=C['text']
        )
        self.notes_header_label.pack(side=tk.LEFT)

        new_btn = ttk.Button(sidebar_header, text="+", width=3,
                             command=self.new_note, style='Accent.TButton')
        new_btn.pack(side=tk.RIGHT)

        sort_label = 'A–Z' if self.sort_mode == 'alpha' else 'Date'
        self.sort_btn = ttk.Button(sidebar_header, text=sort_label, width=5,
                                   command=self._toggle_sort, style='Compact.TButton')
        self.sort_btn.pack(side=tk.RIGHT, padx=(0, 4))

        # ── Search box ────────────────────────────────────────────────
        search_wrap = tk.Frame(inner, bg=C['surface'])
        search_wrap.pack(fill=tk.X, pady=(0, 8))

        search_icon = tk.Label(search_wrap, text="⌕",
                               bg=C['surface'], fg=C['muted'],
                               font=('Segoe UI', 11))
        search_icon.pack(side=tk.LEFT, padx=(6, 2))

        self.search_var = tk.StringVar()
        self.search_entry = tk.Entry(
            search_wrap,
            textvariable=self.search_var,
            bg=C['surface'], fg=C['muted'],
            insertbackground=C['accent'],
            relief=tk.FLAT,
            font=('Segoe UI', 10),
            bd=0
        )
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=5, padx=(0, 6))
        self.search_entry.insert(0, "Search...")
        self.search_entry.bind('<FocusIn>', lambda e: self.on_search_focus_in(e))
        self.search_entry.bind('<FocusOut>', lambda e: self.on_search_focus_out(e))
        self.search_entry.bind('<Escape>', self._clear_search)
        self.search_entry.bind('<Down>', self._focus_note_list)

        # ── Note listbox ──────────────────────────────────────────────
        list_frame = tk.Frame(inner, bg=C['sidebar'])
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
            highlightthickness=0,
            bg=C['sidebar'],
            fg=C['text'],
            selectbackground=C['accent'],
            selectforeground='#ffffff',
        )
        self.note_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.note_listbox.yview)

        self.note_listbox.bind('<<ListboxSelect>>', self.on_note_select)
        self.note_listbox.bind('<Double-Button-1>', self.rename_note)
        self.note_listbox.bind('<Delete>', lambda e: self.delete_note())
        self.note_listbox.bind('<Motion>', self._on_list_motion)
        self.note_listbox.bind('<Leave>', self._on_list_leave)
        self.note_listbox.bind('<Button-3>', self._on_list_right_click)
        self.note_listbox.bind('<Up>', self._on_list_arrow)
        self.note_listbox.bind('<Down>', self._on_list_arrow)

        # Now that listbox exists, we can set up the search trace
        self.search_var.trace_add('write', lambda *args: self.filter_notes())

        # ── Vertical divider (drag to resize) ────────────────────────
        divider = tk.Frame(main_container, bg=C['surface2'], width=4,
                           cursor='sb_h_double_arrow')
        divider.pack(side=tk.LEFT, fill=tk.Y)
        divider.bind('<ButtonPress-1>', self._on_divider_press)
        divider.bind('<B1-Motion>', self._on_divider_drag)
        divider.bind('<ButtonRelease-1>', self._on_divider_release)

        # ── Right side — editor ───────────────────────────────────────
        editor_container = tk.Frame(main_container, bg=C['bg'])
        editor_container.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # Editor toolbar
        toolbar = tk.Frame(editor_container, bg=C['bg'])
        toolbar.pack(fill=tk.X, padx=20, pady=(14, 10))

        self.title_entry = tk.Entry(
            toolbar, font=('Segoe UI', 14, 'bold'),
            bg=C['bg'], fg=C['text'],
            insertbackground=C['accent'],
            relief=tk.FLAT, highlightthickness=0, borderwidth=0,
        )
        self.title_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self.title_entry.bind('<Return>', self._on_title_edit)
        self.title_entry.bind('<FocusOut>', self._on_title_edit)

        delete_btn = ttk.Button(toolbar, text="Delete",
                                command=self.delete_note, style='Danger.TButton')
        delete_btn.pack(side=tk.RIGHT, padx=(5, 0))

        save_txt_btn = ttk.Button(toolbar, text="Save TXT",
                                  command=self.export_as_txt, style='TButton')
        save_txt_btn.pack(side=tk.RIGHT, padx=(5, 0))

        export_all_btn = ttk.Button(toolbar, text="Export All",
                                    command=self.export_all_notes, style='TButton')
        export_all_btn.pack(side=tk.RIGHT, padx=(5, 0))

        # Thin horizontal rule below toolbar
        tk.Frame(editor_container, bg=C['surface2'], height=1).pack(fill=tk.X)

        # Find bar (hidden by default; shown dynamically before editor_frame)
        self.find_bar = tk.Frame(editor_container, bg=C['surface'])
        find_inner = tk.Frame(self.find_bar, bg=C['surface'])
        find_inner.pack(fill=tk.X, padx=12, pady=5)

        tk.Label(find_inner, text="Find", bg=C['surface'], fg=C['subtext'],
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 8))

        self.find_entry = tk.Entry(
            find_inner, bg=C['bg'], fg=C['text'],
            insertbackground=C['accent'], relief=tk.FLAT,
            font=('Segoe UI', 10), highlightthickness=1,
            highlightbackground=C['surface2'], highlightcolor=C['accent'],
        )
        self.find_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.find_entry.bind('<KeyRelease>', lambda e: self._find_in_note())
        self.find_entry.bind('<Return>', lambda e: self._find_next() or "break")
        self.find_entry.bind('<Shift-Return>', lambda e: self._find_prev() or "break")
        self.find_entry.bind('<Escape>', lambda e: self._hide_find_bar())

        self.find_count_label = tk.Label(
            find_inner, text="", bg=C['surface'], fg=C['muted'],
            font=('Segoe UI', 9), width=8, anchor=tk.W,
        )
        self.find_count_label.pack(side=tk.LEFT, padx=(8, 4))

        self.case_btn = tk.Label(
            find_inner, text="Aa", cursor='hand2',
            bg=C['surface'], fg=C['muted'],
            font=('Segoe UI', 9, 'bold'), padx=4, pady=2,
        )
        self.case_btn.pack(side=tk.LEFT, padx=(0, 6))
        self.case_btn.bind('<Button-1>', lambda _: self._toggle_case_sensitive())

        ttk.Button(find_inner, text="↑", width=2,
                   command=self._find_prev, style='TButton').pack(side=tk.LEFT, padx=(0, 2))
        ttk.Button(find_inner, text="↓", width=2,
                   command=self._find_next, style='TButton').pack(side=tk.LEFT, padx=(0, 8))
        ttk.Button(find_inner, text="✕", width=2,
                   command=self._hide_find_bar, style='TButton').pack(side=tk.LEFT)

        # Replace row
        replace_inner = tk.Frame(self.find_bar, bg=C['surface'])
        replace_inner.pack(fill=tk.X, padx=12, pady=(0, 5))

        tk.Label(replace_inner, text="Replace", bg=C['surface'], fg=C['subtext'],
                 font=('Segoe UI', 9)).pack(side=tk.LEFT, padx=(0, 8))

        self.replace_entry = tk.Entry(
            replace_inner, bg=C['bg'], fg=C['text'],
            insertbackground=C['accent'], relief=tk.FLAT,
            font=('Segoe UI', 10), highlightthickness=1,
            highlightbackground=C['surface2'], highlightcolor=C['accent'],
        )
        self.replace_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=3)
        self.replace_entry.bind('<Return>', lambda _: self._replace_one() or "break")
        self.replace_entry.bind('<Escape>', lambda _: self._hide_find_bar())

        ttk.Button(replace_inner, text="Replace", style='TButton',
                   command=self._replace_one).pack(side=tk.LEFT, padx=(8, 2))
        ttk.Button(replace_inner, text="Replace All", style='TButton',
                   command=self._replace_all).pack(side=tk.LEFT)

        tk.Frame(self.find_bar, bg=C['surface2'], height=1).pack(fill=tk.X)

        # Text editor
        self.editor_frame = tk.Frame(editor_container, bg=C['bg'])
        self.editor_frame.pack(fill=tk.BOTH, expand=True)

        self.text_font = font.Font(family="Consolas", size=self.editor_font_size)

        self.text_editor = tk.Text(
            self.editor_frame,
            wrap=tk.WORD,
            font=self.text_font,
            bg=C['bg'],
            fg=C['text'],
            insertbackground=C['accent'],
            selectbackground=C['select'],
            selectforeground=C['text'],
            highlightthickness=0,
            borderwidth=0,
            relief=tk.FLAT,
            padx=24,
            pady=20,
            spacing1=3,
            spacing3=3,
            undo=True,
            maxundo=-1
        )
        self.text_editor.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        text_scrollbar = ttk.Scrollbar(self.editor_frame, command=self.text_editor.yview)
        text_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.text_editor.config(yscrollcommand=text_scrollbar.set)

        # Find highlight tags ('find_current' configured last so it takes priority)
        self.text_editor.tag_configure('find', background='#ffeea6')
        self.text_editor.tag_configure('find_current', background='#f5c518')

        # URL tag — blue underline, hand cursor on hover
        self.text_editor.tag_configure('url', foreground=C['accent'], underline=True)
        self.text_editor.tag_bind('url', '<Button-1>', self._open_url)
        self.text_editor.tag_bind('url', '<Enter>',
                                  lambda e: self.text_editor.config(cursor='hand2'))
        self.text_editor.tag_bind('url', '<Leave>',
                                  lambda e: self.text_editor.config(cursor=''))

        # Tab inserts indentation instead of moving focus
        self.text_editor.bind('<Tab>', self._on_tab)
        self.text_editor.bind('<Shift-Tab>', self._on_shift_tab)

        # Bind text change to auto-save and live word count
        self.text_editor.bind('<<Modified>>', self.on_text_modified)
        self.text_editor.bind('<KeyRelease>', lambda e: self._update_status())

        # Keyboard shortcuts — bind Ctrl+N on the editor directly so "break"
        # prevents the Text widget's class binding from inserting a newline first
        self.text_editor.bind('<Control-n>', lambda e: self.new_note() or "break")
        self.text_editor.bind('<Control-z>', self._on_ctrl_z)
        self.root.bind('<Control-n>', lambda e: self.new_note())
        self.root.bind('<Control-s>', lambda e: self.save_current_note())
        self.root.bind('<Control-d>', lambda e: self.delete_note())
        self.root.bind('<Control-f>', lambda e: self._show_find_bar())
        self.root.bind('<Control-h>', lambda e: self._show_find_bar(focus_replace=True))
        self.root.bind('<Control-slash>', lambda e: self._focus_search())
        self.root.bind('<Control-Shift-c>', lambda e: self._copy_to_clipboard())
        self.root.bind('<Control-equal>', lambda e: self._change_font_size(1))
        self.root.bind('<Control-plus>', lambda e: self._change_font_size(1))
        self.root.bind('<Control-minus>', lambda e: self._change_font_size(-1))
        self.root.bind('<Control-0>', lambda e: self._change_font_size(0))
        self.root.bind('<Control-w>', lambda e: self.on_closing())
        self.root.bind('<Control-q>', lambda e: self.on_closing())
        self.root.bind('<F2>', lambda _: self.rename_note())

        # ── Status bar ────────────────────────────────────────────────
        status_frame = tk.Frame(self.root, bg=C['surface'], height=26)
        status_frame.pack(side=tk.BOTTOM, fill=tk.X)
        status_frame.pack_propagate(False)

        self.status_bar = tk.Label(
            status_frame, text="Ready",
            bg=C['surface'], fg=C['muted'],
            font=('Segoe UI', 9),
            anchor=tk.W,
            padx=14
        )
        self.status_bar.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        _Tooltip(self.status_bar, self._created_tooltip_text)

        # Populate note list
        self.update_note_list()

    # ------------------------------------------------------------------
    # Listbox hover effects
    # ------------------------------------------------------------------

    def _on_divider_press(self, event):
        self._drag_start_x = event.x_root
        self._drag_start_width = self.sidebar.winfo_width()

    def _on_divider_drag(self, event):
        delta = event.x_root - self._drag_start_x
        new_width = max(150, min(500, self._drag_start_width + delta))
        self.sidebar.config(width=new_width)

    def _on_divider_release(self, _):
        self.sidebar_width = self.sidebar.winfo_width()
        self.config['sidebar_width'] = self.sidebar_width
        self.save_config()

    def _on_list_motion(self, event):
        idx = self.note_listbox.nearest(event.y)
        if idx == self._hovered_idx:
            return
        # Restore previous hovered item
        if self._hovered_idx is not None:
            sel = self.note_listbox.curselection()
            if self._hovered_idx not in sel:
                self.note_listbox.itemconfig(self._hovered_idx, bg=C['sidebar'])
        # Highlight new item
        self._hovered_idx = idx
        sel = self.note_listbox.curselection()
        if idx not in sel:
            self.note_listbox.itemconfig(idx, bg=C['surface'])

    def _on_list_leave(self, event):
        if self._hovered_idx is not None:
            sel = self.note_listbox.curselection()
            if self._hovered_idx not in sel:
                self.note_listbox.itemconfig(self._hovered_idx, bg=C['sidebar'])
        self._hovered_idx = None

    def _on_list_arrow(self, event):
        size = len(self.displayed_note_ids)
        if size == 0:
            return "break"
        try:
            current = self.displayed_note_ids.index(self.current_note_id)
        except ValueError:
            current = 0
        if event.keysym == 'Up':
            new_idx = max(0, current - 1)
        else:
            new_idx = min(size - 1, current + 1)
        if new_idx != current:
            self.save_current_note()
            self.load_note(self.displayed_note_ids[new_idx])
        return "break"

    def _focus_note_list(self, _event=None):
        if self.note_listbox.size() == 0:
            return
        sel = self.note_listbox.curselection()
        if not sel:
            self.note_listbox.selection_set(0)
            self.note_listbox.event_generate('<<ListboxSelect>>')
        self.note_listbox.focus_set()
        return "break"

    def _on_list_right_click(self, event):
        idx = self.note_listbox.nearest(event.y)
        if idx < 0 or idx >= len(self.displayed_note_ids):
            return  # Clicked on placeholder or empty area

        # Select the right-clicked note
        self.note_listbox.selection_clear(0, tk.END)
        self.note_listbox.selection_set(idx)
        note_id = self.displayed_note_ids[idx]
        if note_id != self.current_note_id:
            self.save_current_note()
            self.load_note(note_id)

        is_pinned = self.notes.get(note_id, {}).get('pinned', False)
        menu = tk.Menu(self.root, tearoff=0,
                       bg=C['bg'], fg=C['text'],
                       activebackground=C['accent'], activeforeground='#ffffff',
                       font=('Segoe UI', 10), bd=0, relief=tk.FLAT)
        created = self.notes.get(note_id, {}).get('created', '')
        if created:
            menu.add_command(label=f"Created {self._time_ago(created)}",
                             state='disabled', foreground=C['muted'])
            menu.add_separator()
        menu.add_command(label="Unpin" if is_pinned else "Pin",
                         command=lambda nid=note_id: self.toggle_pin(nid))
        menu.add_separator()
        menu.add_command(label="Rename", command=self.rename_note)
        menu.add_command(label="Duplicate", command=self.duplicate_note)
        menu.add_command(label="Export as TXT", command=self.export_as_txt)
        menu.add_separator()
        menu.add_command(label="Delete", command=self.delete_note,
                         foreground=C['red'], activeforeground='#ffffff')

        menu.tk_popup(event.x_root, event.y_root)

    # ------------------------------------------------------------------
    # Search helpers
    # ------------------------------------------------------------------

    def _copy_to_clipboard(self):
        content = self.text_editor.get('1.0', tk.END).strip()
        if not content:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(content)
        self.status_bar.config(text="Copied to clipboard")
        self.root.after(2000, self._update_status)

    def _focus_search(self):
        self.on_search_focus_in(None)
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, tk.END)

    def _clear_search(self, event=None):
        self.search_var.set("")
        self.text_editor.focus_set()
        return "break"

    def on_search_focus_in(self, event):
        if self.search_var.get() == "Search...":
            self.search_var.set("")
        self.search_entry.config(fg=C['text'])

    def on_search_focus_out(self, event):
        if self.search_var.get() == "":
            self.search_var.set("Search...")
        if self.search_var.get() == "Search...":
            self.search_entry.config(fg=C['muted'])

    # ------------------------------------------------------------------
    # Note list management
    # ------------------------------------------------------------------

    def _rebuild_listbox(self, note_items):
        """Rebuild the listbox from (note_id, note_data) pairs and restore selection."""
        self._hovered_idx = None
        self.note_listbox.delete(0, tk.END)
        self.displayed_note_ids = []

        for note_id, note_data in note_items:
            title = note_data.get('title', 'Untitled')
            display = title if len(title) <= 30 else title[:29] + '…'
            prefix = "📌 " if note_data.get('pinned', False) else "  "
            self.note_listbox.insert(tk.END, prefix + display)
            self.displayed_note_ids.append(note_id)

        # Empty-state placeholder
        if not self.displayed_note_ids:
            searching = self.search_var.get() not in ('', 'Search...')
            msg = 'No results' if searching else 'Press + to create a note'
            self.note_listbox.insert(tk.END, msg)
            self.note_listbox.itemconfig(0, fg=C['muted'])

        # Update header count
        total = len(self.notes)
        displayed = len(self.displayed_note_ids)
        if total == 0:
            self.notes_header_label.config(text="Notes")
        elif displayed < total:
            self.notes_header_label.config(text=f"Notes ({displayed} of {total})")
        else:
            self.notes_header_label.config(text=f"Notes ({total})")

        # Restore selection highlight for the current note
        if self.current_note_id in self.displayed_note_ids:
            idx = self.displayed_note_ids.index(self.current_note_id)
            self.note_listbox.selection_set(idx)
            self.note_listbox.see(idx)

    def _sorted_notes(self, note_items):
        """Sort notes with pinned always first, then by current sort mode."""
        if self.sort_mode == 'alpha':
            by_key = sorted(note_items, key=lambda x: x[1].get('title', '').lower())
        else:
            by_key = sorted(note_items, key=lambda x: x[1]['modified'], reverse=True)
        return sorted(by_key, key=lambda x: x[1].get('pinned', False), reverse=True)

    def filter_notes(self):
        search_term = self.search_var.get().lower()
        if search_term == "search...":
            search_term = ""

        # Reflect live editor content so unsaved edits are searchable
        if search_term and self.current_note_id and self.current_note_id in self.notes:
            live = self.text_editor.get('1.0', tk.END).strip()
            self.notes[self.current_note_id]['content'] = live

        notes = self._sorted_notes(self.notes.items())

        if search_term:
            notes = [
                (note_id, note_data) for note_id, note_data in notes
                if search_term in note_data.get('title', '').lower()
                or search_term in note_data.get('content', '').lower()
            ]

        self._rebuild_listbox(notes)

    def update_note_list(self):
        self._rebuild_listbox(self._sorted_notes(self.notes.items()))

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
            # Save scroll position of the note we're leaving
            if self.current_note_id:
                self._scroll_positions[self.current_note_id] = self.text_editor.yview()[0]

            self.current_note_id = note_id
            note_data = self.notes[note_id]

            title = note_data.get('title', 'Untitled')
            self.title_entry.delete(0, tk.END)
            self.title_entry.insert(0, title)
            self.root.title(f"Notes \u2014 {title}")

            self.text_editor.delete('1.0', tk.END)
            self.text_editor.insert('1.0', note_data.get('content', ''))
            self._tag_urls()

            self.text_editor.edit_modified(False)

            # Restore scroll position (deferred so content is fully rendered first)
            fraction = self._scroll_positions.get(note_id, 0.0)
            self.root.after(0, lambda f=fraction: self.text_editor.yview_moveto(f))

            self.config['last_note_id'] = note_id
            self.save_config()

            self.update_note_list()
            self._update_status()

    def new_note(self):
        self.save_current_note()

        now = datetime.now()
        note_id = uuid.uuid4().hex

        self.notes[note_id] = {
            'title': '',
            'content': '',
            'created': now.isoformat(),
            'modified': now.isoformat()
        }

        self.current_note_id = note_id
        self.load_note(note_id)
        self.text_editor.mark_set('insert', '1.0')
        self.text_editor.focus_set()

    def duplicate_note(self):
        if not self.current_note_id or self.current_note_id not in self.notes:
            return
        self.save_current_note()
        source = self.notes[self.current_note_id]
        new_id = uuid.uuid4().hex
        base_title = source.get('title', 'Untitled')
        if base_title.startswith("Copy of "):
            base_title = base_title[len("Copy of "):]
        new_title = f"Copy of {base_title}"
        new_content = source.get('content', '')
        # Replace just the first line with the new title
        lines = new_content.split('\n')
        lines[0] = new_title
        new_content = '\n'.join(lines)
        self.notes[new_id] = {
            'title': new_title[:50],
            'content': new_content,
            'created': datetime.now().isoformat(),
            'modified': datetime.now().isoformat(),
        }
        self.save_notes()
        self.load_note(new_id)

    def delete_note(self):
        if not self.current_note_id:
            return

        has_content = bool(self.notes.get(self.current_note_id, {}).get('content', '').strip())
        if has_content and not messagebox.askyesno("Delete Note", "Are you sure you want to delete this note?"):
            return

        if self.current_note_id in self.notes:
            self._deleted_note = (self.current_note_id, dict(self.notes[self.current_note_id]))
            del self.notes[self.current_note_id]
            self.save_notes()

            if self.notes:
                most_recent = max(self.notes.items(), key=lambda x: x[1]['modified'])[0]
                self.load_note(most_recent)
            else:
                self.new_note()

            self.text_editor.focus_set()
            self.status_bar.config(text="Note deleted  ·  Ctrl+Z to undo")

    def _on_ctrl_z(self, event):
        if self._deleted_note is not None:
            self._restore_deleted_note()
            return "break"
        try:
            self.text_editor.edit_undo()
        except tk.TclError:
            pass
        return "break"

    def _toggle_sort(self):
        self.sort_mode = 'alpha' if self.sort_mode == 'modified' else 'modified'
        self.sort_btn.config(text='A–Z' if self.sort_mode == 'alpha' else 'Date')
        self.config['sort_mode'] = self.sort_mode
        self.save_config()
        self.update_note_list()

    def toggle_pin(self, note_id):
        if note_id not in self.notes:
            return
        self.notes[note_id]['pinned'] = not self.notes[note_id].get('pinned', False)
        self.save_notes()
        self.update_note_list()

    def _on_tab(self, event):
        self.text_editor.insert(tk.INSERT, '\t')
        return "break"

    def _on_shift_tab(self, event):
        line_start = self.text_editor.index('insert linestart')
        line_text = self.text_editor.get(line_start, f'{line_start} lineend')
        if line_text.startswith('\t'):
            self.text_editor.delete(line_start, f'{line_start} + 1 chars')
        elif line_text.startswith('    '):
            self.text_editor.delete(line_start, f'{line_start} + 4 chars')
        elif line_text.startswith(' '):
            # Remove however many leading spaces exist (up to 3)
            spaces = len(line_text) - len(line_text.lstrip(' '))
            self.text_editor.delete(line_start, f'{line_start} + {min(spaces, 3)} chars')
        return "break"

    def _show_find_bar(self, focus_replace=False):
        self.find_bar.pack(fill=tk.X, before=self.editor_frame)
        if focus_replace:
            self.replace_entry.focus_set()
            self.replace_entry.selection_range(0, tk.END)
        else:
            self.find_entry.focus_set()
            self.find_entry.selection_range(0, tk.END)
        self._find_in_note()

    def _hide_find_bar(self):
        self.find_bar.pack_forget()
        self.text_editor.tag_remove('find', '1.0', tk.END)
        self.text_editor.tag_remove('find_current', '1.0', tk.END)
        self._find_matches = []
        self._find_idx = -1
        self.find_count_label.config(text="")
        self._find_case_sensitive = False
        self.case_btn.config(fg=C['muted'])
        self.text_editor.focus_set()

    def _find_in_note(self):
        query = self.find_entry.get()
        self.text_editor.tag_remove('find', '1.0', tk.END)
        self.text_editor.tag_remove('find_current', '1.0', tk.END)
        self._find_matches = []
        self._find_idx = -1

        if not query:
            self.find_count_label.config(text="")
            return

        content = self.text_editor.get('1.0', tk.END)
        if self._find_case_sensitive:
            search_content, search_query = content, query
        else:
            search_content, search_query = content.lower(), query.lower()
        pos = 0
        while True:
            idx = search_content.find(search_query, pos)
            if idx == -1:
                break
            start = f"1.0 + {idx} chars"
            end = f"1.0 + {idx + len(query)} chars"
            self.text_editor.tag_add('find', start, end)
            self._find_matches.append((start, end))
            pos = idx + 1

        if self._find_matches:
            self._find_idx = 0
            self._highlight_current_match()
        else:
            self.find_count_label.config(text="No results")

    def _highlight_current_match(self):
        self.text_editor.tag_remove('find_current', '1.0', tk.END)
        if not self._find_matches:
            return
        start, end = self._find_matches[self._find_idx]
        self.text_editor.tag_add('find_current', start, end)
        self.text_editor.see(start)
        self.find_count_label.config(
            text=f"{self._find_idx + 1} of {len(self._find_matches)}")

    def _find_next(self):
        if not self._find_matches:
            return
        self._find_idx = (self._find_idx + 1) % len(self._find_matches)
        self._highlight_current_match()

    def _toggle_case_sensitive(self):
        self._find_case_sensitive = not self._find_case_sensitive
        active_fg = C['accent'] if self._find_case_sensitive else C['muted']
        self.case_btn.config(fg=active_fg)
        self._find_in_note()

    def _replace_one(self):
        if not self._find_matches or self._find_idx < 0:
            return
        replacement = self.replace_entry.get()
        start, end = self._find_matches[self._find_idx]
        self.text_editor.delete(start, end)
        self.text_editor.insert(start, replacement)
        self._find_in_note()

    def _replace_all(self):
        query = self.find_entry.get()
        if not query:
            return
        replacement = self.replace_entry.get()
        self._find_in_note()
        if not self._find_matches:
            return
        for start, end in reversed(self._find_matches):
            self.text_editor.delete(start, end)
            self.text_editor.insert(start, replacement)
        count = len(self._find_matches)
        self._find_in_note()
        self.find_count_label.config(text=f"{count} replaced")

    def _find_prev(self):
        if not self._find_matches:
            return
        self._find_idx = (self._find_idx - 1) % len(self._find_matches)
        self._highlight_current_match()

    def _tag_urls(self):
        self.text_editor.tag_remove('url', '1.0', tk.END)
        content = self.text_editor.get('1.0', tk.END)
        for match in URL_RE.finditer(content):
            start = f"1.0 + {match.start()} chars"
            end = f"1.0 + {match.end()} chars"
            self.text_editor.tag_add('url', start, end)

    def _open_url(self, event):
        idx = self.text_editor.index(f"@{event.x},{event.y}")
        for start, end in zip(*[iter(self.text_editor.tag_ranges('url'))] * 2):
            if self.text_editor.compare(start, '<=', idx) and \
               self.text_editor.compare(idx, '<=', end):
                webbrowser.open(self.text_editor.get(start, end))
                break

    def _restore_deleted_note(self):
        note_id, note_data = self._deleted_note
        self._deleted_note = None
        self.notes[note_id] = note_data
        self.save_notes()
        self.load_note(note_id)
        self.status_bar.config(text="Note restored")
        self.root.after(3000, self._update_status)

    def on_text_modified(self, event):
        if self.text_editor.edit_modified():
            if self.auto_save_after_id:
                self.root.after_cancel(self.auto_save_after_id)
            self.auto_save_after_id = self.root.after(1000, self.auto_save)

    def auto_save(self):
        undo_expired = self._deleted_note is not None
        self._deleted_note = None
        self.save_current_note()
        self._tag_urls()
        if undo_expired:
            self.status_bar.config(text=f"Auto-saved  ·  Undo window expired  ·  {self._word_count_text()}")
        else:
            self.status_bar.config(text=f"Auto-saved  ·  {self._word_count_text()}")
        self.root.after(2000, self._update_status)

    def _word_count_text(self):
        content = self.text_editor.get('1.0', tk.END).strip()
        if not content:
            return "0 words"
        words = len(content.split())
        chars = len(content)
        return f"{words} word{'s' if words != 1 else ''}  ·  {chars} chars"

    def _change_font_size(self, delta):
        if delta == 0:
            self.editor_font_size = 11
        else:
            self.editor_font_size = max(8, min(28, self.editor_font_size + delta))
        self.text_font.configure(size=self.editor_font_size)
        self.config['editor_font_size'] = self.editor_font_size
        self.save_config()

    def _update_status(self):
        parts = []
        modified = self.notes.get(self.current_note_id, {}).get('modified', '')
        if modified:
            parts.append(self._time_ago(modified))
        wc = self._word_count_text()
        if wc:
            parts.append(wc)
        try:
            pos = self.text_editor.index(tk.INSERT)
            line, col = pos.split('.')
            parts.append(f"Ln {line}, Col {int(col) + 1}")
        except Exception:
            pass
        self.status_bar.config(text="  ·  ".join(parts) if parts else "Ready")

    def _created_tooltip_text(self):
        created = self.notes.get(self.current_note_id, {}).get('created', '')
        if not created:
            return ''
        try:
            dt = datetime.fromisoformat(created)
            return f"Created {dt.strftime('%Y/%m/%d, %H:%M')}"
        except Exception:
            return ''

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
            elif seconds < 7 * 86400:
                d = seconds // 86400
                return f"{d} day{'s' if d != 1 else ''} ago"
            elif dt.year == datetime.now().year:
                return f"{dt.strftime('%b')} {dt.day}"
            else:
                return dt.strftime("%Y/%m/%d")
        except Exception:
            return ""

    def save_current_note(self):
        if not self.current_note_id:
            return

        # Skip if nothing has changed — avoids bumping modified timestamp on navigation
        if not self.text_editor.edit_modified():
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

        self.title_entry.delete(0, tk.END)
        self.title_entry.insert(0, title)
        self.root.title(f"Notes \u2014 {title}")
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

    def _on_title_edit(self, event=None):
        if not self.current_note_id or self.current_note_id not in self.notes:
            return
        new_title = self.title_entry.get().strip()[:50] or 'Untitled'
        # Sync the first line of the editor content to match
        content = self.text_editor.get('1.0', tk.END).rstrip('\n')
        lines = content.split('\n')
        lines[0] = new_title
        self.text_editor.delete('1.0', tk.END)
        self.text_editor.insert('1.0', '\n'.join(lines))
        self._tag_urls()
        self.notes[self.current_note_id].update({
            'title': new_title,
            'content': '\n'.join(lines),
            'modified': datetime.now().isoformat(),
        })
        self.root.title(f"Notes \u2014 {new_title}")
        self.save_notes()
        self.update_note_list()
        self.text_editor.edit_modified(False)

    def export_all_notes(self):
        if not self.notes:
            messagebox.showinfo("Export All", "No notes to export.")
            return

        folder = filedialog.askdirectory(title="Choose a folder to export notes into")
        if not folder:
            return

        folder_path = Path(folder)
        saved = 0
        failed = 0
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
                failed += 1

        if failed:
            self.status_bar.config(text=f"Exported {saved} note{'s' if saved != 1 else ''}  ·  {failed} failed — check folder permissions")
        else:
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
            tmp = self.notes_file.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.notes, indent=2, ensure_ascii=False), encoding='utf-8')
            tmp.replace(self.notes_file)
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
            tmp = self.config_file.with_suffix('.tmp')
            tmp.write_text(json.dumps(self.config, indent=2), encoding='utf-8')
            tmp.replace(self.config_file)
        except Exception as e:
            if hasattr(self, 'status_bar'):
                self.status_bar.config(text=f"Warning: settings not saved — {e}")
                self.root.after(4000, self._update_status)

    def on_closing(self):
        self.config['geometry'] = self.root.geometry()
        if self.current_note_id:
            self._scroll_positions[self.current_note_id] = self.text_editor.yview()[0]
        self.config['scroll_positions'] = self._scroll_positions
        self.save_config()
        self.save_current_note()
        self.root.destroy()


def main():
    data_dir = Path.home() / ".simple_notes"
    data_dir.mkdir(exist_ok=True)
    if not _acquire_single_instance_lock(data_dir / "app.lock"):
        _tmp = tk.Tk()
        _tmp.withdraw()
        messagebox.showwarning("Already Running",
                               "sNotes is already open.\nCheck your taskbar.")
        _tmp.destroy()
        return

    root = tk.Tk()
    try:
        from PIL import Image, ImageTk
        _icon = ImageTk.PhotoImage(Image.open(Path(__file__).parent / "favicon.ico"))
        root.iconphoto(True, _icon)
    except Exception:
        pass  # icon missing or invalid — not fatal
    app = NoteApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
