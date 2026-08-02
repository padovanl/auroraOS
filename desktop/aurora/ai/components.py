"""What Aurora AI can install, where it goes, and whether it's there.

Each component is installed on request (Settings → AI) and can be removed to
free the space again.
"""

import glob
import os
import shutil
import subprocess
import tarfile

from aurora.ai import base_dir, catalog
from aurora.ai.download import fetch, is_complete


def runtime_dir():
    return os.path.join(base_dir(), "llama")


def server_binary():
    found = glob.glob(os.path.join(runtime_dir(), "*", "llama-server"))
    return found[0] if found else None


def runtime_installed():
    return server_binary() is not None


def install_runtime(progress=None, cancelled=None):
    item = catalog()["runtime"]
    archive = os.path.join(base_dir(), "downloads", os.path.basename(item["url"]))
    fetch(item, archive, progress, cancelled)
    target = runtime_dir()
    shutil.rmtree(target, ignore_errors=True)
    os.makedirs(target)
    with tarfile.open(archive) as tar:
        tar.extractall(target, filter="data")
    os.remove(archive)
    return server_binary()


def model_path(kind, model_id=None):
    """kind 'chat' (with a model id) or 'embed'."""
    item = catalog()["embed"] if kind == "embed" else catalog()["chat"][model_id]
    return os.path.join(base_dir(), "models", item["file"])


def model_installed(kind, model_id=None):
    item = catalog()["embed"] if kind == "embed" else catalog()["chat"].get(model_id)
    return item is not None and is_complete(item, model_path(kind, model_id))


def install_model(kind, model_id=None, progress=None, cancelled=None):
    item = catalog()["embed"] if kind == "embed" else catalog()["chat"][model_id]
    return fetch(item, model_path(kind, model_id), progress, cancelled)


def remove_model(kind, model_id=None):
    for path in (model_path(kind, model_id), model_path(kind, model_id) + ".part"):
        if os.path.exists(path):
            os.remove(path)


# --- speech: a private venv with faster-whisper and Piper ---------------------

def venv_dir():
    return os.path.join(base_dir(), "venv")


def venv_python():
    return os.path.join(venv_dir(), "bin", "python3")


def speech_installed():
    return os.path.exists(os.path.join(venv_dir(), ".aurora-speech-ok"))


def install_speech(log=None):
    """Create the venv and pip-install the pinned speech packages."""
    if not os.path.exists(venv_python()):
        subprocess.run(["python3", "-m", "venv", venv_dir()], check=True)
    cmd = [venv_python(), "-m", "pip", "install", "--disable-pip-version-check",
           "--no-input", *catalog()["speech_pip"]]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    for line in proc.stdout:
        if log:
            log(line.rstrip())
    if proc.wait() != 0:
        raise RuntimeError("pip could not install the speech packages")
    open(os.path.join(venv_dir(), ".aurora-speech-ok"), "w").close()


def whisper_dir(model_id):
    return os.path.join(base_dir(), "whisper", model_id)


def whisper_installed(model_id):
    files = catalog()["whisper"][model_id]["files"]
    return all(is_complete(item, os.path.join(whisper_dir(model_id), name))
               for name, item in files.items())


def install_whisper(model_id, progress=None, cancelled=None):
    files = catalog()["whisper"][model_id]["files"]
    total = sum(i["size"] for i in files.values())
    done_before = 0
    for name, item in files.items():
        fetch(item, os.path.join(whisper_dir(model_id), name),
              (lambda d, _t, b=done_before: progress(b + d, total)) if progress else None,
              cancelled)
        done_before += item["size"]
    return whisper_dir(model_id)


def voice_for(locale_name):
    """The catalog voice for a locale like 'it_IT.UTF-8' (English if none)."""
    voices = catalog()["voices"]
    code = (locale_name or "en_US").split(".")[0]
    if code in voices:
        return code
    lang = code.split("_")[0]
    if lang == "zh":
        return "zh_CN"
    return next((c for c in voices if c.startswith(lang + "_")), "en_US")


def voice_paths(code):
    v = catalog()["voices"][code]
    folder = os.path.join(base_dir(), "voices")
    return (os.path.join(folder, f"{v['name']}.onnx"),
            os.path.join(folder, f"{v['name']}.onnx.json"))


def voice_installed(code):
    v = catalog()["voices"][code]
    onnx, js = voice_paths(code)
    return is_complete(v["onnx"], onnx) and is_complete(v["json"], js)


def install_voice(code, progress=None, cancelled=None):
    v = catalog()["voices"][code]
    onnx, js = voice_paths(code)
    fetch(v["json"], js, None, cancelled)
    fetch(v["onnx"], onnx, progress, cancelled)
    return onnx


def disk_usage():
    total = 0
    for root, _dirs, files in os.walk(base_dir()):
        for f in files:
            try:
                total += os.path.getsize(os.path.join(root, f))
            except OSError:
                pass
    return total


def remove_everything():
    shutil.rmtree(base_dir(), ignore_errors=True)
