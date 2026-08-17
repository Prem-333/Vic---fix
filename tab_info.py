"""
Vic - Fix: File Inspector Tab
=============================
Displays detailed information about an MKV file, like mkvinfo.
"""

import customtkinter as ctk
import threading
from tkinter import messagebox

from ui_components import Colors, FileDropZone
from media_processor import MediaProcessor


class TabInfo(ctk.CTkFrame):
    def __init__(self, master, app_ref):
        super().__init__(master, fg_color="transparent")
        self.app = app_ref
        
        self.file_path = None
        self._build_ui()

    def _build_ui(self):
        # File Drop
        self.drop_zone = FileDropZone(
            self,
            label="Drop Media File Here",
            on_file_selected=self._on_file,
            height=120
        )
        self.drop_zone.pack(fill="x", padx=20, pady=(20, 10))
        
        # Info Text Area
        self.text_area = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Consolas", size=13),
            fg_color=Colors.BG_INPUT,
            text_color=Colors.TEXT_PRIMARY,
            state="disabled",
            wrap="word"
        )
        self.text_area.pack(fill="both", expand=True, padx=20, pady=(0, 20))

    def _on_file(self, path):
        self.file_path = path
        if path:
            self._load_info(path)
        else:
            self._set_text("")

    def _load_info(self, path):
        self._set_text("Loading...")
        
        def _worker():
            mp = MediaProcessor()
            try:
                info = mp.probe(path)
                
                lines = []
                lines.append("=== CONTAINER ===")
                fmt = info.get("format", {})
                lines.append(f"Format:       {fmt.get('format_name', 'unknown')}")
                lines.append(f"Duration:     {fmt.get('duration', 'unknown')} s")
                lines.append(f"Size:         {fmt.get('size', 'unknown')} bytes")
                lines.append(f"Bitrate:      {fmt.get('bit_rate', 'unknown')} bps")
                
                lines.append("\n=== TRACKS ===")
                for stream in info.get("streams", []):
                    idx = stream.get("index")
                    ctype = stream.get("codec_type", "unknown").upper()
                    cname = stream.get("codec_name", "unknown")
                    lang = stream.get("tags", {}).get("language", "und")
                    title = stream.get("tags", {}).get("title", "")
                    
                    details = f"[{idx}] {ctype}: {cname} (Lang: {lang})"
                    if title:
                        details += f" - {title}"
                        
                    lines.append(details)
                    
                    if ctype == "VIDEO":
                        lines.append(f"    Res: {stream.get('width')}x{stream.get('height')}")
                    elif ctype == "AUDIO":
                        lines.append(f"    Channels: {stream.get('channels')}, SR: {stream.get('sample_rate')}Hz")
                
                chapters = info.get("chapters", [])
                if chapters:
                    lines.append("\n=== CHAPTERS ===")
                    for ch in chapters:
                        start = ch.get("start_time")
                        title = ch.get("tags", {}).get("title", "Chapter")
                        lines.append(f"[{start}s] {title}")
                
                self.after(0, lambda: self._set_text("\n".join(lines)))
                
            except Exception as e:
                self.after(0, lambda: self._set_text(f"Error loading info:\n{e}"))
                
        threading.Thread(target=_worker, daemon=True).start()

    def _set_text(self, text):
        self.text_area.configure(state="normal")
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", text)
        self.text_area.configure(state="disabled")
