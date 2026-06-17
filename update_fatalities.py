"""update_fatalities.py — Modal editor for fatality JSON records.

Modern flat-design: custom colour palette, hover effects, custom dialogs.
One record at a time, vertical layout, dynamic search, record locking.
"""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

ACCENT      = "#c63f3f"   # primary red
ACCENT_HOV  = "#a53434"   # deep red (hover / active)
BG_GREY     = "#f5f5f5"   # page background
WHITE       = "#ffffff"   # card / input background
TEXT_DARK   = "#222222"   # main text
TEXT_MUTED  = "#888888"   # secondary text
BORDER      = "#dcdcdc"   # subtle borders
FONT        = "Segoe UI"

KEY_FIELDS  = {"id"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_json(path: str) -> list[dict] | None:
    if not os.path.exists(path):
        _error_dialog(None, "File Missing", f"'{path}' does not exist.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        _error_dialog(None, "Invalid JSON", f"'{path}' is not valid JSON.\n{exc}")
        return None
    if not isinstance(data, list):
        _error_dialog(None, "Bad Structure", f"'{path}' must contain a JSON array.")
        return None
    return data


def _save_json(path: str, data: list[dict]) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        return True
    except OSError as exc:
        _error_dialog(None, "Save Error", f"Could not write '{path}'.\n{exc}")
        return False


def _flatten_dict(d: dict, parent_key: str = '') -> dict:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}.{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(_flatten_dict(v, new_key).items())
        else:
            items.append((new_key, v))
    return dict(items)


def _unflatten_dict(flat_dict: dict) -> dict:
    result = {}
    for k, v in flat_dict.items():
        parts = k.split('.')
        d = result
        for part in parts[:-1]:
            if part not in d:
                d[part] = {}
            d = d[part]
        d[parts[-1]] = v
    return result


# ---------------------------------------------------------------------------
# Custom dialogs (replace messagebox)
# ---------------------------------------------------------------------------

def _error_dialog(parent: tk.Toplevel | None, title: str, message: str):
    """Styled error dialog."""
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.configure(bg=WHITE)

    if parent:
        dlg.transient(parent)
        dlg.grab_set()
        _center_on_parent(dlg, parent)

    pad = {"padx": 24, "pady": 16}

    # Icon row
    icon_row = ttk.Frame(dlg)
    icon_row.pack(fill=tk.X, **pad)
    canvas = tk.Canvas(icon_row, width=28, height=28, bg=WHITE, highlightthickness=0)
    canvas.pack(side=tk.LEFT)
    canvas.create_oval(2, 2, 26, 26, fill=ACCENT, outline="")
    canvas.create_line(9, 9, 19, 19, fill=WHITE, width=2)
    canvas.create_line(19, 9, 9, 19, fill=WHITE, width=2)

    msg_lbl = tk.Label(icon_row, text=message, font=(FONT, 10), bg=WHITE,
                       fg=TEXT_DARK, justify=tk.LEFT, wraplength=380)
    msg_lbl.pack(side=tk.LEFT, padx=(12, 0))

    # OK button
    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(fill=tk.X, padx=24, pady=(0, 16))
    ok = tk.Label(btn_frame, text="OK", font=(FONT, 10, "bold"),
                  bg=ACCENT, fg=WHITE, padx=28, pady=6, cursor="hand2")
    ok.pack(side=tk.RIGHT)
    _bind_hover(ok, ACCENT, ACCENT_HOV)
    ok.bind("<Button-1>", lambda e: dlg.destroy())

    dlg.wait_window()


def _confirm_yesnocancel(parent: tk.Toplevel, title: str, message: str,
                         yes_text="Yes", no_text="No", cancel_text="Cancel",
                         yes_bg=ACCENT, no_bg=BORDER, cancel_bg=BORDER) -> bool | None:
    """Styled Yes/No/Cancel dialog. Returns True (yes), False (no), None (cancel)."""
    result = [None]

    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.configure(bg=WHITE)
    dlg.transient(parent)
    dlg.grab_set()
    _center_on_parent(dlg, parent)

    pad = {"padx": 24, "pady": 16}

    # Icon
    icon_row = ttk.Frame(dlg)
    icon_row.pack(fill=tk.X, **pad)
    canvas = tk.Canvas(icon_row, width=28, height=28, bg=WHITE, highlightthickness=0)
    canvas.pack(side=tk.LEFT)
    canvas.create_oval(2, 2, 26, 26, fill="#f0ad4e", outline="")
    canvas.create_text(14, 14, text="!", fill=WHITE, font=(FONT, 14, "bold"))

    msg_lbl = tk.Label(icon_row, text=message, font=(FONT, 10), bg=WHITE,
                       fg=TEXT_DARK, justify=tk.LEFT, wraplength=380)
    msg_lbl.pack(side=tk.LEFT, padx=(12, 0))

    # Buttons
    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(fill=tk.X, padx=24, pady=(0, 16))

    def _press(val):
        result[0] = val
        dlg.destroy()

    # Cancel (skip if no cancel text)
    if cancel_text:
        cancel = tk.Label(btn_frame, text=cancel_text, font=(FONT, 10, "bold"),
                          bg=cancel_bg, fg=TEXT_DARK if cancel_bg != ACCENT else WHITE,
                          padx=20, pady=6, cursor="hand2")
        cancel.pack(side=tk.RIGHT, padx=(6, 0))
        _bind_hover(cancel, cancel_bg, "#c0c0c0")
        cancel.bind("<Button-1>", lambda e: _press(None))

    # No
    no = tk.Label(btn_frame, text=no_text, font=(FONT, 10, "bold"),
                  bg=no_bg, fg=TEXT_DARK if no_bg != ACCENT else WHITE,
                  padx=20, pady=6, cursor="hand2")
    no.pack(side=tk.RIGHT, padx=(6, 0))
    _bind_hover(no, no_bg, "#c0c0c0")
    no.bind("<Button-1>", lambda e: _press(False))

    # Yes
    yes = tk.Label(btn_frame, text=yes_text, font=(FONT, 10, "bold"),
                   bg=yes_bg, fg=WHITE, padx=20, pady=6, cursor="hand2")
    yes.pack(side=tk.RIGHT, padx=(6, 0))
    _bind_hover(yes, yes_bg, ACCENT_HOV)
    yes.bind("<Button-1>", lambda e: _press(True))

    dlg.wait_window()
    return result[0]


def _confirm_yesno(parent: tk.Toplevel, title: str, message: str) -> bool:
    """Styled Yes/No dialog."""
    return _confirm_yesnocancel(parent, title, message,
                                yes_text="Yes", no_text="No", cancel_text="") is True


# ---------------------------------------------------------------------------
# Interaction helpers
# ---------------------------------------------------------------------------

def _bind_hover(widget: tk.Label, normal_bg: str, hover_bg: str):
    """Bind hover effects on a tk.Label used as a button."""
    widget.bind("<Enter>", lambda e: widget.configure(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.configure(bg=normal_bg))


def _center_on_parent(dlg: tk.Toplevel, parent: tk.Toplevel | tk.Tk):
    """Centre *dlg* over *parent*."""
    dlg.update_idletasks()
    pw, ph = parent.winfo_width(), parent.winfo_height()
    px, py = parent.winfo_rootx(), parent.winfo_rooty()
    dw, dh = dlg.winfo_width(), dlg.winfo_height()
    x = px + (pw - dw) // 2
    y = py + (ph - dh) // 2
    dlg.geometry(f"+{x}+{y}")


# ---------------------------------------------------------------------------
# Styled entry
# ---------------------------------------------------------------------------

def _styled_entry(parent, **kw) -> tk.Entry:
    """Create a flat entry with subtle border."""
    e = tk.Entry(parent,
                 font=(FONT, 10),
                 bg=WHITE,
                 fg=TEXT_DARK,
                 relief=tk.FLAT,
                 highlightbackground=BORDER,
                 highlightcolor=ACCENT,
                 highlightthickness=1,
                 insertbackground=TEXT_DARK,
                 **kw)
    return e


# ---------------------------------------------------------------------------
# Update Fatalities modal
# ---------------------------------------------------------------------------

class UpdateFatalities(tk.Toplevel):
    """Modern flat-design modal for editing fatality records."""

    def __init__(self, parent: tk.Tk, file_path: str):
        super().__init__(parent)
        self.configure(bg=BG_GREY)
        self._loaded = False

        data = _load_json(file_path)
        if data is None:
            self.destroy()
            return

        self._loaded = True

        self.file_path = file_path
        self.original_data = data
        self.working_data = [dict(r) for r in data]
        self.dirty = False
        self._record_dirty = False
        self._record_snapshot: dict | None = None
        self.updated_summary: list[str] = []

        self._search_text = ""
        self._filtered = list(range(len(self.working_data)))
        self._filtered_pos = 0
        self._entry_widgets: dict[str, tk.Entry] = {}

        self._build_ui()
        self._apply_search()

        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        # Size & centre
        self.update_idletasks()
        w = 800
        ph = self.winfo_screenheight()
        h = min(850, ph - 80)
        pw = self.winfo_screenwidth()
        x = (pw - w) // 2
        y = (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")

        parent.wait_window(self)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        filename = os.path.basename(self.file_path)
        self.title(f"Update — {filename}")

        outer = tk.Frame(self, bg=BG_GREY, padx=20, pady=16)
        outer.pack(fill=tk.BOTH, expand=True)

        # --- Title ---
        title_lbl = tk.Label(outer, text=filename, font=(FONT, 16, "bold"),
                             bg=BG_GREY, fg=TEXT_DARK, anchor=tk.W)
        title_lbl.pack(fill=tk.X, pady=(0, 12))

        # --- Search bar ---
        search_frame = tk.Frame(outer, bg=BG_GREY)
        search_frame.pack(fill=tk.X, pady=(0, 8))

        search_icon = tk.Label(search_frame, text="\U0001F50D", font=(FONT, 12),
                               bg=BG_GREY, fg=TEXT_MUTED)
        search_icon.pack(side=tk.LEFT, padx=(0, 6))

        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())
        self._search_entry = _styled_entry(search_frame, width=36, textvariable=self._search_var)
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._search_count = tk.Label(search_frame, text="", font=(FONT, 9),
                                      bg=BG_GREY, fg=TEXT_MUTED)
        self._search_count.pack(side=tk.RIGHT, padx=(8, 0))

        # --- Navigation bar ---
        nav_frame = tk.Frame(outer, bg=BG_GREY)
        nav_frame.pack(fill=tk.X, pady=(0, 8))

        self._prev_btn = self._flat_btn(nav_frame, "\u25c0  Previous", self._prev,
                                        bg=BORDER, fg=TEXT_DARK, side=tk.LEFT)
        self._record_label = tk.Label(nav_frame, text="", font=(FONT, 10, "bold"),
                                      bg=BG_GREY, fg=TEXT_DARK)
        self._record_label.pack(side=tk.LEFT, expand=True)
        self._next_btn = self._flat_btn(nav_frame, "Next  \u25b6", self._next,
                                        bg=BORDER, fg=TEXT_DARK, side=tk.RIGHT)

        # --- Record-lock bar (hidden until dirty) ---
        self._lock_frame = tk.Frame(outer, bg="#fff3cd")
        lock_lbl = tk.Label(self._lock_frame,
                            text="\u26a0  Record locked — you have unsaved changes",
                            font=(FONT, 9, "bold"), bg="#fff3cd", fg="#856404")
        lock_lbl.pack(side=tk.LEFT, padx=(10, 10), pady=6)

        self._discard_btn = tk.Label(self._lock_frame, text="Discard Changes",
                                     font=(FONT, 9, "bold"),
                                     bg="#e0e0e0", fg=TEXT_DARK,
                                     padx=14, pady=4, cursor="hand2")
        self._discard_btn.pack(side=tk.RIGHT, padx=(0, 5), pady=4)
        _bind_hover(self._discard_btn, "#e0e0e0", "#c0c0c0")
        self._discard_btn.bind("<Button-1>", lambda e: self._discard_record())

        self._update_record_btn = tk.Label(self._lock_frame, text="Update Record",
                                           font=(FONT, 9, "bold"),
                                           bg=ACCENT, fg=WHITE,
                                           padx=14, pady=4, cursor="hand2")
        self._update_record_btn.pack(side=tk.RIGHT, padx=(0, 5), pady=4)
        _bind_hover(self._update_record_btn, ACCENT, ACCENT_HOV)
        self._update_record_btn.bind("<Button-1>", lambda e: self._update_record())

        # --- Scrollable fields area (white card) ---
        self._card = tk.Frame(outer, bg=WHITE, highlightbackground=BORDER,
                             highlightthickness=1)
        self._card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        canvas_frame = tk.Frame(self._card, bg=WHITE)
        canvas_frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        self._canvas = tk.Canvas(canvas_frame, bg=WHITE, borderwidth=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=self._canvas.yview)

        self._fields_frame = tk.Frame(self._canvas, bg=WHITE)
        self._fields_frame.bind(
            "<Configure>",
            lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")),
        )

        self._canvas.create_window((0, 0), window=self._fields_frame, anchor="nw")
        self._canvas.configure(yscrollcommand=scrollbar.set)

        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        def _on_mousewheel(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # --- File-level buttons (bottom) ---
        btn_frame = tk.Frame(outer, bg=BG_GREY)
        btn_frame.pack(fill=tk.X)

        self._flat_btn(btn_frame, "Close", self._cancel,
                       bg="#e0e0e0", fg=TEXT_DARK, side=tk.RIGHT)
        self._save_btn = self._flat_btn(btn_frame, "Update", lambda: None,
                       bg="#e0e0e0", fg="#a0a0a0", side=tk.RIGHT, right_pad=6)

        self.bind("<Control-Return>", lambda _e: self._save())
        self.bind("<Escape>", lambda _e: self._cancel())

    # ------------------------------------------------------------------
    # Flat button helper
    # ------------------------------------------------------------------

    def _flat_btn(self, parent, text, command, bg, fg, side,
                  right_pad=0) -> tk.Label:
        """Create a flat label-button with hover."""
        btn = tk.Label(parent, text=text, font=(FONT, 10, "bold"),
                       bg=bg, fg=fg, padx=18, pady=6, cursor="hand2")
        btn.pack(side=side, padx=(0, right_pad))
        hover_bg = ACCENT_HOV if bg == ACCENT else "#c0c0c0"
        _bind_hover(btn, bg, hover_bg)
        btn.bind("<Button-1>", lambda e: command())
        return btn

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def _on_search_changed(self):
        self._search_text = self._search_var.get().strip().lower()
        self._apply_search()

    def _apply_search(self):
        if not self._search_text:
            self._filtered = list(range(len(self.working_data)))
        else:
            self._filtered = []
            for i, record in enumerate(self.working_data):
                for value in record.values():
                    if self._search_text in str(value).lower():
                        self._filtered.append(i)
                        break

        self._filtered_pos = 0
        total = len(self._filtered)
        self._search_count.configure(
            text=f"{total} match{'es' if total != 1 else ''}" if self._search_text else ""
        )
        self._show_record()

    # ------------------------------------------------------------------
    # Record display
    # ------------------------------------------------------------------

    def _show_record(self):
        for child in self._fields_frame.winfo_children():
            child.destroy()

        total = len(self._filtered)
        full_total = len(self.working_data)

        if self._search_text:
            self._record_label.configure(
                text=f"Record {self._filtered_pos + 1} of {total}  "
                f"(filtered from {full_total})"
            )
        else:
            self._record_label.configure(
                text=f"Record {self._filtered_pos + 1} of {total}"
            )

        self._prev_btn.configure(
            text="\u25c0  Previous",
            state=tk.NORMAL if self._filtered_pos > 0 else tk.DISABLED
        )
        self._next_btn.configure(
            text="Next  \u25b6",
            state=tk.NORMAL if self._filtered_pos < total - 1 else tk.DISABLED
        )

        self._record_dirty = False
        self._record_snapshot = None
        self._set_locked(False)

        if total == 0:
            tk.Label(self._fields_frame, text="(No matching records)",
                     font=(FONT, 11), bg=WHITE, fg=TEXT_MUTED).pack(pady=30)
            self._entry_widgets = {}
            return

        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]
        self._record_snapshot = dict(record)
        self._entry_widgets = {}

        flat_record = _flatten_dict(record)

        current_group = None
        # Field rows
        for field_name, raw_value in flat_record.items():
            parts = field_name.split('.')
            if len(parts) > 1:
                group = ".".join(parts[:-1])
                sub_field = parts[-1]
            else:
                group = ""
                sub_field = field_name

            if group != current_group:
                if group != "":
                    header_frame = tk.Frame(self._fields_frame, bg=WHITE)
                    header_frame.pack(fill=tk.X, padx=16, pady=(16, 4))
                    hdr_lbl = tk.Label(header_frame, text=group.replace('_', ' ').upper(), font=(FONT, 11, "bold"),
                                       bg=WHITE, fg=ACCENT, anchor=tk.W)
                    hdr_lbl.pack(side=tk.LEFT)
                current_group = group

            row_frame = tk.Frame(self._fields_frame, bg=WHITE)
            row_frame.pack(fill=tk.X, padx=16, pady=4)

            lbl = tk.Label(row_frame, text=sub_field, font=(FONT, 10),
                           bg=WHITE, fg=TEXT_DARK, width=26, anchor=tk.E)
            lbl.pack(side=tk.LEFT, padx=(0, 10))

            if isinstance(raw_value, list):
                display_value = json.dumps(raw_value, ensure_ascii=False)
            else:
                display_value = str(raw_value) if raw_value is not None else ""
            is_readonly = not field_name.startswith("derived_details.")

            if is_readonly:
                if "\n" in display_value or len(display_value) > 40:
                    lines = max(3, min(12, display_value.count('\n') + (len(display_value) // 40) + 1))
                    text_w = tk.Text(row_frame, font=(FONT, 10), bg="#f0f0f0", fg=TEXT_MUTED,
                                     relief=tk.FLAT, highlightbackground=BORDER,
                                     highlightcolor=ACCENT, highlightthickness=1,
                                     insertbackground=TEXT_DARK, width=42, height=lines, wrap=tk.WORD)
                    text_w.insert("1.0", display_value)
                    text_w.configure(state=tk.DISABLED)
                    text_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    self._entry_widgets[field_name] = text_w
                else:
                    entry = _styled_entry(row_frame, width=42)
                    entry.insert(0, display_value)
                    entry.configure(state="readonly",
                                    readonlybackground="#f0f0f0",
                                    fg=TEXT_MUTED)
                    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    self._entry_widgets[field_name] = entry
            else:
                if "\n" in display_value or len(display_value) > 40:
                    lines = max(3, min(12, display_value.count('\n') + (len(display_value) // 40) + 1))
                    text_w = tk.Text(row_frame, font=(FONT, 10), bg=WHITE, fg=TEXT_DARK,
                                     relief=tk.FLAT, highlightbackground=BORDER,
                                     highlightcolor=ACCENT, highlightthickness=1,
                                     insertbackground=TEXT_DARK, width=42, height=lines, wrap=tk.WORD)
                    text_w.insert("1.0", display_value)
                    text_w.bind("<KeyRelease>", lambda _e: self._on_field_edited())
                    text_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                    self._entry_widgets[field_name] = text_w
                else:
                    entry = _styled_entry(row_frame, width=42)
                    entry.insert(0, display_value)
                    entry.bind("<KeyRelease>", lambda _e: self._on_field_edited())
                    entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    self._entry_widgets[field_name] = entry

        # Bottom padding so last row isn't flush
        tk.Frame(self._fields_frame, bg=WHITE, height=8).pack()

    # ------------------------------------------------------------------
    # Record locking
    # ------------------------------------------------------------------

    def _on_field_edited(self):
        if not self._record_dirty:
            self._record_dirty = True
            self._set_locked(True)

    def _set_locked(self, locked: bool):
        state = tk.DISABLED if locked else tk.NORMAL
        self._prev_btn.configure(state=state)
        self._next_btn.configure(state=state)

        if locked:
            self._lock_frame.pack(fill=tk.X, pady=(0, 6),
                                  before=self._card)
        else:
            self._lock_frame.pack_forget()

        self._update_save_button_state()

    def _update_save_button_state(self):
        if not hasattr(self, "_save_btn"):
            return
        is_dirty = self.dirty or self._record_dirty
        
        search_state = tk.DISABLED if is_dirty else tk.NORMAL
        self._search_entry.configure(state=search_state)

        if is_dirty:
            self._save_btn.configure(bg=ACCENT, fg=WHITE, cursor="hand2")
            _bind_hover(self._save_btn, ACCENT, ACCENT_HOV)
            self._save_btn.bind("<Button-1>", lambda e: self._save())
        else:
            self._save_btn.configure(bg="#e0e0e0", fg="#a0a0a0", cursor="arrow")
            self._save_btn.unbind("<Enter>")
            self._save_btn.unbind("<Leave>")
            self._save_btn.unbind("<Button-1>")

    # ------------------------------------------------------------------
    # Per-record actions
    # ------------------------------------------------------------------

    def _read_form(self) -> dict | None:
        if not self._entry_widgets:
            return {}

        actual_idx = self._filtered[self._filtered_pos]
        original = self.working_data[actual_idx]
        flat_original = _flatten_dict(original)
        flat_result: dict = {}

        for field_name, entry in self._entry_widgets.items():
            if isinstance(entry, tk.Text):
                raw_value = entry.get("1.0", "end-1c")
            else:
                raw_value = entry.get()
            orig_val = flat_original.get(field_name, "")
            is_readonly = not field_name.startswith("derived_details.")

            if is_readonly:
                flat_result[field_name] = orig_val
            else:
                try:
                    if isinstance(orig_val, bool):
                        val = raw_value.strip().lower()
                        if val in ("true", "1", "yes"):
                            flat_result[field_name] = True
                        elif val in ("false", "0", "no", ""):
                            flat_result[field_name] = False
                        else:
                            raise ValueError(f"'{raw_value}' is not a valid boolean")
                    elif isinstance(orig_val, int):
                        flat_result[field_name] = int(raw_value.strip())
                    elif isinstance(orig_val, float):
                        flat_result[field_name] = float(raw_value.strip())
                    elif isinstance(orig_val, list):
                        flat_result[field_name] = json.loads(raw_value)
                    else:
                        flat_result[field_name] = raw_value
                except (ValueError, TypeError, json.JSONDecodeError) as exc:
                    _error_dialog(
                        self,
                        "Type Error",
                        f"Field '{field_name}': '{raw_value}' does not match "
                        f"expected type ({type(orig_val).__name__}).\n\n{exc}",
                    )
                    return None
        return _unflatten_dict(flat_result)

    def _update_record(self):
        updated = self._read_form()
        if updated is None:
            return

        actual_idx = self._filtered[self._filtered_pos]
        self.working_data[actual_idx] = updated

        record_id = updated.get("id", updated.get("full_name", f"Row {actual_idx + 1}"))
        msg = f"• {record_id}"
        if msg not in self.updated_summary:
            self.updated_summary.append(msg)

        self.dirty = True
        self._record_dirty = False
        self._set_locked(False)
        self._show_record()

    def _discard_record(self):
        if self._record_snapshot is not None:
            actual_idx = self._filtered[self._filtered_pos]
            self.working_data[actual_idx] = dict(self._record_snapshot)

        self._record_dirty = False
        self._set_locked(False)
        self._show_record()

    # ------------------------------------------------------------------
    # Navigation (blocked when record is dirty)
    # ------------------------------------------------------------------

    def _prev(self):
        if self._record_dirty:
            return
        if self._filtered_pos > 0:
            self._filtered_pos -= 1
            self._show_record()

    def _next(self):
        if self._record_dirty:
            return
        if self._filtered_pos < len(self._filtered) - 1:
            self._filtered_pos += 1
            self._show_record()

    # ------------------------------------------------------------------
    # File-level actions
    # ------------------------------------------------------------------

    def _save(self):
        if not self.dirty and not self._record_dirty:
            self.destroy()
            return

        if self._record_dirty:
            updated = self._read_form()
            if updated is None:
                return
            actual_idx = self._filtered[self._filtered_pos]
            self.working_data[actual_idx] = updated
            record_id = updated.get("id", updated.get("full_name", f"Row {actual_idx + 1}"))
            msg = f"• {record_id}"
            if getattr(self, "updated_summary", None) is None:
                self.updated_summary = []
            if msg not in self.updated_summary:
                self.updated_summary.append(msg)

            self._record_dirty = False
            self._set_locked(False)

        if getattr(self, "updated_summary", []):
            bullet_points = "\n".join(self.updated_summary)
            msg = f"Process the following updates?\n\n{bullet_points}"
            ok = _confirm_yesno(self, "Confirm Updates", msg)
            if not ok:
                return

        if not _save_json(self.file_path, self.working_data):
            return

        self.original_data.clear()
        self.original_data.extend(self.working_data)
        self.dirty = False
        self.updated_summary = []
        self._show_record()

    def _cancel(self):
        if self._record_dirty or self.dirty:
            ok = _confirm_yesno(
                self,
                "Discard Changes?",
                "You have unsaved changes.\nClose and discard all changes?",
            )
            if not ok:
                return
        self.destroy()
