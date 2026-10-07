#!/usr/bin/env python3
"""A stand-in OpenAI-compatible model for the website screenshots
(tools/vm-screenshots.py): the Assistant and Writing Tools show real-looking
answers without downloading a model. Never shipped in the image."""

import json
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

ANSWERS = {
    "disk": "Open **Settings → Storage**: it shows what takes the space.\n\n"
            "1. Click **Clean Up** to empty the Trash, old downloads and caches.\n"
            "2. Turn on **Storage Sense** to do it every week.\n"
            "3. In Files, sort Downloads by size and remove what you don't need.",
    "meeting": "They're going to the meeting tomorrow; we should prepare the slides.",
}


class FakeLLM(BaseHTTPRequestHandler):
    def do_GET(self):
        self._json({"data": [{"id": "aurora-demo"}]})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        prompt = json.dumps(body.get("messages", [])).lower()
        answer = next((a for k, a in ANSWERS.items() if k in prompt),
                      "Here's a short answer, written on this computer.")
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for i in range(0, len(answer), 12):
            chunk = {"choices": [{"delta": {"content": answer[i:i + 12]}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
            self.wfile.flush()
            time.sleep(0.01)
        self.wfile.write(b"data: [DONE]\n\n")

    def _json(self, data):
        raw = json.dumps(data).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *_args):
        pass


HTTPServer(("127.0.0.1", 47699), FakeLLM).serve_forever()
