"""Procedural score v5 for the MoSense 30s film — matched to Galbot ET1 official film.

Reference (youtube 1nopOx83KTs, "Meet GALBOT ET1.", 49.3s) analyzed:
  - ~109 BPM, unhurried
  - transient density: sparse intro, from ~20s bursts of 0.2s-spaced hits
    (the "35s+ rhythm" the user pointed at: rapid-fire cuts)
  - brightness: centroid climbs 1.1k -> 3-4.7k peak, ends dark (~700Hz)
  - energy: smooth ramp 0.10 -> 0.23, no silence gaps
  - extreme width (side ratio 1.25: phase-designed, wider than mono)
  - harmony: E / B / C# / F# / A# cluster -> open, heroic fifth-based
  - body: sub 20-27% + lowmid 27-34%, hi controlled

v5 "hero machine" translation:
  - 109 BPM
  - orchestral-electronic hybrid: string-like ostinato + synth sub pulse
    + big cinematic hits on every scene boundary
  - THE signature: from Act3 (11s) a 0.2s-spaced staccato ostinato (cut-sync
    engine, mirroring ref's rapid-fire section); Act4 doubles the layer
  - brightness arc: dark pads -> ostinato opens filter -> shimmer peak at 18-24
    -> final act drops to near-sub-only (centroid ~800)
  - wide: L/R phase-offset detune layers + short haas on hits
  - E-based open harmony: E5(no3) - B - C#m - F#m ... heroic fifth stacks
Film locks: ping@0.5 (ripple), hit@11 (cards), full peak@18 (montage),
last-breath hits@25.4/26.0 (ring close), dark resolve 26-30, fade 28.6->29.8.
"""
from __future__ import annotations

import math
import wave
from pathlib import Path

import numpy as np

SR = 44100
DUR = 30.0
N = int(SR * DUR)
BPM = 109.0
BEAT = 60.0 / BPM
BAR = 4 * BEAT

rng = np.random.default_rng(31)

def f(midi: float) -> float:
    return 440.0 * 2 ** ((midi - 69) / 12)

# open heroic harmony on E (fifth stacks, no busy thirds)
CHORDS = {
    "E5":  dict(bass=28, tones=[40, 47, 52, 59]),   # E B E B
    "B":   dict(bass=35, tones=[47, 54, 59, 66]),   # B F# B F#
    "C#m": dict(bass=37, tones=[49, 56, 61, 66]),   # C# G# C# F#
    "F#m": dict(bass=30, tones=[42, 49, 54, 61]),   # F# C# F# C#
}
PROG = ["E5", "B", "C#m", "F#m"]

