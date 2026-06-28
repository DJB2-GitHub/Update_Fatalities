"""Fatalities Editor — Tkinter desktop application (modern flat-design).

Reads .env for FATALITY_FILE_DIRECTORY and FILES_AVAILABLE_FOR_UPDATE,
displays a Main Menu modal, then opens a selected file in the
update_fatalities modal. Key fields (id) are read-only.
The app guards against quitting with unsaved changes.
"""

from __future__ import annotations

import json
import os
import tkinter as tk
from tkinter import ttk

from update_fatalities import UpdateFatalities

# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

RED_PRIMARY   = "#c63f3f"
RED_DEEP      = "#a53434"
BG_GREY       = "#f5f5f5"
WHITE         = "#ffffff"
TEXT_DARK     = "#333333"
TEXT_MUTED    = "#888888"
FONT_FAMILY   = "Segoe UI"

ENV_PATH = ".env"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_env(path: str = ENV_PATH) -> dict[str, str]:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as fh:
        result = {
            line.partition("=")[0].strip(): line.partition("=")[2].strip().strip('"').strip("'")
            for line in (l.strip() for l in fh)
            if line and not line.startswith("#") and "=" in line
        }
    os.environ.update(result)
    return result


def _make_datasets(env: dict[str, str], directory: str, env_key: str) -> dict[str, str]:
    """Build {label: full_path} from a comma-separated env value."""
    return {
        os.path.splitext(f.strip())[0]: os.path.join(directory, f.strip())
        for f in env.get(env_key, "").split(",") if f.strip()
    }


def load_config() -> dict[str, dict[str, str]]:
    env = _read_env()
    directory = env.get("FATALITY_FILE_DIRECTORY", "")

    if not directory:
        _show_error("FATALITY_FILE_DIRECTORY not found in .env")
        return {}

    live = _make_datasets(env, directory, "FILES_AVAILABLE_FOR_UPDATE")

    if not live:
        _show_error("No datasets configured (FILES_AVAILABLE_FOR_UPDATE).")
        return {}

    return {"live": live}


def load_json(path: str) -> list[dict] | None:
    if not os.path.exists(path):
        _show_error(f"'{path}' does not exist.")
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        _show_error(f"'{path}' is not valid JSON.\n{exc}")
        return None
    if not isinstance(data, list):
        _show_error(f"'{path}' must contain a JSON array.")
        return None
    return data


def save_json(path: str, data: list[dict]) -> bool:
    try:
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)
        return True
    except OSError as exc:
        _show_error(f"Could not write '{path}'.\n{exc}")
        return False


# ---------------------------------------------------------------------------
# Custom styled modals (replace messagebox)
# ---------------------------------------------------------------------------

def _show_error(message: str):
    """Custom error dialog."""
    StyledDialog(None, "Error", message, icon="error", buttons=[("OK", None)])


def _ask_yes_no_cancel(parent: tk.Tk, title: str, message: str) -> bool | None:
    """Custom yes/no/cancel. Returns True/False/None."""
    dialog = StyledDialog(
        parent, title, message, icon="warning",
        buttons=[("Yes", True), ("No", False), ("Cancel", None)],
    )
    return dialog.result


def _ask_yes_no(parent: tk.Tk, title: str, message: str) -> bool:
    """Custom yes/no. Returns True/False."""
    dialog = StyledDialog(
        parent, title, message, icon="question",
        buttons=[("Yes", True), ("No", False)],
    )
    return dialog.result


