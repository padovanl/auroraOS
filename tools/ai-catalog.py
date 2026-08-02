#!/usr/bin/env python3
"""Regenerate desktop/aurora/ai/catalog.json: everything Aurora AI can download,
pinned by URL, size and SHA-256.

Usage: tools/ai-catalog.py      (needs network; run when bumping versions)

Nothing here ships in the ISO. Aurora downloads an item only when the user
turns on the feature that needs it, into ~/.local/share/aurora/ai, and checks
the hash before using it.
"""

import hashlib
import json
import os
import urllib.parse
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "desktop", "aurora", "ai", "catalog.json")

LLAMA_TAG = "b11149"
LLAMA_ASSET = f"llama-{LLAMA_TAG}-bin-ubuntu-vulkan-x64.tar.gz"

# id: (name, repo, file, RAM needed in GB, description)
CHAT_MODELS = {
    "qwen3-1.7b": ("Qwen3 1.7B", "unsloth/Qwen3-1.7B-GGUF", "Qwen3-1.7B-Q4_K_M.gguf", 4,
                   "Fast, for any computer. Good for commands, short answers and rewriting."),
    "qwen3-4b": ("Qwen3 4B", "Qwen/Qwen3-4B-GGUF", "Qwen3-4B-Q4_K_M.gguf", 8,
                 "Balanced. Recommended with 8 GB of memory or more."),
    "gemma3-4b": ("Gemma 3 4B", "ggml-org/gemma-3-4b-it-GGUF", "gemma-3-4b-it-Q4_K_M.gguf", 8,
                  "Google's model, strong at writing and translation."),
    "qwen3-8b": ("Qwen3 8B", "Qwen/Qwen3-8B-GGUF", "Qwen3-8B-Q4_K_M.gguf", 16,
                 "The most capable. Needs 16 GB of memory; best with a graphics card."),
}
EMBED_MODEL = ("EmbeddingGemma 300M", "ggml-org/embeddinggemma-300M-GGUF",
               "embeddinggemma-300M-Q8_0.gguf")
WHISPER_MODELS = {
    "base": ("Whisper base", "Systran/faster-whisper-base", "Quick, good in quiet rooms."),
    "small": ("Whisper small", "Systran/faster-whisper-small", "More accurate, a bit slower."),
}
WHISPER_FILES = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]
# Locale (language_TERRITORY) → Piper voice. zh_TW uses the Mandarin voice.
VOICES = {
    "en_US": "en_US-lessac-medium", "en_GB": "en_GB-alba-medium",
    "it_IT": "it_IT-paola-medium", "de_DE": "de_DE-thorsten-medium",
    "fr_FR": "fr_FR-siwis-medium", "es_ES": "es_ES-davefx-medium",
    "pt_BR": "pt_BR-faber-medium", "pt_PT": "pt_PT-tugão-medium",
    "nl_NL": "nl_NL-pim-medium", "pl_PL": "pl_PL-gosia-medium",
    "sv_SE": "sv_SE-alma-medium", "tr_TR": "tr_TR-dfki-medium",
    "ru_RU": "ru_RU-irina-medium", "uk_UA": "uk_UA-ukrainian_tts-medium",
    "zh_CN": "zh_CN-huayan-medium", "ja_JP": "ja_JP-hi_fi_captain-medium",
    "ko_KR": "ko_KR-kss-medium", "ar_EG": "ar_JO-kareem-medium",
    "hi_IN": "hi_IN-priyamvada-medium",
}
# Python packages for speech, installed with pip into a private venv.
SPEECH_PIP = ["faster-whisper==1.2.1", "piper-tts==1.8.0"]


def get_json(url):
    with urllib.request.urlopen(url, timeout=60) as r:
        return json.load(r)


def hf_files(repo, path=""):
    url = f"https://huggingface.co/api/models/{repo}/tree/main"
    if path:
        url += "/" + urllib.parse.quote(path)
    return {f["path"]: f for f in get_json(url)}


def hf_item(repo, path, files=None):
    """URL, size and SHA-256 of a file on Hugging Face (small files are hashed here)."""
    files = files or hf_files(repo, os.path.dirname(path))
    info = files[path]
    url = f"https://huggingface.co/{repo}/resolve/main/{urllib.parse.quote(path)}"
    sha = (info.get("lfs") or {}).get("oid")
    size = info.get("size")
    if not sha:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = r.read()
        sha, size = hashlib.sha256(data).hexdigest(), len(data)
    return {"url": url, "size": size, "sha256": sha}


def main():
    rel = get_json(f"https://api.github.com/repos/ggml-org/llama.cpp/releases/tags/{LLAMA_TAG}")
    asset = next(a for a in rel["assets"] if a["name"] == LLAMA_ASSET)
    catalog = {
        "runtime": {"name": f"llama.cpp {LLAMA_TAG} (Vulkan, falls back to the CPU)",
                    "url": asset["browser_download_url"], "size": asset["size"],
                    "sha256": asset["digest"].split(":", 1)[1]},
        "chat": {}, "embed": None, "whisper": {}, "voices": {}, "speech_pip": SPEECH_PIP,
    }
    for mid, (name, repo, path, ram, desc) in CHAT_MODELS.items():
        catalog["chat"][mid] = dict(name=name, ram_gb=ram, description=desc,
                                    file=path, **hf_item(repo, path))
        print("chat", mid)
    name, repo, path = EMBED_MODEL
    catalog["embed"] = dict(name=name, file=path, **hf_item(repo, path))
    for mid, (name, repo, desc) in WHISPER_MODELS.items():
        files = hf_files(repo)
        catalog["whisper"][mid] = {"name": name, "description": desc,
                                   "files": {f: hf_item(repo, f, files) for f in WHISPER_FILES}}
        print("whisper", mid)
    for loc, voice in VOICES.items():
        lang, rest = voice.split("_", 1)
        region = voice.split("-")[0]
        speaker, quality = voice.split("-")[1], voice.split("-")[2]
        folder = f"{lang}/{region}/{speaker}/{quality}"
        files = hf_files("rhasspy/piper-voices", folder)
        catalog["voices"][loc] = {
            "name": voice,
            "onnx": hf_item("rhasspy/piper-voices", f"{folder}/{voice}.onnx", files),
            "json": hf_item("rhasspy/piper-voices", f"{folder}/{voice}.onnx.json", files),
        }
        print("voice", loc)
    with open(OUT, "w") as f:
        json.dump(catalog, f, indent=1, ensure_ascii=False)
        f.write("\n")
    print("wrote", os.path.relpath(OUT))


if __name__ == "__main__":
    main()
