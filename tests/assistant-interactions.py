"""The Assistant in a real GTK session: the view follows a long streamed reply to
the bottom, stops following when the user scrolls up, and an attached file
reaches a model on this computer (a fake OpenAI-compatible server)."""
import json
import os
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import GLib  # noqa: E402

requests = []


class FakeLLM(BaseHTTPRequestHandler):
    def do_GET(self):   # /v1/models, for the model picker
        body = json.dumps({"data": [{"id": "fake"}, {"id": "fake-embed"}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        requests.append(json.loads(body))
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        answer = "".join(f"Line {i}: a long answer that keeps the view busy.\n" for i in range(80))
        for i in range(0, len(answer), 40):
            self.wfile.write(("data: " + json.dumps(
                {"choices": [{"delta": {"content": answer[i:i + 40]}}]}) + "\n\n").encode())
            self.wfile.flush()
            time.sleep(0.01)
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *_args):
        pass


server = HTTPServer(("127.0.0.1", 47698), FakeLLM)
threading.Thread(target=server.serve_forever, daemon=True).start()

from aurora import settings  # noqa: E402
s = settings.get()
s.set_string("ai-provider", "openai")
s.set_string("ai-openai-url", "http://127.0.0.1:47698/v1")
s.set_string("ai-openai-model", "fake")
s.set_boolean("ai-enabled", True)

from aurora.assistant import AssistantApp, AssistantWindow  # noqa: E402


def settle(predicate, timeout=20, what="condition"):
    deadline = time.monotonic() + timeout
    ctx = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while ctx.pending():
            ctx.iteration(False)
        if predicate():
            for _ in range(20):          # let layout and idle handlers finish
                while ctx.pending():
                    ctx.iteration(False)
                time.sleep(0.02)
            return
        time.sleep(0.02)
    raise AssertionError(f"timed out waiting for {what}")


def at_bottom(win):
    adj = win.scroller.get_vadjustment()
    return adj.get_value() + adj.get_page_size() >= adj.get_upper() - 2


app = AssistantApp()
app.register(None)
win = AssistantWindow(app)
win.set_default_size(420, 520)
win.present()
settle(lambda: win.get_height() > 100, what="the window")
settle(lambda: win._models is not None, what="the model list")
assert [m for m, _l in win._models[1]] == ["fake"], "embedding models can't chat"
print("ok: the model picker lists the server's chat models")

win.send("Tell me a long story")
settle(lambda: not win.busy, what="the first reply")
adj = win.scroller.get_vadjustment()
assert adj.get_upper() > adj.get_page_size() * 2, "reply should overflow the view"
assert at_bottom(win), (f"view not at the bottom after the reply: value {adj.get_value()}, "
                        f"page {adj.get_page_size()}, upper {adj.get_upper()}")
print("ok: the view follows a streamed reply to the bottom")

# Scrolling up while a reply streams stops following; the "latest" button appears.
win.send("And another one")
settle(lambda: win.busy and len(requests) >= 2, what="the second reply to start")
win._on_user_scroll(None, 0, -1)
adj.set_value(0)
settle(lambda: not win.busy, what="the second reply")
assert adj.get_value() < 10, "view jumped down while the user was reading above"
assert win.latest.get_visible(), "the jump-to-latest button should appear"
win._resume_follow()
settle(lambda: at_bottom(win), what="jump to latest")
print("ok: scrolling up stops following; jump to latest works")

# An attached file goes to a model on this computer.
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "notes.txt")
    with open(path, "w") as f:
        f.write("The secret word is aurora-borealis-42.")
    win.new_chat()
    win._queue_file(path)
    settle(lambda: len(win.attachments) == 1, what="the attachment")
    before = len(requests)
    win.send("What is the secret word?")
    settle(lambda: not win.busy and len(requests) > before, what="the reply with attachment")
    sent = json.dumps(requests[-1])
    assert "aurora-borealis-42" in sent, "the attached text did not reach the model"
    print("ok: attachments reach a model on this computer")

# A cloud endpoint must not receive attachments.
s.set_string("ai-openai-url", "https://api.example.com/v1")
with tempfile.TemporaryDirectory() as tmp:
    path = os.path.join(tmp, "private.txt")
    with open(path, "w") as f:
        f.write("never leaves")
    win.new_chat()
    win._queue_file(path)
    settle(lambda: len(win.attachments) == 1, what="the second attachment")
    before = len(requests)
    win.send("Summarize")
    settle(lambda: True)
    assert len(requests) == before and not win.busy, "attachment sent to a cloud endpoint"
    print("ok: attachments are never sent to a cloud endpoint")
print("ASSISTANT INTERACTIONS PASSED")
