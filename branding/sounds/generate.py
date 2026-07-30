#!/usr/bin/env python3
"""Synthesize the Aurora session sounds (no samples, no copyrighted audio).

Usage: generate.py OUTPUT_DIR   → startup.wav, shutdown.wav

The idea is a sky lighting up. Startup: a warm pad (D♭ major 9) swells in
voice by voice, a soft tone glides up an octave like a ribbon of light, and
high "sparkles" twinkle over it. Shutdown is the same palette the other way
round: a short descending arpeggio over a pad that settles and fades.
Everything goes through a synthetic stereo reverb (convolution with decaying
noise), for the airy, far-away feel. 48 kHz, 16-bit stereo.
"""

import os
import sys
import wave

import numpy as np

RATE = 48000
rng = np.random.default_rng(2026)


def note(name):
    """'Db4' → frequency in Hz."""
    names = {"C": 0, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "Gb": 6, "G": 7,
             "Ab": 8, "A": 9, "Bb": 10, "B": 11}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave + 1) - 69) / 12)


def envelope(n, attack, release, start=0.0, sustain_end=None):
    """Smooth attack (raised cosine), hold, then an exponential release."""
    t = np.arange(n) / RATE
    env = np.zeros(n)
    a0, a1 = start, start + attack
    rise = (t >= a0) & (t < a1)
    env[rise] = 0.5 - 0.5 * np.cos(np.pi * (t[rise] - a0) / attack)
    hold_end = sustain_end if sustain_end is not None else a1
    env[(t >= a1) & (t < hold_end)] = 1.0
    tail = t >= hold_end
    env[tail] = np.exp(-(t[tail] - hold_end) / release)
    return env


def pad_voice(freq, n, detune_cents=7):
    """Three slightly detuned soft oscillators: a wide, shimmering tone."""
    t = np.arange(n) / RATE
    out = np.zeros(n)
    for cents in (-detune_cents, 0, detune_cents):
        f = freq * 2 ** (cents / 1200)
        phase = rng.random() * 2 * np.pi
        # Sine plus a little 2nd and 3rd harmonic: warm, not buzzy.
        out += (np.sin(2 * np.pi * f * t + phase) + 0.18 * np.sin(4 * np.pi * f * t + phase)
                + 0.06 * np.sin(6 * np.pi * f * t + phase))
    # Slow tremolo, like light rippling.
    return out / 3 * (1 + 0.08 * np.sin(2 * np.pi * (0.35 + rng.random() * 0.3) * t))


def glide(f0, f1, n, start, length):
    """A pure tone sliding from f0 to f1 with gentle vibrato."""
    t = np.arange(n) / RATE
    k = np.clip((t - start) / length, 0, 1)
    k = k * k * (3 - 2 * k)                       # smoothstep
    freq = f0 * (f1 / f0) ** k * (1 + 0.004 * np.sin(2 * np.pi * 5.2 * t))
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    return np.sin(phase)


def sparkles(n, count, start, end, notes):
    """Short bell pings high up, scattered in time and across the stereo field."""
    left, right = np.zeros(n), np.zeros(n)
    for _ in range(count):
        at = start + (end - start) * rng.random() ** 0.8
        s = int(at * RATE)
        length = int(0.6 * RATE)
        if s + length >= n:
            continue
        t = np.arange(length) / RATE
        f = notes[rng.integers(len(notes))] * (2 if rng.random() < 0.4 else 1)
        ping = (np.sin(2 * np.pi * f * t) + 0.3 * np.sin(2 * np.pi * f * 2.76 * t)) \
            * np.exp(-t / 0.16) * (1 - np.exp(-t / 0.004))
        pan = rng.uniform(-0.9, 0.9)
        gain = rng.uniform(0.25, 0.6)
        left[s:s + length] += ping * gain * (1 - pan) / 2
        right[s:s + length] += ping * gain * (1 + pan) / 2
    return left, right


