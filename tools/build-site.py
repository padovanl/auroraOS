#!/usr/bin/env python3
"""Build docs/technical.html from the "Under the hood" section of README.md.

The README is the single source of truth: this copies the text between
<!-- tech:start --> and <!-- tech:end --> into the website, so the two never
disagree. It understands the small Markdown subset that section uses:
headings, paragraphs, bullet and numbered lists (one nesting level), tables,
**bold**, *italic*, `code` and [links](url).

Usage: tools/build-site.py           (run by `make site`)
       tools/build-site.py --check   (exit 1 if docs/technical.html is out of date)
"""

import html
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(ROOT, "README.md")
OUT = os.path.join(ROOT, "docs", "technical.html")
REPO_README = "https://github.com/padovanl/aurora-os/blob/main/README.md"


def inline(text):
    text = html.escape(text, quote=False)
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)

    def link(m):
        label, url = m.group(1), m.group(2)
        if url.startswith("#"):
            url = REPO_README + url          # README anchors → the README on GitHub
        elif not url.startswith(("http", "mailto:")):
            url = "https://github.com/padovanl/aurora-os/blob/main/" + url
        return f'<a href="{url}">{label}</a>'
    return re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, text)


def slug(text):
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def convert(md):
    out, toc = [], []
    lines = md.splitlines()
    i = 0
    para = []

    def flush_para():
        if para:
            out.append(f"<p>{inline(' '.join(para))}</p>")
            para.clear()

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        if not stripped or stripped.startswith("<!--"):
            flush_para()
            i += 1
            continue
        m = re.match(r"^(#{3,4})\s+(.*)", stripped)
        if m:
            flush_para()
            level = len(m.group(1)) - 1          # ### → h2, #### → h3
            title = m.group(2)
            sid = slug(title)
            if level == 2:
                toc.append((sid, title))
            out.append(f'<h{level} id="{sid}">{inline(title)}</h{level}>')
            i += 1
            continue
        if stripped.startswith("|"):
            flush_para()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-+:?", c) for c in cells):
                    rows.append(cells)
                i += 1
            head, body = rows[0], rows[1:]
            out.append('<div class="table-wrap"><table><thead><tr>' +
                       "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>" +
                       "".join("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
                               for r in body) + "</tbody></table></div>")
            continue
        m = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", line)
        if m:
            flush_para()
            ordered = m.group(2)[0].isdigit()
            tag = "ol" if ordered else "ul"
            items = []
            while i < len(lines):
                lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)", lines[i])
                if lm and len(lm.group(1)) == 0:
                    items.append([lm.group(3), []])
                elif lm and items:
                    items[-1][1].append(lm.group(3))
                elif lines[i].startswith("  ") and lines[i].strip() and items:
                    target = items[-1][1] if items[-1][1] else None
                    if target is not None:
                        target[-1] += " " + lines[i].strip()
                    else:
                        items[-1][0] += " " + lines[i].strip()
                else:
                    break
                i += 1
            parts = []
            for text, subs in items:
                sub_html = ("<ul>" + "".join(f"<li>{inline(s)}</li>" for s in subs) + "</ul>"
                            if subs else "")
                parts.append(f"<li>{inline(text)}{sub_html}</li>")
            out.append(f"<{tag}>{''.join(parts)}</{tag}>")
            continue
        para.append(stripped)
        i += 1
    flush_para()
    return "\n".join(out), toc


def main():
    with open(README) as f:
        text = f.read()
    start, end = text.index("<!-- tech:start -->"), text.index("<!-- tech:end -->")
    body, toc = convert(text[start:end])
    nav = "".join(f'<a href="#{sid}">{html.escape(title)}</a>' for sid, title in toc)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Under the hood · Aurora OS</title>
  <meta name="description" content="Every technical choice behind Aurora OS: components, alternatives we considered and why.">
  <link rel="icon" href="assets/logo.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="assets/site.css">
</head>
<body class="doc-page">
<!-- Generated by tools/build-site.py from README.md. Edit the README, not this file. -->
<header class="nav">
  <a class="brand" href="index.html"><img src="assets/logo.svg" alt="" width="28" height="28"> Aurora OS</a>
  <nav>
    <a href="index.html#features">Features</a>
    <a href="index.html#developers">Developers</a>
    <a href="index.html#install">Install</a>
    <a href="technical.html">Under the hood</a>
    <a class="repo-link" data-repo-link href="#">GitHub</a>
  </nav>
  <a class="btn btn-small" href="index.html#download">Download</a>
</header>
<main class="doc">
  <aside class="doc-toc"><p class="eyebrow">On this page</p>{nav}</aside>
  <article class="doc-body">
    <p class="eyebrow">Under the hood</p>
    <h1>Every technical choice, explained.</h1>
    {body}
  </article>
</main>
<footer class="footer">
  <div><a class="brand" href="index.html"><img src="assets/logo.svg" alt="" width="24" height="24"> Aurora OS</a>
    <p>Built on Debian. Made with care for people who build things.</p></div>
  <div class="footer-links"><a data-repo-link href="#">Source code</a>
    <a data-repo-link data-path="/blob/main/README.md" href="#">Full documentation</a></div>
</footer>
<div class="lightbox" hidden><img alt=""></div>
<script src="assets/site.js"></script>
</body>
</html>
"""
    if "--check" in sys.argv:
        current = open(OUT).read() if os.path.exists(OUT) else ""
        if current != page:
            print("docs/technical.html is out of date: run `make site`")
            sys.exit(1)
        print("docs/technical.html is up to date")
        return
    with open(OUT, "w") as f:
        f.write(page)
    print(f"wrote {os.path.relpath(OUT, ROOT)} ({len(toc)} sections)")


if __name__ == "__main__":
    main()
