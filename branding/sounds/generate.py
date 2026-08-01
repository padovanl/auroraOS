#!/usr/bin/env python3
"""Synthesize the Aurora session sounds (no samples, no copyrighted audio).

Usage: generate.py OUTPUT_DIR   → startup.wav, shutdown.wav

Warm and organic rather than electronic: a marimba (modal synthesis of a
wooden bar, with the soft click of the mallet) plays a short motif in D major
over a round bass note, then settles on a chord held by a soft felt pad.
Startup rises and resolves; shutdown walks back down and fades. A short room
reverb gives it space without making it sound far away.
48 kHz, 16-bit stereo.
"""

import os
import sys
import wave

import numpy as np

RATE = 48000
rng = np.random.default_rng(2026)


def note(name):
    """'D4' / 'F#5' → frequency in Hz."""
    names = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6, "G": 7,
             "G#": 8, "A": 9, "A#": 10, "B": 11}
    pitch, octave = name[:-1], int(name[-1])
    return 440.0 * 2 ** ((names[pitch] + 12 * (octave + 1) - 69) / 12)


def marimba(freq, length, velocity=1.0):
    """A struck wooden bar: tuned partials (1 : 3.93 : 9.2) that die out fast,
    the upper ones faster, plus a short filtered noise click for the mallet."""
    t = np.arange(int(length * RATE)) / RATE
    tone = np.zeros_like(t)
    for ratio, amp, decay in ((1.0, 1.0, 0.55), (3.93, 0.32 * velocity, 0.09),
                              (9.2, 0.08 * velocity, 0.03)):
        if freq * ratio < RATE / 2.2:
            tone += amp * np.sin(2 * np.pi * freq * ratio * t) * np.exp(-t / decay)
    # Resonator tube: a touch of the fundamental that rings a little longer.
    tone += 0.25 * np.sin(2 * np.pi * freq * t) * np.exp(-t / 0.9)
    click = rng.standard_normal(len(t)) * np.exp(-t / 0.0025)
    click = np.convolve(click, np.ones(12) / 12, mode="same") * 0.35 * velocity
    attack = 1 - np.exp(-t / 0.0015)
    return (tone + click) * attack * velocity


def felt_pad(freqs, length, attack, hold, release):
    """A soft sustained chord (a few warm harmonics, gently swelling)."""
    t = np.arange(int(length * RATE)) / RATE
    out = np.zeros_like(t)
    for f in freqs:
        for cents in (-4, 4):
            ff = f * 2 ** (cents / 1200)
            out += (np.sin(2 * np.pi * ff * t) + 0.22 * np.sin(4 * np.pi * ff * t)
                    + 0.07 * np.sin(6 * np.pi * ff * t))
    env = np.clip(t / attack, 0, 1) ** 2
    tail = t > attack + hold
    env[tail] *= np.exp(-(t[tail] - attack - hold) / release)
    return out / (2 * len(freqs)) * env


def room(left, right, seconds=1.0, decay=0.35, wet=0.16):
    """A short, dark room reverb (convolution with decaying noise)."""
    n_ir = int(seconds * RATE)
    t = np.arange(n_ir) / RATE
    out = []
    for sig in (left, right):
        ir = rng.standard_normal(n_ir) * np.exp(-t / (decay / 3))
        ir = np.convolve(ir, np.ones(40) / 40, mode="same")
        ir[: int(0.012 * RATE)] = 0                    # a little pre-delay
        ir /= np.sqrt(np.sum(ir ** 2))
        size = 1 << int(np.ceil(np.log2(len(sig) + n_ir)))
        conv = np.fft.irfft(np.fft.rfft(sig, size) * np.fft.rfft(ir, size), size)[:len(sig)]
        out.append(sig * (1 - wet) + conv * wet * 1.2)
    return out


def place(buf_l, buf_r, sound, at, pan):
    s = int(at * RATE)
    end = min(len(buf_l), s + len(sound))
    part = sound[: end - s]
    buf_l[s:end] += part * (1 - pan) / 2
    buf_r[s:end] += part * (1 + pan) / 2


def finish(left, right, fade_s, peak):
    n = len(left)
    fade = np.ones(n)
    f = int(fade_s * RATE)
    fade[-f:] = np.linspace(1, 0, f) ** 2
    stereo = np.stack([left, right], axis=1) * fade[:, None]
    stereo *= peak / np.max(np.abs(stereo))
    return (stereo * 32767).astype("<i2")


def startup():
    n = int(2.8 * RATE)
    left, right = np.zeros(n), np.zeros(n)
    # A round bass note on the downbeat…
    place(left, right, marimba(note("D3"), 2.0, 0.9) * 0.9, 0.0, 0.0)
    # …a rising motif, then two notes that land on the chord.
    motif = [("D4", 0.00, -0.3, 0.8), ("A4", 0.13, 0.2, 0.75), ("F#5", 0.26, -0.15, 0.8),
             ("E5", 0.42, 0.25, 0.7), ("A5", 0.58, -0.05, 0.9)]
    for name, at, pan, vel in motif:
        place(left, right, marimba(note(name), 1.8, vel) * 0.55, at, pan)
    # The chord everything resolves to, struck softly together, with a felt pad.
    for name, pan in (("D5", -0.35), ("F#5", 0.35), ("A5", 0.0)):
        place(left, right, marimba(note(name), 2.0, 0.55) * 0.35, 0.60, pan)
    pad = felt_pad([note("D4"), note("F#4"), note("A4"), note("D5")], 2.2,
                   attack=0.35, hold=0.5, release=0.5) * 0.18
    place(left, right, pad, 0.55, 0.0)
    left, right = room(left, right)
    return finish(left, right, fade_s=0.5, peak=0.7)


def shutdown():
    n = int(2.3 * RATE)
    left, right = np.zeros(n), np.zeros(n)
    motif = [("A5", 0.00, 0.3, 0.7), ("F#5", 0.14, -0.2, 0.65), ("D5", 0.28, 0.15, 0.62),
             ("A4", 0.44, -0.1, 0.6)]
    for name, at, pan, vel in motif:
        place(left, right, marimba(note(name), 1.6, vel) * 0.5, at, pan)
    place(left, right, marimba(note("D4"), 1.8, 0.55) * 0.5, 0.62, 0.0)
    place(left, right, marimba(note("D3"), 1.7, 0.6) * 0.6, 0.62, 0.0)
    pad = felt_pad([note("D4"), note("A4"), note("D5")], 1.7, attack=0.25, hold=0.2,
                   release=0.45) * 0.14
    place(left, right, pad, 0.55, 0.0)
    left, right = room(left, right, decay=0.3)
    return finish(left, right, fade_s=0.6, peak=0.6)


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
