"""
Vic - Fix: Sync Engine
======================
Handles audio extraction and cross-correlation synchronization.

Strategy for handling massive files (up to 100GB):
- Extract ONLY the first 5 minutes of audio from each video.
- Downsample to 16kHz mono WAV (~9.6 MB per sample).
- Run cross-correlation on these small arrays — takes ~100ms.
- Total RAM usage stays well under 500MB.

Cross-Correlation Math
----------------------
Given two audio signals a[n] and b[n], the cross-correlation c[k]
measures similarity as a function of time-lag k:

    c[k] = Σ_n  a[n] · b[n - k]

The lag k_max at which |c[k]| is maximized is the optimal alignment:
  - k_max > 0  →  a's events occur k_max samples LATER than b's
  - k_max < 0  →  a's events occur |k_max| samples EARLIER than b's

Converting to seconds:  offset = k_max / sample_rate

This offset is passed to FFmpeg's -itsoffset flag during the muxing
phase to perfectly synchronize the swapped audio tracks.
"""

import subprocess
import tempfile
import os
import sys
import wave

import numpy as np
from scipy.signal import correlate, correlation_lags

from media_processor import get_secure_env

# Subprocess flag to hide console windows on Windows
_CREATION_FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)


class SyncEngine:
    """Extracts short audio samples and calculates sync offset via cross-correlation."""

    # ── Configuration ──────────────────────────────────────────────────────
    # 16kHz mono WAV: 5 minutes = 4,800,000 samples × 2 bytes ≈ 9.6 MB
    # This keeps total RAM for both samples + correlation well under 200MB.
    SAMPLE_RATE = 16000            # Hz — sufficient for speech/music sync
    SAMPLE_DURATION_SECONDS = 300  # 5 minutes

    def __init__(self, status_callback=None):
        """
        Args:
            status_callback: Optional callable(str) invoked with status messages.
                             Used by the UI to display progress text.
        """
        self._status_callback = status_callback
        self._temp_dir = tempfile.mkdtemp(prefix="vicfix_sync_")

    def _emit_status(self, message: str):
        """Send a status update (thread-safe — the UI schedules it via after())."""
        if self._status_callback:
            self._status_callback(message)

    # ── Audio Extraction ───────────────────────────────────────────────────

    def extract_audio_sample(self, video_path: str, label: str = "video") -> str:
        """
        Extract the first 5 minutes of audio from a video file as 16kHz mono WAV.

        FFmpeg command breakdown:
          -y                    Overwrite output without asking
          -i <input>            Input video file
          -t 300                Process only the first 300 seconds (5 min)
          -vn                   Discard all video streams (audio only)
          -ac 1                 Mix down to 1 channel (mono)
          -ar 16000             Resample to 16,000 Hz
          -acodec pcm_s16le     16-bit signed little-endian PCM
          -f wav                Output format: WAV

        This takes only a few seconds even for 100GB files because FFmpeg
        reads only the first 5 minutes of the audio stream, not the entire file.

        Args:
            video_path: Absolute path to the input video file.
            label:      Human-readable label for status messages (e.g., "Video A").

        Returns:
            Path to the extracted WAV sample file in the temp directory.

        Raises:
            ValueError:  If the video has no audio track.
            RuntimeError: If FFmpeg encounters an error.
        """
        self._emit_status(f"Extracting audio sample from {label}...")

        output_path = os.path.join(self._temp_dir, f"{label.replace(' ', '_')}_sample.wav")
        video_path = os.path.abspath(video_path)

        cmd = [
            "ffmpeg", "-y",
            "-nostdin", "-err_detect", "explode",
            "-protocol_whitelist", "file,pipe,crypto,data",
            "-i", video_path,
            "-t", str(self.SAMPLE_DURATION_SECONDS),
            "-vn",
            "-ac", "1",
            "-ar", str(self.SAMPLE_RATE),
            "-acodec", "pcm_s16le",
            "-f", "wav",
            output_path,
        ]

        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            creationflags=_CREATION_FLAGS,
            env=get_secure_env(),
        )

        stderr_text = result.stderr.decode("utf-8", errors="replace")

        if result.returncode != 0:
            # Detect the specific "no audio stream" failure
            no_audio_markers = [
                "does not contain any stream",
                "output file #0 does not contain",
                "could not find codec",
                "encoder not found",
            ]
            if any(m in stderr_text.lower() for m in no_audio_markers):
                raise ValueError(f"{label} does not contain an audio track.")
            raise RuntimeError(
                f"FFmpeg audio extraction failed for {label}:\n{stderr_text[-600:]}"
            )

        # Sanity check: output must exist and have meaningful content
        if not os.path.exists(output_path) or os.path.getsize(output_path) < 100:
            raise ValueError(
                f"{label} does not contain a usable audio track "
                f"(extraction produced no output)."
            )

        self._emit_status(f"Audio sample extracted from {label} ✓")
        return output_path

    # ── WAV Loading ────────────────────────────────────────────────────────

    @staticmethod
    def _load_wav_as_float32(wav_path: str) -> np.ndarray:
        """
        Load a 16-bit PCM WAV file into a normalized float32 NumPy array.

        Normalization: int16 range [-32768, 32767] → float32 range [-1.0, 1.0].
        This ensures cross-correlation values are scale-independent and
        the confidence metric is meaningful.

        Args:
            wav_path: Path to a 16-bit PCM WAV file.

        Returns:
            1-D NumPy float32 array with values in [-1.0, 1.0].
        """
        with wave.open(wav_path, "rb") as wf:
            n_frames = wf.getnframes()
            raw_bytes = wf.readframes(n_frames)

        # Interpret raw bytes as signed 16-bit integers, then normalize
        samples = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32)
        samples /= 32768.0
        return samples

    # ── Cross-Correlation Offset Calculation ──────────────────────────────

    def calculate_offset(self, video_a_path: str, video_b_path: str) -> tuple:
        """
        Calculate the time offset between two videos' audio tracks.

        Full pipeline:
        1. Extract 5-minute 16kHz mono samples from both videos
        2. Load samples as normalized float32 arrays
        3. Compute full cross-correlation via scipy.signal.correlate
        4. Find the lag at peak absolute correlation
        5. Convert lag (in samples) to offset (in seconds)
        6. Compute a normalized confidence metric

        Offset interpretation:
        - offset > 0: A's audio events happen LATER than B's
                      (A started recording after B)
        - offset < 0: A's audio events happen EARLIER than B's
                      (A started recording before B)

        When applying the offset during muxing:
        - Video A + Audio B: use -itsoffset +offset on Audio B
          (delay B's audio to match A's timeline)
        - Video B + Audio A: use -itsoffset -offset on Audio A
          (advance A's audio to match B's timeline)

        Args:
            video_a_path: Absolute path to Video A.
            video_b_path: Absolute path to Video B.

        Returns:
            Tuple of (offset_seconds: float, confidence: float):
            - offset_seconds: Time offset in seconds (see interpretation above).
            - confidence: Normalized peak correlation strength in [0.0, 1.0].
                          Values above ~0.1 typically indicate a valid match.
        """
        # ── Step 1: Extract audio samples via FFmpeg ──
        wav_a_path = self.extract_audio_sample(video_a_path, "Video A")
        wav_b_path = self.extract_audio_sample(video_b_path, "Video B")

        # ── Step 2: Load WAV files as NumPy arrays ──
        self._emit_status("Loading audio samples into memory...")
        samples_a = self._load_wav_as_float32(wav_a_path)
        samples_b = self._load_wav_as_float32(wav_b_path)

        if len(samples_a) == 0 or len(samples_b) == 0:
            raise ValueError("One or both audio samples are empty (0 frames).")

        # ── Step 3: Compute cross-correlation ──
        self._emit_status("Computing cross-correlation for sync offset...")

        # correlate(a, b, mode='full') computes:
        #   c[k] = Σ_n  a[n+lag] · b[n]   for lag in correlation_lags(...)
        #
        # 'full' mode returns all (len_a + len_b - 1) lag values, ensuring
        # we find the global optimum even for large offsets.
        #
        # We take abs() to handle phase-inverted recordings (e.g., different
        # microphone polarities that produce inverted waveforms).
        correlation = correlate(samples_a, samples_b, mode="full")

        # correlation_lags() returns the actual lag values corresponding to
        # each index in the correlation output — avoids error-prone manual
        # index arithmetic.
        lags = correlation_lags(len(samples_a), len(samples_b), mode="full")

        # ── Step 4: Find the peak ──
        peak_index = np.argmax(np.abs(correlation))
        best_lag_samples = lags[peak_index]

        # ── Step 5: Convert lag (samples) → offset (seconds) ──
        offset_seconds = float(best_lag_samples) / self.SAMPLE_RATE

        # ── Step 6: Compute confidence metric ──
        # Normalized correlation coefficient: divide the peak correlation by
        # the geometric mean of both signals' energies (L2 norms).
        # This gives a value analogous to Pearson's r — 1.0 = perfect match.
        energy_a = np.sqrt(np.sum(samples_a ** 2))
        energy_b = np.sqrt(np.sum(samples_b ** 2))
        denominator = energy_a * energy_b

        if denominator > 0:
            confidence = float(abs(correlation[peak_index]) / denominator)
            confidence = min(confidence, 1.0)  # Clamp for numerical safety
        else:
            confidence = 0.0

        # ── Log results ──
        direction = "behind" if offset_seconds > 0 else "ahead of"
        self._emit_status(
            f"Sync offset: {offset_seconds:+.3f}s "
            f"(A is {abs(offset_seconds):.3f}s {direction} B) "
            f"| Confidence: {confidence:.1%}"
        )

        return offset_seconds, confidence

    # ── Cleanup ────────────────────────────────────────────────────────────

    def cleanup(self):
        """Remove all temporary WAV files created during processing."""
        import shutil

        if os.path.exists(self._temp_dir):
            try:
                shutil.rmtree(self._temp_dir)
            except OSError:
                pass  # Best-effort cleanup; temp dir will be reclaimed by OS
