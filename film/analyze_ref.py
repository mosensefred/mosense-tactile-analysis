"""Analyze the reference track: tempo, key, energy curve, spectral character.

Produces ref/analysis.json so the v3 score can be matched to the reference's
actual rhythm and brightness instead of guessing from the video title.
"""
from __future__ import annotations

import json
import subprocess
import wave
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
WAV = HERE / "ref" / "track.wav"
OUT = HERE / "ref" / "analysis.json"


def load_wav(path: Path):
    with wave.open(str(path), "rb") as w:
        sr = w.getframerate()
        n = w.getnframes()
        ch = w.getnchannels()
        sw = w.getsampwidth()
        raw = w.readframes(n)
    if sw == 2:
        x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    else:
        raise RuntimeError(f"unexpected sample width {sw}")
    if ch == 2:
        x = x.reshape(-1, 2).mean(axis=1)
    return sr, x


def onset_envelope(x: np.ndarray, sr: int, hop: int = 512) -> np.ndarray:
    frames = len(x) // hop
    env = np.zeros(frames)
    for i in range(frames - 1):
        a = np.abs(np.fft.rfft(x[i * hop : (i + 1) * hop] * np.hanning(hop)))
        b = np.abs(np.fft.rfft(x[(i + 1) * hop : (i + 2) * hop] * np.hanning(hop)))
        env[i] = np.sum(np.maximum(0, b - a))
    return env


def estimate_bpm(env: np.ndarray, sr: int, hop: int = 512) -> tuple[float, np.ndarray]:
    """Autocorrelation of onset envelope over 60-180 BPM lags."""
    env = env - env.mean()
    frame_rate = sr / hop
    bpms = np.arange(60, 181, 0.25)
    lags = 60.0 / bpms * frame_rate
    scores = []
    for bpm, lag in zip(bpms, lags):
        lag_i = int(round(lag))
        if lag_i >= len(env) - 1:
            scores.append(0.0)
            continue
        # correlation at lag and 2x lag (reinforces the true beat period)
        c1 = np.corrcoef(env[:-lag_i], env[lag_i:])[0, 1] if lag_i > 1 else 0
        c2 = np.corrcoef(env[: -2 * lag_i], env[2 * lag_i :])[0, 1] if 2 * lag_i < len(env) else 0
        scores.append(0.6 * c1 + 0.4 * c2)
    scores = np.nan_to_num(np.array(scores))
    best = bpms[np.argmax(scores)]
    return float(best), scores


def spectral_centroid_profile(x: np.ndarray, sr: int, hop: int = 2048) -> np.ndarray:
    frames = len(x) // hop
    freqs = np.fft.rfftfreq(hop, 1 / sr)
    cents = []
    for i in range(frames):
        mag = np.abs(np.fft.rfft(x[i * hop : (i + 1) * hop] * np.hanning(hop))) + 1e-12
        cents.append(np.sum(freqs * mag) / np.sum(mag))
    return np.array(cents)


def chroma_profile(x: np.ndarray, sr: int, hop: int = 4096) -> np.ndarray:
    frames = len(x) // hop
    freqs = np.fft.rfftfreq(hop, 1 / sr)
    # map freq -> pitch class (12 bins), energy-weighted
    mask = freqs > 55
    note = 12 * np.log2(freqs[mask] / 440.0) + 69
    pc = np.mod(np.round(note).astype(int), 12)
    agg = np.zeros(12)
    for i in range(frames):
        mag = np.abs(np.fft.rfft(x[i * hop : (i + 1) * hop] * np.hanning(hop)))[mask] + 1e-12
        for p in range(12):
            agg[p] += np.sum(mag[pc == p])
    return agg / agg.sum()


def energy_curve(x: np.ndarray, sr: int, win_s: float = 0.5) -> np.ndarray:
    w = int(sr * win_s)
    n = len(x) // w
    return np.array([np.sqrt(np.mean(x[i * w : (i + 1) * w] ** 2)) for i in range(n)])


def main() -> None:
    sr, x = load_wav(WAV)
    dur = len(x) / sr
    print(f"sr={sr} dur={dur:.1f}s")

    env = onset_envelope(x, sr)
    bpm, _ = estimate_bpm(env, sr)
    print(f"estimated BPM = {bpm:.1f}")

    cent = spectral_centroid_profile(x, sr)
    print(f"centroid: mean={cent.mean():.0f} Hz  p10={np.percentile(cent,10):.0f}  p90={np.percentile(cent,90):.0f}")

    chroma = chroma_profile(x, sr)
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    top = np.argsort(chroma)[::-1][:5]
    print("top pitch classes:", ", ".join(f"{names[i]} {chroma[i]:.2f}" for i in top))

    ec = energy_curve(x, sr)
    # downsample energy curve to per-2s for readability
    per2 = [float(np.mean(ec[i : i + 4])) for i in range(0, len(ec) - 3, 4)]
    print("energy per 2s:", " ".join(f"{v:.3f}" for v in per2[:20]), "...")
    # where does it peak / drop?
    print(f"energy peak at t={int(np.argmax(ec) * 0.5)}s, quiet start {ec[:4].mean():.3f}, loud {ec.max():.3f}")

    OUT.write_text(json.dumps({
        "duration": dur,
        "bpm": bpm,
        "centroid_mean": float(cent.mean()),
        "centroid_p90": float(np.percentile(cent, 90)),
        "chroma": {names[i]: float(chroma[i]) for i in range(12)},
        "energy_per_2s": per2,
    }, indent=2))
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