def reverb(left, right, seconds=2.4, decay=0.75, wet=0.38):
    """Convolution with exponentially decaying noise (different per side)."""
    n_ir = int(seconds * RATE)
    t = np.arange(n_ir) / RATE
    out = []
    for sig in (left, right):
        ir = rng.standard_normal(n_ir) * np.exp(-t / (decay / 3))
        # Darken the tail: a running average acts as a gentle low-pass.
        ir = np.convolve(ir, np.ones(24) / 24, mode="same")
        ir /= np.sqrt(np.sum(ir ** 2))
        size = 1 << int(np.ceil(np.log2(len(sig) + n_ir)))
        conv = np.fft.irfft(np.fft.rfft(sig, size) * np.fft.rfft(ir, size), size)[:len(sig)]
        out.append(sig * (1 - wet) + conv * wet * 1.4)
    return out


def finish(left, right, fade_s=0.5, peak=0.72):
    n = len(left)
    fade = np.ones(n)
    f = int(fade_s * RATE)
    fade[-f:] = np.linspace(1, 0, f) ** 2
    stereo = np.stack([left, right], axis=1) * fade[:, None]
    stereo *= peak / np.max(np.abs(stereo))
    return (stereo * 32767).astype("<i2")


def startup():
    length = 4.6
    n = int(length * RATE)
    left, right = np.zeros(n), np.zeros(n)
    # The sky fills in from the bottom: each voice enters a little later.
    chord = [("Db3", 0.00, -0.1), ("Ab3", 0.18, 0.25), ("F4", 0.36, -0.3),
             ("C5", 0.54, 0.35), ("Eb5", 0.72, -0.2)]
    for name, start, pan in chord:
        env = envelope(n, attack=1.1, release=0.9, start=start, sustain_end=2.6)
        v = pad_voice(note(name), n) * env * 0.2
        left += v * (1 - pan) / 2
        right += v * (1 + pan) / 2
    # The ribbon: a soft tone rising an octave, Ab4 → Ab5.
    rib = glide(note("Ab4"), note("Ab5"), n, start=0.5, length=1.6) \
        * envelope(n, attack=0.7, release=0.6, start=0.4, sustain_end=2.2) * 0.16
    left += rib * 0.45
    right += rib * 0.55
    # Stars coming out.
    sl, sr = sparkles(n, 26, 0.6, 3.0, [note(x) for x in ("Db6", "Eb6", "F6", "Ab6", "Bb6")])
    left += sl * 0.22
    right += sr * 0.22
    left, right = reverb(left, right)
    return finish(left, right, fade_s=0.9)


def shutdown():
    length = 3.2
    n = int(length * RATE)
    left, right = np.zeros(n), np.zeros(n)
    # A pad that settles and fades…
    for name, pan in (("Db3", 0.0), ("Ab3", 0.2), ("F4", -0.2)):
        env = envelope(n, attack=0.35, release=0.7, start=0.0, sustain_end=1.0)
        v = pad_voice(note(name), n) * env * 0.2
        left += v * (1 - pan) / 2
        right += v * (1 + pan) / 2
    # …under a descending arpeggio of soft bells, like lights going out.
    t = np.arange(n) / RATE
    for i, name in enumerate(("Eb5", "C5", "Ab4", "F4", "Db4")):
        start = 0.05 + i * 0.16
        s = int(start * RATE)
        tt = t[: n - s]
        f = note(name)
        bell = (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(2 * np.pi * f * 2 * tt)) \
            * np.exp(-tt / 0.55) * (1 - np.exp(-tt / 0.01)) * 0.22
        pan = 0.4 - i * 0.2
        left[s:] += bell * (1 - pan) / 2
        right[s:] += bell * (1 + pan) / 2
    # The ribbon sinks back: Ab5 → Ab4.
    rib = glide(note("Ab5"), note("Ab4"), n, start=0.1, length=1.2) \
        * envelope(n, attack=0.25, release=0.5, start=0.0, sustain_end=0.9) * 0.1
    left += rib * 0.5
    right += rib * 0.5
    left, right = reverb(left, right, decay=0.6)
    return finish(left, right, fade_s=0.8, peak=0.62)


def write(path, data):
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(data.tobytes())
    print(path)


def main():
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    write(os.path.join(out, "startup.wav"), startup())
    write(os.path.join(out, "shutdown.wav"), shutdown())


if __name__ == "__main__":
    main()
