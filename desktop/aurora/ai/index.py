"""Search your documents by meaning, entirely on this computer.

The indexer walks the folders chosen in Settings → AI, extracts text (plain
text and code, Markdown, PDF with pdftotext, Word/LibreOffice documents),
cuts it into overlapping passages and stores an embedding vector for each in
~/.local/share/aurora/ai/index.sqlite. Only changed files are re-read.

A search embeds the query with the same model and ranks passages by cosine
similarity (numpy). One result per file, best passage first.
"""

import os
import re
import sqlite3
import subprocess
import time
import zipfile

from aurora import settings
from aurora.ai import base_dir

TEXT_EXT = {".txt", ".md", ".markdown", ".rst", ".org", ".tex", ".csv", ".json", ".yaml",
            ".yml", ".toml", ".ini", ".py", ".js", ".ts", ".go", ".rs", ".c", ".h", ".cpp",
            ".java", ".kt", ".rb", ".php", ".sh", ".html", ".css", ".sql"}
DOC_EXT = {".pdf", ".docx", ".odt"}
MAX_FILE = 20 * 1024 * 1024
PASSAGE = 900          # characters per passage
OVERLAP = 150
BATCH = 16
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", ".cache", "build", "dist"}


def db_path():
    return os.path.join(base_dir(), "index.sqlite")


def connect(path=None):
    path = path or db_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    db = sqlite3.connect(path)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS files (path TEXT PRIMARY KEY, mtime REAL, size INTEGER);
        CREATE TABLE IF NOT EXISTS passages (path TEXT, pos INTEGER, text TEXT, vec BLOB);
        CREATE INDEX IF NOT EXISTS passages_path ON passages(path);
    """)
    return db


def folders():
    s = settings.get()
    items = s.get_strv("ai-index-folders") if s else ["~/Documents"]
    return [os.path.expanduser(f) for f in items]


def extract(path):
    """The text of a document, or '' if it can't be read."""
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext in TEXT_EXT:
            with open(path, "rb") as f:
                data = f.read(MAX_FILE)
            if b"\0" in data[:4096]:
                return ""
            return data.decode("utf-8", errors="replace")
        if ext == ".pdf":
            res = subprocess.run(["pdftotext", "-layout", "-q", path, "-"],
                                 capture_output=True, text=True, timeout=60)
            return res.stdout
        if ext in (".docx", ".odt"):
            member = "word/document.xml" if ext == ".docx" else "content.xml"
            with zipfile.ZipFile(path) as z:
                xml = z.read(member).decode("utf-8", errors="replace")
            xml = re.sub(r"</(w:p|text:p|text:h)>", "\n", xml)
            return re.sub(r"<[^>]+>", "", xml)
    except (OSError, zipfile.BadZipFile, KeyError, subprocess.TimeoutExpired):
        return ""
    return ""


def passages(text):
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    out, i = [], 0
    while i < len(text):
        out.append(text[i:i + PASSAGE])
        i += PASSAGE - OVERLAP
    return [p for p in out if len(p.strip()) > 40]


def candidates():
    for root_dir in folders():
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
            for name in files:
                path = os.path.join(root, name)
                ext = os.path.splitext(name)[1].lower()
                if ext in TEXT_EXT or ext in DOC_EXT:
                    try:
                        st = os.stat(path)
                    except OSError:
                        continue
                    if st.st_size <= MAX_FILE:
                        yield path, st.st_mtime, st.st_size


def update(embed, db=None, progress=None, should_stop=None):
    """Index new and changed files, forget deleted ones. embed(list[str]) → vectors."""
    db = db or connect()
    known = {p: (m, s) for p, m, s in db.execute("SELECT path, mtime, size FROM files")}
    seen = set()
    todo = []
    for path, mtime, size in candidates():
        seen.add(path)
        if known.get(path) != (mtime, size):
            todo.append((path, mtime, size))
    for path in set(known) - seen:
        db.execute("DELETE FROM passages WHERE path = ?", (path,))
        db.execute("DELETE FROM files WHERE path = ?", (path,))
    for n, (path, mtime, size) in enumerate(todo):
        if should_stop and should_stop():
            break
        chunks = passages(extract(path))
        vectors = []
        for i in range(0, len(chunks), BATCH):
            vectors.extend(embed(chunks[i:i + BATCH]))
        db.execute("DELETE FROM passages WHERE path = ?", (path,))
        db.executemany("INSERT INTO passages VALUES (?, ?, ?, ?)",
                       [(path, i, c, _pack(v)) for i, (c, v) in enumerate(zip(chunks, vectors))])
        db.execute("INSERT OR REPLACE INTO files VALUES (?, ?, ?)", (path, mtime, size))
        db.commit()
        if progress:
            progress(n + 1, len(todo), path)
    db.commit()
    return len(todo)


def _pack(vec):
    import numpy as np   # only for vectors: reading files works without it
    v = np.asarray(vec, dtype=np.float32)
    n = np.linalg.norm(v)
    return (v / n if n else v).tobytes()


def search(query_vec, db=None, limit=8):
    """[(path, score, passage)] best first, one per file."""
    db = db or connect()
    rows = db.execute("SELECT path, text, vec FROM passages").fetchall()
    if not rows:
        return []
    import numpy as np
    q = np.asarray(query_vec, dtype=np.float32)
    q /= np.linalg.norm(q) or 1.0
    mat = np.frombuffer(b"".join(r[2] for r in rows), dtype=np.float32).reshape(len(rows), -1)
    scores = mat @ q
    best = {}
    for i in np.argsort(-scores):
        path, text, _v = rows[i]
        if path not in best:
            best[path] = (float(scores[i]), text)
        if len(best) >= limit:
            break
    return [(p, s, t) for p, (s, t) in best.items()]


def stats(db=None):
    db = db or connect()
    files = db.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    chunks = db.execute("SELECT COUNT(*) FROM passages").fetchone()[0]
    return files, chunks


def run_indexer():
    """`aurora-ai index`: update the index with the local embedding model."""
    from aurora.ai.providers import embed
    start = time.time()
    n = update(embed)
    files, chunks = stats()
    print(f"indexed {n} changed files in {time.time() - start:.0f} s "
          f"({files} files, {chunks} passages)")
