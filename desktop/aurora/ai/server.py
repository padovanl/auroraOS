"""Start and stop the local llama.cpp servers on demand.

Two servers, each bound to 127.0.0.1 only:
- chat  (port 47651): the chosen chat model, OpenAI-compatible API;
- embed (port 47652): the embedding model for semantic search.

A server starts on the first request and stops after IDLE_MINUTES without
requests (a small reaper process watches the "last used" time), so the model
only takes memory while you use it.
"""

import json
import os
import signal
import subprocess
import sys
import time
import urllib.request

from aurora import settings
from aurora.ai import components, state_dir
from aurora.i18n import _

PORTS = {"chat": 47651, "embed": 47652}
IDLE_MINUTES = 10


def url(kind):
    return f"http://127.0.0.1:{PORTS[kind]}"


def healthy(kind, timeout=1.0):
    try:
        with urllib.request.urlopen(url(kind) + "/health", timeout=timeout) as r:
            return r.status == 200 and json.load(r).get("status") == "ok"
    except (OSError, ValueError):
        return False


def _pidfile(kind):
    return os.path.join(state_dir(), f"{kind}.pid")


def touch(kind):
    with open(os.path.join(state_dir(), f"{kind}.last"), "w") as f:
        f.write(str(time.time()))


def last_used(kind):
    try:
        with open(os.path.join(state_dir(), f"{kind}.last")) as f:
            return float(f.read())
    except (OSError, ValueError):
        return 0.0


def chat_model_id():
    s = settings.get()
    return s.get_string("ai-model") if s else "qwen3-1.7b"


def command(kind):
    binary = components.server_binary()
    if binary is None:
        raise RuntimeError(_("the AI runtime is not installed (Settings → AI)"))
    if kind == "chat":
        model = components.model_path("chat", chat_model_id())
        extra = ["--ctx-size", "8192", "--jinja", "--n-gpu-layers", "99"]
    else:
        model = components.model_path("embed")
        extra = ["--embeddings", "--pooling", "mean", "--ctx-size", "2048",
                 "--n-gpu-layers", "99"]
    if not os.path.exists(model):
        raise RuntimeError(_("the AI model is not downloaded (Settings → AI)"))
    threads = max(2, (os.cpu_count() or 4) - 2)
    return [binary, "--model", model, "--host", "127.0.0.1", "--port", str(PORTS[kind]),
            "--threads", str(threads), "--no-webui", *extra]


def ensure(kind, wait=180):
    """Make sure the server is up; returns its base URL."""
    touch(kind)
    if healthy(kind):
        return url(kind)
    log = open(os.path.join(state_dir(), f"{kind}.log"), "w")
    proc = subprocess.Popen(command(kind), stdout=log, stderr=subprocess.STDOUT,
                            start_new_session=True)
    with open(_pidfile(kind), "w") as f:
        f.write(str(proc.pid))
    _start_reaper()
    deadline = time.time() + wait
    while time.time() < deadline:
        if proc.poll() is not None:
            raise RuntimeError(_("the AI model stopped unexpectedly (see {log})").format(log=log.name))
        if healthy(kind):
            return url(kind)
        time.sleep(0.5)
    raise RuntimeError(_("the AI model did not start in {n} seconds").format(n=wait))


def stop(kind):
    try:
        with open(_pidfile(kind)) as f:
            pid = int(f.read())
        os.kill(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass
    try:
        os.remove(_pidfile(kind))
    except OSError:
        pass


def running(kind):
    try:
        with open(_pidfile(kind)) as f:
            os.kill(int(f.read()), 0)
        return True
    except (OSError, ValueError):
        return False


def _start_reaper():
    lock = os.path.join(state_dir(), "reaper.pid")
    try:
        with open(lock) as f:
            os.kill(int(f.read()), 0)
        return                             # already watching
    except (OSError, ValueError):
        pass
    env = dict(os.environ)
    env["PYTHONPATH"] = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))) + os.pathsep + env.get("PYTHONPATH", "")
    proc = subprocess.Popen([sys.executable, "-m", "aurora.ai.server", "reap"],
                            env=env, start_new_session=True,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    with open(lock, "w") as f:
        f.write(str(proc.pid))


def reap():
    """Stop servers that have been idle for IDLE_MINUTES; exit when none run."""
    while True:
        alive = False
        for kind in PORTS:
            if running(kind):
                if time.time() - last_used(kind) > IDLE_MINUTES * 60:
                    stop(kind)
                else:
                    alive = True
        if not alive:
            return
        time.sleep(30)


if __name__ == "__main__" and sys.argv[1:] == ["reap"]:
    reap()
