"""
Vic - Fix: Multiplexer Tab
==========================
Equivalent to MKVToolNix GUI's primary muxing interface.
"""

import customtkinter as ctk
import threading
import os
from tkinter import filedialog, messagebox

from ui_components import Colors, StatusProgressPanel
from media_processor import MediaProcessor


class TabMuxer(ctk.CTkFrame):
    def __init__(self, master, app_ref):
        super().__init__(master, fg_color="transparent")
        self.app = app_ref
        
        self.input_files = [] # list of dicts: {'path': str, 'tracks': list}
        self.track_vars = {} # (file_idx, stream_idx) -> ctk.BooleanVar
        
        self._build_ui()

    def _build_ui(self):
        # --- Top: Input Files ---
        self.frame_inputs = ctk.CTkFrame(self, fg_color=Colors.BG_CARD)
        self.frame_inputs.pack(fill="x", padx=20, pady=(20, 10))
        
        lbl_inputs = ctk.CTkLabel(self.frame_inputs, text="Input files:", font=ctk.CTkFont(weight="bold"))
        lbl_inputs.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.list_inputs = ctk.CTkScrollableFrame(self.frame_inputs, height=100, fg_color=Colors.BG_INPUT)
        self.list_inputs.pack(fill="x", padx=10, pady=5)
        
        btn_frame = ctk.CTkFrame(self.frame_inputs, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=(0, 10))
        
        ctk.CTkButton(btn_frame, text="+ Add source files", width=120, command=self._add_files).pack(side="left")
        ctk.CTkButton(btn_frame, text="- Remove all", width=120, fg_color=Colors.ERROR, hover_color=Colors.ERROR_HOVER, command=self._clear_inputs).pack(side="left", padx=10)
        
        # --- Middle: Tracks ---
        self.frame_tracks = ctk.CTkFrame(self, fg_color=Colors.BG_CARD)
        self.frame_tracks.pack(fill="both", expand=True, padx=20, pady=10)
        
        lbl_tracks = ctk.CTkLabel(self.frame_tracks, text="Tracks, chapters and tags:", font=ctk.CTkFont(weight="bold"))
        lbl_tracks.pack(anchor="w", padx=10, pady=(10, 0))
        
        self.list_tracks = ctk.CTkScrollableFrame(self.frame_tracks, fg_color=Colors.BG_INPUT)
        self.list_tracks.pack(fill="both", expand=True, padx=10, pady=5)
        
        # --- Bottom: Output ---
        self.frame_out = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_out.pack(fill="x", padx=20, pady=10)
        
        self.out_entry = ctk.CTkEntry(self.frame_out, placeholder_text="Output file path")
        self.out_entry.pack(side="left", fill="x", expand=True, padx=(0, 10))
        
        ctk.CTkButton(self.frame_out, text="Browse", width=80, command=self._browse_out).pack(side="left", padx=(0, 10))
        
        self.btn_mux = ctk.CTkButton(self.frame_out, text="Start multiplexing", fg_color=Colors.ACCENT, command=self._start_muxing, state="disabled")
        self.btn_mux.pack(side="left")
        
        # Status
        self.status_panel = StatusProgressPanel(self)
        self.status_panel.pack(fill="x", padx=20, pady=(0, 20))

    def _add_files(self):
        paths = filedialog.askopenfilenames(title="Select Media Files")
        if not paths: return
        
        self.status_panel.set_status("Probing files...")
        
        def _worker():
            mp = MediaProcessor()
            for path in paths:
                try:
                    tracks = mp.get_tracks(path)
                    self.input_files.append({'path': path, 'tracks': tracks})
                except Exception:
                    pass
            self.after(0, self._render_all)
            
        threading.Thread(target=_worker, daemon=True).start()

    def _clear_inputs(self):
        self.input_files.clear()
        self.track_vars.clear()
        self._render_all()

    def _render_all(self):
        # Render inputs
        for w in self.list_inputs.winfo_children(): w.destroy()
        for i, f in enumerate(self.input_files):
            name = os.path.basename(f['path'])
            ctk.CTkLabel(self.list_inputs, text=f"[{i}] {name}", anchor="w").pack(fill="x")
            
        # Render tracks
        for w in self.list_tracks.winfo_children(): w.destroy()
        
        for f_idx, f in enumerate(self.input_files):
            for t in f['tracks']:
                row = ctk.CTkFrame(self.list_tracks, fg_color="transparent")
                row.pack(fill="x", pady=2)
                
                key = (f_idx, t['index'])
                if key not in self.track_vars:
                    self.track_vars[key] = ctk.BooleanVar(value=True)
                    
                cb = ctk.CTkCheckBox(row, text=f"{t['type'].upper()} ({t['codec']}) - {t['language']} (from file {f_idx})", variable=self.track_vars[key])
                cb.pack(side="left")
                
        # Update output path
        if self.input_files and not self.out_entry.get():
            base = os.path.splitext(self.input_files[0]['path'])[0]
            self.out_entry.insert(0, f"{base}_muxed.mkv")
            
        self.btn_mux.configure(state="normal" if self.input_files else "disabled")
        self.status_panel.reset()

    def _browse_out(self):
        p = filedialog.asksaveasfilename(defaultextension=".mkv", filetypes=[("MKV", "*.mkv"), ("MP4", "*.mp4")])
        if p:
            self.out_entry.delete(0, 'end')
            self.out_entry.insert(0, p)

    def _start_muxing(self):
        out_path = self.out_entry.get()
        if not out_path: return
        
        selected = []
        for f_idx, f in enumerate(self.input_files):
            for t in f['tracks']:
                if self.track_vars[(f_idx, t['index'])].get():
                    selected.append({
                        'file_idx': f_idx,
                        'stream_idx': t['index'],
                        'type': t['type'],
                        # In a full implementation we'd read delay/lang from per-track UI inputs
                    })
                    
        if not selected:
            messagebox.showinfo("Error", "No tracks selected")
            return
            
        self.btn_mux.configure(state="disabled")
        
        def _worker():
            mp = MediaProcessor(
                status_callback=lambda s: self.after(0, lambda: self.status_panel.set_status(s)),
                progress_callback=lambda p: self.after(0, lambda: self.status_panel.set_progress(p))
            )
            try:
                paths = [f['path'] for f in self.input_files]
                mp.mux_tracks(paths, selected, out_path)
                self.after(0, lambda: messagebox.showinfo("Success", "Multiplexing complete!"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, lambda: self.btn_mux.configure(state="normal"))
                
        threading.Thread(target=_worker, daemon=True).start()
