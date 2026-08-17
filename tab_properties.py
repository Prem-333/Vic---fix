"""
Vic - Fix: Properties Editor Tab
================================
Edit file and track properties (title, language, flags) directly.
"""

import customtkinter as ctk
import threading
import os
from tkinter import messagebox, filedialog

from ui_components import Colors, FileDropZone, StatusProgressPanel
from media_processor import MediaProcessor


class TabProperties(ctk.CTkFrame):
    def __init__(self, master, app_ref):
        super().__init__(master, fg_color="transparent")
        self.app = app_ref
        
        self.file_path = None
        self.tracks = []
        self.track_widgets = {} # index -> dict of variables
        
        self._build_ui()

    def _build_ui(self):
        # File Drop
        self.drop_zone = FileDropZone(
            self, label="Select File to Edit", on_file_selected=self._on_file, height=120
        )
        self.drop_zone.pack(fill="x", padx=20, pady=(20, 10))
        
        # Track Properties List
        self.frame_props = ctk.CTkFrame(self, fg_color=Colors.BG_CARD)
        self.frame_props.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(self.frame_props, text="Track Properties:", font=ctk.CTkFont(weight="bold")).pack(anchor="w", padx=10, pady=10)
        
        self.list_props = ctk.CTkScrollableFrame(self.frame_props, fg_color=Colors.BG_INPUT)
        self.list_props.pack(fill="both", expand=True, padx=10, pady=5)
        
        # Action
        self.btn_apply = ctk.CTkButton(self, text="Apply Changes", fg_color=Colors.ACCENT, command=self._on_apply, state="disabled")
        self.btn_apply.pack(pady=10)
        
        # Status
        self.status_panel = StatusProgressPanel(self)
        self.status_panel.pack(fill="x", padx=20, pady=(0, 20))

    def _on_file(self, path):
        self.file_path = path
        
        for w in self.list_props.winfo_children():
            w.destroy()
        self.track_widgets.clear()
        
        if path:
            self.btn_apply.configure(state="disabled")
            self._load_tracks(path)
        else:
            self.btn_apply.configure(state="disabled")

    def _load_tracks(self, path):
        self.status_panel.set_status("Loading tracks...")
        
        def _worker():
            mp = MediaProcessor()
            try:
                tracks = mp.get_tracks(path)
                self.after(0, lambda: self._render_tracks(tracks))
            except Exception as e:
                self.after(0, lambda: self.status_panel.set_status(f"Error: {e}", Colors.ERROR))
                
        threading.Thread(target=_worker, daemon=True).start()

    def _render_tracks(self, tracks):
        self.tracks = tracks
        self.status_panel.reset()
        
        if not tracks:
            ctk.CTkLabel(self.list_props, text="No editable tracks found").pack(pady=20)
            return
            
        for t in tracks:
            row = ctk.CTkFrame(self.list_props, fg_color="transparent")
            row.pack(fill="x", pady=5)
            
            lbl = ctk.CTkLabel(row, text=f"[{t['index']}] {t['type'].upper()} ({t['codec']})", width=150, anchor="w")
            lbl.grid(row=0, column=0, padx=5, sticky="w")
            
            # Title
            title_var = ctk.StringVar(value=t.get('name', ''))
            ctk.CTkLabel(row, text="Name:").grid(row=0, column=1, padx=5)
            ctk.CTkEntry(row, textvariable=title_var, width=150).grid(row=0, column=2, padx=5)
            
            # Language
            lang_var = ctk.StringVar(value=t.get('language', 'und'))
            ctk.CTkLabel(row, text="Lang:").grid(row=0, column=3, padx=5)
            ctk.CTkEntry(row, textvariable=lang_var, width=60).grid(row=0, column=4, padx=5)
            
            # Flags
            def_var = ctk.BooleanVar(value=t.get('default', False))
            ctk.CTkCheckBox(row, text="Default", variable=def_var).grid(row=0, column=5, padx=10)
            
            fcd_var = ctk.BooleanVar(value=t.get('forced', False))
            ctk.CTkCheckBox(row, text="Forced", variable=fcd_var).grid(row=0, column=6, padx=10)
            
            self.track_widgets[t['index']] = {
                'name': title_var,
                'lang': lang_var,
                'default': def_var,
                'forced': fcd_var
            }
            
        self.btn_apply.configure(state="normal")

    def _on_apply(self):
        # We need a new file to write to, as FFmpeg doesn't edit in-place reliably.
        # MKVPropEdit DOES, but we are using FFmpeg. We'll mux to a temp file then replace.
        out_path = filedialog.asksaveasfilename(
            title="Save Edited File",
            initialfile=f"edited_{os.path.basename(self.file_path)}",
            defaultextension=".mkv",
            filetypes=[("MKV", "*.mkv"), ("MP4", "*.mp4")]
        )
        
        if not out_path: return
        
        props = []
        for t in self.tracks:
            idx = t['index']
            w = self.track_widgets[idx]
            props.append({
                'index': idx,
                'name': w['name'].get(),
                'lang': w['lang'].get(),
                'default': w['default'].get(),
                'forced': w['forced'].get()
            })
            
        self.btn_apply.configure(state="disabled")
        
        def _worker():
            mp = MediaProcessor(
                status_callback=lambda s: self.after(0, lambda: self.status_panel.set_status(s)),
                progress_callback=lambda p: self.after(0, lambda: self.status_panel.set_progress(p))
            )
            try:
                mp.edit_properties(self.file_path, props, out_path)
                self.after(0, lambda: messagebox.showinfo("Success", "Properties applied successfully!"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, lambda: self.btn_apply.configure(state="normal"))
                
        threading.Thread(target=_worker, daemon=True).start()