class StyledDialog(tk.Toplevel):
    """Flat-design modal dialog replacing tkinter messagebox."""

    def __init__(self, parent, title: str, message: str, *,
                 icon: str = "info", buttons: list[tuple[str, object]]):
        super().__init__(parent)
        self.result: object = None
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=WHITE)

        if parent:
            self.transient(parent)
            self._centre(parent)
        else:
            self._centre_on_screen()
        self.grab_set()

        # Icon + message area
        top = tk.Frame(self, bg=WHITE)
        top.pack(fill=tk.X, padx=24, pady=(24, 12))

        icon_colours = {"error": RED_PRIMARY, "warning": "#e6a817", "question": "#3b82f6", "info": "#6b7280"}
        colour = icon_colours.get(icon, "#6b7280")

        canvas = tk.Canvas(top, width=36, height=36, bg=WHITE, highlightthickness=0)
        canvas.pack(side=tk.LEFT, padx=(0, 16))
        if icon == "error":
            canvas.create_oval(4, 4, 32, 32, fill=colour, outline="")
            canvas.create_line(12, 12, 24, 24, fill=WHITE, width=3)
            canvas.create_line(24, 12, 12, 24, fill=WHITE, width=3)
        elif icon == "warning":
            canvas.create_polygon(18, 4, 32, 30, 4, 30, fill=colour, outline="")
            canvas.create_text(18, 22, text="!", fill=WHITE, font=(FONT_FAMILY, 14, "bold"))
        elif icon == "question":
            canvas.create_oval(4, 4, 32, 32, fill=colour, outline="")
            canvas.create_text(18, 18, text="?", fill=WHITE, font=(FONT_FAMILY, 14, "bold"))
        else:
            canvas.create_oval(4, 4, 32, 32, fill=colour, outline="")
            canvas.create_text(18, 18, text="i", fill=WHITE, font=(FONT_FAMILY, 14, "bold"))

        msg_lbl = tk.Label(
            top, text=message, bg=WHITE, fg=TEXT_DARK,
            font=(FONT_FAMILY, 10), justify=tk.LEFT, wraplength=380,
        )
        msg_lbl.pack(side=tk.LEFT)

        # Separator
        ttk.Separator(self, orient=tk.HORIZONTAL).pack(fill=tk.X)

        # Buttons
        btn_frame = tk.Frame(self, bg=WHITE)
        btn_frame.pack(fill=tk.X, padx=16, pady=12)

        for idx, (text, value) in enumerate(reversed(buttons)):
            is_primary = (value is True) or (value is not None and idx == 0)
            bg = RED_PRIMARY if is_primary else WHITE
            fg = WHITE if is_primary else TEXT_DARK
            hover_bg = RED_DEEP if is_primary else BG_GREY

            btn = tk.Frame(btn_frame, bg=bg, cursor="hand2")
            btn.pack(side=tk.RIGHT, padx=4)

            lbl = tk.Label(
                btn, text=text, bg=bg, fg=fg,
                font=(FONT_FAMILY, 10), padx=18, pady=6,
            )
            lbl.pack()

            # Hover effects
            lbl._orig_bg = bg
            lbl._orig_fg = fg
            lbl._hover_bg = hover_bg
            lbl._hover_fg = WHITE if not is_primary else WHITE
            btn._orig_bg = bg

            lbl.bind("<Enter>", lambda e, b=btn, l=lbl: self._on_hover(e, b, l))
            lbl.bind("<Leave>", lambda e, b=btn, l=lbl: self._on_leave(e, b, l))
            lbl.bind("<Button-1>", lambda e, v=value: self._choose(v))

        self.protocol("WM_DELETE_WINDOW", lambda: self._choose(None))
        self.wait_window()

    def _on_hover(self, event, btn_frame, label):
        btn_frame.configure(bg=label._hover_bg)
        label.configure(bg=label._hover_bg, fg=label._hover_fg)

    def _on_leave(self, event, btn_frame, label):
        btn_frame.configure(bg=label._orig_bg)
        label.configure(bg=label._orig_bg, fg=label._orig_fg)

    def _choose(self, value):
        self.result = value
        self.destroy()

    def _centre(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _centre_on_screen(self):
        self.update_idletasks()
        w, h = self.winfo_width(), self.winfo_height()
        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x = (sw - w) // 2
        y = (sh - h) // 2
        self.geometry(f"+{x}+{y}")


# ---------------------------------------------------------------------------
# Help Viewer Modal
# ---------------------------------------------------------------------------

class HelpViewer(tk.Toplevel):
    def __init__(self, parent):
        super().__init__(parent)
        self.title("Help / README")
        self.geometry("800x600")
        self.configure(bg=WHITE)
        self.transient(parent)

        self.update_idletasks()
        x = (self.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.winfo_screenheight() // 2) - (600 // 2)
        self.geometry(f'+{x}+{y}')
        self.grab_set()

        header = tk.Frame(self, bg=RED_PRIMARY, height=60)
        header.pack(fill=tk.X)
        
        lbl = tk.Label(header, text="Search Help:", bg=RED_PRIMARY, fg=WHITE, font=(FONT_FAMILY, 11, "bold"))
        lbl.pack(side=tk.LEFT, padx=(20, 10), pady=15)
        
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", self._on_search)
        search_entry = tk.Entry(header, textvariable=self.search_var, font=(FONT_FAMILY, 11), width=40)
        search_entry.pack(side=tk.LEFT, pady=15)
        
        text_frame = tk.Frame(self, bg=WHITE)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        self.text_w = tk.Text(text_frame, font=(FONT_FAMILY, 10), wrap=tk.WORD, 
                              relief=tk.FLAT, bg="#f9f9f9", fg=TEXT_DARK, padx=10, pady=10)
        
        scrollbar = ttk.Scrollbar(text_frame, command=self.text_w.yview)
        self.text_w.configure(yscrollcommand=scrollbar.set)
        
        self.text_w.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.text_w.tag_configure("search", background="#ffeb3b", foreground="black")
        self.text_w.tag_configure("h1", font=(FONT_FAMILY, 16, "bold"), foreground=RED_PRIMARY, spacing1=10, spacing3=10)
        self.text_w.tag_configure("h2", font=(FONT_FAMILY, 14, "bold"), foreground=RED_DEEP, spacing1=8, spacing3=8)
        self.text_w.tag_configure("h3", font=(FONT_FAMILY, 12, "bold"), spacing1=5, spacing3=5)
        
        self._load_readme()
        
    def _load_readme(self):
        readme_path = "README.md"
        if not os.path.exists(readme_path):
            self.text_w.insert(tk.END, "README.md not found.")
            self.text_w.configure(state=tk.DISABLED)
            return
            
        with open(readme_path, "r", encoding="utf-8") as f:
            content = f.read()
            
        self.text_w.insert(tk.END, content)
        
        import re
        for match in re.finditer(r'^#\s+(.+)$', content, re.MULTILINE):
            self.text_w.tag_add("h1", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        for match in re.finditer(r'^##\s+(.+)$', content, re.MULTILINE):
            self.text_w.tag_add("h2", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
        for match in re.finditer(r'^###\s+(.+)$', content, re.MULTILINE):
            self.text_w.tag_add("h3", f"1.0 + {match.start()} chars", f"1.0 + {match.end()} chars")
            
        self.text_w.configure(state=tk.DISABLED)
        
    def _on_search(self, *args):
        query = self.search_var.get().lower()
        self.text_w.tag_remove("search", "1.0", tk.END)
        
        if not query:
            return
            
        start_idx = "1.0"
        first_match = None
        while True:
            start_idx = self.text_w.search(query, start_idx, nocase=True, stopindex=tk.END)
            if not start_idx:
                break
            if not first_match:
                first_match = start_idx
                
            end_idx = f"{start_idx} + {len(query)} chars"
            self.text_w.tag_add("search", start_idx, end_idx)
            start_idx = end_idx
            
        if first_match:
            self.text_w.see(first_match)

# ---------------------------------------------------------------------------
# Main Menu modal
# ---------------------------------------------------------------------------

class MainMenu(tk.Toplevel):
    """Flat-design modal with dataset choices and Quit."""

    def __init__(self, parent: tk.Tk, datasets: dict[str, str], on_update, on_quit):
        super().__init__(parent)
        self.title("Fatalities Editor")
        self.resizable(False, False)
        self.configure(bg=WHITE)

        self._on_update = on_update
        self._on_quit = on_quit
        self._buttons_locked = False   # guard to prevent clicks while modal is open

        self.protocol("WM_DELETE_WINDOW", self._quit)

        # Minimize / restore parent together with this modal
        self.bind("<Unmap>", self._on_unmap)
        self.bind("<Map>", self._on_map)
        # When parent is restored from taskbar, restore this modal too
        self._on_parent_map_id = parent.bind("<Map>", self._on_parent_map, add=True)

        self._build(datasets)
        self._centre(parent)
        self.grab_set()

    def _build(self, datasets: dict[str, dict[str, str]]):
        # Header
        header = tk.Frame(self, bg=RED_PRIMARY, height=56)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        title_lbl = tk.Label(
            header, text="Fatalities Editor", bg=RED_PRIMARY, fg=WHITE,
            font=(FONT_FAMILY, 16, "bold"),
        )
        title_lbl.pack(side=tk.LEFT, padx=20, pady=12)

        about_lbl = tk.Label(
            header, text="\u2139", bg=RED_PRIMARY, fg=WHITE,
            font=(FONT_FAMILY, 16, "bold"), cursor="hand2"
        )
        about_lbl.pack(side=tk.RIGHT, padx=20, pady=12)
        about_lbl.bind("<Button-1>", lambda e: self.show_about())

        help_lbl = tk.Label(
            header, text="?", bg=RED_PRIMARY, fg=WHITE,
            font=(FONT_FAMILY, 16, "bold"), cursor="hand2"
        )
        help_lbl.pack(side=tk.RIGHT, padx=(0, 10), pady=12)
        help_lbl.bind("<Button-1>", lambda e: self.show_help())

        # Body
        body = tk.Frame(self, bg=WHITE, padx=24, pady=20)
        body.pack(fill=tk.BOTH, expand=True)

        self._all_buttons = []

        heading_lbl = tk.Label(
            body, text="Live OnThis Day app", bg=WHITE, fg=TEXT_DARK,
            font=(FONT_FAMILY, 12, "bold"),
        )
        heading_lbl.pack(anchor="w", pady=(8, 4))

        for label, file_path in datasets.get("live", {}).items():
            btn = self._flat_button(body, f"  Update {label}", self._update, file_path)
            btn.pack(fill=tk.X, pady=3)

        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(16, 12))

        backup_btn = self._flat_button(body, "  Backup Fatalities.json to folder for OneDrive sync", lambda _e: self._backup_files(), None)
        backup_btn.pack(fill=tk.X, pady=3)

        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(12, 12))

        quit_btn = self._flat_button(body, "  Quit", lambda _e: self._quit(), None, is_danger=False)
        quit_btn.pack(fill=tk.X, pady=3)

    def show_help(self):
        HelpViewer(self)

    def show_about(self):
        about_win = tk.Toplevel(self)
        about_win.title("About")
        about_win.geometry("450x540")
        about_win.configure(bg="white")
        about_win.resizable(False, False)
        about_win.transient(self)

        about_win.update_idletasks()
        x = (about_win.winfo_screenwidth() // 2) - (450 // 2)
        y = (about_win.winfo_screenheight() // 2) - (540 // 2)
        about_win.geometry(f'+{x}+{y}')
        about_win.grab_set()

        header = tk.Frame(about_win, bg="#1A237E", height=60)
        header.pack(fill=tk.X)
        tk.Label(header, text="APPLICATION INFORMATION", font=("Helvetica", 10, "bold"), 
                 bg="#1A237E", fg="white").pack(pady=20)

        content = tk.Frame(about_win, bg="white", padx=30, pady=20)
        content.pack(fill=tk.BOTH, expand=True)
        tk.Label(content, text="Update Fatalities", font=("Helvetica", 18, "bold"), 
                 bg="white", fg="#1A237E", wraplength=380).pack(pady=(0, 20))

        details = [
            ("AppName", "APPLICATION_NAME"),
            ("Developer", "DEVELOPER_NAME"),
            ("Email", "DEVELOPER_EMAIL"),
            ("Mobile", "DEVELOPER_MOBILE"),
            ("Release Date", "APP_ORIGINAL_RELEASE_DATE"),
            ("Version", "APP_VERSION"),
            ("Version Date", "APP_VERSION_DATE"),
        ]

        for label, env_key in details:
            val = os.environ.get(env_key, "N/A")
            if label == "Version Date" and val != "N/A":
                try:
                    from datetime import datetime
                    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                        try:
                            dt = datetime.strptime(val, fmt)
                            val = dt.strftime("%d-%b-%Y")
                            break
                        except ValueError:
                            continue
                except Exception:
                    pass
            row = tk.Frame(content, bg="white")
            row.pack(fill=tk.X, pady=4)
            tk.Label(row, text=f"{label}:", font=("Helvetica", 10, "bold"), 
                     bg="white", fg="#666666", width=15, anchor="w").pack(side=tk.LEFT)
            tk.Label(row, text=val, font=("Helvetica", 9), 
                     bg="white", fg="#333333").pack(side=tk.LEFT)

        # Extra info
        files = os.environ.get("FILES_AVAILABLE_FOR_UPDATE", "N/A")
        directory = os.environ.get("FATALITY_FILE_DIRECTORY", "N/A")
        extra = f'Used to maintain "derived_details" record details {files} in {directory}'
        row = tk.Frame(content, bg="white")
        row.pack(fill=tk.X, pady=4)
        tk.Label(row, text=extra, font=("Helvetica", 9), 
                 bg="white", fg="#333333", wraplength=380, justify=tk.LEFT, anchor="w").pack(side=tk.LEFT)

        tk.Button(about_win, text="CLOSE", command=about_win.destroy, bg="#1A237E", 
                  fg="white", font=("Helvetica", 10, "bold"), padx=30, pady=5, 
                  relief=tk.FLAT).pack(pady=20)

    def _flat_button(self, parent, text, command, user_data, is_danger=False):
        """Create a flat-design clickable button using a Frame + Label."""
        frame = tk.Frame(parent, bg=WHITE, cursor="hand2")
        lbl = tk.Label(
            frame, text=text, bg=WHITE, fg=TEXT_DARK if not is_danger else RED_PRIMARY,
            font=(FONT_FAMILY, 11), anchor="w", padx=14, pady=8,
            borderwidth=1, relief="solid",
        )
        lbl.pack(fill=tk.X)

        lbl._orig_bg = WHITE
        lbl._hover_bg = BG_GREY
        lbl._orig_fg = TEXT_DARK if not is_danger else RED_PRIMARY
        lbl._hover_fg = TEXT_DARK if not is_danger else RED_DEEP

        lbl.bind("<Enter>", lambda e, f=frame, l=lbl: self._on_hover(e, f, l))
        lbl.bind("<Leave>", lambda e, f=frame, l=lbl: self._on_leave(e, f, l))
        lbl.bind("<Button-1>", lambda e, d=user_data: command(d))

        self._all_buttons.append(frame)
        return frame

    def _on_hover(self, event, frame, label):
        frame.configure(bg=label._hover_bg)
        label.configure(bg=label._hover_bg, fg=label._hover_fg)

    def _on_leave(self, event, frame, label):
        frame.configure(bg=label._orig_bg)
        label.configure(bg=label._orig_bg, fg=label._orig_fg)

    def _update(self, arg):
        if self._buttons_locked:
            return  # prevent opening a second modal on top of an existing one
        if isinstance(arg, tuple):
            file_path, modal_title = arg
        else:
            file_path, modal_title = arg, None
        self._set_buttons_locked(True)
        try:
            self._on_update(file_path, modal_title)
        finally:
            self._set_buttons_locked(False)

    def _set_buttons_locked(self, locked: bool):
        """Disable / enable all buttons and show visual feedback."""
        self._buttons_locked = locked
        for btn in self._all_buttons:
            try:
                if not btn.winfo_exists():
                    continue
                for child in btn.winfo_children():
                    if locked:
                        child.configure(state=tk.DISABLED, cursor="watch")
                    else:
                        child.configure(state=tk.NORMAL, cursor="hand2")
            except tk.TclError:
                pass  # Tk instance destroyed, nothing to clean up

    def _on_unmap(self, event=None):
        """When this modal is minimised, minimise the parent too."""
        # Release grab so Windows allows the title-bar minimise to proceed
        try:
            self.grab_release()
        except Exception:
            pass
        self.after(100, self._sync_parent_iconify)

    def _sync_parent_iconify(self):
        try:
            if self.winfo_exists() and self.state() == 'iconic':
                parent = self.master
                if parent and parent.winfo_exists():
                    parent.iconify()
        except Exception:
            pass

    def _on_map(self, event=None):
        """When this modal is restored, restore the parent too."""
        # Re-establish grab that was released on minimise
        try:
            self.grab_set()
        except Exception:
            pass
        try:
            parent = self.master
            if parent and parent.winfo_exists() and parent.state() == 'iconic':
                parent.deiconify()
        except Exception:
            pass

    def _on_parent_map(self, event=None):
        """When the parent is restored (e.g. from taskbar), restore this modal too."""
        try:
            if self.winfo_exists() and self.state() == 'iconic':
                self.deiconify()
        except Exception:
            pass

    def destroy(self):
        """Clean up parent bindings before destroying."""
        try:
            self.master.unbind("<Map>", self._on_parent_map_id)
        except Exception:
            pass
        super().destroy()

    def _backup_files(self):
        """Copy AU/NZ Fatalities.json to OneDrive sync folder with timestamp.
        Keeps only the 3 most recent backups per file; deletes older ones."""
        import shutil
        import glob as _glob
        from datetime import datetime
        from tkinter import messagebox

        env = _read_env()
        backup_dir = env.get("BACKUP_FATALITIES_TO_ONEDRIVE_SYNC", "")
        if not backup_dir:
            messagebox.showerror("Backup Error", "BACKUP_FATALITIES_TO_ONEDRIVE_SYNC not found in .env")
            return

        src_dir = env.get("FATALITY_FILE_DIRECTORY", "")
        files_str = env.get("FILES_AVAILABLE_FOR_UPDATE", "")
        if not src_dir or not files_str:
            messagebox.showerror("Backup Error", "FATALITY_FILE_DIRECTORY or FILES_AVAILABLE_FOR_UPDATE missing in .env")
            return

        src_files = [f.strip() for f in files_str.split(",") if f.strip()]
        if not src_files:
            messagebox.showerror("Backup Error", "No source files configured in FILES_AVAILABLE_FOR_UPDATE")
            return

        # Ensure backup directory exists
        try:
            os.makedirs(backup_dir, exist_ok=True)
        except OSError as e:
            messagebox.showerror("Backup Error", f"Cannot create backup directory:\n{backup_dir}\n\n{e}")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        copied = []
        errors = []

        for filename in src_files:
            src_path = os.path.join(src_dir, filename)
            if not os.path.exists(src_path):
                errors.append(f"Source not found: {src_path}")
                continue

            base, ext = os.path.splitext(filename)
            dest_name = f"{base}_{timestamp}{ext}"
            dest_path = os.path.join(backup_dir, dest_name)

            try:
                shutil.copy2(src_path, dest_path)
                copied.append(dest_name)
            except OSError as e:
                errors.append(f"Copy failed for {filename}: {e}")
                continue

            # Prune old backups — keep only the 3 most recent for this base name
            pattern = os.path.join(backup_dir, f"{base}_*{ext}")
            existing = sorted(_glob.glob(pattern), reverse=True)
            for old in existing[3:]:
                try:
                    os.remove(old)
                except OSError:
                    pass

        # Build result message
        msg_parts = []
        if copied:
            msg_parts.append(f"Backed up {len(copied)} file(s) to:\n{backup_dir}\n")
            for name in copied:
                msg_parts.append(f"  \u2714 {name}")
        if errors:
            msg_parts.append("\nErrors:")
            for err in errors:
                msg_parts.append(f"  \u2718 {err}")

        if not copied and errors:
            messagebox.showerror("Backup Failed", "\n".join(msg_parts))
        else:
            messagebox.showinfo("Backup Complete", "\n".join(msg_parts))

    def _quit(self):
        if self._buttons_locked:
            return  # prevent quitting while a modal is open
        self._on_quit()

    def _centre(self, parent):
        self.update_idletasks()
        w = max(self.winfo_width(), 400)
        h = max(self.winfo_height(), 300)
        pw = parent.winfo_screenwidth()
        ph = parent.winfo_screenheight()
        x = (pw - w) // 2
        y = (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


# ---------------------------------------------------------------------------
# Main application (invisible root)
# ---------------------------------------------------------------------------

class App(tk.Tk):
    """Root window — withdrawn; the Main Menu is the visible entry point."""

    def __init__(self):
        # Single instance check via local port binding (ignored by firewall, robust cross-platform)
        import socket
        import sys
        from tkinter import messagebox
        try:
            self._lock_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._lock_socket.bind(('127.0.0.1', 58284))
        except socket.error:
            root = tk.Tk()
            root.withdraw()
            messagebox.showwarning("Already Running", "Fatalities Editor is already running.")
            root.destroy()
            sys.exit(0)

        super().__init__()
        self.withdraw()
        self.configure(bg=BG_GREY)

        self._datasets = load_config()

        if not self._datasets:
            _show_error("No datasets configured. Exiting.")
            self.destroy()
            return

        self._menu = MainMenu(
            self, self._datasets,
            on_update=self._open_editor,
            on_quit=self._quit,
        )

        self.protocol("WM_DELETE_WINDOW", self._quit)
        self.mainloop()

    # ------------------------------------------------------------------
    # Editor
    # ------------------------------------------------------------------

    def _open_editor(self, file_path: str, modal_title: str | None = None):
        if not os.path.exists(file_path):
            _show_error(f"'{file_path}' does not exist.")
            return
        UpdateFatalities(self._menu, file_path, modal_title=modal_title)

    # ------------------------------------------------------------------
    # Quit
    # ------------------------------------------------------------------

    def _quit(self):
        self.destroy()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys, traceback

    print("Starting Fatalities Editor...", flush=True)
    try:
        App()
    except Exception:
        traceback.print_exc()
        if sys.platform == "win32":
            input("\nPress Enter to exit...")
