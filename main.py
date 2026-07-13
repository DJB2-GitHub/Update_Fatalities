"""Fatalities Editor — Tkinter desktop application (modern flat-design).

Reads .env for FATALITY_FILE_DIRECTORY and FILES_AVAILABLE_FOR_UPDATE,
displays a Main Menu modal, then opens a selected file in the
update_fatalities modal. Key fields (id) are read-only.
The app guards against quitting with unsaved changes.
"""

from __future__ import annotations

import glob
import json
import os
import re
import threading
import tkinter as tk
import webbrowser
from tkinter import ttk

from update_fatalities import UpdateFatalities
from push_json_updates_to_firestore import push_updates


# ---------------------------------------------------------------------------
# Design tokens
# ---------------------------------------------------------------------------

RED_PRIMARY   = "#c63f3f"
RED_DEEP      = "#a53434"
BG_GREY       = "#f5f5f5"
WHITE         = "#ffffff"
TEXT_DARK     = "#333333"
TEXT_MUTED    = "#888888"
BORDER        = "#dcdcdc"
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
    datasets = {}
    for f in env.get(env_key, "").split(","):
        f = f.strip()
        if not f:
            continue
        base = os.path.splitext(f)[0]
        if base.lower() == "au_fatalities":
            label = "AU_Fatalities.json"
        elif base.lower() == "nz_fatalities":
            label = "NZ_Fatalities.json"
        else:
            label = base
        datasets[label] = os.path.join(directory, f)
    return datasets


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

def _show_error(message: str, auto_close_seconds: float = 0):
    """Custom error dialog."""
    StyledDialog(None, "Error", message, icon="error", buttons=[("OK", None)],
                 auto_close_seconds=auto_close_seconds)


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
                 icon: str = "info", buttons: list[tuple[str, object]],
                 auto_close_seconds: float = 0, width: int = 50):
        super().__init__(parent)
        self.result: object = None
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=WHITE)

        if auto_close_seconds > 0:
            print(f"StyledDialog: scheduling auto-close in {auto_close_seconds}s", flush=True)
            self.after(int(auto_close_seconds * 1000), self._auto_close)

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

        msg_lbl = tk.Text(
            top, bg=WHITE, fg=TEXT_DARK, font=(FONT_FAMILY, 10),
            wrap=tk.WORD, relief=tk.FLAT, borderwidth=0,
            highlightthickness=0, padx=0, pady=0,
            cursor="arrow", state=tk.NORMAL, width=width,
        )
        msg_lbl.insert("1.0", message)
        lines = message.count("\n") + 1
        msg_lbl.configure(state=tk.DISABLED, height=min(lines, 12))
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

    def _auto_close(self):
        """Auto-close the dialog (called by after() timer)."""
        print("_auto_close firing", flush=True)
        try:
            self.destroy()
        except Exception:
            pass

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
# Report Modal
# ---------------------------------------------------------------------------

RECIPIENTS_PATH = "recipients.json"
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$')


def _load_recipients() -> list[str]:
    if not os.path.exists(RECIPIENTS_PATH):
        return ["darryljbaker@live.com"]
    try:
        with open(RECIPIENTS_PATH, "r", encoding="utf-8") as fh:
            data = json.load(fh)
            if isinstance(data, list):
                return [str(e) for e in data if isinstance(e, str)]
    except (json.JSONDecodeError, OSError):
        pass
    return ["darryljbaker@live.com"]


def _save_recipients(recipients: list[str]):
    with open(RECIPIENTS_PATH, "w", encoding="utf-8") as fh:
        json.dump(recipients, fh, indent=2, ensure_ascii=False)


