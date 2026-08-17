"""
Vic - Fix: Media Processor
==========================
FFmpeg wrapper for full MKVToolNix-equivalent capabilities.
"""

import subprocess
import os
import json
import threading


# ── Constants ──────────────────────────────────────────────────────────────

# Hide console windows when launching FFmpeg on Windows
_CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


# ── Utility Functions ──────────────────────────────────────────────────────

def format_file_size(size_bytes: int) -> str:
    """Format byte count as human-readable size (e.g., '4.2 GB')."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(size_bytes) < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} PB"


def format_duration(seconds: float) -> str:
    """Format seconds as HH:MM:SS or MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h}:{m:02d}:{s:02d}" if h > 0 else f"{m}:{s:02d}"


def get_secure_env() -> dict:
    """Return a strictly sanitized environment dictionary for subprocesses."""
    # Only allow absolutely critical system variables to prevent DLL hijacking
    # and environment injection.
    safe_keys = {"PATH", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", "TMP", "USERPROFILE"}
    safe_env = {k: v for k, v in os.environ.items() if k.upper() in safe_keys}
    return safe_env


# ── Media Processor ───────────────────────────────────────────────────────

class MediaProcessor:
    """
    Wraps FFmpeg/ffprobe for file inspection, muxing, extraction, and splitting.
    """

    def __init__(self, status_callback=None, progress_callback=None):
        self._status_callback = status_callback
        self._progress_callback = progress_callback
        self._env = get_secure_env()

    def _emit_status(self, message: str):
        if self._status_callback:
            self._status_callback(message)

    def _emit_progress(self, value: float):
        if self._progress_callback:
            self._progress_callback(value)

    # ── FFmpeg Availability ────────────────────────────────────────────────

    @staticmethod
    def check_ffmpeg() -> bool:
        env = get_secure_env()
        for tool in ("ffmpeg", "ffprobe"):
            try:
                result = subprocess.run(
                    [tool, "-version"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=_CREATION_FLAGS,
                    env=env,
                )
                if result.returncode != 0:
                    return False
            except FileNotFoundError:
                return False
        return True

    # ── File Probing ───────────────────────────────────────────────────────

    def probe(self, file_path: str) -> dict:
        file_path = os.path.abspath(file_path)
        cmd = [
            "ffprobe",
            "-nostdin",
            "-err_detect", "explode",
            "-protocol_whitelist", "file,pipe,crypto,data",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            "-show_chapters",
            file_path,
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_CREATION_FLAGS,
            env=self._env,
        )

        if result.returncode != 0:
            error = result.stderr.decode("utf-8", errors="replace")
            raise RuntimeError(
                f"ffprobe failed for '{os.path.basename(file_path)}':\n{error[-400:]}"
            )

        return json.loads(result.stdout.decode("utf-8"))

    def has_audio_stream(self, file_path: str) -> bool:
        try:
            info = self.probe(file_path)
            return any(s.get("codec_type") == "audio" for s in info.get("streams", []))
        except (RuntimeError, json.JSONDecodeError, KeyError):
            return False

    def get_duration(self, file_path: str) -> float:
        try:
            info = self.probe(file_path)
            fmt_duration = info.get("format", {}).get("duration")
            if fmt_duration:
                return float(fmt_duration)
            for stream in info.get("streams", []):
                dur = stream.get("duration")
                if dur:
                    return float(dur)
        except (RuntimeError, ValueError, json.JSONDecodeError, KeyError):
            pass
        return 0.0

    def get_file_info(self, file_path: str) -> dict:
        info = {
            "name": os.path.basename(file_path),
            "size": "Unknown",
            "duration": "Unknown",
            "video_codec": "—",
            "audio_codec": "—",
            "has_audio": False,
        }

        try:
            info["size"] = format_file_size(os.path.getsize(file_path))
        except OSError:
            pass

        try:
            probe_data = self.probe(file_path)
            duration_str = probe_data.get("format", {}).get("duration")
            if duration_str:
                info["duration"] = format_duration(float(duration_str))

            for stream in probe_data.get("streams", []):
                codec_type = stream.get("codec_type", "")
                codec_name = stream.get("codec_name", "unknown")

                if codec_type == "video" and info["video_codec"] == "—":
                    info["video_codec"] = codec_name.upper()
                elif codec_type == "audio" and info["audio_codec"] == "—":
                    info["audio_codec"] = codec_name.upper()
                    info["has_audio"] = True
        except (RuntimeError, json.JSONDecodeError, ValueError, KeyError):
            pass

        return info

    def get_tracks(self, file_path: str) -> list:
        try:
            probe_data = self.probe(file_path)
            tracks = []
            for stream in probe_data.get("streams", []):
                track = {
                    "index": stream.get("index"),
                    "type": stream.get("codec_type"),
                    "codec": stream.get("codec_name"),
                    "language": stream.get("tags", {}).get("language", "und"),
                    "name": stream.get("tags", {}).get("title", ""),
                    "default": stream.get("disposition", {}).get("default", 0) == 1,
                    "forced": stream.get("disposition", {}).get("forced", 0) == 1,
                }
                
                if track["type"] == "video":
                    track["details"] = f"{stream.get('width', '?')}x{stream.get('height', '?')}"
                elif track["type"] == "audio":
                    channels = stream.get("channels", "?")
                    sr = stream.get("sample_rate", "?")
                    track["details"] = f"{channels} ch, {sr} Hz"
                else:
                    track["details"] = ""
                    
                tracks.append(track)
            return tracks
        except Exception:
            return []

    def get_chapters(self, file_path: str) -> list:
        try:
            probe_data = self.probe(file_path)
            chapters = []
            for chap in probe_data.get("chapters", []):
                chapters.append({
                    "id": chap.get("id"),
                    "start": float(chap.get("start_time", 0)),
                    "end": float(chap.get("end_time", 0)),
                    "title": chap.get("tags", {}).get("title", f"Chapter {chap.get('id')}"),
                })
            return chapters
        except Exception:
            return []

    def get_attachments(self, file_path: str) -> list:
        try:
            probe_data = self.probe(file_path)
            attachments = []
            for stream in probe_data.get("streams", []):
                if stream.get("codec_type") == "attachment":
                    attachments.append({
                        "index": stream.get("index"),
                        "filename": stream.get("tags", {}).get("filename", "unknown"),
                        "mimetype": stream.get("tags", {}).get("mimetype", "unknown"),
                    })
            return attachments
        except Exception:
            return []

    # ── General FFmpeg Runner ────────────────────────────────────────────────
    
    def _run_ffmpeg(self, cmd: list, duration: float, cancel_event: threading.Event = None, output_path: str = None):
        """Helper to run ffmpeg, parse progress, and handle cancellation."""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_CREATION_FLAGS,
            universal_newlines=True,
            env=self._env,
        )

        stderr_lines = []

        def _drain_stderr():
            try:
                for line in process.stderr:
                    stderr_lines.append(line)
            except (ValueError, OSError):
                pass

        stderr_thread = threading.Thread(target=_drain_stderr, daemon=True)
        stderr_thread.start()

        try:
            for line in process.stdout:
                if cancel_event and cancel_event.is_set():
                    process.kill()
                    process.wait()
                    if output_path and os.path.exists(output_path):
                        try:
                            os.remove(output_path)
                        except OSError:
                            pass
                    raise InterruptedError("Operation cancelled by user.")

                line = line.strip()

                if line.startswith("out_time_us="):
                    try:
                        time_us = int(line.split("=", 1)[1])
                        if time_us > 0 and duration > 0:
                            progress = min(time_us / (duration * 1_000_000), 0.99)
                            self._emit_progress(progress)
                    except (ValueError, IndexError, ZeroDivisionError):
                        pass
                elif line == "progress=end":
                    self._emit_progress(1.0)
        except (ValueError, OSError):
            pass

        process.wait()
        stderr_thread.join(timeout=10)

        if process.returncode != 0:
            error_text = "".join(stderr_lines)
            if output_path and os.path.exists(output_path):
                try:
                    os.remove(output_path)
                except OSError:
                    pass
            raise RuntimeError(f"FFmpeg command failed:\n{error_text[-800:]}")

    # ── Core MKVToolNix Equivalents ────────────────────────────────────────

    def mux_swap(
        self,
        video_source: str,
        audio_source: str,
        output_path: str,
        offset_seconds: float = 0.0,
        preserve_subtitles: bool = True,
        cancel_event: threading.Event = None,
    ) -> str:
        video_source = os.path.abspath(video_source)
        audio_source = os.path.abspath(audio_source)
        output_path = os.path.abspath(output_path)

        out_name = os.path.basename(output_path)
        self._emit_status(f"Muxing: {out_name}...")
        self._emit_progress(0.0)

        cmd = ["ffmpeg", "-y", "-nostdin", "-err_detect", "explode", "-protocol_whitelist", "file,pipe,crypto,data"]
        cmd.extend(["-i", video_source])

        if abs(offset_seconds) > 0.0005:
            cmd.extend(["-itsoffset", f"{offset_seconds:.6f}"])
        cmd.extend(["-i", audio_source])

        cmd.extend([
            "-map", "0:v:0",
            "-map", "1:a:0",
        ])

        if preserve_subtitles:
            cmd.extend(["-map", "0:s?"])

        cmd.extend(["-c", "copy", "-shortest", "-progress", "pipe:1", output_path])
        duration = self.get_duration(video_source)
        
        self._run_ffmpeg(cmd, duration, cancel_event, output_path)
        self._emit_status(f"Muxing complete: {out_name} ✓")
        return output_path

    def mux_tracks(self, inputs: list, track_selections: list, output_path: str, cancel_event: threading.Event = None):
        """
        Advanced Multiplexer.
        inputs: list of file paths
        track_selections: list of dicts { 'file_idx': int, 'stream_idx': int, 'type': str, 'name': str, 'lang': str, 'default': bool, 'forced': bool, 'delay': float }
        """
        inputs = [os.path.abspath(i) for i in inputs]
        output_path = os.path.abspath(output_path)

        self._emit_status(f"Multiplexing to {os.path.basename(output_path)}...")
        self._emit_progress(0.0)

        cmd = ["ffmpeg", "-y", "-nostdin", "-err_detect", "explode", "-protocol_whitelist", "file,pipe,crypto,data"]
        
        input_map = {} 
        new_inputs = []
        
        for track in track_selections:
            key = (track['file_idx'], track.get('delay', 0.0))
            if key not in input_map:
                input_map[key] = len(new_inputs)
                new_inputs.append(key)
                
        for orig_idx, delay in new_inputs:
            if abs(delay) > 0.0005:
                cmd.extend(["-itsoffset", f"{delay:.6f}"])
            cmd.extend(["-i", inputs[orig_idx]])
            
        for out_idx, track in enumerate(track_selections):
            new_in_idx = input_map[(track['file_idx'], track.get('delay', 0.0))]
            
            cmd.extend(["-map", f"{new_in_idx}:{track['stream_idx']}"])
            
            if track.get('name'):
                cmd.extend([f"-metadata:s:{out_idx}", f"title={track['name']}"])
            if track.get('lang'):
                cmd.extend([f"-metadata:s:{out_idx}", f"language={track['lang']}"])
                
            disp = []
            if track.get('default'):
                disp.append("default")
            if track.get('forced'):
                disp.append("forced")
            
            if not disp:
                disp.append("0")
                
            cmd.extend([f"-disposition:s:{out_idx}", "+".join(disp)])

        cmd.extend(["-c", "copy", "-progress", "pipe:1", output_path])
        
        duration = max([self.get_duration(f) for f in inputs]) if inputs else 0
        self._run_ffmpeg(cmd, duration, cancel_event, output_path)
        self._emit_status("Multiplexing complete ✓")
        return output_path

    def extract_tracks(self, file_path: str, tracks_to_extract: list, output_dir: str, cancel_event: threading.Event = None):
        """
        Extract specific streams to individual files.
        tracks_to_extract: list of dicts { 'index': int, 'type': str, 'ext': str }
        """
        file_path = os.path.abspath(file_path)
        output_dir = os.path.abspath(output_dir)

        self._emit_status("Extracting tracks...")
        self._emit_progress(0.0)
        
        cmd = ["ffmpeg", "-y", "-nostdin", "-err_detect", "explode", "-protocol_whitelist", "file,pipe,crypto,data", "-i", file_path]
        
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        output_files = []
        
        for t in tracks_to_extract:
            # Traversal protection: ensure strictly basename and alphanumeric ext
            safe_ext = ''.join(c for c in t['ext'] if c.isalnum())
            safe_filename = f"{base_name}_track{t['index']}.{safe_ext}"
            out_file = os.path.join(output_dir, safe_filename)
            output_files.append(out_file)
            cmd.extend(["-map", f"0:{t['index']}", "-c", "copy", out_file])
            
        if not output_files:
            return
            
        cmd.insert(-1 * (len(output_files) * 5), "-progress")
        cmd.insert(-1 * (len(output_files) * 5), "pipe:1")

        duration = self.get_duration(file_path)
        self._run_ffmpeg(cmd, duration, cancel_event)
        self._emit_status("Extraction complete ✓")

    def split_by_duration(self, file_path: str, segment_seconds: float, output_dir: str, cancel_event: threading.Event = None):
        file_path = os.path.abspath(file_path)
        output_dir = os.path.abspath(output_dir)

        self._emit_status("Splitting by duration...")
        self._emit_progress(0.0)
        
        base_name = os.path.splitext(os.path.basename(file_path))[0]
        ext = os.path.splitext(file_path)[1]
        
        # Traversal protection: extension is safe because it's from os.path.splitext of basename
        out_pattern = os.path.join(output_dir, f"{base_name}_%03d{ext}")
        
        cmd = [
            "ffmpeg", "-y", "-nostdin", "-err_detect", "explode", "-protocol_whitelist", "file,pipe,crypto,data", "-i", file_path,
            "-c", "copy",
            "-f", "segment",
            "-segment_time", str(segment_seconds),
            "-reset_timestamps", "1",
            "-progress", "pipe:1",
            out_pattern
        ]
        
        duration = self.get_duration(file_path)
        self._run_ffmpeg(cmd, duration, cancel_event)
        self._emit_status("Splitting complete ✓")

    def concat_files(self, file_list: list, output_path: str, cancel_event: threading.Event = None):
        file_list = [os.path.abspath(f) for f in file_list]
        output_path = os.path.abspath(output_path)

        self._emit_status("Merging files...")
        self._emit_progress(0.0)
        
        list_file = output_path + ".list.txt"
        with open(list_file, "w", encoding="utf-8") as f:
            for file_path in file_list:
                sanitized = file_path.replace('\n', '').replace('\r', '')
                safe_path = sanitized.replace("'", "'\\''")
                f.write(f"file '{safe_path}'\n")
                
        cmd = [
            "ffmpeg", "-y",
            "-nostdin", "-err_detect", "explode",
            "-protocol_whitelist", "file,pipe,crypto,data",
            "-f", "concat",
            "-safe", "0",
            "-i", list_file,
            "-c", "copy",
            "-progress", "pipe:1",
            output_path
        ]
        
        duration = sum([self.get_duration(f) for f in file_list])
        
        try:
            self._run_ffmpeg(cmd, duration, cancel_event, output_path)
            self._emit_status("Merge complete ✓")
        finally:
            if os.path.exists(list_file):
                os.remove(list_file)

    def edit_properties(self, file_path: str, track_props: list, output_path: str, cancel_event: threading.Event = None):
        file_path = os.path.abspath(file_path)
        output_path = os.path.abspath(output_path)

        self._emit_status("Applying properties...")
        self._emit_progress(0.0)
        
        cmd = ["ffmpeg", "-y", "-nostdin", "-err_detect", "explode", "-protocol_whitelist", "file,pipe,crypto,data", "-i", file_path, "-map", "0", "-c", "copy"]
        
        for track in track_props:
            idx = track['index']
            if 'name' in track:
                cmd.extend([f"-metadata:s:{idx}", f"title={track['name']}"])
            if 'lang' in track:
                cmd.extend([f"-metadata:s:{idx}", f"language={track['lang']}"])
                
            disp = []
            if track.get('default'):
                disp.append("default")
            if track.get('forced'):
                disp.append("forced")
            
            if disp:
                cmd.extend([f"-disposition:s:{idx}", "+".join(disp)])
            else:
                cmd.extend([f"-disposition:s:{idx}", "0"])
                
        cmd.extend(["-progress", "pipe:1", output_path])
        duration = self.get_duration(file_path)
        self._run_ffmpeg(cmd, duration, cancel_event, output_path)
        self._emit_status("Properties applied ✓")