def chord_at(t: float) -> dict:
    if t < 4.0 or t >= 25.0:
        return CHORDS["E5"]
    return CHORDS[PROG[int((t - 4.0) // BAR) % 4]]

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
    """Haas widener: delayed R channel — the ref's wider-than-mono trick."""
    i0 = sec(at)
    seg = sig[: N - i0]
    d = sec(offset_ms / 1000.0)
    if seg.size <= d:
        place(seg, at, gain)
        return
    m = seg.size - d
    master[i0 : i0 + m, 0] += seg[:m] * gain
    master[i0 + d : i0 + seg.size, 1] += seg[d:] * gain

# ── instruments: hero-machine set ──────────────────────────
def big_hit(vel=1.0, dark=0.0):
    """Cinematic impact: sub drop + noise + low tom layer."""
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
    """0.2s-grid staccato ostinato note — the cut-sync engine."""
    n = sec(dur)
    x = 0.55 * osc(freq, n, "saw", detune=0.005) + 0.45 * osc(freq, n, "square")
    x = fft_lowpass(x, cutoff)
    e = env_adsr(n, 0.002, 0.04, 0.35, 0.05)
    return x * e * 0.55

def string_pad(tones, dur, cutoff):
    """Ostinato-bed strings: slow-attack detuned saws, wide L/R split."""
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
    """Ground-floor sub pulse on the beat grid."""
    n = sec(dur)
    t = np.arange(n) / SR
    x = np.sin(2 * np.pi * freq * t) + 0.18 * np.sin(2 * np.pi * freq * 2 * t)
    e = env_adsr(n, 0.004, 0.05, 0.75, 0.06)
    return x * e

def shimmer(vel=1.0):
    """High sparkle hit (the ref's 3-4.7k centroid moments)."""
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
    """Open-fifth heroic lead line."""
    n = sec(dur)
    t = np.arange(n) / SR
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.0 * t)
    ph = 2 * np.pi * freq * np.cumsum(vib) / SR
    x = np.sin(ph) + 0.30 * np.sin(ph * 1.5)          # fifth above
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
# ARRANGEMENT — the ET1 arc compressed to 30s
# ═══════════════════════════════════════════════════════════

# ── Act 1 (0-4): dark space, sonar, low string entry ──
n4 = sec(4.0)
t = np.arange(n4) / SR
drone = (np.sin(2 * np.pi * f(28) * t)
         + 0.28 * np.sin(2 * np.pi * f(28) * 2 * t + 0.6)) * env_adsr(n4, 1.9, 0, 1, 1.1) * 0.28
place(drone, 0.0)
place(sonar(f(88), 1.8), 0.5, 0.48, pan=-0.2)            # ripple trigger
place(sonar(f(83), 1.4), 2.2, 0.26, pan=0.25)
place_haas(big_hit(0.4, dark=0.5), 1.2, 0.8)
place(riser(1.7, 0.15), 2.3)

# ── Act 2 (4-11): pulse + strings build, dark→mid brightness ──
for t0 in np.arange(4.0, 11.0, BAR):
    ch = chord_at(t0)
    pw = string_pad(ch["tones"], min(BAR + 0.3, 11.3 - t0),
                    cutoff=800 + 900 * (t0 - 4) / 7)
    place_haas(pw[:, 0], t0, 0.20)
    place_haas(pw[:, 1], t0, 0.20)
bt, vb = 4.0, 0
while bt < 11.0:
    ch = chord_at(bt)
    place(pulse_kick(0.6 + 0.3 * (bt - 4) / 7), bt)
    place(sub_pulse(f(ch["bass"]), 0.20), bt, 0.42 + 0.18 * (bt - 4) / 7)
    bt += BEAT; vb += 1
# sparse ostinato preview (quarter notes only, dark cutoff)
tt = 8.0; i = 0
while tt < 11.0:
    ch = chord_at(tt)
    tones = ch["tones"]
    place(staccato(f(tones[i % len(tones)] + 12), 1200), tt, 0.16,
          pan=0.3 if i % 2 else -0.3)
    i += 1; tt += BEAT
place(riser(1.7, 0.22), 9.3)

# ── Act 3 (11-18): THE GRID — 0.2s staccato cut-sync engine ──
place_haas(big_hit(0.55), 11.0)                          # cards enter
place(shimmer(0.6), 11.0)
for t0 in np.arange(11.0, 18.0, BAR):
    ch = chord_at(t0)
    pw = string_pad(ch["tones"], min(BAR + 0.3, 18.3 - t0), cutoff=1900)
    place_haas(pw[:, 0], t0, 0.22)
    place_haas(pw[:, 1], t0, 0.22)
bt, vb = 11.0, 0
while bt < 18.0:
    ch = chord_at(bt)
    place(pulse_kick(0.92 if vb % 4 == 0 else 0.82), bt)
    place(sub_pulse(f(ch["bass"]), 0.20), bt, 0.55)
    bt += BEAT; vb += 1
# staccato ostinato on the 0.2s grid (5 per beat ~ 16th+ at 109bpm)
grid = 0.2
tt, i = 11.0, 0
while tt < 18.0:
    ch = chord_at(tt)
    tones = [m + 12 for m in ch["tones"]] + [m + 24 for m in ch["tones"][:2]]
    g = 0.20 + 0.06 * (tt - 11) / 7
    place(staccato(f(tones[i % len(tones)]), 2600), tt, g,
          pan=0.34 if i % 2 else -0.34)
    # accent every 5th note (bar feel)
    if i % 5 == 0:
        place(staccato(f(tones[i % len(tones)]) , 3400, dur=0.12), tt, g * 1.3, pan=0)
    i += 1; tt += grid

# ── Act 4 (18-25): peak — doubled ostinato + hero lead + shimmer ──
place_haas(big_hit(0.68), 18.0)
place(shimmer(0.8), 18.0)
place_haas(big_hit(0.4, dark=0.3), 19.85)               # mid-act punctuation
for t0 in np.arange(18.0, 25.0, BAR):
    ch = chord_at(t0)
    pw = string_pad(ch["tones"] + [m + 12 for m in ch["tones"][:2]],
                    min(BAR + 0.3, 25.3 - t0), cutoff=2600)
    place_haas(pw[:, 0], t0, 0.22)
    place_haas(pw[:, 1], t0, 0.22)
bt, vb = 18.0, 0
while bt < 25.0:
    ch = chord_at(bt)
    place(pulse_kick(1.0 if vb % 4 == 0 else 0.9), bt)
    place(sub_pulse(f(ch["bass"]), 0.20), bt, 0.62)
    if vb % 4 == 2:
        place(sub_pulse(f(ch["bass"] + 7), 0.14), bt, 0.3)
    bt += BEAT; vb += 1
# ostinato layer A: same 0.2 grid, brighter
tt, i = 18.0, 0
while tt < 25.0:
    ch = chord_at(tt)
    tones = [m + 12 for m in ch["tones"]] + [m + 24 for m in ch["tones"]]
    place(staccato(f(tones[i % len(tones)]), 4200), tt, 0.22,
          pan=0.36 if i % 2 else -0.36)
    if i % 5 == 0:
        place(staccato(f(tones[i % len(tones)]), 5200, dur=0.12), tt, 0.30, pan=0)
    i += 1; tt += grid
# ostinato layer B: offset by half-grid, octave down (the doubling)
tt, i = 18.0 + grid / 2, 0
while tt < 25.0:
    ch = chord_at(tt)
    tones = [m for m in ch["tones"]]
    place(staccato(f(tones[i % len(tones)]), 2000, dur=0.12), tt, 0.16,
          pan=-0.3 if i % 2 else 0.3)
    i += 1; tt += grid
# hero lead: open fifth line
melody = [
    (18.00, 76, 0.90), (18.90, 83, 0.45), (19.35, 81, 0.45),
    (19.80, 78, 0.90), (20.70, 81, 0.45), (21.15, 78, 0.45),
    (21.60, 76, 0.90), (22.50, 74, 0.45), (22.95, 76, 0.45),
    (23.40, 78, 0.45), (23.85, 81, 1.05),
]
for t0, m, d in melody:
    place_haas(hero_lead(f(m), d), t0, 0.9)
# shimmer washes on the peak
place(shimmer(0.5), 21.6)
place(shimmer(0.6), 23.4)
place(riser(1.2, 0.16), 23.8)

# ── Act 5 (25-30):骤暗 resolve — centroid crashes to ~800Hz ──
place_haas(big_hit(0.6, dark=0.7), 25.0)                # strip-down hit
n5 = sec(4.8)
t5 = np.arange(n5) / SR
# near-sub-only drone (dark resolve, ref ends ~700Hz centroid)
outdrone = (np.sin(2 * np.pi * f(28) * t5)
            + 0.20 * np.sin(2 * np.pi * f(28) * 2 * t5)
            + 0.10 * np.sin(2 * np.pi * f(35) * t5)) * env_adsr(n5, 0.7, 0, 1, 1.5) * 0.34
place(outdrone, 25.0)
pw = string_pad(CHORDS["E5"]["tones"], 4.6, cutoff=600)
place_haas(pw[:, 0], 25.0, 0.15)
place_haas(pw[:, 1], 25.0, 0.15)
place(hero_lead(f(88), 2.4), 25.3, 0.55)
place(sonar(f(95), 1.8), 26.0, 0.38, pan=0.1)           # ring closes
place(fft_lowpass(big_hit(0.45, dark=0.8), 300), 26.05, 0.7)
place(fft_lowpass(pulse_kick(0.4), 160), 27.7, 0.55)
place(fft_lowpass(pulse_kick(0.28), 160), 28.6, 0.35)

# ═══════════════════════════════════════════════════════════
# MASTER — wide, smooth ramp, controlled top
# ───────────────────────────────────────────────────────────
stereo = master.copy()
for c in range(2):
    stereo[:, c] = fft_lowpass(stereo[:, c], 15000)
    stereo[:, c] = fft_highpass(stereo[:, c], 25)

fade = np.ones(N)
i0, i1 = sec(28.6), sec(29.8)
fade[i0:i1] = np.linspace(1, 0, i1 - i0)
fade[i1:] = 0.0
fade[: sec(0.015)] = np.linspace(0, 1, sec(0.015))
stereo *= fade[:, None]

stereo = np.tanh(stereo * 1.28) / math.tanh(1.28)
peak = np.abs(stereo).max()
stereo *= (10 ** (-1.2 / 20)) / max(peak, 1e-9)

pcm = (stereo * 32767).astype(np.int16)
out = Path(__file__).parent / "music.wav"
with wave.open(str(out), "wb") as w:
    w.setnchannels(2)
    w.setsampwidth(2)
    w.setframerate(SR)
    w.writeframes(pcm.tobytes())

# self-report vs ref targets
side = stereo[:, 0] - stereo[:, 1]
mid = stereo.mean(axis=1)
print(f"music.wav v5: {DUR}s, peak -1.2 dBFS")
print(f"side ratio: {np.sqrt(np.mean(side**2)) / (np.sqrt(np.mean(mid**2)) + 1e-9):.3f} (ref 1.25)")
for lab, (a, b) in [("11-18", (11, 18)), ("18-25", (18, 25)), ("26-29.5", (26, 29.5))]:
    seg = mid[sec(a):sec(b)]
    X = np.abs(np.fft.rfft(seg))
    fr = np.fft.rfftfreq(seg.size, 1 / SR)
    tot = X.sum()
    cent = np.sum(fr * X) / tot
    print(f"  {lab}: centroid {cent:.0f} Hz, hi>6k {X[fr>6000].sum()/tot:.3f}")
# transient density in the peak
hop = 512
frames = (sec(25) - sec(18)) // hop - 1
env = np.zeros(frames)
seg = mid[sec(18):sec(25)]
for i in range(frames):
    aa = np.abs(np.fft.rfft(seg[i*hop:(i+1)*hop]*np.hanning(hop)))
    bb = np.abs(np.fft.rfft(seg[(i+1)*hop:(i+2)*hop]*np.hanning(hop)))
    env[i] = np.sum(np.maximum(0, bb - aa))
th = env.mean() + 1.5 * env.std()
pk = sum(1 for i in range(2, frames-2)
         if env[i] > th and env[i] == max(env[i-2:i+3]))
print(f"  peak transient density: {pk/7:.2f}/s (ref 35s+ ~2.3/s)")