class ReportModal(tk.Toplevel):
    """Modal for creating and distributing the OnThisDay report."""

    def __init__(self, parent):
        super().__init__(parent)
        self.title("Create and Distribute Report")
        self.resizable(False, False)
        self.configure(bg=WHITE)
        self.transient(parent)
        self.grab_set()

        self._recipients = _load_recipients()
        self._check_vars: list[tk.BooleanVar] = []

        self._build()
        self._centre(parent)

    def _build(self):
        # Header
        header = tk.Frame(self, bg=RED_PRIMARY, height=48)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(header, text="Create and Distribute Report", bg=RED_PRIMARY, fg=WHITE,
                 font=(FONT_FAMILY, 14, "bold")).pack(side=tk.LEFT, padx=20, pady=10)

        body = tk.Frame(self, bg=WHITE, padx=24, pady=16)
        body.pack(fill=tk.BOTH, expand=True)

        # Hotlink to report site
        report_link = tk.Label(body, text="\U0001F517 Create Report", bg=WHITE, fg="#4a90d9",
                               font=(FONT_FAMILY, 10, "underline"), cursor="hand2", anchor="w")
        report_link.pack(fill=tk.X, pady=(0, 8))
        report_link.bind("<Button-1>", lambda e: webbrowser.open(_read_env().get("ONTHISDAY_WEB_APP", "https://djb-OnThisDay.web.app")))

        # --- Recipients list with checkboxes ---
        tk.Label(body, text="Email Recipients", bg=WHITE, fg=TEXT_DARK,
                 font=(FONT_FAMILY, 10, "bold"), anchor="w").pack(fill=tk.X)

        list_frame = tk.Frame(body, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(4, 8))

        self._list_canvas = tk.Canvas(list_frame, bg=WHITE, borderwidth=0, highlightthickness=0,
                                       height=150)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._list_canvas.yview)
        self._list_inner = tk.Frame(self._list_canvas, bg=WHITE)
        self._list_inner.bind("<Configure>",
                              lambda _e: self._list_canvas.configure(
                                  scrollregion=self._list_canvas.bbox("all")))
        self._list_canvas_window = self._list_canvas.create_window(
            (0, 0), window=self._list_inner, anchor="nw")
        self._list_canvas.configure(yscrollcommand=scrollbar.set)
        self._list_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # CRUD buttons
        crud_frame = tk.Frame(body, bg=WHITE)
        crud_frame.pack(fill=tk.X, pady=(0, 12))

        add_btn = tk.Frame(crud_frame, bg=RED_PRIMARY, cursor="hand2")
        add_btn.pack(side=tk.LEFT, padx=(0, 6))
        al = tk.Label(add_btn, text="  Add  ", bg=RED_PRIMARY, fg=WHITE,
                       font=(FONT_FAMILY, 9), padx=10, pady=3)
        al.pack()
        al.bind("<Button-1>", lambda e: self._add_recipient())

        edit_btn = tk.Frame(crud_frame, bg="#4a90d9", cursor="hand2")
        edit_btn.pack(side=tk.LEFT, padx=(0, 6))
        el = tk.Label(edit_btn, text="  Edit  ", bg="#4a90d9", fg=WHITE,
                       font=(FONT_FAMILY, 9), padx=10, pady=3)
        el.pack()
        el.bind("<Button-1>", lambda e: self._edit_recipient())

        del_btn = tk.Frame(crud_frame, bg="#e67e22", cursor="hand2")
        del_btn.pack(side=tk.LEFT)
        dl = tk.Label(del_btn, text="  Delete  ", bg="#e67e22", fg=WHITE,
                       font=(FONT_FAMILY, 9), padx=10, pady=3)
        dl.pack()
        dl.bind("<Button-1>", lambda e: self._delete_recipients())

        # --- HTML Report file lookup ---
        tk.Label(body, text="HTML Report", bg=WHITE, fg=TEXT_DARK,
                 font=(FONT_FAMILY, 10, "bold"), anchor="w").pack(fill=tk.X)
        self._report_var = tk.StringVar()
        html_files = self._scan_html_reports()
        if html_files:
            self._report_var.set(html_files[0])
        report_cb = ttk.Combobox(body, textvariable=self._report_var, values=html_files,
                                  state="readonly", font=(FONT_FAMILY, 9))
        report_cb.pack(fill=tk.X, pady=(4, 4))

        # Status label
        self._status_label = tk.Label(body, text="", bg=WHITE, fg=RED_PRIMARY,
                                       font=(FONT_FAMILY, 9, "bold"), anchor="w")
        self._status_label.pack(fill=tk.X, pady=(0, 4))

        # --- Action buttons ---
        btn_row = tk.Frame(body, bg=WHITE)
        btn_row.pack(fill=tk.X, pady=(4, 0))

        close_btn = tk.Frame(btn_row, bg="#e0e0e0", cursor="hand2")
        close_btn.pack(side=tk.RIGHT, padx=(6, 0))
        cl = tk.Label(close_btn, text="  Close  ", bg="#e0e0e0", fg=TEXT_DARK,
                       font=(FONT_FAMILY, 10), padx=16, pady=6)
        cl.pack()
        cl.bind("<Button-1>", lambda e: self.destroy())

        self._send_btn_frame = tk.Frame(btn_row, bg=RED_PRIMARY, cursor="hand2")
        self._send_btn_frame.pack(side=tk.RIGHT, padx=(6, 0))
        self._send_btn_label = tk.Label(self._send_btn_frame, text="  Email OnThisDay Report  ",
                                         bg=RED_PRIMARY, fg=WHITE,
                                         font=(FONT_FAMILY, 10, "bold"), padx=16, pady=6)
        self._send_btn_label.pack()
        self._send_btn_label.bind("<Button-1>", lambda e: self._create_report())
        self._refresh_list()

    # ------------------------------------------------------------------
    # Recipient list rendering
    # ------------------------------------------------------------------

    def _refresh_list(self):
        for w in self._list_inner.winfo_children():
            w.destroy()
        self._check_vars.clear()

        for email in self._recipients:
            var = tk.BooleanVar(value=False)
            self._check_vars.append(var)
            row = tk.Frame(self._list_inner, bg=WHITE)
            row.pack(fill=tk.X)
            cb = tk.Checkbutton(row, text=email, variable=var,
                                bg=WHITE, fg=TEXT_DARK, font=(FONT_FAMILY, 9),
                                anchor="w", selectcolor=WHITE,
                                activebackground=WHITE)
            cb.pack(fill=tk.X, padx=6, pady=2)

    # ------------------------------------------------------------------
    # CRUD operations
    # ------------------------------------------------------------------

    def _add_recipient(self):
        dialog = _RecipientDialog(self, "Add Recipient", "")
        if dialog.result:
            email = dialog.result.strip()
            if not EMAIL_RE.match(email):
                _show_error("Invalid email address.")
                return
            if email in self._recipients:
                _show_error("Email already in list.")
                return
            self._recipients.append(email)
            _save_recipients(self._recipients)
            self._refresh_list()

    def _edit_recipient(self):
        selected = self._get_selected_indices()
        if len(selected) != 1:
            _show_error("Select exactly one recipient to edit.")
            return
        idx = selected[0]
        old_email = self._recipients[idx]
        dialog = _RecipientDialog(self, "Edit Recipient", old_email)
        if dialog.result:
            new_email = dialog.result.strip()
            if not EMAIL_RE.match(new_email):
                _show_error("Invalid email address.")
                return
            if new_email != old_email and new_email in self._recipients:
                _show_error("Email already in list.")
                return
            self._recipients[idx] = new_email
            _save_recipients(self._recipients)
            self._refresh_list()

    def _delete_recipients(self):
        selected = self._get_selected_indices()
        if not selected:
            _show_error("Select at least one recipient to delete.")
            return
        for idx in sorted(selected, reverse=True):
            del self._recipients[idx]
        _save_recipients(self._recipients)
        self._refresh_list()

    def _get_selected_indices(self) -> list[int]:
        return [i for i, v in enumerate(self._check_vars) if v.get()]

    def _scan_html_reports(self) -> list[str]:
        env = _read_env()
        report_dir = env.get("ONTHISDAY_HTML_REPORT_DIR", "")
        prefix = env.get("ONTHISDAY_HTML_FILE_PREFIX", "")
        if not report_dir or not os.path.isdir(report_dir):
            return []
        pattern = os.path.join(report_dir, f"{prefix}*.html")
        files = sorted(glob.glob(pattern))
        return [os.path.basename(f) for f in files]

    def _create_report(self):
        """Send HTML report via Outlook to selected recipients."""
        env = _read_env()
        warn_timeout = float(env.get("WARNING_MESSAGE_AUTOCLOSE_SECONDS", "0") or 0)
        print(f"_create_report: WARNING_MESSAGE_AUTOCLOSE_SECONDS={warn_timeout}", flush=True)
        selected = self._get_selected_indices()
        if not selected:
            _show_error("Select at least one recipient.", auto_close_seconds=warn_timeout)
            return
        report_name = self._report_var.get().strip()
        if not report_name:
            _show_error("No HTML report selected.", auto_close_seconds=warn_timeout)
            return
        report_dir = env.get("ONTHISDAY_HTML_REPORT_DIR", "")
        report_path = os.path.join(report_dir, report_name)
        if not os.path.isfile(report_path):
            _show_error(f"Report file not found:\n{report_path}", auto_close_seconds=warn_timeout)
            return
        # Extract date from filename for subject (e.g. "08Jul2026" → "08-Jul")
        date_match = re.search(r'(\d{2}[A-Z][a-z]{2}\d{4})', report_name)
        if date_match:
            from datetime import datetime
            try:
                dt = datetime.strptime(date_match.group(1), "%d%b%Y")
                date_display = dt.strftime("%d-%b")
            except ValueError:
                date_display = date_match.group(1)
        else:
            date_display = ""
        subject = f"On this day in Vietnam - {date_display}" if date_display else "On this day in Vietnam"
        emails = [self._recipients[i] for i in selected]
        # Read HTML content for body
        try:
            with open(report_path, "r", encoding="utf-8") as fh:
                html_body = fh.read()
        except OSError as exc:
            _show_error(f"Cannot read report file:\n{exc}", auto_close_seconds=warn_timeout)
            return
        # Disable button and show status
        self._set_sending(True)
        try:
            import pythoncom
            import win32com.client
            pythoncom.CoInitialize()
            try:
                outlook = win32com.client.GetActiveObject("Outlook.Application")
            except Exception:
                outlook = win32com.client.Dispatch("Outlook.Application")
            mail = outlook.CreateItem(0)  # 0 = olMailItem
            mail.To = "; ".join(emails)
            mail.Subject = subject
            mail.HTMLBody = html_body
            try:
                mail.Send()
            except Exception:
                # Fallback: open compose window for manual send
                mail.Display(False)
            self._set_sending(False)
            StyledDialog(
                self, "Report Sent",
                f"Email sent to:\n" +
                "\n".join(f"  \u2022 {e}" for e in emails) +
                f"\n\nSubject: {subject}\nReport: {report_name}",
                icon="info",
                buttons=[("OK", None)],
            )
        except Exception as exc:
            self._set_sending(False)
            _show_error(f"Failed to send email:\n{exc}", auto_close_seconds=warn_timeout)

    def _set_sending(self, sending: bool):
        if sending:
            self._status_label.configure(text="Sending email with attachment...")
            self._send_btn_label.configure(state=tk.DISABLED, cursor="watch")
            self._send_btn_frame.configure(cursor="watch")
        else:
            self._status_label.configure(text="")
            self._send_btn_label.configure(state=tk.NORMAL, cursor="hand2")
            self._send_btn_frame.configure(cursor="hand2")
        self.update_idletasks()

    def _centre(self, parent):
        self.update_idletasks()
        w = max(self.winfo_width(), 480)
        h = max(self.winfo_height(), 420)
        pw = parent.winfo_screenwidth()
        ph = parent.winfo_screenheight()
        x = (pw - w) // 2
        y = (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


class _RecipientDialog(tk.Toplevel):
    """Simple single-field entry dialog for add/edit recipient."""

    def __init__(self, parent, title: str, initial: str):
        super().__init__(parent)
        self.title(title)
        self.resizable(False, False)
        self.configure(bg=WHITE)
        self.transient(parent)
        self.grab_set()
        self.result: str | None = None

        body = tk.Frame(self, bg=WHITE, padx=24, pady=16)
        body.pack()

        tk.Label(body, text="Email address:", bg=WHITE, fg=TEXT_DARK,
                 font=(FONT_FAMILY, 10)).pack(anchor="w", pady=(0, 4))
        self._entry = tk.Entry(body, font=(FONT_FAMILY, 10), width=36,
                               bg=WHITE, fg=TEXT_DARK, relief=tk.SOLID,
                               highlightbackground=BORDER, highlightthickness=1)
        self._entry.insert(0, initial)
        self._entry.pack(pady=(0, 12))
        self._entry.focus_set()
        self._entry.select_range(0, tk.END)

        btn_row = tk.Frame(body, bg=WHITE)
        btn_row.pack(fill=tk.X)

        cancel = tk.Label(btn_row, text="  Cancel  ", bg="#e0e0e0", fg=TEXT_DARK,
                          font=(FONT_FAMILY, 10), padx=12, pady=4, cursor="hand2")
        cancel.pack(side=tk.RIGHT, padx=(4, 0))
        cancel.bind("<Button-1>", lambda e: self._choose(None))

        ok_btn = tk.Label(btn_row, text="  OK  ", bg=RED_PRIMARY, fg=WHITE,
                          font=(FONT_FAMILY, 10, "bold"), padx=16, pady=4, cursor="hand2")
        ok_btn.pack(side=tk.RIGHT, padx=(4, 0))
        ok_btn.bind("<Button-1>", lambda e: self._choose(self._entry.get()))

        self._entry.bind("<Return>", lambda e: self._choose(self._entry.get()))
        self._entry.bind("<Escape>", lambda e: self._choose(None))

        self._centre(parent)
        self.wait_window()

    def _choose(self, value):
        self.result = value
        self.destroy()

    def _centre(self, parent):
        self.update_idletasks()
        w = max(self.winfo_width(), 340)
        h = max(self.winfo_height(), 120)
        pw = parent.winfo_screenwidth()
        ph = parent.winfo_screenheight()
        x = (pw - w) // 2
        y = (ph - h) // 2
        self.geometry(f"{w}x{h}+{x}+{y}")


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
            body, text="OnThisDay in Vietnam webapp", bg=WHITE, fg=TEXT_DARK,
            font=(FONT_FAMILY, 12, "bold"),
        )
        heading_lbl.pack(anchor="w", pady=(8, 4))

        for label, file_path in datasets.get("live", {}).items():
            btn = self._flat_button(body, f"  Update {label}", self._update, file_path)
            btn.pack(fill=tk.X, pady=3)

        au_path = datasets.get("live", {}).get("AU_Fatalities.json")
        push_au_btn = self._flat_button(body, "  Push AU Updates to Firestore", lambda _e, c="AU", p=au_path: self._run_push(c, p), None)
        push_au_btn.pack(fill=tk.X, pady=3)

        nz_path = datasets.get("live", {}).get("NZ_Fatalities.json")
        push_nz_btn = self._flat_button(body, "  Push NZ Updates to Firestore", lambda _e, c="NZ", p=nz_path: self._run_push(c, p), None)
        push_nz_btn.pack(fill=tk.X, pady=3)

        backup_btn = self._flat_button(body, "  Backup Firestore Fatalities to folder for OneDrive sync", lambda _e: self._backup_files(), None)
        backup_btn.pack(fill=tk.X, pady=3)
        self._backup_btn_frame = backup_btn
        self._backup_btn_label: tk.Label = backup_btn.winfo_children()[0]

        ttk.Separator(body, orient=tk.HORIZONTAL).pack(fill=tk.X, pady=(12, 12))

        report_btn = self._flat_button(body, "  Create and Distribute Report", lambda _e: self._open_report_modal(), None)
        report_btn.pack(fill=tk.X, pady=3)

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

    def _open_report_modal(self):
        if self._buttons_locked:
            return
        self._set_buttons_locked(True)
        try:
            ReportModal(self)
        finally:
            self._set_buttons_locked(False)

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

    def _run_push(self, country_code: str, file_path: str | None):
        if not file_path or not os.path.exists(file_path):
            _show_error(f"Cannot find dataset for {country_code}")
            return

        if self._buttons_locked:
            return

        if not _ask_yes_no(self, "Confirm Push", f"Push updates to Firestore for {country_code}?"):
            return

        self._set_buttons_locked(True)

        progress_win = tk.Toplevel(self)
        progress_win.title("Pushing to Firestore...")
        progress_win.geometry("400x120")
        progress_win.configure(bg=WHITE)
        progress_win.resizable(False, False)
        progress_win.transient(self)
        progress_win.grab_set()

        progress_win.update_idletasks()
        pw, ph = self.winfo_screenwidth(), self.winfo_screenheight()
        w, h = progress_win.winfo_width(), progress_win.winfo_height()
        progress_win.geometry(f"+{(pw-w)//2}+{(ph-h)//2}")

        lbl = tk.Label(progress_win, text=f"Pushing {country_code} updates...", bg=WHITE, fg=TEXT_DARK, font=(FONT_FAMILY, 11))
        lbl.pack(pady=(20, 10))

        progress_var = tk.StringVar(value="Starting...")
        status_lbl = tk.Label(progress_win, textvariable=progress_var, bg=WHITE, fg=TEXT_MUTED, font=(FONT_FAMILY, 9))
        status_lbl.pack()

        def _cb(current, total):
            progress_var.set(f"Updated {current} of {total} records")

        def _task():
            try:
                count = push_updates(country_code, file_path, _cb)
                msg = f"Successfully pushed {count} updates."
                icon = "info"
            except Exception as e:
                msg = f"Error pushing updates:\n{str(e)}"
                icon = "error"

            def _on_finish():
                progress_win.destroy()
                self._set_buttons_locked(False)
                StyledDialog(self, "Push Result", msg, icon=icon, buttons=[("OK", None)])

            self.after(0, _on_finish)

        threading.Thread(target=_task, daemon=True).start()

    def _sync_parent_iconify(self):
        try:
            if self.winfo_exists() and self.state() == 'iconic':
                parent = self.master
                # Never touch the hidden root tk.Tk window
                if parent and parent.winfo_exists() and not isinstance(parent, tk.Tk):
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
            # Never touch the hidden root tk.Tk window
            if parent and parent.winfo_exists() and parent.state() == 'iconic' and not isinstance(parent, tk.Tk):
                parent.deiconify()
        except Exception:
            pass

    def _on_parent_map(self, event=None):
        """When the parent is restored (e.g. from taskbar), restore this modal too."""
        # Never respond to the hidden root tk.Tk window being mapped
        if event is not None and isinstance(event.widget, tk.Tk):
            return
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
        """Fetch AU/NZ Fatalities from Firestore and save to OneDrive sync folder as JSON with timestamp.
        Keeps only the 3 most recent backups per file; deletes older ones."""
        import json
        import glob as _glob
        from datetime import datetime
        from tkinter import messagebox
        from coords import _load_json

        self._backup_btn_label.configure(fg=TEXT_MUTED, text="  Backing up...")
        self._backup_btn_label.unbind("<Button-1>")

        def _do_backup():
            env = _read_env()
            backup_dir = env.get("BACKUP_FATALITIES_TO_ONEDRIVE_SYNC", "")
            if not backup_dir:
                messagebox.showerror("Backup Error", "BACKUP_FATALITIES_TO_ONEDRIVE_SYNC not found in .env")
                return

            files_str = env.get("FILES_AVAILABLE_FOR_UPDATE", "")
            if not files_str:
                messagebox.showerror("Backup Error", "FILES_AVAILABLE_FOR_UPDATE missing in .env")
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
                base, ext = os.path.splitext(filename)

                try:
                    # Fetch data from Firestore using our modified load logic
                    data = _load_json(filename)
                    if data is None:
                        errors.append(f"Failed to fetch data for {filename} from Firestore")
                        continue

                    dest_name = f"{base}_{len(data)}_{timestamp}{ext}"
                    dest_path = os.path.join(backup_dir, dest_name)

                    with open(dest_path, "w", encoding="utf-8") as fh:
                        json.dump(data, fh, indent=2, ensure_ascii=False)
                    copied.append((dest_name, len(data)))
                except Exception as e:
                    errors.append(f"Backup failed for {filename}: {e}")
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
                for name, count in copied:
                    msg_parts.append(f"  \u2714 {name} ({count} records)")
            if errors:
                msg_parts.append("\nErrors:")
                for err in errors:
                    msg_parts.append(f"  \u2718 {err}")

            if not copied and errors:
                messagebox.showerror("Backup Failed", "\n".join(msg_parts))
            else:
                messagebox.showinfo("Backup Complete", "\n".join(msg_parts))

        try:
            _do_backup()
        finally:
            self._backup_btn_label.configure(fg=TEXT_DARK, text="  Backup Firestore Fatalities to folder for OneDrive sync")
            self._backup_btn_label.bind("<Button-1>", lambda e: self._backup_files())

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
        self.attributes('-alpha', 0.0)  # ensure root stays fully invisible on Windows
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
