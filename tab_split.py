"""
Vic - Fix: Split & Merge Tab
============================
Splits files by duration/size or merges multiple files sequentially.
"""

import customtkinter as ctk
import threading
import os
from tkinter import filedialog, messagebox

from ui_components import Colors, FileDropZone, StatusProgressPanel
from media_processor import MediaProcessor


class TabSplit(ctk.CTkFrame):
    def __init__(self, master, app_ref):
        super().__init__(master, fg_color="transparent")
        self.app = app_ref
        
        self.split_file = None
        self.merge_files = []
        
        self._build_ui()

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        
        # --- SPLIT SECTION (Left) ---
        self.frame_split = ctk.CTkFrame(self, fg_color=Colors.BG_CARD)
        self.frame_split.grid(row=0, column=0, padx=(20, 10), pady=(20, 10), sticky="nsew")
        
        ctk.CTkLabel(self.frame_split, text="✂️ Split File", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        self.drop_split = FileDropZone(self.frame_split, label="Source File", on_file_selected=self._on_split_file, height=100)
        self.drop_split.pack(fill="x", padx=10, pady=10)
        
        self.entry_duration = ctk.CTkEntry(self.frame_split, placeholder_text="Segment duration (seconds)")
        self.entry_duration.pack(fill="x", padx=10, pady=10)
        
        self.entry_out_dir = ctk.CTkEntry(self.frame_split, placeholder_text="Output Directory")
        self.entry_out_dir.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(self.frame_split, text="Browse Dir", command=lambda: self._browse_dir(self.entry_out_dir)).pack(padx=10, pady=5)
        
        self.btn_split = ctk.CTkButton(self.frame_split, text="Split File", fg_color=Colors.ACCENT, command=self._on_split, state="disabled")
        self.btn_split.pack(pady=10)
        
        # --- MERGE SECTION (Right) ---
        self.frame_merge = ctk.CTkFrame(self, fg_color=Colors.BG_CARD)
        self.frame_merge.grid(row=0, column=1, padx=(10, 20), pady=(20, 10), sticky="nsew")
        
        ctk.CTkLabel(self.frame_merge, text="🔗 Merge Files", font=ctk.CTkFont(size=18, weight="bold")).pack(pady=10)
        
        self.list_merge = ctk.CTkScrollableFrame(self.frame_merge, height=120, fg_color=Colors.BG_INPUT)
        self.list_merge.pack(fill="x", padx=10, pady=5)
        
        btn_frame = ctk.CTkFrame(self.frame_merge, fg_color="transparent")
        btn_frame.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(btn_frame, text="Add files", width=80, command=self._add_merge_files).pack(side="left")
        ctk.CTkButton(btn_frame, text="Clear", width=60, command=self._clear_merge_files).pack(side="right")
        
        self.entry_merge_out = ctk.CTkEntry(self.frame_merge, placeholder_text="Output File Path")
        self.entry_merge_out.pack(fill="x", padx=10, pady=10)
        
        self.btn_merge = ctk.CTkButton(self.frame_merge, text="Merge Files", fg_color=Colors.ACCENT, command=self._on_merge, state="disabled")
        self.btn_merge.pack(pady=10)
        
        # --- STATUS ---
        self.status_panel = StatusProgressPanel(self)
        self.status_panel.grid(row=1, column=0, columnspan=2, sticky="ew", padx=20, pady=(0, 20))

    def _browse_dir(self, entry):
        d = filedialog.askdirectory()
        if d:
            entry.delete(0, 'end')
            entry.insert(0, d)

    def _on_split_file(self, path):
        self.split_file = path
        if path:
            self.entry_out_dir.delete(0, 'end')
            self.entry_out_dir.insert(0, os.path.dirname(path))
            self.btn_split.configure(state="normal")
        else:
            self.btn_split.configure(state="disabled")

    def _add_merge_files(self):
        paths = filedialog.askopenfilenames()
        if paths:
            self.merge_files.extend(paths)
            self._render_merge_list()

    def _clear_merge_files(self):
        self.merge_files.clear()
        self._render_merge_list()

    def _render_merge_list(self):
        for w in self.list_merge.winfo_children(): w.destroy()
        for i, f in enumerate(self.merge_files):
            ctk.CTkLabel(self.list_merge, text=os.path.basename(f)).pack(anchor="w")
            
        if self.merge_files and not self.entry_merge_out.get():
            base = os.path.splitext(self.merge_files[0])[0]
            self.entry_merge_out.insert(0, f"{base}_merged.mkv")
            
        self.btn_merge.configure(state="normal" if len(self.merge_files) > 1 else "disabled")

    def _on_split(self):
        try:
            sec = float(self.entry_duration.get())
        except ValueError:
            messagebox.showerror("Error", "Invalid duration")
            return
            
        out_dir = self.entry_out_dir.get()
        if not out_dir or not self.split_file: return
        
        self.btn_split.configure(state="disabled")
        
        def _worker():
            mp = MediaProcessor(
                status_callback=lambda s: self.after(0, lambda: self.status_panel.set_status(s)),
                progress_callback=lambda p: self.after(0, lambda: self.status_panel.set_progress(p))
            )
            try:
                mp.split_by_duration(self.split_file, sec, out_dir)
                self.after(0, lambda: messagebox.showinfo("Success", "Split complete!"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, lambda: self.btn_split.configure(state="normal"))
                
        threading.Thread(target=_worker, daemon=True).start()

    def _on_merge(self):
        out_path = self.entry_merge_out.get()
        if not out_path or len(self.merge_files) < 2: return
        
        self.btn_merge.configure(state="disabled")
        
        def _worker():
            mp = MediaProcessor(
                status_callback=lambda s: self.after(0, lambda: self.status_panel.set_status(s)),
                progress_callback=lambda p: self.after(0, lambda: self.status_panel.set_progress(p))
            )
            try:
                mp.concat_files(self.merge_files, out_path)
                self.after(0, lambda: messagebox.showinfo("Success", "Merge complete!"))
            except Exception as e:
                self.after(0, lambda: messagebox.showerror("Error", str(e)))
            finally:
                self.after(0, lambda: self.btn_merge.configure(state="normal"))
                
        threading.Thread(target=_worker, daemon=True).start()
