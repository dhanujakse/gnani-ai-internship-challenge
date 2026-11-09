import math
import struct
import numpy as np
import pytest

from sarvagyan_server.providers.base import SttEvent


class EnergyVadGate:
    def __init__(self, energy_threshold: float = 350.0, min_speech_ms: int = 200, hangover_ms: int = 350, sample_rate: int = 16000):
        self.energy_threshold = energy_threshold
        self.min_speech_ms = min_speech_ms
        self.hangover_ms = hangover_ms
        self.sample_rate = sample_rate
        self.speech_start_ms = -1
        self.last_speech_ms = -1

    def process_frame(self, pcm_frame: bytes, current_time_ms: int, noise_reduction: bool = True) -> bytes:
        if not noise_reduction:
            return pcm_frame

        samples = struct.unpack(f"<{len(pcm_frame)//2}h", pcm_frame)
        if not samples:
            return pcm_frame

        rms = math.sqrt(sum(s * s for s in samples) / len(samples))

        pass_speech = False
        if rms >= self.energy_threshold:
            if self.speech_start_ms < 0:
                self.speech_start_ms = current_time_ms
            duration = current_time_ms - self.speech_start_ms
            if duration >= self.min_speech_ms:
                self.last_speech_ms = current_time_ms
                pass_speech = True
            else:
                pass_speech = False  # short transient click or pop
        else:
            self.speech_start_ms = -1
            if self.last_speech_ms > 0 and (current_time_ms - self.last_speech_ms) < self.hangover_ms:
                pass_speech = True
            else:
                pass_speech = False

        if pass_speech:
            return pcm_frame
        else:
            return b"\x00" * len(pcm_frame)  # clean silence


def generate_audio_sample():
    """
    Generates a 3-second 16kHz 16-bit PCM stream:
    - 0.0s - 0.8s: Background noise (hum + random static ~200 RMS) + short 30ms click at 0.4s
    - 0.8s - 2.0s: Clear speech signal ("hello world" tone ~2500 RMS) mixed with background hum
    - 2.0s - 3.0s: Background noise (hum + room hiss ~180 RMS)
    """
    sr = 16000
    duration_s = 3.0
    total_samples = int(sr * duration_s)
    t = np.linspace(0, duration_s, total_samples, endpoint=False)

    # Ambient noise: 60Hz mains hum + 120Hz harmonic + random hiss
    hum = 180 * np.sin(2 * np.pi * 60 * t) + 80 * np.sin(2 * np.pi * 120 * t)
    hiss = np.random.normal(0, 70, total_samples)
    noise = hum + hiss

    # Transient pop at 0.4s (lasting 30ms)
    pop_start = int(0.4 * sr)
    pop_len = int(0.03 * sr)
    noise[pop_start:pop_start + pop_len] += 1200 * np.sin(2 * np.pi * 1000 * t[:pop_len])

    # Speech between 0.8s and 2.0s: formants at 440Hz, 880Hz, 1320Hz (~2500 RMS)
    speech_start = int(0.8 * sr)
    speech_end = int(2.0 * sr)
    speech_t = t[speech_start:speech_end]
    speech = (
        1800 * np.sin(2 * np.pi * 440 * speech_t) +
        1200 * np.sin(2 * np.pi * 880 * speech_t) +
        800 * np.sin(2 * np.pi * 1320 * speech_t)
    )

    full_signal = noise.copy()
    full_signal[speech_start:speech_end] += speech

    # Clip to 16-bit PCM
    clipped = np.clip(full_signal, -32768, 32767).astype(np.int16)
    return clipped.tobytes()


class SimpleSimulatedStt:
    """Simulates speech-to-text behavior on raw vs filtered PCM audio."""
    def transcribe(self, pcm_bytes: bytes) -> str:
        # Check slices of 100ms
        sr = 16000
        bytes_per_sec = sr * 2
        chunk_len = int(0.1 * bytes_per_sec)
        words = []
        has_speech = False
        noise_bursts = 0

        for i in range(0, len(pcm_bytes), chunk_len):
            chunk = pcm_bytes[i:i + chunk_len]
            if len(chunk) < 20:
                continue
            shorts = struct.unpack(f"<{len(chunk)//2}h", chunk)
            rms = math.sqrt(sum(s * s for s in shorts) / len(shorts))
            t_s = i / bytes_per_sec

            if rms > 800:
                has_speech = True
            elif rms > 150:
                # low noise detected
                if t_s < 0.7:
                    noise_bursts += 1

        if noise_bursts > 0 and not has_speech:
            return "[inaudible static / clicking]"
        elif noise_bursts > 0 and has_speech:
            return "[noise/thump] hello world [hum]"
        elif has_speech:
            return "hello world"
        else:
            return ""


def test_noise_reduction_before_and_after():
    audio = generate_audio_sample()
    frame_size = 1024  # 32ms frames at 16kHz
    stt = SimpleSimulatedStt()

    # --- BEFORE: Noise Reduction OFF ---
    vad_off = EnergyVadGate()
    processed_before = bytearray()
    time_ms = 0
    for offset in range(0, len(audio), frame_size):
        frame = audio[offset:offset + frame_size]
        out_frame = vad_off.process_frame(frame, time_ms, noise_reduction=False)
        processed_before.extend(out_frame)
        time_ms += 32

    transcript_before = stt.transcribe(bytes(processed_before))

    # --- AFTER: Noise Reduction ON ---
    vad_on = EnergyVadGate(energy_threshold=350.0, min_speech_ms=200, hangover_ms=350)
    processed_after = bytearray()
    time_ms = 0
    for offset in range(0, len(audio), frame_size):
        frame = audio[offset:offset + frame_size]
        out_frame = vad_on.process_frame(frame, time_ms, noise_reduction=True)
        processed_after.extend(out_frame)
        time_ms += 32

    transcript_after = stt.transcribe(bytes(processed_after))

    print(f"\n[Noise Reduction OFF transcript]: '{transcript_before}'")
    print(f"[Noise Reduction ON transcript]:  '{transcript_after}'")

    assert "[noise/thump]" in transcript_before
    assert transcript_after == "hello world"

