"""Dictation and read-aloud, on this computer.

Dictation: `pw-record` captures the microphone (16 kHz mono) until you press
the shortcut again; faster-whisper turns it into text in the private venv;
`wtype` types it into the app you're using (Wayland virtual keyboard).

Read aloud: the selected text (Wayland primary selection) goes through a
Piper voice for your language and plays with `pw-play`.
"""

import locale
import os
import signal
import subprocess

from aurora import settings
from aurora.ai import components, state_dir
from aurora.i18n import _

WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "speechworker.py")


def _language():
    """Dictation language: the one chosen in Settings, or None to let Whisper detect it."""
    s = settings.get()
    return (s.get_string("ai-dictation-language") if s else "") or None


def voice_code():
    """The read-aloud voice: chosen in Settings, else the system language's."""
    s = settings.get()
    chosen = s.get_string("ai-voice") if s else ""
    if chosen and chosen in components.catalog()["voices"]:
        return chosen
    return components.voice_for(locale.getlocale(locale.LC_MESSAGES)[0]
                                or os.environ.get("LANG"))


class Dictation:
    def __init__(self):
        self.recorder = None
        self.path = os.path.join(state_dir(), "dictation.wav")

    @property
    def recording(self):
        return self.recorder is not None

    def ready(self):
        s = settings.get()
        model = s.get_string("ai-whisper-model") if s else "small"
        return components.speech_installed() and components.whisper_installed(model)

    def start(self):
        self.recorder = subprocess.Popen(
            ["pw-record", "--rate", "16000", "--channels", "1", "--format", "s16", self.path])

    def stop(self):
        """Stop recording; returns the recognized text (blocking: call from a thread)."""
        rec, self.recorder = self.recorder, None
        if rec is None:
            return ""
        rec.send_signal(signal.SIGINT)
        try:
            rec.wait(5)
        except subprocess.TimeoutExpired:
            rec.kill()
        s = settings.get()
        model = s.get_string("ai-whisper-model") if s else "small"
        res = subprocess.run([components.venv_python(), WORKER, "transcribe", self.path,
                              components.whisper_dir(model), _language() or ""],
                             capture_output=True, text=True, timeout=600)
        try:
            os.remove(self.path)
        except OSError:
            pass
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip().splitlines()[-1] if res.stderr.strip()
                               else _("speech recognition failed"))
        return res.stdout.strip()


def type_text(text):
    """Type text into the focused window."""
    subprocess.run(["wtype", "--", text], check=False)


def selected_text():
    for args in (["wl-paste", "--primary", "--no-newline"], ["wl-paste", "--no-newline"]):
        res = subprocess.run(args, capture_output=True, text=True)
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout
    return ""


_player = None


def speak(text):
    """Read text aloud (blocking until the audio is ready, then plays in background)."""
    global _player
    stop_speaking()
    code = voice_code()
    if not components.voice_installed(code):
        code = "en_US"
    onnx, _json = components.voice_paths(code)
    out = os.path.join(state_dir(), "speech.wav")
    res = subprocess.run([components.venv_python(), WORKER, "speak", onnx, out],
                         input=text[:20000], capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip().splitlines()[-1] if res.stderr.strip()
                           else _("speech synthesis failed"))
    _player = subprocess.Popen(["pw-play", out])


def stop_speaking():
    global _player
    if _player is not None and _player.poll() is None:
        _player.terminate()
    _player = None


def speaking():
    return _player is not None and _player.poll() is None
