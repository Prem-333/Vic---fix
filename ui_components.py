"""
Vic - Fix: UI Components
========================
Shared UI components for the Vic - Fix application.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import os

class Colors:
    """Centralized color definitions for the entire application."""
    BG_DARK        = "#0d0d14"
    BG_CARD        = "#16161f"
    BG_CARD_HOVER  = "#1e1e2a"
    BG_INPUT       = "#1a1a26"
    BORDER         = "#2a2a3a"
    BORDER_LOADED  = "#6c5ce7"
    BORDER_SUCCESS = "#00cec9"
    TEXT_PRIMARY   = "#eaeaf0"
    TEXT_SECONDARY = "#9090a8"
    TEXT_MUTED     = "#555568"
    ACCENT         = "#6c5ce7"
    ACCENT_HOVER   = "#7f70f0"
    ACCENT_GLOW    = "#8b7cf7"
    SUCCESS        = "#00cec9"
    SUCCESS_DARK   = "#00b5b0"
    ERROR          = "#ff6b6b"
    ERROR_HOVER    = "#ff8787"
    WARNING        = "#feca57"
    PROGRESS_BG    = "#1e1e30"
    PROGRESS_FG    = "#6c5ce7"


class FileDropZone(ctk.CTkFrame):
    """A stylized panel for selecting files via click-to-browse."""
    
    def __init__(self, master, label: str, on_file_selected, supported_extensions=None, **kwargs):
        super().__init__(
            master,
            corner_radius=16,
            fg_color=Colors.BG_CARD,
            border_color=Colors.BORDER,
            border_width=2,
            **kwargs,
        )

        self._label_text = label
        self._on_file_selected = on_file_selected
        self.file_path = None
        self.supported_extensions = supported_extensions or frozenset({
            ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm",
            ".m4v", ".mpg", ".mpeg", ".ts", ".mts", ".m2ts", ".vob",
            ".3gp", ".ogv", ".divx",
        })

        self.configure(cursor="hand2")
        self.bind("<Button-1>", self._on_click)

        self._icon_label = ctk.CTkLabel(self, text="🎬", font=ctk.CTkFont(size=44), text_color=Colors.TEXT_SECONDARY, cursor="hand2")
        self._icon_label.pack(pady=(28, 4))
        self._icon_label.bind("<Button-1>", self._on_click)

        self._title_label = ctk.CTkLabel(self, text=label, font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"), text_color=Colors.TEXT_PRIMARY, cursor="hand2")
        self._title_label.pack(pady=(4, 2))
        self._title_label.bind("<Button-1>", self._on_click)

        self._hint_label = ctk.CTkLabel(self, text="Click to browse for a file", font=ctk.CTkFont(family="Segoe UI", size=11), text_color=Colors.TEXT_MUTED, cursor="hand2")
        self._hint_label.pack(pady=(0, 4))
        self._hint_label.bind("<Button-1>", self._on_click)

        self._info_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Segoe UI", size=10), text_color=Colors.TEXT_SECONDARY, wraplength=260, cursor="hand2")
        self._info_label.pack(pady=(0, 4))
        self._info_label.bind("<Button-1>", self._on_click)

        self._clear_btn = ctk.CTkButton(
            self, text="✕  Remove", font=ctk.CTkFont(family="Segoe UI", size=11), width=90, height=28,
            corner_radius=8, fg_color="transparent", hover_color=Colors.ERROR, text_color=Colors.TEXT_MUTED,
            border_width=1, border_color=Colors.BORDER, command=self._clear_file,
        )
        self._clear_btn.pack(pady=(0, 16))
        self._clear_btn.pack_forget()

    def _on_click(self, event=None):
        if self.cget("cursor") != "hand2":
            return
            
        exts = " ".join(f"*{ext}" for ext in sorted(self.supported_extensions)) if self.supported_extensions else "*.*"
        filetypes = [("Media files", exts), ("All files", "*.*")] if self.supported_extensions else [("All files", "*.*")]
        
        file_path = filedialog.askopenfilename(title=f"Select {self._label_text}", filetypes=filetypes)
        if file_path:
            self._accept_file(file_path)

    def _accept_file(self, file_path: str):
        file_path = os.path.normpath(file_path)
        if not os.path.isfile(file_path):
            messagebox.showerror("File Not Found", f"Cannot find the file:\n{file_path}")
            return

        self.file_path = file_path
        self._update_display()
        self._on_file_selected(file_path)

    def _update_display(self):
        if self.file_path:
            name = os.path.basename(self.file_path)
            display_name = name if len(name) <= 30 else name[:27] + "..."
            
            try:
                size_bytes = os.path.getsize(self.file_path)
                if size_bytes >= 1024 ** 3: size_str = f"{size_bytes / 1024**3:.2f} GB"
                elif size_bytes >= 1024 ** 2: size_str = f"{size_bytes / 1024**2:.1f} MB"
                elif size_bytes >= 1024: size_str = f"{size_bytes / 1024:.0f} KB"
                else: size_str = f"{size_bytes} B"
            except OSError:
                size_str = "Unknown size"

            self._icon_label.configure(text="✅")
            self._title_label.configure(text=display_name)
            self._hint_label.configure(text=size_str, text_color=Colors.TEXT_SECONDARY)
            self.configure(border_color=Colors.BORDER_LOADED)
            self._clear_btn.pack(pady=(0, 16))
        else:
            self._icon_label.configure(text="🎬")
            self._title_label.configure(text=self._label_text)
            self._hint_label.configure(text="Click to browse for a file", text_color=Colors.TEXT_MUTED)
            self._info_label.configure(text="")
            self.configure(border_color=Colors.BORDER)
            self._clear_btn.pack_forget()

    def set_info_text(self, text: str):
        self._info_label.configure(text=text)

    def _clear_file(self):
        self.file_path = None
        self._update_display()
        self._on_file_selected(None)

    def set_enabled(self, enabled: bool):
        if enabled:
            self.configure(cursor="hand2")
            self._clear_btn.configure(state="normal")
            self._icon_label.configure(cursor="hand2")
            self._title_label.configure(cursor="hand2")
        else:
            self.configure(cursor="arrow")
            self._clear_btn.configure(state="disabled")
            self._icon_label.configure(cursor="arrow")
            self._title_label.configure(cursor="arrow")


class StatusProgressPanel(ctk.CTkFrame):
    """Shared progress bar and status panel."""
    
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            fg_color=Colors.BG_CARD,
            corner_radius=14,
            border_width=1,
            border_color=Colors.BORDER,
            **kwargs
        )
        
        self._status_label = ctk.CTkLabel(
            self, text="Ready", font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=Colors.TEXT_SECONDARY, anchor="w"
        )
        self._status_label.pack(fill="x", padx=20, pady=(14, 5))

        self._progress_bar = ctk.CTkProgressBar(
            self, height=10, corner_radius=5, fg_color=Colors.PROGRESS_BG,
            progress_color=Colors.PROGRESS_FG, border_width=0
        )
        self._progress_bar.pack(fill="x", padx=20, pady=(0, 5))
        self._progress_bar.set(0)

        self._detail_label = ctk.CTkLabel(
            self, text="", font=ctk.CTkFont(family="Segoe UI", size=10),
            text_color=Colors.TEXT_MUTED, anchor="w"
        )
        self._detail_label.pack(fill="x", padx=20, pady=(0, 12))
        
        self._last_progress = 0.0

    def set_status(self, message: str, color=Colors.TEXT_SECONDARY):
        self._status_label.configure(text=message, text_color=color)

    def set_progress(self, value: float):
        if abs(value - self._last_progress) >= 0.005 or value <= 0.001 or value >= 0.999:
            self._last_progress = value
            self._progress_bar.set(value)

    def set_detail(self, message: str):
        self._detail_label.configure(text=message)

    def reset(self):
        self.set_progress(0)
        self.set_status("Ready")
        self.set_detail("")
