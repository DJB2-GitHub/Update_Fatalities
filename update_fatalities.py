"""update_fatalities.py — Modal editor for fatality JSON records.

Modern flat-design: custom colour palette, hover effects, custom dialogs.
One record at a time, vertical layout, dynamic search, record locking.
Side panel for AI results (revealed on demand).
"""

from __future__ import annotations

import json
import os
import re
import threading
import tkinter as tk
import urllib.request
from tkinter import ttk

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

ACCENT      = "#c63f3f"
ACCENT_HOV  = "#a53434"
BG_GREY     = "#f5f5f5"
WHITE       = "#ffffff"
TEXT_DARK   = "#222222"
TEXT_MUTED  = "#888888"
BORDER      = "#dcdcdc"
FONT        = "Segoe UI"

KEY_FIELDS  = {"id"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def validate_and_parse_coordinate(coord_str: str):
    """
    Validates a GPS coordinate string and attempts to parse it into (lat, lon).
    Returns: (is_valid: bool, message: str, coordinates: tuple or None)
    """
    if not coord_str or not str(coord_str).strip():
        return False, "Input is empty.", None

    coord_str = str(coord_str).strip()
    
    # 1. Decimal Degrees (e.g., "10.34694 N, 107.07263 E" or "10.34694, 107.07263")
    dec_regex = re.compile(r"^(-?\d+\.\d+)\s*([NS]?)[,\s]+(-?\d+\.\d+)\s*([EW]?)$", re.IGNORECASE)
    match = dec_regex.match(coord_str)
    
    if match:
        lat = float(match.group(1))
        lat_dir = match.group(2).upper() if match.group(2) else ""
        lon = float(match.group(3))
        lon_dir = match.group(4).upper() if match.group(4) else ""
        
        if lat_dir == 'S': lat *= -1
        if lon_dir == 'W': lon *= -1
            
        # Mathematical bounds check
        if not (-90 <= lat <= 90):
            return False, f"Invalid latitude ({lat}): Must be between -90 and 90.", None
        if not (-180 <= lon <= 180):
            return False, f"Invalid longitude ({lon}): Must be between -180 and 180.", None
            
        return True, "Valid Decimal Degrees", (round(lat, 5), round(lon, 5))

    # 2. Military Grid Reference System (MGRS) (e.g., 48PYS713677 or 48P YS 713 677)
    clean_mgrs = re.sub(r"\s+", "", coord_str).upper()
    mgrs_regex = re.compile(r"^[1-6][0-9][C-X][A-Z]{2}\d{4,10}$", re.IGNORECASE)
    
    if mgrs_regex.match(clean_mgrs):
        try:
            # Requires: pip install mgrs
            import mgrs
            m = mgrs.MGRS()
            lat, lon = m.toLatLon(clean_mgrs)
            return True, "Valid MGRS", (round(lat, 5), round(lon, 5))
        except ImportError:
            return True, "Valid MGRS format (Tip: install 'mgrs' python library to calculate lat/lon)", None
        except Exception as e:
            return False, f"MGRS format looks valid but math decoding failed: {str(e)}", None

    # 3. Degrees, Minutes, Seconds (DMS) (e.g., 10° 20' N, 107° 04' E)
    dms_regex = re.compile(r"(\d+)[^0-9A-Z]+(\d+)[^0-9A-Z]*([NSEW]?)", re.IGNORECASE)
    matches = list(dms_regex.finditer(coord_str))
    
    if len(matches) >= 2:
        return True, "Valid DMS (Degrees/Minutes)", None # Add math translation here if needed

    # 4. Fallback Error
    error_msg = (
        f"Unrecognized coordinate format: '{coord_str}'.\n"
        "Acceptable formats are:\n"
        "  1. Decimal Degrees: '10.34694 N, 107.07263 E' or '10.34694, 107.07263'\n"
        "  2. MGRS: '48PYS458630' or '48P YS 458 630'\n"
        "  3. DMS: '10° 20\' N, 107° 04\' E'"
    )
    return False, error_msg, None


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


# ---------------------------------------------------------------------------
# Custom dialogs
# ---------------------------------------------------------------------------

def _error_dialog(parent: tk.Toplevel | None, title: str, message: str):
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.configure(bg=WHITE)
    if parent:
        dlg.transient(parent)
        _center_on_parent(dlg, parent)
    dlg.grab_set()
    pad = {"padx": 24, "pady": 16}
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
    result = [None]
    dlg = tk.Toplevel(parent)
    dlg.title(title)
    dlg.resizable(False, False)
    dlg.configure(bg=WHITE)
    dlg.transient(parent)
    _center_on_parent(dlg, parent)
    dlg.grab_set()
    pad = {"padx": 24, "pady": 16}
    icon_row = ttk.Frame(dlg)
    icon_row.pack(fill=tk.X, **pad)
    canvas = tk.Canvas(icon_row, width=28, height=28, bg=WHITE, highlightthickness=0)
    canvas.pack(side=tk.LEFT)
    canvas.create_oval(2, 2, 26, 26, fill="#f0ad4e", outline="")
    canvas.create_text(14, 14, text="!", fill=WHITE, font=(FONT, 14, "bold"))
    msg_lbl = tk.Label(icon_row, text=message, font=(FONT, 10), bg=WHITE,
                       fg=TEXT_DARK, justify=tk.LEFT, wraplength=380)
    msg_lbl.pack(side=tk.LEFT, padx=(12, 0))
    btn_frame = ttk.Frame(dlg)
    btn_frame.pack(fill=tk.X, padx=24, pady=(0, 16))
    def _press(val):
        result[0] = val
        dlg.destroy()
    if cancel_text:
        cancel = tk.Label(btn_frame, text=cancel_text, font=(FONT, 10, "bold"),
                          bg=cancel_bg, fg=TEXT_DARK if cancel_bg != ACCENT else WHITE,
                          padx=20, pady=6, cursor="hand2")
        cancel.pack(side=tk.RIGHT, padx=(6, 0))
        _bind_hover(cancel, cancel_bg, "#c0c0c0")
        cancel.bind("<Button-1>", lambda e: _press(None))
    no = tk.Label(btn_frame, text=no_text, font=(FONT, 10, "bold"),
                  bg=no_bg, fg=TEXT_DARK if no_bg != ACCENT else WHITE,
                  padx=20, pady=6, cursor="hand2")
    no.pack(side=tk.RIGHT, padx=(6, 0))
    _bind_hover(no, no_bg, "#c0c0c0")
    no.bind("<Button-1>", lambda e: _press(False))
    yes = tk.Label(btn_frame, text=yes_text, font=(FONT, 10, "bold"),
                   bg=yes_bg, fg=WHITE, padx=20, pady=6, cursor="hand2")
    yes.pack(side=tk.RIGHT, padx=(6, 0))
    _bind_hover(yes, yes_bg, ACCENT_HOV)
    yes.bind("<Button-1>", lambda e: _press(True))
    dlg.wait_window()
    return result[0]


def _confirm_yesno(parent: tk.Toplevel, title: str, message: str) -> bool:
    return _confirm_yesnocancel(parent, title, message,
                                yes_text="Yes", no_text="No", cancel_text="") is True


# ---------------------------------------------------------------------------
# Interaction helpers
# ---------------------------------------------------------------------------

def _bind_hover(widget: tk.Label, normal_bg: str, hover_bg: str):
    widget.bind("<Enter>", lambda e: widget.configure(bg=hover_bg))
    widget.bind("<Leave>", lambda e: widget.configure(bg=normal_bg))


def _center_on_parent(dlg: tk.Toplevel, parent: tk.Toplevel | tk.Tk):
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
    fnt = kw.pop("font", (FONT, 10))
    return tk.Entry(parent, font=fnt, bg=WHITE, fg=TEXT_DARK,
                    relief=tk.FLAT, highlightbackground=BORDER,
                    highlightcolor=ACCENT, highlightthickness=1,
                    insertbackground=TEXT_DARK, **kw)


# ---------------------------------------------------------------------------
# Update Fatalities modal
# ---------------------------------------------------------------------------

class UpdateFatalities(tk.Toplevel):
    """Modern flat-design modal for editing fatality records with AI side panel."""

    def __init__(self, parent: tk.Tk | tk.Toplevel, file_path: str, *, modal_title: str | None = None):
        super().__init__(parent)
        self.configure(bg=BG_GREY)
        self._loaded = False
        self._modal_title = modal_title

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

        self._search_text = ""
        self._filtered = list(range(len(self.working_data)))
        self._filtered_pos = 0
        self._entry_widgets: dict[str, tk.Entry] = {}

        self._build_ui()
        self._apply_search()

        self.transient(parent)
        self.protocol("WM_DELETE_WINDOW", self._cancel)

        self.update_idletasks()
        w = 1250
        ph = self.winfo_screenheight()
        h = min(950, ph - 40)
        pw = self.winfo_screenwidth()
        x = (pw - w) // 2
        y = (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")
        self.grab_set()

        parent.wait_window(self)

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self):
        filename = os.path.basename(self.file_path)
        if self._modal_title:
            self.title(self._modal_title)
        else:
            self.title(f"Update {filename}")

        outer = tk.Frame(self, bg=BG_GREY)
        outer.pack(fill=tk.BOTH, expand=True)

        # --- Main content (left) ---
        main = tk.Frame(outer, bg=BG_GREY, padx=20, pady=16)
        main.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Title
        tk.Label(main, text=f"Update {filename}", font=(FONT, 16, "bold"),
                 bg=BG_GREY, fg=TEXT_DARK, anchor=tk.W).pack(fill=tk.X, pady=(0, 12))

        # Search
        sf = tk.Frame(main, bg=BG_GREY)
        sf.pack(fill=tk.X, pady=(0, 8))
        tk.Label(sf, text="\U0001F50D", font=(FONT, 12), bg=BG_GREY, fg=TEXT_MUTED).pack(side=tk.LEFT, padx=(0, 6))
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._on_search_changed())
        self._search_entry = _styled_entry(sf, width=24, textvariable=self._search_var)
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._search_count = tk.Label(sf, text="", font=(FONT, 9), bg=BG_GREY, fg=TEXT_MUTED)
        self._search_count.pack(side=tk.RIGHT, padx=(8, 0))

        # Nav
        nf = tk.Frame(main, bg=BG_GREY)
        nf.pack(fill=tk.X, pady=(0, 8))
        self._prev_btn = self._flat_btn(nf, "\u25c0  Previous", self._prev, bg=BORDER, fg=TEXT_DARK, side=tk.LEFT)
        self._record_label = tk.Label(nf, text="", font=(FONT, 10, "bold"), bg=BG_GREY, fg=TEXT_DARK)
        self._record_label.pack(side=tk.LEFT, expand=True)
        self._next_btn = self._flat_btn(nf, "Next  \u25b6", self._next, bg=BORDER, fg=TEXT_DARK, side=tk.RIGHT)

        # Lock bar
        self._lock_frame = tk.Frame(main, bg="#fff3cd")
        tk.Label(self._lock_frame, text="\u26a0  Record locked — you have unsaved changes",
                 font=(FONT, 9, "bold"), bg="#fff3cd", fg="#856404").pack(side=tk.LEFT, padx=(10, 10), pady=6)
        self._discard_btn = tk.Label(self._lock_frame, text="Discard Changes", font=(FONT, 9, "bold"),
                                     bg="#e0e0e0", fg=TEXT_DARK, padx=14, pady=4, cursor="hand2")
        self._discard_btn.pack(side=tk.RIGHT, padx=(0, 5), pady=4)
        _bind_hover(self._discard_btn, "#e0e0e0", "#c0c0c0")
        self._discard_btn.bind("<Button-1>", lambda e: self._discard_record())
        self._update_record_btn = tk.Label(self._lock_frame, text="Update Record", font=(FONT, 9, "bold"),
                                           bg=ACCENT, fg=WHITE, padx=14, pady=4, cursor="hand2")
        self._update_record_btn.pack(side=tk.RIGHT, padx=(0, 5), pady=4)
        _bind_hover(self._update_record_btn, ACCENT, ACCENT_HOV)
        self._update_record_btn.bind("<Button-1>", lambda e: self._update_record())

        # Card
        self._card = tk.Frame(main, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        self._card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        cf = tk.Frame(self._card, bg=WHITE)
        cf.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)
        self._canvas = tk.Canvas(cf, bg=WHITE, borderwidth=0, highlightthickness=0)
        sb = ttk.Scrollbar(cf, orient=tk.VERTICAL, command=self._canvas.yview)
        self._fields_frame = tk.Frame(self._canvas, bg=WHITE)
        self._fields_frame.bind("<Configure>", lambda _e: self._canvas.configure(scrollregion=self._canvas.bbox("all")))
        self._canvas_window = self._canvas.create_window((0, 0), window=self._fields_frame, anchor="nw")
        self._canvas.bind("<Configure>", lambda e: self._canvas.itemconfig(self._canvas_window, width=e.width))
        self._canvas.configure(yscrollcommand=sb.set)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        def _mw(event):
            self._canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        self._canvas.bind_all("<MouseWheel>", _mw)

        # Bottom buttons
        bf = tk.Frame(main, bg=BG_GREY)
        bf.pack(fill=tk.X)
        self._flat_btn(bf, "Close", self._cancel, bg="#e0e0e0", fg=TEXT_DARK, side=tk.RIGHT)
        self._flat_btn(bf, "AI", self._ai_lookup, bg="#4a90d9", fg=WHITE, side=tk.LEFT)
        
        self._live_search_var = tk.BooleanVar(value=True)
        self._live_search_chk = tk.Checkbutton(
            bf, text="Live Search", variable=self._live_search_var,
            bg=BG_GREY, fg=TEXT_DARK, activebackground=BG_GREY, font=(FONT, 9)
        )
        self._live_search_chk.pack(side=tk.LEFT, padx=(10, 0))

        self.bind("<Escape>", lambda _e: self._cancel())

        # --- Side panel (right, hidden) ---
        self._side_panel = tk.Frame(outer, bg="#f0f2f5", width=500)
        self._side_panel.pack_propagate(False)

        sh = tk.Frame(self._side_panel, bg="#4a90d9", height=40)
        sh.pack(fill=tk.X)
        sh.pack_propagate(False)
        tk.Label(sh, text="AI RESULTS", font=(FONT, 10, "bold"), bg="#4a90d9", fg=WHITE).pack(side=tk.LEFT, padx=12, pady=8)
        hb = tk.Label(sh, text="\u2715", font=(FONT, 12, "bold"), bg="#4a90d9", fg=WHITE, padx=10, pady=4, cursor="hand2")
        hb.pack(side=tk.RIGHT)
        hb.bind("<Button-1>", lambda e: self._hide_side_panel())

        tk.Label(self._side_panel, text="PROMPT", font=(FONT, 8, "bold"),
                 bg="#f0f2f5", fg=TEXT_MUTED, anchor="w").pack(fill=tk.X, padx=12, pady=(10, 2))
        self._side_prompt = tk.Text(self._side_panel, font=(FONT, 8), wrap=tk.WORD,
                                    bg=WHITE, fg=TEXT_DARK, padx=8, pady=6, height=12,
                                    relief=tk.FLAT, highlightthickness=0)
        self._side_prompt.pack(fill=tk.X, padx=12, pady=(0, 6))

        tk.Label(self._side_panel, text="RESPONSE", font=(FONT, 8, "bold"),
                 bg="#f0f2f5", fg=TEXT_MUTED, anchor="w").pack(fill=tk.X, padx=12, pady=(4, 2))
        self._side_resp = tk.Text(self._side_panel, font=(FONT, 9), wrap=tk.WORD,
                                  bg=WHITE, fg=TEXT_DARK, padx=8, pady=6,
                                  relief=tk.FLAT, highlightthickness=0)
        self._side_resp.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 10))

    # ------------------------------------------------------------------
    # Flat button helper
    # ------------------------------------------------------------------

    def _flat_btn(self, parent, text, command, bg, fg, side, right_pad=0) -> tk.Label:
        btn = tk.Label(parent, text=text, font=(FONT, 10, "bold"),
                       bg=bg, fg=fg, padx=18, pady=6, cursor="hand2")
        btn.pack(side=side, padx=(0, right_pad))
        hover_bg = ACCENT_HOV if bg == ACCENT else ("#3a7bc8" if bg == "#4a90d9" else "#c0c0c0")
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
                def _search_dict(d):
                    for v in d.values():
                        if isinstance(v, dict):
                            if _search_dict(v):
                                return True
                        elif self._search_text in str(v).lower():
                            return True
                    return False
                if _search_dict(record):
                    self._filtered.append(i)
        self._filtered_pos = 0
        total = len(self._filtered)
        self._search_count.configure(text=f"{total} match{'es' if total != 1 else ''}" if self._search_text else "")
        self._show_record()

    # ------------------------------------------------------------------
    # Record display
    # ------------------------------------------------------------------

    def _apply_hotlinks(self, text_widget: tk.Text):
        text_widget.tag_remove("link", "1.0", tk.END)
        content = text_widget.get("1.0", "end-1c")
        import re
        pattern = r'(https?://[^\s]+|www\.[^\s]+)'
        for match in re.finditer(pattern, content):
            start = match.start()
            end = match.end()
            text_widget.tag_add("link", f"1.0+{start}c", f"1.0+{end}c")
            
        text_widget.tag_config("link", foreground="#4a90d9", underline=1)
        
        def _on_click(event):
            idx = text_widget.index(f"@{event.x},{event.y}")
            tags = text_widget.tag_names(idx)
            if "link" in tags:
                ranges = text_widget.tag_ranges("link")
                for i in range(0, len(ranges), 2):
                    if text_widget.compare(ranges[i], "<=", idx) and text_widget.compare(idx, "<=", ranges[i+1]):
                        url = text_widget.get(ranges[i], ranges[i+1])
                        if url.startswith("www."):
                            url = "http://" + url
                        import webbrowser
                        webbrowser.open(url)
                        break

        def _on_enter(event):
            text_widget.config(cursor="hand2")
        def _on_leave(event):
            text_widget.config(cursor="xterm")
            
        text_widget.tag_bind("link", "<Button-1>", _on_click)
        text_widget.tag_bind("link", "<Enter>", _on_enter)
        text_widget.tag_bind("link", "<Leave>", _on_leave)

    def _show_record(self):
        for child in self._fields_frame.winfo_children():
            child.destroy()
        total = len(self._filtered)
        full_total = len(self.working_data)
        if self._search_text:
            self._record_label.configure(text=f"Record {self._filtered_pos + 1} of {total}  (filtered from {full_total})")
        else:
            self._record_label.configure(text=f"Record {self._filtered_pos + 1} of {total}")
        self._prev_btn.configure(state=tk.NORMAL if self._filtered_pos > 0 else tk.DISABLED)
        self._next_btn.configure(state=tk.NORMAL if self._filtered_pos < total - 1 else tk.DISABLED)
        self._record_dirty = False
        self._record_snapshot = None
        self._set_locked(False)
        if total == 0:
            tk.Label(self._fields_frame, text="(No matching records)", font=(FONT, 11),
                     bg=WHITE, fg=TEXT_MUTED).pack(pady=30)
            self._entry_widgets = {}
            return
        import copy
        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]
        self._record_snapshot = copy.deepcopy(record)
        self._entry_widgets = {}

        def _render_fields(parent_frame, data_dict, prefix_path=()):
            items = list(data_dict.items())
            items.sort(key=lambda x: 1 if x[0] == 'summary' else 0)
            for field_name, raw_value in items:
                current_path = prefix_path + (field_name,)
                if isinstance(raw_value, dict):
                    hf = tk.Frame(parent_frame, bg=WHITE)
                    hf.pack(fill=tk.X, padx=16 if not prefix_path else 0, pady=(12, 4))
                    tk.Label(hf, text=field_name.upper(), font=(FONT, 10, "bold"), bg=WHITE, fg=ACCENT).pack(side=tk.LEFT, padx=(16 if not prefix_path else 0, 0))
                    sub_frame = tk.Frame(parent_frame, bg=WHITE)
                    sub_frame.pack(fill=tk.X, padx=(32, 0), pady=0)
                    _render_fields(sub_frame, raw_value, current_path)
                else:
                    rf = tk.Frame(parent_frame, bg=WHITE)
                    rf.pack(fill=tk.X, padx=16 if not prefix_path else 0, pady=4)
                    label_width = 24 if not prefix_path else 22
                    tk.Label(rf, text=f"{field_name}", font=(FONT, 10), bg=WHITE, fg=TEXT_DARK,
                             width=label_width, anchor=tk.E).pack(side=tk.LEFT, padx=(0, 10))
                    # Format list values (e.g. youtube_links) as newline-separated text
                    if isinstance(raw_value, list):
                        dv = "\n".join(str(item) for item in raw_value)
                    else:
                        dv = str(raw_value) if raw_value is not None else ""
                    is_editable = prefix_path and (prefix_path[0] == "derived_details" or field_name == "service_status")
                    entry_font = (FONT, 12) if is_editable else (FONT, 10)
                    if not is_editable:
                        entry = _styled_entry(rf, width=42, font=entry_font)
                        entry.insert(0, dv)
                        entry.configure(state="readonly", readonlybackground="#f0f0f0", fg=TEXT_MUTED)
                        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    else:
                        if field_name in ("circumstances_of_death", "summary"):
                            text_height = 3 if field_name == "summary" else 4
                            entry = tk.Text(rf, font=entry_font, height=text_height, width=42, wrap=tk.WORD,
                                            bg=WHITE, fg=TEXT_DARK, relief=tk.FLAT, 
                                            highlightbackground=BORDER, highlightcolor=ACCENT, 
                                            highlightthickness=1, insertbackground=TEXT_DARK)
                            entry.insert("1.0", dv)
                            
                            def _on_text_edited(_e, tw=entry):
                                self._on_field_edited()
                                self._apply_hotlinks(tw)
                                
                            entry.bind("<KeyRelease>", _on_text_edited)
                            self._apply_hotlinks(entry)
                            entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=4)
                        elif isinstance(raw_value, list):
                            # youtube_links or other list fields: multi-line text, one URL per line
                            text_height = 3
                            entry = tk.Text(rf, font=entry_font, height=text_height, width=42, wrap=tk.WORD,
                                            bg=WHITE, fg=TEXT_DARK, relief=tk.FLAT,
                                            highlightbackground=BORDER, highlightcolor=ACCENT,
                                            highlightthickness=1, insertbackground=TEXT_DARK)
                            entry.insert("1.0", dv)

                            def _on_list_edited(_e, tw=entry):
                                self._on_field_edited()
                                self._apply_hotlinks(tw)

                            entry.bind("<KeyRelease>", _on_list_edited)
                            self._apply_hotlinks(entry)
                            entry.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, pady=4)
                        elif field_name and any(kw in field_name.lower() for kw in ('gps', 'coordinate', 'grid')):
                            entry = _styled_entry(rf, width=42, font=entry_font)
                            entry.insert(0, dv)
                            
                            def _update_link_style(*args, w=entry):
                                val_str = w.get().strip()
                                if val_str:
                                    is_valid, _, parsed = validate_and_parse_coordinate(val_str)
                                    if is_valid and parsed is not None:
                                        fnt = list(entry_font)
                                        fnt.append("underline")
                                        w.configure(fg="#4a90d9", font=tuple(fnt), cursor="hand2")
                                        return
                                w.configure(fg=TEXT_DARK, font=entry_font, cursor="xterm")
                                
                            _update_link_style()
                            entry.bind("<KeyRelease>", lambda e, w=entry: (_update_link_style(), self._on_field_edited()))
                            
                            def _open_map(event, w=entry):
                                val_str = w.get().strip()
                                if val_str:
                                    is_valid, _, parsed = validate_and_parse_coordinate(val_str)
                                    if is_valid and parsed is not None:
                                        import webbrowser
                                        webbrowser.open(f"https://www.google.com/maps?q={parsed[0]},{parsed[1]}")
                                        
                            entry.bind("<Double-Button-1>", _open_map)
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                        else:
                            entry = _styled_entry(rf, width=42, font=entry_font)
                            entry.insert(0, dv)
                            entry.bind("<KeyRelease>", lambda _e: self._on_field_edited())
                            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    self._entry_widgets[current_path] = entry

        _render_fields(self._fields_frame, record)
        tk.Frame(self._fields_frame, bg=WHITE, height=8).pack()
        
        self.update_idletasks()
        self._canvas.yview_moveto(0)

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
        self._search_entry.configure(state=state)
        if locked:
            self._lock_frame.pack(fill=tk.X, pady=(0, 6), before=self._card)
        else:
            self._lock_frame.pack_forget()

    # ------------------------------------------------------------------
    # Per-record actions
    # ------------------------------------------------------------------

    def _read_form(self) -> dict | None:
        if not self._entry_widgets:
            return {}
        actual_idx = self._filtered[self._filtered_pos]
        original = self.working_data[actual_idx]
        
        import copy
        result = copy.deepcopy(original)
        
        for path_tuple, entry in self._entry_widgets.items():
            if isinstance(entry, tk.Text):
                raw_value = entry.get("1.0", "end-1c")
            else:
                raw_value = entry.get()
            
            orig_val = original
            for key in path_tuple:
                if isinstance(orig_val, dict):
                    orig_val = orig_val.get(key, "")
                else:
                    orig_val = ""
                    
            field_name = path_tuple[-1]
            is_editable = len(path_tuple) > 0 and (path_tuple[0] == "derived_details" or field_name == "service_status")
            
            if not is_editable:
                val = orig_val
            else:
                try:
                    if isinstance(orig_val, bool):
                        val_str = raw_value.strip().lower()
                        if val_str in ("true", "1", "yes"):
                            val = True
                        elif val_str in ("false", "0", "no", ""):
                            val = False
                        else:
                            raise ValueError(f"'{raw_value}' is not a valid boolean")
                    elif isinstance(orig_val, int):
                        val = int(raw_value.strip())
                    elif isinstance(orig_val, float):
                        val = float(raw_value.strip())
                    elif isinstance(orig_val, list):
                        # Parse newline-separated text back to list (e.g. youtube_links)
                        lines = raw_value.strip().split("\n")
                        val = [line.strip() for line in lines if line.strip()]
                    else:
                        val = raw_value
                        
                        # Apply coordinate GPS validation (skip non-coordinate placeholders)
                        if field_name and any(kw in field_name.lower() for kw in ('gps', 'coordinate', 'grid')):
                            val_str = str(val).strip()
                            if val_str and not re.match(r'^[A-Za-z]+$', val_str):
                                is_valid, msg, parsed = validate_and_parse_coordinate(val_str)
                                if not is_valid:
                                    _error_dialog(self, "Invalid Coordinate Format", msg)
                                    return None
                                if parsed is not None:
                                    val = f"{parsed[0]}, {parsed[1]}"
                                else:
                                    val = val_str

                except (ValueError, TypeError) as exc:
                    _error_dialog(self, "Type Error",
                                  f"Field '{'.'.join(path_tuple)}': '{raw_value}' does not match "
                                  f"expected type ({type(orig_val).__name__}).\n\n{exc}")
                    return None
                    
            target = result
            for key in path_tuple[:-1]:
                if key not in target or not isinstance(target[key], dict):
                    target[key] = {}
                target = target[key]
            target[path_tuple[-1]] = val
            
        return result

    def _update_record(self):
        updated = self._read_form()
        if updated is None:
            return
        record_id = updated.get("referenceID", str(self._filtered_pos + 1))
        ok = _confirm_yesno(self, "Confirm Update", f'Please confirm update for "{record_id}"')
        if not ok:
            return
        actual_idx = self._filtered[self._filtered_pos]
        self.working_data[actual_idx] = updated
        if not _save_json(self.file_path, self.working_data):
            return
        self.original_data.clear()
        self.original_data.extend(self.working_data)
        self.dirty = False
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
    # Navigation
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
    # Side panel
    # ------------------------------------------------------------------

    def _show_side_panel(self):
        self._side_panel.pack(side=tk.LEFT, fill=tk.Y, pady=16, after=self.winfo_children()[0].winfo_children()[0])

    def _hide_side_panel(self):
        self._side_panel.pack_forget()

    # ------------------------------------------------------------------
    # AI Lookup
    # ------------------------------------------------------------------

    def _ai_lookup(self):
        if not self._filtered:
            return

        is_live_search = self._live_search_var.get()
        confirm_msg = f"Proceed with AI Lookup?\n\nLive Search Grounding is currently: {'ON' if is_live_search else 'OFF'}"
        if not _confirm_yesno(self, "Confirm AI", confirm_msg):
            return

        actual_idx = self._filtered[self._filtered_pos]
        record = self.working_data[actual_idx]

        # Read from serviceRecordAuthority (the authoritative source)
        sra = record.get("serviceRecordAuthority", {}) if isinstance(record.get("serviceRecordAuthority"), dict) else {}
        svc = sra.get("service_number", "")
        name = sra.get("full_name", "")
        dob = sra.get("date_of_birth", "")
        dod = sra.get("date_of_death", "")
        rank = sra.get("rank", "")
        unit = sra.get("unit", "")

        # Derive Armed Forces from referenceID prefix (AU / NZ)
        ref_id = record.get("referenceID", "")
        forces_map = {"AU": "Australian Armed Forces", "NZ": "New Zealand Armed Forces"}
        af = forces_map.get(ref_id[:2], ref_id[:2] if ref_id else "")

        # Read derived_details
        dd = record.get("derived_details", {}) if isinstance(record.get("derived_details"), dict) else {}
        pod = dd.get("place_of_death", "")
        ftype = sra.get("fatality_type", "")

        # Use the detailed archivist prompt for testing datasets
        if "testing" in self.file_path.lower():
            country_map = {"AU": "Australia", "NZ": "New Zealand"}
            country = country_map.get(ref_id[:2], "")
            user_prompt = (
                f"As a military archivist / historian researching the detailed story behind the death of this soldier in the Vietnam War, "
                f"I require you to do deep research and complete as much as possible of the extra_derived_data output fields. It is imperative you approach this task to help paint a picture of all personal and tactical events surrounding his death.\n"
                f"You will be provided the following input values to identify the soldier to be researched. If an input value is blank then ignore it in the research:\n"
                f"country = {country}\n"
                f"service number = {svc}\n"
                f"service status = {sra.get('service_status', '')}\n"
                f"full name = {name}\n"
                f"sex = {sra.get('sex', '')}\n"
                f"date of death = {dod}\n"
                f"date of birth = {dob}\n"
                f"rank = {rank}\n"
                f"unit = {unit}\n"
                f"fatality type = {ftype}\n"
                f"Using ONLY these values, produce the JSON structure below.\n"
                f"Fill all fields using the provided values and best-effort military-archivist historical reconstruction.\n"
                f"If a field cannot be determined, leave it empty.\n"
                f"YouTube references must be historically credible and directly relevant.\n"
                f"DERIVED FIELD \"1_unit_served_with\":\n"
                f"Create a single-line summary by joining all NON-EMPTY hierarchy elements from \"extra_unit_served_with\" in the following order:\n"
                f"country, service, corps_or_branch, command_or_division, brigade_or_group, regiment_or_battalion, sub_unit, platoon_or_troop, section_or_squad, team_or_crew\n"
                f"Separate each element with \", \" and skip empty fields.\n"
                f"Example:\n"
                f"\"Australia, Australian Army, Royal Australian Infantry Corps, 1ATF, 4RAR, B Company, 5 Platoon\"\n"
                f"DERIVED DATA REQUIREMENTS:\n"
                f"2. Identify the military operation underway at the time of death.\n"
                f"3. Provide a full operational and tactical setting including mission objectives, terrain, enemy situation, friendly force disposition, and a narrative summary.\n"
                f"4. State the cause of death.\n"
                f"5. Provide the exact or approximate grid reference.\n"
                f"6. Identify the map sheet number and UTM zone.\n"
                f"7. Provide a detailed location description.\n"
                f"8. Reconstruct the unit's movements in the 48 hours prior.\n"
                f"9. List any AARs, war diaries, contact reports, or casualty reports.\n"
                f"10. Identify others killed or wounded in the same incident.\n"
                f"11. Provide burial and repatriation details.\n"
                f"12. Identify the tank/APC track, fire support base, patrol route, or engineer lane involved.\n"
                f"13. If the exact grid is unavailable, provide the most probable grid and archival sources.\n"
                f"14. Provide notes on accuracy and confidence level.\n"
                f"15. Search for relevant YouTube videos and return them as:\n\n"
                f"[\n"
                f"  {{\n"
                f"    \"title\": \"\",\n"
                f"    \"url\": \"\",\n"
                f"    \"relevance_reason\": \"\"\n"
                f"  }}\n"
                f"]\n"
                f"Only include historically credible and directly relevant videos.\n"
                f"OUTPUT FORMAT:\n"
                f"{{\n"
                f"  \"full_name\": \"\",\n"
                f"  \"extra_unit_served_with\": {{\n"
                f"    \"country\": \"\",\n"
                f"    \"service\": \"\",\n"
                f"    \"corps_or_branch\": \"\",\n"
                f"    \"command_or_division\": \"\",\n"
                f"    \"brigade_or_group\": \"\",\n"
                f"    \"regiment_or_battalion\": \"\",\n"
                f"    \"sub_unit\": \"\",\n"
                f"    \"platoon_or_troop\": \"\",\n"
                f"    \"section_or_squad\": \"\",\n"
                f"    \"team_or_crew\": \"\"\n"
                f"  }},\n"
                f"  \"extra_derived_data\": {{\n"
                f"    \"1_unit_served_with\": \"\",\n"
                f"    \"2_operation_name\": \"\",\n"
                f"    \"3_operational_tactical_setting\": \"\",\n"
                f"    \"4_cause_of_death\": \"\",\n"
                f"    \"5_grid_reference\": \"\",\n"
                f"    \"6_map_sheet_or_utm_zone\": \"\",\n"
                f"    \"7_location_description\": \"\",\n"
                f"    \"8_unit_movements_prior_48hrs\": \"\",\n"
                f"    \"9_associated_AARs_or_war_diaries\": \"\",\n"
                f"    \"10_related_casualties\": \"\",\n"
                f"    \"11_burial_and_repatriation\": \"\",\n"
                f"    \"12_tank_APC_track_FSB_patrol_route_engineer_lane\": \"\",\n"
                f"    \"13_probable_grid_and_archival_sources\": \"\",\n"
                f"    \"14_notes_on_accuracy\": \"\",\n"
                f"    \"15_youtube_references\": []\n"
                f"  }}\n"
                f"}}"
            )
        else:
            user_prompt = (
                "Using the values I provide in the placeholders below, generate a detailed narrative focused only on:\n\n"
                "1. The circumstances of death, clearly separated into:\n"
                "   - confirmed facts\n"
                "   - details supported by official or semi-official sources\n"
                "   - reasonable inference based on context\n"
                "   - what remains unknown\n\n"
                "2. The best available approximation of the place of death, using one of the following (whichever is most appropriate or best supported by sources):\n"
                "   - GPS latitude/longitude\n"
                "   - UTM coordinates\n"
                "   - MGRS grid reference\n\n"
                "If the exact location is not documented, provide the closest verifiable location (such as a base, town, road, or landmark) and explain why this is the most accurate approximation.\n\n"
                "3. The individual's pre-service occupation, as recorded in official enlistment or memorial records.\n\n"
                "4. The enlistment type: whether they were a Regular soldier or a Conscript (e.g., National Service, Draft, or similar).\n\n"
                "Use only the values I supply.\n"
                "Do not invent or alter identity details.\n"
                "Present the answer in normal text, not structured data.\n\n"
                "Identity anchor values:\n\n"
                f"- Service Number: {svc}\n"
                f"- Full Name: {name}\n"
                f"- Date of Birth: {dob}\n"
                f"- Date of Death: {dod}\n"
                f"- Armed Forces: {af}\n"
                f"- Rank: {rank}\n"
                f"- Unit: {unit}\n"
                f"- Place of Death: {pod}\n"
                "- Fatality Type: *[leave blank for the model to determine from records]*"
            )

        env = {}
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    env[k.strip()] = v.strip().strip('"').strip("'")

        api_key = env.get("GEMINI_API_KEY", "")
        models_str = env.get("GEMINI_TEXT_TO_TEXT_MODELS_TO_USE", "gemini-2.5-flash")
        models = [m.strip() for m in models_str.split(",") if m.strip()]

        if not api_key:
            _error_dialog(self, "AI Error", "GEMINI_API_KEY not found in .env")
            return

        # Show side panel with prompt, loading response
        self._side_prompt.configure(state=tk.NORMAL)
        self._side_prompt.delete("1.0", tk.END)
        self._side_prompt.insert("1.0", user_prompt)
        self._side_resp.delete("1.0", tk.END)
        self._show_side_panel()

        def _task():
            last_error = ""
            is_testing = "testing" in self.file_path.lower()
            for model in models:
                self.after(0, lambda m=model: self._side_resp_replace(f"Using {m} to get additional details...."))
                try:
                    url = (f"https://generativelanguage.googleapis.com/v1beta/models/"
                           f"{model}:generateContent?key={api_key}")
                    # Use appropriate system instruction and token budget
                    if is_testing:
                        system_text = (
                            "You are a military archivist and historian specializing in the Vietnam War. "
                            "You produce structured JSON output from provided soldier identity values. "
                            "You always return valid, parseable JSON exactly matching the requested schema."
                        )
                        max_tokens = 8192
                    else:
                        system_text = "I am a highly skilled historian."
                        max_tokens = 2048
                    payload = {
                        "systemInstruction": {"parts": [{"text": system_text}]},
                        "contents": [{"parts": [{"text": user_prompt}]}],
                        "generationConfig": {"temperature": 0.3, "maxOutputTokens": max_tokens},
                    }
                    if is_live_search:
                        payload["tools"] = [{"google_search": {}}]
                        
                    body = json.dumps(payload).encode("utf-8")
                    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                    with urllib.request.urlopen(req, timeout=60) as resp:
                        data = json.loads(resp.read().decode("utf-8"))
                        content = data["candidates"][0]["content"]["parts"][0]["text"]
                    # For testing: strip markdown fences and pretty-print JSON
                    if is_testing:
                        content = self._extract_json(content)
                    self.after(0, lambda c=content: self._side_resp_replace(c))
                    return
                except Exception as exc:
                    last_error = f"{model}: {exc}"
                    continue
            self.after(0, lambda: self._side_resp_replace(f"All models failed.\n\n{last_error}"))

        threading.Thread(target=_task, daemon=True).start()

    def _extract_json(self, text: str) -> str:
        """Strip markdown code fences and pretty-print JSON if possible."""
        import re as _re
        # Remove ```json ... ``` or ``` ... ``` fences
        cleaned = _re.sub(r'```(?:json)?\s*\n?', '', text)
        cleaned = _re.sub(r'```\s*$', '', cleaned)
        cleaned = cleaned.strip()
        # Try to parse and pretty-print
        try:
            parsed = json.loads(cleaned)
            return json.dumps(parsed, indent=2, ensure_ascii=False)
        except (json.JSONDecodeError, ValueError):
            return text  # Return original if not valid JSON

    def _side_resp_replace(self, text: str):
        self._side_resp.delete("1.0", tk.END)
        self._side_resp.insert("1.0", text)

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
            self.working_data[self._filtered[self._filtered_pos]] = updated
            self._record_dirty = False
            self._set_locked(False)
        if not _save_json(self.file_path, self.working_data):
            return
        self.original_data.clear()
        self.original_data.extend(self.working_data)
        self.dirty = False
        self._show_record()

    def _cancel(self):
        if self._record_dirty:
            ok = _confirm_yesno(self, "Discard Changes?",
                                "You have unsaved changes.\nClose and discard all changes?")
            if not ok:
                return
        self.destroy()
