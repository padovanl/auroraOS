#!/usr/bin/env python3
"""Build the website's generated pages: docs/technical.html from the "Under the
hood" section of README.md, and ai.html, developers.html and install.html from
docs/_src/*.body.html, all with the same header and footer.

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
REPO_README = "https://github.com/padovanl/auroraOS/blob/main/README.md"


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
            url = "https://github.com/padovanl/auroraOS/blob/main/" + url
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


NAV = [("index.html#features", "Features"), ("ai.html", "AI"),
       ("developers.html", "Developers &amp; Gaming"), ("install.html", "Install"),
       ("technical.html", "Under the hood")]


def header(active):
    if active.startswith("technical-"):
        active = "technical.html"
    links = "".join(f'<a href="{href}"{" class=\"active\"" if href == active else ""}>{label}</a>'
                    for href, label in NAV)
    return f"""<header class="nav">
  <a class="brand" href="index.html"><img src="assets/logo.svg" alt="" width="28" height="28"> Aurora OS</a>
  <nav>
    {links}
    <a class="repo-link" data-repo-link href="#">GitHub</a>
  </nav>
  <a class="btn btn-small" href="index.html#download">Download</a>
</header>"""


FOOTER = """<footer class="footer">
  <div><a class="brand" href="index.html"><img src="assets/logo.svg" alt="" width="24" height="24"> Aurora OS</a>
    <p>Built on Debian. Made with care for people who build things.</p></div>
  <div class="footer-links"><a href="ai.html">Aurora AI</a> <a href="install.html">Install guide</a>
    <a data-repo-link href="#">Source code</a>
    <a data-repo-link data-path="/blob/main/README.md" href="#">Full documentation</a></div>
</footer>
<div class="lightbox" hidden><img alt=""></div>
<script src="assets/site.js"></script>
</body>
</html>
"""


def page(filename, title, description, body, body_class=""):
    cls = f' class="{body_class}"' if body_class else ""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} · Aurora OS</title>
  <meta name="description" content="{description}">
  <link rel="icon" href="assets/logo.svg" type="image/svg+xml">
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="assets/site.css">
</head>
<body{cls}>
<!-- Generated by tools/build-site.py. Edit docs/_src/ or the README, not this file. -->
{header(filename)}
{body}
{FOOTER}"""


PAGES = [  # (file, title, description, source in docs/_src)
    ("ai.html", "Aurora AI", "A private AI assistant built into Aurora OS: local models, "
     "Spotlight, the terminal, writing tools, dictation and search by meaning.", "ai.body.html"),
    ("developers.html", "Developers and gaming", "Developer tools ready on day one, Dev Hub, "
     "AI in the terminal, and Game Hub for Steam, Windows and Android apps.",
     "developers.body.html"),
    ("install.html", "Install guide", "Download Aurora OS, write it to a USB stick, try it "
     "live and install it step by step; snapshots, sharing and troubleshooting.",
     "install.body.html"),
]


# Aurora icons shown on the website (the marquee on the home page), copied from the
# icon theme generator so the site always shows the real ones.
SITE_ICONS = {
    "apps": ["org.gnome.Geary", "org.gnome.Calendar", "org.gnome.Weather", "org.gnome.Maps",
             "org.gnome.clocks", "org.gnome.Calculator", "org.gnome.Loupe",
             "org.gnome.Rhythmbox3", "io.github.celluloid_player.Celluloid",
             "org.gnome.Snapshot", "org.gnome.Software", "org.gnome.Ptyxis",
             "system-file-manager", "preferences-system", "org.gnome.SystemMonitor",
             "org.gnome.baobab", "org.gnome.seahorse.Application", "org.gnome.Characters",
             "org.gnome.font-viewer", "timeshift", "org.gnome.DejaDup", "org.gnome.Firmware",
             "org.gnome.TextEditor", "org.gnome.Papers", "org.gnome.SoundRecorder"],
    "places": ["folder", "user-home", "folder-download", "folder-music", "folder-pictures",
               "folder-videos", "folder-documents", "folder-development", "user-trash"],
    "mimetypes": ["application-pdf", "text-x-python", "image-x-generic", "package-x-generic",
                  "x-office-document", "x-office-spreadsheet", "text-html", "application-json",
                  "text-markdown", "application-x-deb", "audio-x-generic", "video-x-generic",
                  "text-x-rust", "text-x-go", "application-javascript"],
}


