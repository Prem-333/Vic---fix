"""
Vic - Fix: Audio Swap Tab
=========================
Extracts the original audio swap functionality into a separate tab.
"""

import customtkinter as ctk
import threading
import os
from tkinter import messagebox

from ui_components import Colors, FileDropZone, StatusProgressPanel
from sync_engine import SyncEngine
from media_processor import MediaProcessor


class TabSwap(ctk.CTkFrame):
    def __init__(self, master, app_ref):
        super().__init__(master, fg_color="transparent")
        self.app = app_ref
        
        self.sync_engine = SyncEngine()
        
        # State
        self.is_processing = False
        self._cancel_event = threading.Event()
        self.file_a = None
        self.file_b = None

        self._build_ui()

    def _build_ui(self):
        # Top Container for Drop Zones
        self.drop_container = ctk.CTkFrame(self, fg_color="transparent")
        self.drop_container.pack(fill="x", padx=20, pady=(20, 10))
        self.drop_container.grid_columnconfigure(0, weight=1)
        self.drop_container.grid_columnconfigure(1, weight=1)

        # Video A
        self.drop_a = FileDropZone(
            self.drop_container,
            label="Video A (Source 1)",
            on_file_selected=self._on_file_a,
            height=200
        )
        self.drop_a.grid(row=0, column=0, padx=(0, 10), sticky="nsew")

        # Swap Icon
        icon_label = ctk.CTkLabel(
            self.drop_container, text="⇄", font=ctk.CTkFont(size=32),
            text_color=Colors.TEXT_MUTED
        )
        icon_label.grid(row=0, column=0, columnspan=2, sticky="ns")

        # Video B
        self.drop_b = FileDropZone(
            self.drop_container,
            label="Video B (Source 2)",
            on_file_selected=self._on_file_b,
            height=200
        )
        self.drop_b.grid(row=0, column=1, padx=(10, 0), sticky="nsew")

        # Action Button
        self.btn_action = ctk.CTkButton(
            self, text="🔄  Swap & Sync Audio",
            font=ctk.CTkFont(family="Segoe UI", size=15, weight="bold"),
            height=50, corner_radius=12,
            fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER,
            command=self._on_action_click, state="disabled"
        )
        self.btn_action.pack(fill="x", padx=20, pady=(10, 20))

        # Status / Progress
        self.status_panel = StatusProgressPanel(self)
        self.status_panel.pack(fill="x", padx=20, pady=0)

    def _on_file_a(self, path):
        self.file_a = path
        self._check_ready()
        if path:
            self._probe_file_async(path, self.drop_a)

    def _on_file_b(self, path):
        self.file_b = path
        self._check_ready()
        if path:
            self._probe_file_async(path, self.drop_b)

    def _probe_file_async(self, file_path, drop_zone):
        def _worker():
            mp = MediaProcessor()
            info = mp.get_file_info(file_path)
            def _update():
                text = f"Codec: {info['video_codec']} / {info['audio_codec']} | {info['duration']}"
                drop_zone.set_info_text(text)
                if not info["has_audio"]:
                    drop_zone.set_info_text("⚠️ No audio stream detected!")
                    drop_zone.configure(border_color=Colors.WARNING)
            self.after(0, _update)
        threading.Thread(target=_worker, daemon=True).start()

    def _check_ready(self):
        if self.file_a and self.file_b and not self.is_processing:
            self.btn_action.configure(state="normal")
        else:
            self.btn_action.configure(state="disabled")

    def _on_action_click(self):
        if self.is_processing:
            if messagebox.askyesno("Cancel", "Are you sure you want to cancel?"):
                self.btn_action.configure(state="disabled", text="Cancelling...")
                self._cancel_event.set()
            return

        self.is_processing = True
        self._cancel_event.clear()
        self.btn_action.configure(text="✕  Cancel", fg_color=Colors.ERROR, hover_color=Colors.ERROR_HOVER)
        self.drop_a.set_enabled(False)
        self.drop_b.set_enabled(False)
        self.status_panel.reset()
        
        threading.Thread(target=self._process_worker, daemon=True).start()

    def _process_worker(self):
        try:
            self._update_status("Step 1: Extracting audio samples...", 0.05)
            
            # Need a local MediaProcessor for this thread to prevent progress clashes
            def _prog_cb(val):
                self._update_progress(val)
                
            mp = MediaProcessor(progress_callback=_prog_cb)
            
            # 1. Extract audio
            sample_a, sample_b = self.sync_engine.extract_audio_samples(
                self.file_a, self.file_b, duration=300, cancel_event=self._cancel_event
            )
            
            self._update_status("Step 2: Calculating synchronization offset...", 0.3)
            # 2. Correlate
            offset = self.sync_engine.calculate_offset(sample_a, sample_b, cancel_event=self._cancel_event)
            
            self._update_status(f"Calculated offset: {offset:.3f} seconds.", 0.35)
            
            # 3. Mux outputs
            out_dir = os.path.dirname(self.file_a)
            base_a, ext_a = os.path.splitext(os.path.basename(self.file_a))
            base_b, ext_b = os.path.splitext(os.path.basename(self.file_b))
            
            out_a = os.path.join(out_dir, f"{base_a}_vicfix{ext_a}")
            out_b = os.path.join(out_dir, f"{base_b}_vicfix{ext_b}")
            
            def _scoped_prog(val, start, end):
                self._update_progress(start + val * (end - start))
            
            # Mux A (Video A + Audio B, meaning we shift B by -offset)
            mp = MediaProcessor(progress_callback=lambda v: _scoped_prog(v, 0.4, 0.7))
            mp.mux_swap(self.file_a, self.file_b, out_a, offset_seconds=-offset, cancel_event=self._cancel_event)
            
            # Mux B (Video B + Audio A, meaning we shift A by +offset)
            mp = MediaProcessor(progress_callback=lambda v: _scoped_prog(v, 0.7, 1.0))
            mp.mux_swap(self.file_b, self.file_a, out_b, offset_seconds=offset, cancel_event=self._cancel_event)
            
            self.after(0, self._on_success)
            
        except InterruptedError:
            self.after(0, self._on_cancel_complete)
        except Exception as e:
            self.after(0, lambda: self._on_error(str(e)))
        finally:
            self.sync_engine.cleanup()

    def _update_status(self, msg, prog):
        self.after(0, lambda: self.status_panel.set_status(msg))
        self.after(0, lambda: self.status_panel.set_progress(prog))
        
    def _update_progress(self, prog):
        self.after(0, lambda: self.status_panel.set_progress(prog))

    def _on_success(self):
        self._reset_ui()
        self.status_panel.set_status("Complete! Output files saved next to originals.", Colors.SUCCESS)
        self.status_panel.set_progress(1.0)
        messagebox.showinfo("Success", "Audio swap and sync completed successfully.")

    def _on_error(self, err_msg):
        self._reset_ui()
        self.status_panel.set_status("Error occurred.", Colors.ERROR)
        messagebox.showerror("Processing Error", f"An error occurred:\n{err_msg}")

    def _on_cancel_complete(self):
        self._reset_ui()
        self.status_panel.set_status("Cancelled.", Colors.WARNING)

    def _reset_ui(self):
        self.is_processing = False
        self.btn_action.configure(text="🔄  Swap & Sync Audio", fg_color=Colors.ACCENT, hover_color=Colors.ACCENT_HOVER, state="normal")
        self.drop_a.set_enabled(True)
        self.drop_b.set_enabled(True)
