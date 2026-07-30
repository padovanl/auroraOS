"""Text from pictures (like Live Text): Tesseract OCR, offline.

Reads English plus the user's language when its Tesseract data is installed
(the image ships the data for every language on the boot menu).
"""

import locale
import os
import subprocess

# Locale language -> Tesseract language code.
TESSERACT_LANGS = {
    "en": "eng", "it": "ita", "de": "deu", "fr": "fra", "es": "spa", "pt": "por",
    "nl": "nld", "pl": "pol", "sv": "swe", "tr": "tur", "ru": "rus", "uk": "ukr",
    "ja": "jpn", "ko": "kor", "ar": "ara", "hi": "hin",
}
TESSDATA_DIRS = ("/usr/share/tesseract-ocr/5/tessdata", "/usr/share/tesseract-ocr/4.00/tessdata")


def installed_languages():
    for d in TESSDATA_DIRS:
        try:
            return {f[:-12] for f in os.listdir(d) if f.endswith(".traineddata")}
        except OSError:
            continue
    return set()


def language_for(loc=None):
    """Tesseract '-l' value: English plus the user's language, if available."""
    loc = loc or locale.getlocale(locale.LC_MESSAGES)[0] or os.environ.get("LANG", "en")
    code = loc.split(".")[0]
    installed = installed_languages()
    if code.startswith("zh"):
        wanted = "chi_tra" if code in ("zh_TW", "zh_HK") else "chi_sim"
    else:
        wanted = TESSERACT_LANGS.get(code.split("_")[0], "eng")
    langs = ["eng"] + ([wanted] if wanted != "eng" else [])
    langs = [lang for lang in langs if not installed or lang in installed]
    return "+".join(langs) or "eng"


def recognize(image_path, timeout=60):
    """The text in an image ('' if none). Blocking: call from a thread."""
    res = subprocess.run(["tesseract", image_path, "-", "-l", language_for()],
                         capture_output=True, text=True, timeout=timeout)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or "tesseract failed")
    return clean(res.stdout)


def clean(text):
    """Trim OCR noise: trailing spaces, runs of blank lines, form feeds."""
    lines = [ln.rstrip() for ln in text.replace("\f", "").splitlines()]
    out, blank = [], False
    for ln in lines:
        if not ln:
            if not blank and out:
                out.append("")
            blank = True
        else:
            out.append(ln)
            blank = False
    return "\n".join(out).strip()
