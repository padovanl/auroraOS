"""Talk to a language model: the local llama.cpp server, Anthropic's Claude,
or any OpenAI-compatible API. All three stream text.

    for piece in chat([{"role": "user", "content": "hi"}]):
        print(piece, end="")
"""

import json
import re
import urllib.error
import urllib.request

from aurora import settings
from aurora.ai import keys, provider

SYSTEM_PROMPT = (
    "You are Aurora, the assistant built into Aurora OS, a Linux desktop based on "
    "Debian 13 (apt, systemd, Wayland with the labwc compositor, bash). Answer in the "
    "language the user writes in. Be concise and practical. Use Markdown code blocks "
    "for commands and code. Never claim to have run a command or opened a file yourself.")

ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"
ANTHROPIC_VERSION = "2023-06-01"


class ProviderError(Exception):
    pass


def _post_stream(url, body, headers, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:300]
        raise ProviderError(f"HTTP {e.code}: {detail}") from e
    except OSError as e:
        raise ProviderError(str(e)) from e
    return resp


def _sse(resp):
    """Yield the JSON payloads of a server-sent-events stream."""
    with resp:
        for raw in resp:
            line = raw.decode("utf-8", errors="replace").strip()
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if data == "[DONE]":
                return
            try:
                yield json.loads(data)
            except ValueError:
                continue


class ThinkFilter:
    """Drops <think>…</think> reasoning some local models print before answering,
    even when the tags arrive split across stream chunks."""

    OPEN, CLOSE = "<think>", "</think>"

    def __init__(self):
        self.buf = ""
        self.inside = False

    def feed(self, text):
        self.buf += text
        out = []
        while True:
            if self.inside:
                end = self.buf.find(self.CLOSE)
                if end < 0:
                    self.buf = self.buf[-(len(self.CLOSE) - 1):]
                    return "".join(out)
                self.buf = self.buf[end + len(self.CLOSE):].lstrip("\n")
                self.inside = False
                continue
            start = self.buf.find(self.OPEN)
            if start >= 0:
                out.append(self.buf[:start])
                self.buf = self.buf[start + len(self.OPEN):]
                self.inside = True
                continue
            # Hold back a trailing "<thi…" that may be the start of a tag.
            keep = next((k for k in range(min(len(self.OPEN) - 1, len(self.buf)), 0, -1)
                         if self.OPEN.startswith(self.buf[-k:])), 0)
            out.append(self.buf[:len(self.buf) - keep])
            self.buf = self.buf[len(self.buf) - keep:]
            return "".join(out)

    def flush(self):
        rest, self.buf = ("" if self.inside else self.buf), ""
        return rest


def _openai_stream(base, model, messages, api_key, max_tokens, local):
    body = {"model": model, "messages": messages, "stream": True, "max_tokens": max_tokens,
            "temperature": 0.4}
    if local:
        # Qwen3 and similar: answer directly, no visible reasoning.
        body["chat_template_kwargs"] = {"enable_thinking": False}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    think = ThinkFilter()
    for event in _sse(_post_stream(base.rstrip("/") + "/chat/completions", body, headers)):
        for choice in event.get("choices", []):
            piece = (choice.get("delta") or {}).get("content") or ""
            if piece:
                text = think.feed(piece)
                if text:
                    yield text
    tail = think.flush()
    if tail:
        yield tail


def _anthropic_stream(model, messages, system, api_key, max_tokens):
    if not api_key:
        raise ProviderError("add your Anthropic API key in Settings → AI")
    body = {"model": model, "max_tokens": max_tokens, "system": system,
            "messages": messages, "stream": True}
    headers = {"x-api-key": api_key, "anthropic-version": ANTHROPIC_VERSION}
    for event in _sse(_post_stream(ANTHROPIC_URL, body, headers)):
        if event.get("type") == "content_block_delta":
            text = (event.get("delta") or {}).get("text")
            if text:
                yield text
        elif event.get("type") == "error":
            raise ProviderError((event.get("error") or {}).get("message", "error"))


def chat(messages, system=SYSTEM_PROMPT, max_tokens=1024):
    """Stream the reply to a list of {role, content} messages."""
    s = settings.get()
    which = provider()
    if which == "anthropic":
        model = s.get_string("ai-anthropic-model") if s else "claude-sonnet-5"
        yield from _anthropic_stream(model, messages, system, keys.get("anthropic"), max_tokens)
        return
    full = [{"role": "system", "content": system}] + list(messages)
    if which == "openai":
        base = s.get_string("ai-openai-url") if s else "https://api.openai.com/v1"
        model = s.get_string("ai-openai-model") if s else ""
        yield from _openai_stream(base, model, full, keys.get("openai"), max_tokens, local=False)
        return
    from aurora.ai import server
    try:
        base = server.ensure("chat") + "/v1"
    except RuntimeError as e:
        raise ProviderError(str(e)) from e
    yield from _openai_stream(base, server.chat_model_id(), full, "", max_tokens, local=True)
    server.touch("chat")


def complete(messages, system=SYSTEM_PROMPT, max_tokens=1024):
    return "".join(chat(messages, system, max_tokens)).strip()


def embed(texts):
    """Embedding vectors for a list of texts (always local)."""
    from aurora.ai import server
    base = server.ensure("embed")
    req = urllib.request.Request(base + "/v1/embeddings", method="POST",
                                 data=json.dumps({"input": texts, "model": "embed"}).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        data = json.load(r)["data"]
    server.touch("embed")
    return [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]


CODE_BLOCK = re.compile(r"```[a-zA-Z0-9_-]*\n(.*?)```", re.S)


def first_code_block(text):
    m = CODE_BLOCK.search(text)
    return m.group(1).strip() if m else ""
