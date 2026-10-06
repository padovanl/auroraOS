"""Aurora AI (downloads, providers, index, catalog), gestures, System Health,
Wi-Fi QR codes and the package build."""

import hashlib
import io
import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from aurora import ai
from aurora.ai import components, download, index, providers


# --- downloads -------------------------------------------------------------

class FakeResponse(io.BytesIO):
    def __init__(self, data, status=200):
        super().__init__(data)
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


def item_for(data):
    return {"url": "https://example.invalid/f", "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def test_download_verifies_and_resumes(tmp_path):
    data = os.urandom(3 * download.CHUNK + 123)
    item = item_for(data)
    dest = str(tmp_path / "model.gguf")
    # A previous attempt left the first 1000 bytes.
    with open(dest + ".part", "wb") as f:
        f.write(data[:1000])
    seen = {}

    def opener(req, timeout):
        seen["range"] = req.get_header("Range")
        return FakeResponse(data[1000:], status=206)
    done = []
    download.fetch(item, dest, progress=lambda d, t: done.append(d), opener=opener)
    assert seen["range"] == "bytes=1000-"
    assert open(dest, "rb").read() == data and done[-1] == len(data)
    assert not os.path.exists(dest + ".part")


def test_download_rejects_a_bad_checksum(tmp_path):
    item = item_for(b"good data")
    dest = str(tmp_path / "x")
    with pytest.raises(download.DownloadError):
        download.fetch(item, dest, opener=lambda req, timeout: FakeResponse(b"evil data"))
    assert not os.path.exists(dest) and not os.path.exists(dest + ".part")


def test_catalog_is_complete_and_pinned():
    cat = ai.catalog()
    items = [cat["runtime"], cat["embed"], *cat["chat"].values()]
    items += [f for w in cat["whisper"].values() for f in w["files"].values()]
    items += [v[k] for v in cat["voices"].values() for k in ("onnx", "json")]
    for it in items:
        assert it["url"].startswith("https://")
        assert len(it["sha256"]) == 64 and it["size"] > 0
    assert set(cat["chat"]) >= {"qwen3-1.7b", "qwen3-4b"}
    assert all("==" in p for p in cat["speech_pip"])


@pytest.mark.parametrize("loc, voice", [("it_IT.UTF-8", "it_IT"), ("de_AT.UTF-8", "de_DE"),
                                        ("zh_TW.UTF-8", "zh_CN"), ("xx_YY", "en_US"),
                                        (None, "en_US")])
def test_voice_for_locale(loc, voice):
    assert components.voice_for(loc) == voice


# --- providers (against a fake OpenAI-compatible server) -------------------

class FakeLLM(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        FakeLLM.last = body
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.end_headers()
        for piece in ("<think>\n\n</think>\n\n", "Use `du", " -sh`", "."):
            chunk = {"choices": [{"delta": {"content": piece}}]}
            self.wfile.write(f"data: {json.dumps(chunk)}\n\n".encode())
        self.wfile.write(b"data: [DONE]\n\n")

    def log_message(self, *a):
        pass


@pytest.fixture
def fake_llm():
    srv = HTTPServer(("127.0.0.1", 0), FakeLLM)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_openai_stream_and_think_filter(fake_llm):
    text = "".join(providers._openai_stream(fake_llm, "m", [{"role": "user", "content": "hi"}],
                                            "", 50, local=True))
    assert text == "Use `du -sh`."
    assert FakeLLM.last["chat_template_kwargs"] == {"enable_thinking": False}
    assert FakeLLM.last["stream"] is True


@pytest.mark.parametrize("chunks, expected", [
    (["<think>\n\n</think>\n\nHello", " world"], "Hello world"),
    (["He", "llo <thi", "nk>secret</th", "ink>there"], "Hello there"),
    (["a <", "b"], "a <b"),
])
def test_think_filter(chunks, expected):
    f = providers.ThinkFilter()
    assert "".join(f.feed(c) for c in chunks) + f.flush() == expected


def test_first_code_block():
    reply = "Here:\n```bash\nfind ~ -size +1G\n```\nFinds big files."
    assert providers.first_code_block(reply) == "find ~ -size +1G"
    assert providers.first_code_block("no code") == ""


# --- search by meaning -------------------------------------------------------

def fake_embed(texts):
    """A tiny bag-of-words embedding, enough to test ranking."""
    vocab = ["bill", "electricity", "pizza", "dough", "train", "ticket"]
    return [[t.lower().count(w) + 0.01 for w in vocab] for t in texts]


def test_index_update_and_search(tmp_path, monkeypatch):
    docs = tmp_path / "Documents"
    docs.mkdir()
    (docs / "bill.txt").write_text("Electricity bill for March: pay the electricity bill. " * 3)
    (docs / "pizza.md").write_text("Pizza dough: flour, water, salt. Let the dough rest. " * 3)
    (docs / ".hidden").mkdir()
    (docs / ".hidden" / "x.txt").write_text("train ticket " * 20)
    monkeypatch.setattr(index, "folders", lambda: [str(docs)])
    db = index.connect(str(tmp_path / "idx.sqlite"))
    assert index.update(fake_embed, db) == 2
    assert index.update(fake_embed, db) == 0          # nothing changed
    hits = index.search(fake_embed(["electricity bill"])[0], db)
    assert os.path.basename(hits[0][0]) == "bill.txt"
    (docs / "bill.txt").unlink()
    index.update(fake_embed, db)
    assert index.stats(db) == (1, index.stats(db)[1])


def test_extract_docx(tmp_path):
    import zipfile
    path = tmp_path / "a.docx"
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", "<w:document><w:body><w:p><w:r><w:t>Hello"
                   "</w:t></w:r></w:p><w:p><w:r><w:t>World</w:t></w:r></w:p></w:body>"
                   "</w:document>")
    assert index.extract(str(path)).split() == ["Hello", "World"]


# --- gestures ----------------------------------------------------------------

def feed(lines):
    from aurora.shell.gestures import Recognizer, parse
    r = Recognizer()
    actions = [r.feed(p) for p in map(parse, lines) if p]
    return [a for a in actions if a]


def swipe(fingers, dx, dy):
    return [f" event7  GESTURE_SWIPE_BEGIN  +1.0s\t{fingers}",
            f" event7  GESTURE_SWIPE_UPDATE +1.1s\t{fingers} {dx:.2f}/{dy:.2f} (0/0 unaccelerated)",
            f" event7  GESTURE_SWIPE_END    +1.2s\t{fingers}"]


@pytest.mark.parametrize("dx, dy, action", [(0, -200, "overview"), (0, 200, "desktop"),
                                            (-200, 10, "workspace-right"),
                                            (200, 10, "workspace-left")])
def test_three_finger_swipes(dx, dy, action):
    assert feed(swipe(3, dx, dy)) == [action]


def test_small_or_four_finger_swipes_do_nothing():
    assert feed(swipe(3, 30, 20)) == []
    assert feed(swipe(4, 0, -300)) == []


def test_four_finger_pinch_opens_launchpad():
    lines = [" event7  GESTURE_PINCH_BEGIN  +1.0s\t4",
             " event7  GESTURE_PINCH_UPDATE +1.1s\t4  0.10/ 0.20 ( 0.10/ 0.20 unaccelerated)  0.55 @ 0.00",
             " event7  GESTURE_PINCH_END    +1.2s\t4"]
    assert feed(lines) == ["launchpad"]


# --- System Health, Wi-Fi QR --------------------------------------------------

def test_smart_status_reads_udisks_objects():
    from aurora.settingsapp.health import smart_status
    objs = {
        "/d1": {"org.freedesktop.UDisks2.Drive": {"Vendor": "ACME", "Model": "SSD"},
                "org.freedesktop.UDisks2.NVMe.Controller": {"SmartCriticalWarning": []}},
        "/d2": {"org.freedesktop.UDisks2.Drive": {"Model": "HDD"},
                "org.freedesktop.UDisks2.Drive.Ata": {"SmartSupported": True, "SmartEnabled": True,
                                                      "SmartFailing": True}},
        "/d3": {"org.freedesktop.UDisks2.Drive": {"Model": "USB stick"}},
    }
    result = dict(smart_status(objs))
    assert result["ACME SSD"] is None
    assert "failing" in result["HDD"]
    assert "USB stick" not in result


def test_wifi_qr_payload_escapes():
    from aurora.settingsapp.network import wifi_qr_payload
    assert wifi_qr_payload('Casa;Rossi', 'pa:ss"1') == 'WIFI:T:WPA;S:Casa\\;Rossi;P:pa\\:ss\\"1;;'
    assert wifi_qr_payload("Open", "") == "WIFI:T:nopass;S:Open;;"


def test_package_build_script_splits_artwork():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = open(os.path.join(root, "build", "package-desktop.sh")).read()
    assert "aurora-artwork" in script and "usr/share/backgrounds" in script
    assert "Maintainer: Luca Padovan" in script


def test_incremental_build_reinstalls_same_version_desktop_packages():
    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    script = open(os.path.join(root, "build", "stages", "40-desktop.sh")).read()
    assert "--reinstall" in script


# --- AI languages ------------------------------------------------------------

class _Settings:
    def __init__(self, **v):
        self.v = v

    def get_string(self, k):
        return self.v.get(k, "")


def test_answer_language_follows_the_user(monkeypatch):
    monkeypatch.setattr(providers.settings, "get", lambda *a: _Settings())
    rule = providers.language_rule()
    assert "language of the user's latest message" in rule and "speak Italian" in rule


def test_answer_language_can_be_fixed(monkeypatch):
    monkeypatch.setattr(providers.settings, "get", lambda *a: _Settings(**{"ai-language": "it"}))
    assert "Always answer in Italian" in providers.language_rule()


def test_dictation_detects_language_unless_chosen(monkeypatch):
    from aurora.ai import speech
    monkeypatch.setattr(speech.settings, "get", lambda *a: _Settings())
    assert speech._language() is None
    monkeypatch.setattr(speech.settings, "get",
                        lambda *a: _Settings(**{"ai-dictation-language": "de"}))
    assert speech._language() == "de"
