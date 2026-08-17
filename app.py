"""
Vic - Fix: Desktop Application
===============================
Modern, dark-themed CustomTkinter GUI.
Now expanded with full MKVToolNix-equivalent capabilities across 6 tabs.
"""

import customtkinter as ctk
from tkinter import messagebox
import os
import sys
import threading

from ui_components import Colors
from media_processor import MediaProcessor

from tab_swap import TabSwap
from tab_info import TabInfo
from tab_muxer import TabMuxer
from tab_extract import TabExtract
from tab_split import TabSplit
from tab_properties import TabProperties

# ── Application Main Window ───────────────────────────────────────────────

class VicFixApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Setup ---
        self.title("Vic - Fix (MKVToolNix Edition)")
        
        # Make the window bigger to accommodate complex tabs
        window_width = 1100
        window_height = 800
        
        # Center window on screen
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()
        x = (screen_width // 2) - (window_width // 2)
        y = (screen_height // 2) - (window_height // 2)
        self.geometry(f"{window_width}x{window_height}+{x}+{y}")
        self.minsize(900, 700)
        
        # Force to front
        self.attributes('-topmost', True)
        self.update()
        self.attributes('-topmost', False)
        self.lift()

        # Set dark theme overrides globally
        ctk.set_appearance_mode("dark")
        self.configure(fg_color=Colors.BG_DARK)

        self._build_ui()
        self._check_dependencies()

    def _build_ui(self):
        """Construct the main tabbed layout."""
        # --- Header ---
        self.header = ctk.CTkFrame(self, fg_color="transparent", height=60)
        self.header.pack(fill="x", padx=20, pady=(20, 10))
        self.header.pack_propagate(False)

        # Logo / Title
        title_label = ctk.CTkLabel(
            self.header,
            text="Vic - Fix",
            font=ctk.CTkFont(family="Segoe UI", size=28, weight="bold"),
            text_color=Colors.TEXT_PRIMARY
        )
        title_label.pack(side="left")
        
        subtitle_label = ctk.CTkLabel(
            self.header,
            text="PRO",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=Colors.ACCENT,
            fg_color=Colors.BG_CARD,
            corner_radius=6
        )
        subtitle_label.pack(side="left", padx=10, pady=(6, 0))

        # --- Tabview ---
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=Colors.BG_CARD,
            segmented_button_fg_color=Colors.BG_INPUT,
            segmented_button_selected_color=Colors.ACCENT,
            segmented_button_selected_hover_color=Colors.ACCENT_HOVER,
            segmented_button_unselected_color=Colors.BG_INPUT,
            segmented_button_unselected_hover_color=Colors.BG_CARD_HOVER,
            text_color=Colors.TEXT_PRIMARY
        )
        self.tabview.pack(fill="both", expand=True, padx=20, pady=(0, 20))

        # Add tabs
        self.tabview.add("🔄 Audio Swap")
        self.tabview.add("🔀 Multiplexer")
        self.tabview.add("📤 Extractor")
        self.tabview.add("✂️ Split & Merge")
        self.tabview.add("⚙️ Properties")
        self.tabview.add("🔍 Inspector")

        # Instantiate tab content
        self.tab_swap = TabSwap(self.tabview.tab("🔄 Audio Swap"), self)
        self.tab_swap.pack(fill="both", expand=True)

        self.tab_muxer = TabMuxer(self.tabview.tab("🔀 Multiplexer"), self)
        self.tab_muxer.pack(fill="both", expand=True)
        
        self.tab_extract = TabExtract(self.tabview.tab("📤 Extractor"), self)
        self.tab_extract.pack(fill="both", expand=True)
        
        self.tab_split = TabSplit(self.tabview.tab("✂️ Split & Merge"), self)
        self.tab_split.pack(fill="both", expand=True)

        self.tab_properties = TabProperties(self.tabview.tab("⚙️ Properties"), self)
        self.tab_properties.pack(fill="both", expand=True)
        
        self.tab_info = TabInfo(self.tabview.tab("🔍 Inspector"), self)
        self.tab_info.pack(fill="both", expand=True)

        # Keyboard shortcuts for tabs (Ctrl+1 to Ctrl+6)
        self.bind("<Control-1>", lambda e: self.tabview.set("🔄 Audio Swap"))
        self.bind("<Control-2>", lambda e: self.tabview.set("🔀 Multiplexer"))
        self.bind("<Control-3>", lambda e: self.tabview.set("📤 Extractor"))
        self.bind("<Control-4>", lambda e: self.tabview.set("✂️ Split & Merge"))
        self.bind("<Control-5>", lambda e: self.tabview.set("⚙️ Properties"))
        self.bind("<Control-6>", lambda e: self.tabview.set("🔍 Inspector"))

    def _check_dependencies(self):
        """Verify FFmpeg is available on launch."""
        def _worker():
            if not MediaProcessor.check_ffmpeg():
                self.after(0, self._show_dependency_error)
        threading.Thread(target=_worker, daemon=True).start()

    def _show_dependency_error(self):
        """Show a fatal error if FFmpeg is missing."""
        msg = (
            "FFmpeg could not be found on your system PATH.\n\n"
            "Vic - Fix relies entirely on FFmpeg to process media files.\n"
            "Please install FFmpeg and ensure it is available in your command line."
        )
        messagebox.showerror("Missing Dependency: FFmpeg", msg)
        self.destroy()
        sys.exit(1)


# ── Entry Point ──────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = VicFixApp()
    app.mainloop()
