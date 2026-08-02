"""Runs inside Aurora AI's private venv (faster-whisper, Piper): no GTK here.

    python3 speechworker.py transcribe AUDIO.wav MODEL_DIR [LANGUAGE]
    python3 speechworker.py speak VOICE.onnx OUT.wav < text
"""

import sys
import wave


def transcribe(audio, model_dir, language=None):
    from faster_whisper import WhisperModel
    model = WhisperModel(model_dir, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(audio, language=language or None, vad_filter=True,
                                       beam_size=5)
    return " ".join(s.text.strip() for s in segments).strip()


def speak(voice, out, text):
    from piper import PiperVoice
    model = PiperVoice.load(voice)
    with wave.open(out, "wb") as wav:
        model.synthesize_wav(text, wav)


def main():
    cmd = sys.argv[1]
    if cmd == "transcribe":
        lang = sys.argv[4] if len(sys.argv) > 4 else None
        print(transcribe(sys.argv[2], sys.argv[3], lang))
    elif cmd == "speak":
        speak(sys.argv[2], sys.argv[3], sys.stdin.read())
    else:
        sys.exit(2)


if __name__ == "__main__":
    main()
