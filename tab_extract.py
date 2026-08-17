"""
Vic - Fix: Track Extractor Tab
==============================
Extracts specific tracks, chapters, or attachments from media files.
"""

import customtkinter as ctk
import threading
import os
from tkinter import filedialog, messagebox

from ui_components import Colors, FileDropZone, StatusProgressPanel
from media_processor import MediaProcessor


class TabExtract(ctk.CTkFrame):
    def __init__(self, master, app_ref):
        super().__init__(master, fg_color="transparent")
        self.app = app_ref
        
        self.file_path = None
        self.tracks = []
        
        self._build_ui()

    def _build_ui(self):
        # File Drop
        self.drop_zone = FileDropZone(
            self, label="Source File", on_file_selected=self._on_file, height=120
        )
        self.drop_zone.pack(fill="x", padx=20, pady=(20, 10))
        
        # Output Dir
        dir_frame = ctk.CTkFrame(self, fg_color="transparent")
        dir_frame.pack(fill="x", padx=20, pady=10)
        
        self.dir_entry = ctk.CTkEntry(dir_frame, placeholder_text="Output Directory")
        self.dir_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(dir_frame, text="Browse", width=80, command=self._browse_dir).pack(side="right")
        
        # Track List
        self.track_scroll = ctk.CTkScrollableFrame(self, fg_color=Colors.BG_CARD)
        self.track_scroll.pack(fill="both", expand=True, padx=20, pady=10)
        
        # Action Panel
        self.action_panel = ctk.CTkFrame(self, fg_color="transparent")
        self.action_panel.pack(fill="x", padx=20, pady=10)
        
        self.btn_extract = ctk.CTkButton(
            self.action_panel, text="📤  Extract Selected", height=40,
            command=self._on_extract, state="disabled", fg_color=Colors.ACCENT
        )
        self.btn_extract.pack(fill="x")
        
        # Status
        self.status_panel = StatusProgressPanel(self)
        self.status_panel.pack(fill="x", padx=20, pady=(0, 20))
        
        self.track_vars = {}
        self.track_exts = {}

    def _browse_dir(self):
        d = filedialog.askdirectory()
        if d:
            self.dir_entry.delete(0, 'end')
            self.dir_entry.insert(0, d)

    def _on_file(self, path):
        self.file_path = path
        
        # Clear tracks
        for widget in self.track_scroll.winfo_children():
            widget.destroy()
        self.track_vars.clear()
        self.track_exts.clear()
        
        if path:
            self.dir_entry.delete(0, 'end')
            self.dir_entry.insert(0, os.path.dirname(path))
            self._load_tracks(path)
        else:
            self.btn_extract.configure(state="disabled")

    def _load_tracks(self, path):
        self.status_panel.set_status("Loading tracks...")
        
        def _worker():
            mp = MediaProcessor()
            tracks = mp.get_tracks(path)
            self.after(0, lambda: self._render_tracks(tracks))
            
        threading.Thread(target=_worker, daemon=True).start()

    def _render_tracks(self, tracks):
        self.tracks = tracks
        self.status_panel.reset()
        
        if not tracks:
            ctk.CTkLabel(self.track_scroll, text="No tracks found").pack(pady=20)
            return
            
        for t in tracks:
            row = ctk.CTkFrame(self.track_scroll, fg_color="transparent")
            row.pack(fill="x", pady=2)
            
            var = ctk.BooleanVar(value=False)
            self.track_vars[t['index']] = var
            
            cb = ctk.CTkCheckBox(row, text=f"[{t['index']}] {t['type'].upper()} ({t['codec']}) - {t['language']}", variable=var)
            cb.pack(side="left", padx=5)
            
            ext_var = ctk.StringVar()
            if t['type'] == "video":
                ext_var.set("mp4")
            elif t['type'] == "audio":
                ext_var.set("mka")
            else:
                ext_var.set("srt")
                
            self.track_exts[t['index']] = ext_var
            
            ext_entry = ctk.CTkEntry(row, textvariable=ext_var, width=60, height=24)
            ext_entry.pack(side="right", padx=5)
            ctk.CTkLabel(row, text="Ext:").pack(side="right")

        self.btn_extract.configure(state="normal")

    def _on_extract(self):
        out_dir = self.dir_entry.get()
        if not out_dir:
            return
            
        selected = []
        for t in self.tracks:
            if self.track_vars[t['index']].get():
                selected.append({
                    'index': t['index'],
                    'type': t['type'],
                    'ext': self.track_exts[t['index']].get().strip('.')
                })
                
        if not selected:
            messagebox.showinfo("Info", "No tracks selected")
            return
            
        self.btn_extract.configure(state="disabled")
        
        def _worker():
            mp = MediaProcessor(
                status_callback=lambda s: self.after(0, lambda: self.status_panel.set_status(s)),
                progress_callback=lambda p: self.after(0, lambda: self.status_panel.set_progress(p))
            )
            try:
                mp.extract_tracks(self.file_path, selected, out_dir)
                self.after(0, lambda: messagebox.showinfo("Success", "Extraction complete!"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, lambda: self.btn_extract.configure(state="normal"))
                
        threading.Thread(target=_worker, daemon=True).start()
