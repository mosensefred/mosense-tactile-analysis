"""Procedural score for the MoSense 60s film — v5 "hero machine" recipe, 60s cut.

Same engine as the 30s final (Galbot ET1 profile: 109 BPM, 0.2s staccato
cut-sync grid, brightness arc 1.1k->4.7k->dark resolve, smooth energy ramp,
Haas width, E-based open fifths), stretched across six acts:

  Act1  0-8    dark space, sonar, strings enter     (centroid low)
  Act2  8-20   pulse + string bed, ostinato preview (rise)
  Act3  20-30  single-layer 0.2s ostinato grid      (mid-bright)
  Act4  30-38  groove thickens, wobble-bass color   (bright)
  Act5  38-48  doubled ostinato + hero lead         (peak, shimmer)
  Act6  48-60  dark resolve, final sonar            (centroid ~800)

Film locks: ping@0.5 (ripple), hit@8 (stack), hit@20 (cards), hit@30
(platforms), full@38 (montage), strip@48, sonar@50 (ring closes 48.6-50.0),
breath hits 51.5/55/58, fade 58.2->59.6.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SR = 44100
DUR = 60.0
N = int(SR * DUR)
BPM = 109.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT

rng = np.random.default_rng(60)

def f(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)

CHORDS = {
    "E5":  dict(bass=28, tones=[40, 47, 52, 59]),
    "B":   dict(bass=35, tones=[47, 54, 59, 66]),
    "C#m": dict(bass=37, tones=[49, 56, 61, 66]),
    "F#m": dict(bass=30, tones=[42, 49, 54, 61]),
    "G#m": dict(bass=32, tones=[44, 51, 56, 63]),
    "A":   dict(bass=33, tones=[45, 52, 57, 64]),
}
# 6-act progression (one chord per ~2 bars, E-centric, adds lift late)
def chord_at(t: float) -> dict:
    if t < 8.0 or t >= 48.0:
        return CHORDS["E5"]
    bars = int((t - 8.0) // (2 * BAR))
    prog = ["E5", "B", "E5", "C#m", "F#m", "B", "E5", "G#m", "A", "B", "C#m", "F#m",
            "E5", "B", "C#m", "G#m", "A", "B", "C#m", "F#m"]
    return CHORDS[prog[bars % len(prog)]]

def sec(x: float) -> int:
    return int(round(x * SR))

def env_adsr(n, a, d, s, r):
    na, nd, nr = sec(a), sec(d), sec(r)
    ns = max(0, n - na - nd - nr)
    parts = [np.linspace(0, 1, max(1, na), endpoint=False)]
    if nd:
        parts.append(np.linspace(1, s, nd, endpoint=False))
    parts.append(np.full(ns, s))
    parts.append(np.linspace(s, 0, max(1, nr)))
    e = np.concatenate(parts) if n > 0 else np.zeros(0)
    return np.pad(e[:n], (0, max(0, n - len(e))))

def fft_lowpass(x, hz, order=2.0):
    if hz >= SR / 2 or x.size == 0:
        return x
    X = np.fft.rfft(x)
    fr = np.fft.rfftfreq(x.size, 1 / SR)
    return np.fft.irfft(X / (1 + (fr / hz) ** (2 * order)), n=x.size)

def fft_highpass(x, hz, order=2.0):
    if x.size == 0:
        return x
    X = np.fft.rfft(x)
    fr = np.fft.rfftfreq(x.size, 1 / SR)
    g = (fr / hz) ** (2 * order)
    return np.fft.irfft(X * g / (1 + g), n=x.size)

def osc(freq, n, kind="saw", detune=0.0, phase=0.0):
    t = np.arange(n) / SR
    if kind == "saw":
        x = 2 * ((freq * t + phase) % 1.0) - 1
        if detune:
            x = (x + 2 * ((freq * (1 + detune) * t + phase) % 1.0) - 1) * 0.5
    elif kind == "square":
        x = np.sign(np.sin(2 * np.pi * freq * t + phase))
    else:
        x = np.sin(2 * np.pi * freq * t + phase)
    return x

master = np.zeros((N, 2))

def place(sig, at, gain=1.0, pan=0.0):
    i0 = sec(at)
    if i0 >= N or sig.size == 0:
        return
    seg = sig[: N - i0]
    theta = (pan + 1) * math.pi / 4
    master[i0 : i0 + seg.size, 0] += seg * math.cos(theta) * gain
    master[i0 : i0 + seg.size, 1] += seg * math.sin(theta) * gain

def place_haas(sig, at, gain=1.0, offset_ms=11.0):
    i0 = sec(at)
    seg = sig[: N - i0]
    d = sec(offset_ms / 1000.0)
    if seg.size <= d:
        place(seg, at, gain)
        return
    m = seg.size - d
    master[i0 : i0 + m, 0] += seg[:m] * gain
    master[i0 + d : i0 + seg.size, 1] += seg[d:] * gain

def big_hit(vel=1.0, dark=0.0):
    n = sec(1.4)
    t = np.arange(n) / SR
    fsw = (110 - 30 * dark) * np.exp(-t / 0.22) + 36
    ph = 2 * np.pi * np.cumsum(fsw) / SR
    sub = np.tanh(np.sin(ph) * 2.2) * np.exp(-t / 0.45) * vel
    noise = fft_lowpass(rng.normal(0, 1, n), 10000 - 4000 * dark)
    noise *= np.exp(-t / (0.09 + 0.05 * dark)) * 0.5 * vel
    return sub + noise

def pulse_kick(vel=1.0):
    n = sec(0.30)
    t = np.arange(n) / SR
    fsw = 140 * np.exp(-t / 0.030) + 40
    ph = 2 * np.pi * np.cumsum(fsw) / SR
    body = np.tanh(np.sin(ph) * 2.4) * np.exp(-t / 0.12) * vel
    click = fft_highpass(rng.normal(0, 1, n), 2400) * np.exp(-t / 0.0035) * 0.3 * vel
    return body + click

def staccato(freq, cutoff, dur=0.16):
    n = sec(dur)
    x = 0.55 * osc(freq, n, "saw", detune=0.005) + 0.45 * osc(freq, n, "square")
    x = fft_lowpass(x, cutoff)
    e = env_adsr(n, 0.002, 0.04, 0.35, 0.05)
    return x * e * 0.55

def string_pad(tones, dur, cutoff):
    n = sec(dur)
    L = np.zeros(n); R = np.zeros(n)
    for i, m in enumerate(tones):
        fr = f(m)
        lay1 = osc(fr, n, "saw", detune=0.0045 + 0.0008 * i)
        lay2 = osc(fr, n, "saw", detune=-0.0055, phase=0.5)
        if i % 2 == 0:
            L += lay1; R += lay2 * 0.6
        else:
            R += lay1; L += lay2 * 0.6
    L /= max(1, 1.6 * len(tones)); R /= max(1, 1.6 * len(tones))
    L = fft_lowpass(L, cutoff); R = fft_lowpass(R, cutoff * 1.06)
    e = env_adsr(n, 0.7, 0.2, 0.85, min(1.2, dur * 0.4))
    return np.stack([L, R], axis=1) * e[:, None]

def sub_pulse(freq, dur):
    n = sec(dur)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.18 * np.sin(2 * np.pi * freq * 2 * t)
    e = env_adsr(n, 0.004, 0.05, 0.75, 0.06)
    return x * e

def shimmer(vel=1.0):
    n = sec(0.9)
    x = fft_highpass(rng.normal(0, 1, n), 5200)
    return x * np.exp(-np.arange(n) / SR / 0.30) * 0.5 * vel

def sonar(freq, decay=1.6):
    n = sec(decay * 2.5)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) * np.exp(-t / decay)
    x += 0.22 * np.sin(2 * np.pi * freq * 2.01 * t) * np.exp(-t / (decay * 0.5))
    x += 0.09 * np.sin(2 * np.pi * freq * 3.02 * t) * np.exp(-t / (decay * 0.3))
    return x * 0.4

def hero_lead(freq, dur):
    n = sec(dur)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.0 * t)
    ph = 2 * np.pi * freq * np.cumsum(vib) / SR
    x = np.sin(ph) + 0.30 * np.sin(ph * 1.5)
    x = fft_lowpass(x, 2600)
    e = env_adsr(n, 0.04, 0.08, 0.8, min(0.4, dur * 0.45))
    return x * e * 0.4

def riser(dur, gain=0.20):
    n = sec(dur)
    out = np.zeros(n)
    for k in range(10):
        i0, i1 = n * k // 10, n * (k + 1) // 10
        x = rng.normal(0, 1, i1 - i0)
        c = 240 * (2 ** (k / 10 * 3.3))
        out[i0:i1] = fft_highpass(fft_lowpass(x, c * 1.5), c * 0.5)
    t = np.arange(n) / SR
    fclimb = f(55) * (2 ** (t / dur * 2.0))
    tone = np.sin(2 * np.pi * np.cumsum(fclimb) / SR) * 0.35
    return (out + tone) * (np.arange(n) / n) ** 2.0 * gain

# ═══════════════════════════════════════════════════════════
# ARRANGEMENT — six acts
# ═══════════════════════════════════════════════════════════

# ── Act 1 (0-8): dark space, sonar, strings rise from nothing ──
n8 = sec(8.0)
t = np.arange(n8) / SR
drone = (np.sin(2 * np.pi * f(28) * t)
         + 0.28 * np.sin(2 * np.pi * f(28) * 2 * t + 0.6)) * env_adsr(n8, 2.2, 0, 1, 1.4) * 0.28
place(drone, 0.0)
place(sonar(f(88), 2.0), 0.5, 0.48, pan=-0.2)            # ripple 1
place(sonar(f(83), 1.5), 4.4, 0.30, pan=0.25)            # ripple 2 (2nd wave)
place_haas(big_hit(0.42, dark=0.55), 1.4, 0.8)
place(riser(2.6, 0.13), 5.2)
# strings fade in late in the act
pw = string_pad(CHORDS["E5"]["tones"], 3.0, cutoff=650)
place_haas(pw[:, 0], 5.4, 0.10)
place_haas(pw[:, 1], 5.4, 0.10)

# ── Act 2 (8-20): pulse begins, stack builds ──
place_haas(big_hit(0.5, dark=0.3), 8.0)                  # stack scene
for t0 in np.arange(8.0, 20.0, BAR):
    ch = chord_at(t0)
    pw = string_pad(ch["tones"], min(BAR + 0.3, 20.3 - t0),
                    cutoff=800 + 1100 * (t0 - 8) / 12)
    place_haas(pw[:, 0], t0, 0.20)
    place_haas(pw[:, 1], t0, 0.20)
bt = 8.0
while bt < 20.0:
    ch = chord_at(bt)
    place(pulse_kick(0.55 + 0.35 * (bt - 8) / 12), bt)
    place(sub_pulse(f(ch["bass"]), 0.20), bt, 0.40 + 0.20 * (bt - 8) / 12)
    bt += BEAT
# ostinato preview: quarter notes from 14, dark
tt, i = 14.0, 0
while tt < 20.0:
    ch = chord_at(tt)
    tones = ch["tones"]
    place(staccato(f(tones[i % len(tones)] + 12), 1200), tt, 0.15,
          pan=0.3 if i % 2 else -0.3)
    i += 1; tt += BEAT
place(riser(1.9, 0.22), 18.0)

# ── Act 3 (20-30): single-layer 0.2s grid (cards) ──
place_haas(big_hit(0.55), 20.0)
place(shimmer(0.6), 20.0)
for t0 in np.arange(20.0, 30.0, BAR):
    ch = chord_at(t0)
    pw = string_pad(ch["tones"], min(BAR + 0.3, 30.3 - t0), cutoff=2000)
    place_haas(pw[:, 0], t0, 0.22)
    place_haas(pw[:, 1], t0, 0.22)
bt = 20.0
while bt < 30.0:
    ch = chord_at(bt)
    place(pulse_kick(0.92 if abs(bt % (4*BEAT)) < 1e-3 else 0.82), bt)
    place(sub_pulse(f(ch["bass"]), 0.20), bt, 0.55)
    bt += BEAT
grid = 0.2
tt, i = 20.0, 0
while tt < 30.0:
    ch = chord_at(tt)
    tones = [m + 12 for m in ch["tones"]] + [m + 24 for m in ch["tones"][:2]]
    g = 0.20 + 0.06 * (tt - 20) / 10
    place(staccato(f(tones[i % len(tones)]), 2800), tt, g,
          pan=0.34 if i % 2 else -0.34)
    if i % 5 == 0:
        place(staccato(f(tones[i % len(tones)]), 3600, dur=0.12), tt, g * 1.3, pan=0)
    i += 1; tt += grid
place(riser(1.7, 0.22), 28.3)

# ── Act 4 (30-38): groove thickens (platforms) ──
place_haas(big_hit(0.6), 30.0)
place(shimmer(0.7), 30.0)
for t0 in np.arange(30.0, 38.0, BAR):
    ch = chord_at(t0)
    pw = string_pad(ch["tones"], min(BAR + 0.3, 38.3 - t0), cutoff=2400)
    place_haas(pw[:, 0], t0, 0.22)
    place_haas(pw[:, 1], t0, 0.22)
bt, vb = 30.0, 0
while bt < 38.0:
    ch = chord_at(bt)
    place(pulse_kick(0.95 if vb % 4 == 0 else 0.85), bt)
    place(sub_pulse(f(ch["bass"]), 0.20), bt, 0.58)
    if vb % 4 == 2:
        place(sub_pulse(f(ch["bass"] + 7), 0.14), bt, 0.30)
    bt += BEAT; vb += 1
tt, i = 30.0, 0
while tt < 38.0:
    ch = chord_at(tt)
    tones = [m + 12 for m in ch["tones"]] + [m + 24 for m in ch["tones"]]
    g = 0.22 + 0.04 * (tt - 30) / 8
    place(staccato(f(tones[i % len(tones)]), 3400), tt, g,
          pan=0.34 if i % 2 else -0.34)
    if i % 5 == 0:
        place(staccato(f(tones[i % len(tones)]), 4400, dur=0.12), tt, g * 1.3, pan=0)
    i += 1; tt += grid
place(riser(1.8, 0.24), 36.2)
place_haas(big_hit(0.35, dark=0.3), 37.1)               # pre-drop punctuation

# ── Act 5 (38-48): peak — doubled ostinato + hero lead ──
place_haas(big_hit(0.68), 38.0)
place(shimmer(0.8), 38.0)
for t0 in np.arange(38.0, 48.0, BAR):
    ch = chord_at(t0)
    pw = string_pad(ch["tones"] + [m + 12 for m in ch["tones"][:2]],
                    min(BAR + 0.3, 48.3 - t0), cutoff=2800)
    place_haas(pw[:, 0], t0, 0.22)
    place_haas(pw[:, 1], t0, 0.22)
bt, vb = 38.0, 0
while bt < 48.0:
    ch = chord_at(bt)
    place(pulse_kick(1.0 if vb % 4 == 0 else 0.9), bt)
    place(sub_pulse(f(ch["bass"]), 0.20), bt, 0.62)
    if vb % 4 == 2:
        place(sub_pulse(f(ch["bass"] + 7), 0.14), bt, 0.32)
    bt += BEAT; vb += 1
# ostinato layer A (bright)
tt, i = 38.0, 0
while tt < 48.0:
    ch = chord_at(tt)
    tones = [m + 12 for m in ch["tones"]] + [m + 24 for m in ch["tones"]]
    place(staccato(f(tones[i % len(tones)]), 4400), tt, 0.22,
          pan=0.36 if i % 2 else -0.36)
    if i % 5 == 0:
        place(staccato(f(tones[i % len(tones)]), 5400, dur=0.12), tt, 0.30, pan=0)
    i += 1; tt += grid
# ostinato layer B (offset half-grid, octave down)
tt, i = 38.0 + grid / 2, 0
while tt < 48.0:
    ch = chord_at(tt)
    tones = [m for m in ch["tones"]]
    place(staccato(f(tones[i % len(tones)]), 2200, dur=0.12), tt, 0.16,
          pan=-0.3 if i % 2 else 0.3)
    i += 1; tt += grid
# hero lead — first statement
melody1 = [
    (38.00, 76, 0.90), (38.90, 83, 0.45), (39.35, 81, 0.45),
    (39.80, 78, 0.90), (40.70, 81, 0.45), (41.15, 78, 0.45),
    (41.60, 76, 0.90), (42.50, 74, 0.45), (42.95, 76, 0.45),
    (43.40, 78, 0.45), (43.85, 81, 0.90),
    (44.90, 83, 0.45), (45.35, 85, 0.45), (45.80, 83, 1.60),
]
for t0, m, d in melody1:
    place_haas(hero_lead(f(m), d), t0, 0.9)
place(shimmer(0.5), 41.6)
place(shimmer(0.6), 43.4)
place(shimmer(0.5), 45.8)
place(riser(2.2, 0.18), 45.8)

# ── Act 6 (48-60): dark resolve + logo ──
place_haas(big_hit(0.6, dark=0.7), 48.0)                # strip-down
n12 = sec(11.5)
t6 = np.arange(n12) / SR
outdrone = (np.sin(2 * np.pi * f(28) * t6)
            + 0.20 * np.sin(2 * np.pi * f(28) * 2 * t6)
            + 0.10 * np.sin(2 * np.pi * f(35) * t6)) * env_adsr(n12, 0.8, 0, 1, 2.0) * 0.34
place(outdrone, 48.0)
pw = string_pad(CHORDS["E5"]["tones"], 6.0, cutoff=700)
place_haas(pw[:, 0], 48.0, 0.15)
place_haas(pw[:, 1], 48.0, 0.15)
place(hero_lead(f(88), 2.6), 48.4, 0.5)
place(sonar(f(95), 2.0), 50.0, 0.38, pan=0.1)           # ring closes
place(fft_lowpass(big_hit(0.45, dark=0.8), 300), 50.05, 0.7)
# second breath: brief warm swell then final darkening
pw2 = string_pad(CHORDS["B"]["tones"], 4.0, cutoff=900)
place_haas(pw2[:, 0], 51.8, 0.13)
place_haas(pw2[:, 1], 51.8, 0.13)
place(hero_lead(f(83), 2.0), 52.2, 0.4)
place(fft_lowpass(pulse_kick(0.5), 160), 51.5, 0.55)
place(fft_lowpass(pulse_kick(0.5), 160), 54.6, 0.5)
place(fft_lowpass(pulse_kick(0.34), 160), 58.0, 0.38)
place(sonar(f(88), 2.2), 55.0, 0.28, pan=-0.15)         # breathing pulse echo
place(sonar(f(90), 1.8), 58.0, 0.22, pan=0.2)

# ═══════════════════════════════════════════════════════════
# MASTER
# ═══════════════════════════════════════════════════════════
stereo = master.copy()
for c in range(2):
    stereo[:, c] = fft_lowpass(stereo[:, c], 15000)
    stereo[:, c] = fft_highpass(stereo[:, c], 25)

fade = np.ones(N)
i0, i1 = sec(58.2), sec(59.6)
fade[i0:i1] = np.linspace(1, 0, i1 - i0)
fade[i1:] = 0.0
fade[: sec(0.015)] = np.linspace(0, 1, sec(0.015))
stereo *= fade[:, None]

stereo = np.tanh(stereo * 1.28) / math.tanh(1.28)
peak = np.abs(stereo).max()
stereo *= (10 ** (-1.2 / 20)) / max(peak, 1e-9)

pcm = (stereo * 32767).astype(np.int16)
out = Path(__file__).parent / "music-60s.wav"
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

mid = stereo.mean(axis=1)
print(f"music-60s.wav: {DUR}s, peak -1.2 dBFS")
for lab, (a, b) in [("20-30", (20, 30)), ("38-48", (38, 48)), ("50-58", (50, 58))]:
    seg = mid[sec(a):sec(b)]
    X = np.abs(np.fft.rfft(seg))
    fr = np.fft.rfftfreq(seg.size, 1 / SR)
    tot = X.sum()
    print(f"  {lab}: centroid {np.sum(fr * X)/tot:.0f} Hz")