def write_icons():
    import importlib.util
    import shutil
    import tempfile
    spec = importlib.util.spec_from_file_location(
        "icons", os.path.join(ROOT, "branding", "icons", "generate.py"))
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    dest = os.path.join(ROOT, "docs", "assets", "icons")
    os.makedirs(dest, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        gen.generate(tmp)
        for context, names in SITE_ICONS.items():
            for name in names:
                src = os.path.realpath(os.path.join(tmp, "Aurora", "scalable", context, name + ".svg"))
                shutil.copyfile(src, os.path.join(dest, name + ".svg"))
    # The animated logo of the home page, with real transparency.
    import subprocess
    subprocess.run([sys.executable, os.path.join(ROOT, "branding", "logo.py"), "webp",
                    os.path.join(ROOT, "docs", "assets", "aurora-logo.webp"), "480"], check=True)
    for name in ("aurora-devhub", "aurora-gamehub", "aurora-assistant", "aurora-logo"):
        shutil.copyfile(os.path.join(ROOT, "desktop", "data", "icons", "scalable", "apps",
                                     name + ".svg"), os.path.join(dest, name + ".svg"))


# "Under the hood" is split into one page per chapter (### in the README), like
# real documentation: a chapter list on the left, "On this page" on the right,
# previous/next at the bottom, and an index page with a filter over every topic.
CHAPTER_ICONS = {
    "platform": "🧱", "boot-and-live-system": "🚀", "installer-and-first-boot": "💿",
    "graphics-and-the-compositor": "🪟", "aurora-s-own-desktop": "🖥️", "aurora-ai": "✦",
    "look-and-feel": "🎨", "session-services": "⚙️", "apps": "🧩",
    "security-and-privacy": "🔒", "developer-experience": "⌨️", "internationalization": "🌍",
    "aurora-s-own-packages-and-repository": "📦", "game-hub": "🎮", "build-system": "🏗️",
    "testing": "🧪", "bugs-we-found-and-how-we-fixed-them": "🐞", "website": "🌐",
}


# One line per chapter, for the index cards and the chapter's lead.
CHAPTER_BLURBS = {
    "platform": "Debian 13, the long-term kernel, systemd, apt with Flatpak, and the firmware "
                "that makes hardware just work.",
    "boot-and-live-system": "GRUB, the live system on SquashFS, how the ISO is mastered, and the "
                            "animated boot splash.",
    "installer-and-first-boot": "Calamares, btrfs with automatic snapshots, encryption, swap, "
                                "and the login screen.",
    "graphics-and-the-compositor": "Wayland, the labwc compositor, and window decorations that "
                                   "look the same everywhere.",
    "aurora-s-own-desktop": "The shell written in Python and GTK 4: top bar, dock, Spotlight, "
                            "notifications, Quick Look and more.",
    "aurora-ai": "Local models with llama.cpp, cloud providers, speech, search by meaning, "
                 "and how privacy is kept.",
    "look-and-feel": "Themes for every toolkit, Aurora's icons and window buttons, animations, "
                     "fonts and artwork made by code.",
    "session-services": "Audio, networking, Bluetooth, power, printing and the other services "
                        "a desktop session runs on.",
    "apps": "Every preinstalled app, the alternatives we compared, and why each one won.",
    "security-and-privacy": "Firewall, updates, encryption, Secure Boot, verified downloads and "
                            "no telemetry.",
    "developer-experience": "What's preinstalled for developers, the terminal setup, containers "
                            "and Dev Hub.",
    "internationalization": "gettext, translations in eleven languages, fonts for every script "
                            "and the language menus.",
    "aurora-s-own-packages-and-repository": "How Aurora's own .deb packages are built, signed and "
                                            "published.",
    "game-hub": "Steam, Proton, Heroic, Lutris, Bottles and Waydroid: gaming set up in one click.",
    "build-system": "Docker, staged build scripts and the steps from source to a bootable ISO.",
    "testing": "Static checks, unit and smoke tests, and real boots and installs in QEMU.",
    "bugs-we-found-and-how-we-fixed-them": "Real bugs met while building and using Aurora, "
                                           "what caused them and how they were fixed.",
    "website": "This website: static pages, generated docs and screenshots from the real ISO.",
}


def chapter_file(sid):
    return f"technical-{sid}.html"


def split_chapters(md):
    """(intro markdown, [(slug, title, markdown)])"""
    parts = re.split(r"^### (.+)$", md, flags=re.M)
    intro, chapters = parts[0], []
    for title, body in zip(parts[1::2], parts[2::2]):
        chapters.append((slug(title), title.strip(), body))
    return intro, chapters


def summary(md):
    """The first sentence of a chapter's first paragraph (or first list item), for its
    index card and lead."""
    for block in re.split(r"\n\s*\n", md):
        b = block.strip()
        if not b or b.startswith(("#", "|", "<!--")):
            continue
        if b.startswith(("-", "*")) or re.match(r"\d+\.", b):
            b = re.split(r"\n(?=[-*] |\d+\. )", b)[0]
            b = re.sub(r"^([-*]|\d+\.)\s+", "", b)
            b = re.sub(r"^\*\*[^*]+:\*\*\s*", "", b)
        text = re.sub(r"<[^>]+>", "", inline(" ".join(b.split())))
        first = re.split(r"(?<=[.!?])\s", text)[0]
        return first if len(first) < 220 else first[:217] + "…"
    return ""


def topics(md):
    return re.findall(r"^#### (.+)$", md, flags=re.M)


def points(md):
    """How many things a chapter covers: its topics, or else its top-level bullets and
    table rows."""
    table_rows = max(0, len(re.findall(r"^\|", md, flags=re.M)) - 2)
    return len(topics(md)) or len(re.findall(r"^[-*] ", md, flags=re.M)) + table_rows


def doc_sidebar(chapters, active):
    items = []
    for sid, title, md in chapters:
        cls = ' class="active"' if sid == active else ""
        items.append(f'<a{cls} href="{chapter_file(sid)}"><span>{CHAPTER_ICONS.get(sid, "•")}</span>'
                     f'{html.escape(title)}</a>')
        if sid == active:
            items.append('<div class="doc-sub">' + "".join(
                f'<a href="#{slug(t)}">{inline(t)}</a>' for t in topics(md)) + "</div>")
    return ('<aside class="doc-nav"><a class="doc-home" href="technical.html">← All chapters</a>'
            '<p class="eyebrow">Under the hood</p>' + "".join(items) + "</aside>")


def tech_pages(md):
    intro, chapters = split_chapters(md)
    out = {}
    intro_html, _ = convert(intro)
    cards = "".join(
        f'<a class="doc-card reveal" href="{chapter_file(sid)}" data-topics="{html.escape(" ".join(topics(body)).lower())}">'
        f'<span class="doc-card-icon">{CHAPTER_ICONS.get(sid, "•")}</span>'
        f'<h3>{html.escape(title)}</h3><p>{CHAPTER_BLURBS.get(sid) or summary(body)}</p>'
        f'<span class="doc-card-meta">{points(body)} topic{"s" if points(body) != 1 else ""} →</span></a>'
        for sid, title, body in chapters)
    all_topics = "".join(
        f'<a href="{chapter_file(sid)}#{slug(t)}" data-topic="{html.escape(t.lower())}">'
        f'<b>{inline(t)}</b><span>{html.escape(title)}</span></a>'
        for sid, title, body in chapters for t in topics(body))
    index = f"""<main class="doc-index">
<section class="section page-sky">
  <div class="section-head">
    <p class="eyebrow">Under the hood</p>
    <h1>Every technical choice, explained.</h1>
    <p class="lead">What Aurora is built from, what else we considered, and why: {len(chapters)}
      chapters, {sum(points(b) for _s, _t, b in chapters)} decisions.</p>
    <div class="doc-search"><input type="search" placeholder="Search topics: labwc, btrfs, Wayland, llama.cpp…"
      aria-label="Search topics" data-doc-search></div>
    <div class="doc-results" data-doc-results hidden>{all_topics}</div>
  </div>
  <div class="doc-intro reveal">{intro_html}</div>
  <div class="doc-cards">{cards}</div>
</section>
</main>"""
    out[OUT] = page("technical.html", "Under the hood", "Every technical choice behind "
                    "Aurora OS: components, alternatives we considered and why.", index,
                    "doc-page")
    for n, (sid, title, body) in enumerate(chapters):
        content, toc = convert(re.sub(r"^#### ", "### ", body, flags=re.M))
        on_page = "".join(f'<a href="#{i}">{html.escape(t)}</a>' for i, t in toc)
        prev_link = next_link = ""
        if n > 0:
            ps, pt, _ = chapters[n - 1]
            prev_link = (f'<a class="doc-pn prev" href="{chapter_file(ps)}"><span>← Previous</span>'
                         f'<b>{html.escape(pt)}</b></a>')
        if n < len(chapters) - 1:
            ns, nt, _ = chapters[n + 1]
            next_link = (f'<a class="doc-pn next" href="{chapter_file(ns)}"><span>Next →</span>'
                         f'<b>{html.escape(nt)}</b></a>')
        body_html = f"""<main class="doc doc-3">
  {doc_sidebar(chapters, sid)}
  <article class="doc-body">
    <nav class="crumbs"><a href="technical.html">Under the hood</a> <span>/</span> {html.escape(title)}</nav>
    <p class="doc-chapter-icon">{CHAPTER_ICONS.get(sid, "")}</p>
    <h1>{html.escape(title)}</h1>
    <p class="lead doc-lead">{CHAPTER_BLURBS.get(sid) or summary(body)}</p>
    {content}
    <div class="doc-prevnext">{prev_link}{next_link}</div>
  </article>
  <aside class="doc-toc"><p class="eyebrow">On this page</p>{on_page}</aside>
</main>"""
        out[os.path.join(ROOT, "docs", chapter_file(sid))] = page(
            chapter_file(sid), f"{title} · Under the hood",
            html.escape(CHAPTER_BLURBS.get(sid) or re.sub(r"<[^>]+>", "", summary(body))),
            body_html, "doc-page")
    return out


def build():
    """{path: html} for every generated page."""
    with open(README) as f:
        text = f.read()
    start, end = text.index("<!-- tech:start -->"), text.index("<!-- tech:end -->")
    out = tech_pages(text[start + len("<!-- tech:start -->"):end])
    for name, title, desc, src in PAGES:
        with open(os.path.join(ROOT, "docs", "_src", src)) as f:
            out[os.path.join(ROOT, "docs", name)] = page(name, title, desc, f.read())
    return out


def main():
    pages = build()
    if "--check" in sys.argv:
        stale = [os.path.relpath(p, ROOT) for p, html_ in pages.items()
                 if not os.path.exists(p) or open(p).read() != html_]
        if stale:
            print(f"out of date: {', '.join(stale)}: run `make site`")
            sys.exit(1)
        print("website pages are up to date")
        return
    for path, html_ in pages.items():
        with open(path, "w") as f:
            f.write(html_)
        print(f"wrote {os.path.relpath(path, ROOT)}")
    write_icons()
    print("wrote docs/assets/icons")


if __name__ == "__main__":
    main()
