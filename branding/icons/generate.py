#!/usr/bin/env python3
"""Generate the Aurora icon theme: apps, folders, devices and file types.

Usage: generate.py OUTPUT_ICONS_DIR

Writes two themes that share the same artwork:
  Aurora       (light desktop) inherits Papirus for everything not drawn here
  Aurora-Dark  (dark desktop)  inherits Papirus-Dark
Symbolic icons (panel, sidebars, buttons) come from Papirus; well-known brand
icons (Firefox, LibreOffice, Steam, VS Code…) are left to their apps.

Everything is drawn by code on a 128 px grid, so the set stays consistent:
apps are rounded squares with a gradient and a white glyph, folders are violet
with an embossed emblem, files are pages with a glyph and a colored type label.
"""

import math
import os
import sys

# --------------------------------------------------------------------------- apps

def app(c1, c2, glyph):
    """A rounded-square app icon with a vertical gradient and a glyph."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        '<defs>'
        f'<linearGradient id="bg" x1="0" y1="0" x2="0.35" y2="1"><stop offset="0" stop-color="{c1}"/>'
        f'<stop offset="1" stop-color="{c2}"/></linearGradient>'
        '<linearGradient id="hl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" '
        'stop-opacity=".30"/><stop offset=".45" stop-color="#fff" stop-opacity="0"/></linearGradient>'
        '</defs>'
        '<rect x="9" y="11" width="110" height="110" rx="27" fill="#000" opacity=".22"/>'
        '<rect x="8" y="8" width="112" height="112" rx="28" fill="url(#bg)"/>'
        '<rect x="8" y="8" width="112" height="112" rx="28" fill="url(#hl)"/>'
        '<rect x="8.5" y="8.5" width="111" height="111" rx="27.5" fill="none" stroke="#fff" '
        'stroke-opacity=".18"/>'
        f'{glyph}</svg>\n')


W = "#ffffff"


def stroke(d, width=8, color=W, extra=""):
    return (f'<path d="{d}" fill="none" stroke="{color}" stroke-width="{width}" '
            f'stroke-linecap="round" stroke-linejoin="round" {extra}/>')


def fill(d, color=W, extra=""):
    return f'<path d="{d}" fill="{color}" {extra}/>'


def gear(cx, cy, r_out, r_in, teeth, hole, color=W, hole_color="#000"):
    pts = []
    for i in range(teeth * 2):
        a0 = math.pi * 2 * i / (teeth * 2) - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        for da in (-0.16, 0.16):
            a = a0 + da
            pts.append(f"{cx + r * math.cos(a):.1f} {cy + r * math.sin(a):.1f}")
    d = "M" + " L".join(pts) + "Z"
    return fill(d, color) + f'<circle cx="{cx}" cy="{cy}" r="{hole}" fill="{hole_color}"/>'


GLYPHS = {
    "mail": fill("M30 44a8 8 0 0 1 8-8h52a8 8 0 0 1 8 8v40a8 8 0 0 1-8 8H38a8 8 0 0 1-8-8z")
    + stroke("M34 44l30 22 30-22", 6, "#3b6fe0"),
    "download": stroke("M64 32v38M48 56l16 16 16-16", 9)
    + stroke("M36 78v8a6 6 0 0 0 6 6h44a6 6 0 0 0 6-6v-8", 8),
    "remote": stroke("M32 42a6 6 0 0 1 6-6h52a6 6 0 0 1 6 6v34a6 6 0 0 1-6 6H38a6 6 0 0 1-6-6z", 7)
    + stroke("M64 82v12M50 94h28", 7) + stroke("M54 66l18-18M60 48h12v12", 6),
    "document": fill("M40 26h34l16 16v54a6 6 0 0 1-6 6H40a6 6 0 0 1-6-6V32a6 6 0 0 1 6-6z")
    + fill("M74 26v12a4 4 0 0 0 4 4h12z", "#ffd3cf")
    + stroke("M44 58h32M44 70h32M44 82h20", 5, "#e0463f"),
    "text": fill("M36 26h40l14 14v56a6 6 0 0 1-6 6H36a6 6 0 0 1-6-6V32a6 6 0 0 1 6-6z")
    + stroke("M40 50h26M40 62h32M40 74h20", 5, "#f0a23a")
    + fill("M92 44l10 10-30 30-13 3 3-13z", "#3a2a1a") + fill("M92 44l10 10 4-4-10-10z", "#ff7a5c"),
    "scanner": fill("M40 30h48v22H40z", W, 'opacity=".75"')
    + fill("M26 58a8 8 0 0 1 8-8h60a8 8 0 0 1 8 8v26a8 8 0 0 1-8 8H34a8 8 0 0 1-8-8z")
    + fill("M34 64h60v5H34z", "#35c3ff") + '<circle cx="88" cy="81" r="4" fill="#4b5565"/>',
    "calendar": fill("M30 40a10 10 0 0 1 10-10h48a10 10 0 0 1 10 10v48a10 10 0 0 1-10 10H40a10 10 0 0 1-10-10z")
    + fill("M30 40a10 10 0 0 1 10-10h48a10 10 0 0 1 10 10v8H30z", "#ff5f57")
    + "".join(f'<circle cx="{44 + 14 * c}" cy="{62 + 12 * r}" r="4.5" fill="{"#ff5f57" if (r, c) == (1, 2) else "#9aa0ad"}"/>'
              for r in range(3) for c in range(4)),
    "contacts": '<circle cx="64" cy="52" r="15" fill="#fff"/>'
    + fill("M36 96c0-17 12-26 28-26s28 9 28 26z"),
    "weather": '<circle cx="54" cy="52" r="17" fill="#ffd35c"/>'
    + fill("M46 94h40a15 15 0 0 0 1-30 20 20 0 0 0-37 4 13 13 0 0 0-4 26z"),
    "maps": fill("M28 42l24-9 24 9 24-9v58l-24 9-24-9-24 9z")
    + stroke("M52 33v58M76 42v58", 3, "#2c9c7a", 'opacity=".35"')
    + fill("M64 88s-15-15-15-26a15 15 0 0 1 30 0c0 11-15 26-15 26z", "#ff5f6d")
    + '<circle cx="64" cy="62" r="5.5" fill="#fff"/>',
    "clock": '<circle cx="64" cy="64" r="36" fill="#fff"/>'
    + "".join(stroke(f"M{64 + 29 * math.cos(a):.1f} {64 + 29 * math.sin(a):.1f}L{64 + 32 * math.cos(a):.1f} {64 + 32 * math.sin(a):.1f}", 3, "#2a2f45")
              for a in [i * math.pi / 6 for i in range(12)])
    + stroke("M64 64V42", 6, "#2a2f45") + stroke("M64 64l16 9", 6, "#ff7a45")
    + '<circle cx="64" cy="64" r="4.5" fill="#2a2f45"/>',
    "calculator": "".join(f'<rect x="{30 + 18 * c}" y="{34 + 20 * r}" width="14" height="14" rx="4" fill="#fff" opacity=".92"/>'
                          for r in range(3) for c in range(3))
    + '<rect x="84" y="34" width="14" height="54" rx="4" fill="#ff9f43"/>'
    + '<rect x="30" y="94" width="68" height="4" rx="2" fill="#fff" opacity=".4"/>',
    "image": fill("M28 42a10 10 0 0 1 10-10h52a10 10 0 0 1 10 10v44a10 10 0 0 1-10 10H38a10 10 0 0 1-10-10z")
    + fill("M34 88l20-24 14 16 10-10 16 18z", "#c24ea8") + '<circle cx="80" cy="50" r="7" fill="#ffb03a"/>',
    "music": fill("M54 84a11 11 0 1 1-8-10.6V42l42-10v44a11 11 0 1 1-8-10.6V50l-26 6z"),
    "video": fill("M52 42v44l36-22z"),
    "camera": fill("M26 54a10 10 0 0 1 10-10h10l6-8h24l6 8h10a10 10 0 0 1 10 10v30a10 10 0 0 1-10 10H36a10 10 0 0 1-10-10z")
    + '<circle cx="64" cy="68" r="16" fill="#2b3040"/><circle cx="64" cy="68" r="9" fill="#5a78ff"/>'
    + '<circle cx="60" cy="64" r="3" fill="#fff" opacity=".8"/>',
    "microphone": fill("M52 42a12 12 0 0 1 24 0v22a12 12 0 0 1-24 0z")
    + stroke("M40 62a24 24 0 0 0 48 0M64 86v10M52 96h24", 7),
    "folder": fill("M28 40a8 8 0 0 1 8-8h18l8 8h30a8 8 0 0 1 8 8v4H28z", W, 'opacity=".7"')
    + fill("M28 52a8 8 0 0 1 8-8h56a8 8 0 0 1 8 8v36a8 8 0 0 1-8 8H36a8 8 0 0 1-8-8z"),
    "terminal": stroke("M38 48l18 16-18 16", 9, "#7ee0b8") + stroke("M64 82h26", 9),
    "store": fill("M32 50a6 6 0 0 1 6-6h52a6 6 0 0 1 6 6l-4 40a8 8 0 0 1-8 8H44a8 8 0 0 1-8-8z")
    + stroke("M50 48v-6a14 14 0 0 1 28 0v6", 7)
    + fill("M64 60l4 9 10 1-7.5 6.5 2.3 9.5L64 81l-8.8 5 2.3-9.5L50 70l10-1z", "#ff7a59"),
    "screenshot": stroke("M34 50V40a6 6 0 0 1 6-6h10M78 34h10a6 6 0 0 1 6 6v10M94 78v10a6 6 0 0 1-6 6H78M50 94H40a6 6 0 0 1-6-6V78", 8)
    + '<circle cx="64" cy="64" r="10" fill="#fff"/>',
    "disk": fill("M28 54a10 10 0 0 1 10-10h52a10 10 0 0 1 10 10v22a10 10 0 0 1-10 10H38a10 10 0 0 1-10-10z")
    + stroke("M40 66h30", 5, "#9aa3b5") + '<circle cx="86" cy="66" r="5" fill="#35d07f"/>',
    "pie": '<circle cx="64" cy="64" r="34" fill="#fff"/>'
    + fill("M64 64V30a34 34 0 0 1 32.3 44.5z", "#ffd35c") + fill("M64 64l32.3 10.5A34 34 0 0 1 52 96z", "#ff7a8a"),
    "pulse": stroke("M26 66h16l8-20 12 40 10-30 6 10h24", 7, "#6fe39a"),
    "logs": "".join(f'<circle cx="36" cy="{40 + 16 * i}" r="4.5" fill="{c}"/>'
                    + stroke(f"M48 {40 + 16 * i}h{w}", 6, W, 'opacity=".9"')
                    for i, (c, w) in enumerate((("#6fe39a", 44), ("#ffd35c", 36), ("#ff6b6b", 46), ("#6fb5ff", 30)))),
    "backup": fill("M40 90h48a18 18 0 0 0 2-35.9 24 24 0 0 0-46.4 4.2A16 16 0 0 0 40 90z")
    + stroke("M64 82V62M54 70l10-10 10 10", 7, "#4a5fd0"),
    "snapshot": stroke("M38 64a26 26 0 1 0 8-18.8", 8) + stroke("M36 36v12h12", 8)
    + stroke("M64 50v15l10 7", 7),
    "key": stroke("M76 76l18 18M86 86l7-7M92 92l6-6", 8) + '<circle cx="54" cy="54" r="20" fill="none" stroke="#fff" stroke-width="9"/>',
    "characters": stroke("M38 90h16v-7a26 26 0 1 1 20 0v7h16", 8),
    "fonts": stroke("M38 94L64 34l26 60M48 74h32", 9),
    "archive": fill("M30 48h68v40a8 8 0 0 1-8 8H38a8 8 0 0 1-8-8z")
    + fill("M26 38a6 6 0 0 1 6-6h64a6 6 0 0 1 6 6v10H26z", W, 'opacity=".75"')
    + stroke("M64 54v36", 6, "#8a5a2b", 'stroke-dasharray="4 5"'),
    "battery": stroke("M30 52a8 8 0 0 1 8-8h44a8 8 0 0 1 8 8v24a8 8 0 0 1-8 8H38a8 8 0 0 1-8-8z", 7)
    + fill("M94 56h4a3 3 0 0 1 3 3v10a3 3 0 0 1-3 3h-4z") + fill("M64 48l-12 18h10l-6 14 16-20H62l6-12z", "#ffe066"),
    "chip": fill("M42 46a4 4 0 0 1 4-4h36a4 4 0 0 1 4 4v36a4 4 0 0 1-4 4H46a4 4 0 0 1-4-4z")
    + "".join(stroke(f"M{x} 32v10M{x} 86v10", 5) for x in (52, 64, 76))
    + "".join(stroke(f"M32 {y}h10M86 {y}h10", 5) for y in (52, 64, 76))
    + '<rect x="54" y="54" width="20" height="20" rx="3" fill="#1f9d80"/>',
    "printer": fill("M42 32h44v18H42z", W, 'opacity=".75"')
    + fill("M26 58a8 8 0 0 1 8-8h60a8 8 0 0 1 8 8v22a8 8 0 0 1-8 8H34a8 8 0 0 1-8-8z")
    + fill("M42 74h44v24H42z", "#eef1f7") + stroke("M50 84h28M50 92h18", 4, "#8b95a8")
    + '<circle cx="88" cy="62" r="4" fill="#35d07f"/>',
    "bluetooth": stroke("M50 46l28 26-14 12V36l14 12-28 26", 8),
    "server": "".join(fill(f"M30 {34 + 22 * i}a6 6 0 0 1 6-6h56a6 6 0 0 1 6 6v8a6 6 0 0 1-6 6H36a6 6 0 0 1-6-6z")
                      + f'<circle cx="84" cy="{38 + 22 * i}" r="3.5" fill="#35d07f"/>' for i in range(3)),
    "cards": fill("M36 40a6 6 0 0 1 7-5l32 6a6 6 0 0 1 5 7l-8 44a6 6 0 0 1-7 5l-32-6a6 6 0 0 1-5-7z", W, 'opacity=".6"')
    + fill("M50 38a6 6 0 0 1 6-6h32a6 6 0 0 1 6 6v48a6 6 0 0 1-6 6H56a6 6 0 0 1-6-6z")
    + fill("M72 48c6 8 14 12 14 19a7 7 0 0 1-12 4l2 8h-8l2-8a7 7 0 0 1-12-4c0-7 8-11 14-19z", "#1f2a3a"),
    "mine": "".join(stroke(f"M{64 + 16 * math.cos(a):.1f} {64 + 16 * math.sin(a):.1f}L{64 + 32 * math.cos(a):.1f} {64 + 32 * math.sin(a):.1f}", 6, "#1b1f2a")
                    for a in [i * math.pi / 4 for i in range(8)])
    + '<circle cx="64" cy="64" r="21" fill="#1b1f2a"/><circle cx="57" cy="57" r="6" fill="#fff" opacity=".8"/>',
    "sudoku": stroke("M34 34h60v60H34zM54 34v60M74 34v60M34 54h60M34 74h60", 4)
    + '<rect x="37" y="37" width="14" height="14" rx="3" fill="#ffd35c"/>'
    + '<rect x="57" y="57" width="14" height="14" rx="3" fill="#fff"/>'
    + '<rect x="77" y="77" width="14" height="14" rx="3" fill="#ff7a8a"/>',
    "tile": fill("M40 30a8 8 0 0 1 8-8h32a8 8 0 0 1 8 8v68a8 8 0 0 1-8 8H48a8 8 0 0 1-8-8z", "#fbf6e8")
    + fill("M40 94h48v4a8 8 0 0 1-8 8H48a8 8 0 0 1-8-8z", "#35b37e")
    + '<circle cx="54" cy="42" r="7" fill="#e5484d"/><circle cx="64" cy="62" r="7" fill="#2f7de1"/>'
    + '<circle cx="74" cy="82" r="7" fill="#35b37e"/>',
    "bars": "".join(f'<rect x="{30 + 18 * i}" y="{96 - h}" width="12" height="{h}" rx="4" fill="{c}"/>'
                    for i, (h, c) in enumerate(((30, "#6fe39a"), (52, "#ffd35c"), (40, "#ff9f6b"), (62, "#6fb5ff")))),
    "network": stroke("M64 44v18M64 62L40 82M64 62l24 20", 6)
    + '<circle cx="64" cy="40" r="11" fill="#fff"/><circle cx="38" cy="86" r="11" fill="#fff"/>'
    + '<circle cx="90" cy="86" r="11" fill="#fff"/>',
    "accounts": fill("M40 88h52a16 16 0 0 0 1-32 22 22 0 0 0-42.6 3.8A14.5 14.5 0 0 0 40 88z")
    + '<circle cx="66" cy="68" r="7" fill="#4a6cf0"/>' + fill("M53 86c0-7 6-11 13-11s13 4 13 11z", "#4a6cf0"),
    "settings": "",  # filled in below (needs the background color for the hole)
}
GLYPHS["settings"] = gear(64, 64, 38, 29, 9, 12, W, "#5b6275")

# icon name(s) → (top color, bottom color, glyph)
APPS = {
    ("org.gnome.Geary", "internet-mail", "mail-client"): ("#5aa2ff", "#3a58e0", "mail"),
    ("transmission", "transmission-gtk"): ("#46c98b", "#1f8f78", "download"),
    ("org.remmina.Remmina", "remmina"): ("#39c4d4", "#2574c9", "remote"),
    ("org.gnome.Papers", "org.gnome.Evince", "evince", "accessories-document-viewer"):
        ("#ff7a6b", "#e0463f", "document"),
    ("org.gnome.TextEditor", "text-editor", "accessories-text-editor", "gedit"):
        ("#ffc65c", "#f0902a", "text"),
    ("org.gnome.SimpleScan", "simple-scan", "scanner"): ("#8a98b3", "#4f5b73", "scanner"),
    ("org.gnome.Calendar", "office-calendar"): ("#ffffff", "#e6e8ef", "calendar"),
    ("org.gnome.Contacts", "x-office-address-book"): ("#c98bff", "#8a4fe0", "contacts"),
    ("org.gnome.Weather",): ("#6ec3ff", "#3a7ff0", "weather"),
    ("org.gnome.Maps",): ("#6fe0b4", "#26a67f", "maps"),
    ("org.gnome.clocks",): ("#3b4467", "#1d2238", "clock"),
    ("org.gnome.Calculator", "accessories-calculator"): ("#5d6478", "#2e3240", "calculator"),
    ("org.gnome.Loupe", "eog", "image-viewer"): ("#ff8fd0", "#b35ee6", "image"),
    ("org.gnome.Rhythmbox3", "rhythmbox", "multimedia-audio-player"): ("#ff7aa2", "#e8375f", "music"),
    ("io.github.celluloid_player.Celluloid", "celluloid", "multimedia-video-player"):
        ("#9c7bff", "#4b3bd6", "video"),
    ("org.gnome.Snapshot", "camera-app"): ("#6b7489", "#343a4a", "camera"),
    ("org.gnome.SoundRecorder", "audio-recorder"): ("#ff8a7a", "#e8455a", "microphone"),
    ("system-file-manager", "org.gnome.Nautilus", "file-manager"): ("#7ec8ff", "#3f7bf0", "folder"),
    ("org.gnome.Ptyxis", "utilities-terminal", "org.gnome.Terminal", "org.gnome.Console",
     "terminal"): ("#2f3445", "#161922", "terminal"),
    ("org.gnome.Software", "system-software-install", "software-store"): ("#ffae5c", "#ff5e7a", "store"),
    ("applets-screenshooter", "org.gnome.Screenshot"): ("#7c8aa6", "#48536b", "screenshot"),
    ("org.gnome.DiskUtility", "gnome-disks", "drive-harddisk-system"): ("#9aa3b5", "#5d6679", "disk"),
    ("org.gnome.baobab", "baobab"): ("#46c7c0", "#1f8a9a", "pie"),
    ("org.gnome.SystemMonitor", "utilities-system-monitor", "gnome-system-monitor"):
        ("#2c3342", "#12161f", "pulse"),
    ("org.gnome.Logs", "logviewer"): ("#3a4152", "#1b1f29", "logs"),
    ("org.gnome.DejaDup", "deja-dup"): ("#8fb1ff", "#4a5fd0", "backup"),
    ("timeshift",): ("#b07bff", "#ff6f91", "snapshot"),
    ("org.gnome.seahorse.Application", "seahorse", "dialog-password"): ("#ffd35c", "#e89a1f", "key"),
    ("org.gnome.Characters", "gucharmap"): ("#4fd1c5", "#2179a8", "characters"),
    ("org.gnome.font-viewer", "font-viewer", "preferences-desktop-font"): ("#ff9a7a", "#e0584a", "fonts"),
    ("org.gnome.FileRoller", "file-roller", "ark"): ("#e0b07a", "#a0692f", "archive"),
    ("org.gnome.PowerStats", "gnome-power-statistics"): ("#5fd38d", "#1f9160", "battery"),
    ("org.gnome.Firmware", "firmware-manager"): ("#4ed8b0", "#1f9d80", "chip"),
    ("printer", "system-config-printer", "printer-network"): ("#9aa3b5", "#5d6679", "printer"),
    ("blueman", "bluetooth", "preferences-bluetooth"): ("#5aa2ff", "#2c62d9", "bluetooth"),
    ("network-server",): ("#3b4467", "#1d2238", "server"),
    ("gnome-aisleriot", "sol"): ("#3fbf7f", "#1d7a52", "cards"),
    ("org.gnome.Mines", "gnome-mines"): ("#d9dde6", "#a9b0c0", "mine"),
    ("org.gnome.Sudoku", "gnome-sudoku"): ("#6f8cff", "#3c50d6", "sudoku"),
    ("org.gnome.Mahjongg", "gnome-mahjongg"): ("#ff8a6b", "#d8433f", "tile"),
    ("btop", "htop"): ("#2c3342", "#12161f", "bars"),
    ("preferences-system-network", "nm-connection-editor"): ("#5aa2ff", "#3a58e0", "network"),
    ("goa-panel", "org.gnome.OnlineAccounts", "gnome-online-accounts",
     "org.gnome.OnlineAccounts.OAuth2"): ("#9ec5ff", "#5a78f0", "accounts"),
    ("preferences-system", "org.gnome.Settings", "preferences-desktop", "gnome-control-center",
     "systemsettings"): ("#9aa1b3", "#5b6275", "settings"),
}

# ------------------------------------------------------------------------ folders

FOLDER_BACK = "#6c4fd8"
FOLDER_TOP = "#b49cff"
FOLDER_BOTTOM = "#7f5ff2"
EMBLEM = "#4a2fb5"


def folder(emblem=""):
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        '<defs><linearGradient id="f" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{FOLDER_TOP}"/><stop offset="1" stop-color="{FOLDER_BOTTOM}"/>'
        '</linearGradient></defs>'
        f'<path d="M12 30a8 8 0 0 1 8-8h30a6 6 0 0 1 4.2 1.8L62 32h46a8 8 0 0 1 8 8v12H12z" fill="{FOLDER_BACK}"/>'
        '<rect x="12" y="43" width="104" height="69" rx="10" fill="#000" opacity=".18"/>'
        '<rect x="12" y="40" width="104" height="70" rx="10" fill="url(#f)"/>'
        '<rect x="12" y="40" width="104" height="70" rx="10" fill="none" stroke="#fff" '
        'stroke-opacity=".35" stroke-width="1.5"/>'
        f'<g opacity=".62">{emblem}</g></svg>\n')


def em_fill(d):
    return f'<path d="{d}" fill="{EMBLEM}"/>'


def em_stroke(d, w=6):
    return (f'<path d="{d}" fill="none" stroke="{EMBLEM}" stroke-width="{w}" '
            'stroke-linecap="round" stroke-linejoin="round"/>')


EMBLEMS = {
    ("folder", "folder-open", "inode-directory", "folder-visiting"): "",
    ("user-home", "folder-home"): em_fill("M64 58l20 16v18a3 3 0 0 1-3 3H71V81H57v14H47a3 3 0 0 1-3-3V74z")
        + em_stroke("M40 76l24-20 24 20", 6),
    ("user-desktop", "folder-desktop"): em_stroke("M44 62h40v24H44zM58 94h12M64 86v8", 5),
    ("folder-documents",): em_fill("M50 58h20l10 10v26H50z"),
    ("folder-download", "folder-downloads"): em_stroke("M64 58v26M54 74l10 10 10-10M48 94h32", 6),
    ("folder-music",): em_fill("M58 90a7 7 0 1 1-5-6.7V62l24-6v28a7 7 0 1 1-5-6.7V66l-14 3.5z"),
    ("folder-pictures", "folder-images"): em_fill("M46 60h36v32H46z")
        + '<path d="M50 88l10-12 7 8 5-5 8 9z" fill="#fff" opacity=".7"/>',
    ("folder-videos", "folder-video"): em_fill("M56 60v32l26-16z"),
    ("folder-publicshare", "folder-public"): '<circle cx="64" cy="66" r="7" fill="%s"/>' % EMBLEM
        + em_fill("M50 94c0-9 6-14 14-14s14 5 14 14z"),
    ("folder-templates",): em_stroke("M50 60h28v32H50zM56 70h16M56 78h16M56 86h10", 4),
    ("folder-remote", "folder-network", "network-workgroup"): em_stroke(
        "M64 58a18 18 0 1 0 0 36 18 18 0 1 0 0-36zM46 76h36M64 58c-8 8-8 28 0 36c8-8 8-28 0-36", 4),
    ("folder-development", "folder-projects", "folder-code"): em_stroke("M56 66l-10 10 10 10M72 66l10 10-10 10", 6),
    ("folder-git",): em_stroke("M56 62v28M56 72c0 8 16 6 16 14", 5)
        + f'<circle cx="56" cy="62" r="5" fill="{EMBLEM}"/><circle cx="56" cy="90" r="5" fill="{EMBLEM}"/>'
        + f'<circle cx="72" cy="86" r="5" fill="{EMBLEM}"/>',
    ("folder-recent", "document-open-recent"): em_stroke("M64 58a18 18 0 1 0 0 36 18 18 0 1 0 0-36zM64 66v10l7 5", 5),
}


def trash(full=False):
    papers = ('<path d="M44 34l12-8 8 10M60 30l14-6 6 12" fill="#fff" stroke="#c9ccd6" '
              'stroke-width="2" stroke-linejoin="round"/>' if full else "")
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        '<defs><linearGradient id="t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9ecf3"/>'
        '<stop offset="1" stop-color="#b9bfcc"/></linearGradient></defs>'
        f'{papers}'
        '<path d="M34 44h60l-6 60a8 8 0 0 1-8 7H48a8 8 0 0 1-8-7z" fill="#000" opacity=".15" transform="translate(0 3)"/>'
        '<path d="M34 44h60l-6 60a8 8 0 0 1-8 7H48a8 8 0 0 1-8-7z" fill="url(#t)"/>'
        '<rect x="28" y="34" width="72" height="12" rx="6" fill="#d5d9e3"/>'
        '<rect x="54" y="28" width="20" height="8" rx="3" fill="#b9bfcc"/>'
        '<path d="M52 58l2 40M64 58v40M76 58l-2 40" stroke="#8d95a8" stroke-width="4" stroke-linecap="round"/>'
        '</svg>\n')


def device(kind):
    base = '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
    grad = ('<defs><linearGradient id="d" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#eef0f5"/>'
            '<stop offset="1" stop-color="#b3b9c6"/></linearGradient></defs>')
    if kind == "hdd":
        body = ('<rect x="16" y="42" width="96" height="48" rx="12" fill="#000" opacity=".15" transform="translate(0 3)"/>'
                '<rect x="16" y="42" width="96" height="48" rx="12" fill="url(#d)"/>'
                '<rect x="28" y="62" width="44" height="6" rx="3" fill="#8d95a8"/>'
                '<circle cx="94" cy="65" r="5" fill="#35d07f"/>')
    elif kind == "usb":
        body = ('<rect x="40" y="18" width="48" height="26" rx="4" fill="#c9ccd6"/>'
                '<rect x="50" y="26" width="8" height="8" fill="#6d7489"/><rect x="70" y="26" width="8" height="8" fill="#6d7489"/>'
                f'<rect x="32" y="40" width="64" height="72" rx="14" fill="{FOLDER_BOTTOM}"/>'
                '<rect x="32" y="40" width="64" height="72" rx="14" fill="#fff" opacity=".12"/>'
                '<circle cx="64" cy="76" r="8" fill="#fff" opacity=".85"/>')
    elif kind == "optical":
        body = ('<circle cx="64" cy="64" r="48" fill="url(#d)"/>'
                '<circle cx="64" cy="64" r="48" fill="none" stroke="#b49cff" stroke-width="6" opacity=".6"/>'
                '<circle cx="64" cy="64" r="14" fill="#8d95a8"/><circle cx="64" cy="64" r="6" fill="#fff"/>')
    else:  # computer
        body = ('<rect x="18" y="26" width="92" height="62" rx="8" fill="#2c3342"/>'
                '<rect x="24" y="32" width="80" height="50" rx="4" fill="#7f5ff2"/>'
                '<rect x="24" y="32" width="80" height="50" rx="4" fill="url(#d)" opacity=".25"/>'
                '<path d="M10 92h108l-6 10H16z" fill="url(#d)"/>')
    return base + grad + body + "</svg>\n"


DEVICES = {
    ("drive-harddisk", "drive-harddisk-solidstate", "drive-multidisk"): "hdd",
    ("drive-removable-media", "drive-removable-media-usb", "media-removable",
     "media-flash"): "usb",
    ("media-optical", "drive-optical", "media-optical-cd", "media-optical-dvd"): "optical",
    ("computer", "computer-laptop", "user-computer"): "computer",
}

# ---------------------------------------------------------------------- file types

PAGE = "M30 10h46l26 26v74a8 8 0 0 1-8 8H30a8 8 0 0 1-8-8V18a8 8 0 0 1 8-8z"


def page(glyph="", label="", color="#8d95a8"):
    tag = ""
    if label:
        w = 16 + 10 * len(label)
        x = 62 - w / 2
        tag = (f'<rect x="{x:.1f}" y="86" width="{w}" height="22" rx="6" fill="{color}"/>'
               f'<text x="62" y="102" text-anchor="middle" font-family="Inter, Noto Sans, DejaVu Sans, sans-serif" '
               f'font-weight="800" font-size="15" letter-spacing=".4" fill="#fff">{label}</text>')
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="128" height="128" viewBox="0 0 128 128">'
        f'<path d="{PAGE}" fill="#000" opacity=".14" transform="translate(0 2.5)"/>'
        f'<path d="{PAGE}" fill="#fbfaff" stroke="#d7d2e4" stroke-width="1.5"/>'
        '<path d="M76 10v18a8 8 0 0 0 8 8h18z" fill="#e3ddf0"/>'
        f'{glyph}{tag}</svg>\n')


def lines(color, n=4, top=44):
    return "".join(f'<rect x="36" y="{top + 11 * i}" width="{46 if i % 3 != 2 else 30}" height="5" rx="2.5" '
                   f'fill="{color}" opacity=".55"/>' for i in range(n))


def code_glyph(color):
    return (f'<path d="M50 44l-12 14 12 14M74 44l12 14-12 14M66 40l-8 36" fill="none" stroke="{color}" '
            'stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>')


FT = {
    "image": ('<rect x="34" y="40" width="56" height="40" rx="6" fill="#ffe3f1"/>'
              '<path d="M38 76l16-18 10 11 8-7 14 14z" fill="#e0559f"/><circle cx="76" cy="52" r="6" fill="#ffae3a"/>',
              "#e0559f"),
    "audio": ('<path d="M56 74a9 9 0 1 1-6-8.5V44l28-7v30a9 9 0 1 1-6-8.5V51l-16 4z" fill="#ff8a3d"/>',
              "#ff8a3d"),
    "video": ('<rect x="34" y="40" width="56" height="40" rx="8" fill="#ece6ff"/>'
              '<path d="M56 48v24l20-12z" fill="#7b5cf0"/>', "#7b5cf0"),
    "archive": ('<path d="M62 30v50" stroke="#c98a2e" stroke-width="7" stroke-dasharray="5 5"/>'
                '<rect x="54" y="62" width="16" height="16" rx="3" fill="#c98a2e"/>', "#c98a2e"),
    "pdf": (lines("#e0463f"), "#e0463f"),
    "text": (lines("#8d95a8", 5, 40), None),
    "doc": (lines("#3a73e0"), "#3a73e0"),
    "sheet": ("".join(f'<rect x="{36 + 18 * c}" y="{42 + 12 * r}" width="16" height="10" rx="2" '
                      f'fill="#23a55a" opacity="{.8 if r == 0 else .35}"/>' for r in range(3) for c in range(3)),
              "#23a55a"),
    "slides": ('<rect x="34" y="40" width="56" height="36" rx="5" fill="#ffe8da"/>'
               '<rect x="42" y="60" width="8" height="10" fill="#ff7a3d"/><rect x="54" y="52" width="8" height="18" fill="#ff7a3d"/>'
               '<rect x="66" y="46" width="8" height="24" fill="#ff7a3d"/>', "#ff7a3d"),
    "exec": ('<circle cx="62" cy="58" r="16" fill="none" stroke="#5b6275" stroke-width="8" '
             'stroke-dasharray="6 4.5"/><circle cx="62" cy="58" r="6" fill="#5b6275"/>', "#5b6275"),
    "iso": ('<circle cx="62" cy="58" r="22" fill="#e6e9f0" stroke="#b49cff" stroke-width="3"/>'
            '<circle cx="62" cy="58" r="6" fill="#8d95a8"/>', "#6d7489"),
    "font": ('<path d="M46 78l16-38 16 38M52 66h20" fill="none" stroke="#e0584a" stroke-width="7" '
             'stroke-linecap="round" stroke-linejoin="round"/>', "#e0584a"),
    "package": ('<path d="M40 48l22-10 22 10v24l-22 10-22-10z" fill="#ffd9a8"/>'
                '<path d="M40 48l22 10 22-10M62 58v24" fill="none" stroke="#c98a2e" stroke-width="3"/>', "#d8433f"),
    "calendar": ('<rect x="38" y="40" width="48" height="40" rx="6" fill="#ffe1df"/>'
                 '<rect x="38" y="40" width="48" height="11" rx="5" fill="#ff5f57"/>', "#ff5f57"),
    "database": ('<ellipse cx="62" cy="44" rx="20" ry="7" fill="#3a73e0"/>'
                 '<path d="M42 44v26c0 4 9 7 20 7s20-3 20-7V44" fill="#8fb4ff"/>'
                 '<ellipse cx="62" cy="44" rx="20" ry="7" fill="#3a73e0"/>', "#3a73e0"),
}

# kind, label, color override, icon names
FILES = [
    ("text", "", None, ["text-x-generic", "text-plain", "text-x-readme", "application-x-zerosize"]),
    ("text", "", None, ["unknown", "application-octet-stream", "text-x-generic-template"]),
    ("pdf", "PDF", None, ["application-pdf", "application-x-pdf"]),
    ("image", "IMG", None, ["image-x-generic", "image-png", "image-jpeg", "image-gif", "image-webp",
                            "image-bmp", "image-tiff", "image-x-xcf", "image-heif", "image-avif"]),
    ("image", "SVG", "#e0559f", ["image-svg+xml", "image-svg+xml-compressed"]),
    ("audio", "", None, ["audio-x-generic", "audio-mpeg", "audio-flac", "audio-ogg", "audio-x-wav",
                         "audio-x-vorbis+ogg", "audio-mp4", "audio-x-opus+ogg", "audio-aac"]),
    ("video", "", None, ["video-x-generic", "video-mp4", "video-x-matroska", "video-webm",
                         "video-quicktime", "video-x-msvideo", "video-mpeg", "video-ogg"]),
    ("archive", "ZIP", None, ["package-x-generic", "application-zip", "application-x-7z-compressed",
                              "application-x-compressed-tar", "application-x-tar",
                              "application-x-xz-compressed-tar", "application-gzip",
                              "application-x-bzip-compressed-tar", "application-x-rar",
                              "application-vnd.rar", "application-x-archive",
                              "application-x-zstd-compressed-tar", "application-x-xz",
                              "application-x-bzip2", "application-zstd"]),
    ("package", "DEB", None, ["application-x-deb", "application-vnd.debian.binary-package"]),
    ("package", "RPM", "#c24e4e", ["application-x-rpm"]),
    ("package", "APP", "#5b6275", ["application-vnd.flatpak.ref", "application-vnd.flatpak",
                                   "application-x-appimage", "application-vnd.appimage"]),
    ("doc", "DOC", None, ["x-office-document", "application-vnd.oasis.opendocument.text",
                          "application-vnd.openxmlformats-officedocument.wordprocessingml.document",
                          "application-msword", "application-rtf", "text-rtf"]),
    ("sheet", "XLS", None, ["x-office-spreadsheet", "application-vnd.oasis.opendocument.spreadsheet",
                            "application-vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                            "application-vnd.ms-excel"]),
    ("sheet", "CSV", "#23a55a", ["text-csv", "text-tab-separated-values"]),
    ("slides", "PPT", None, ["x-office-presentation", "application-vnd.oasis.opendocument.presentation",
                             "application-vnd.openxmlformats-officedocument.presentationml.presentation",
                             "application-vnd.ms-powerpoint"]),
    ("exec", "", None, ["application-x-executable", "application-x-sharedlib",
                        "application-x-pie-executable", "application-x-object"]),
    ("exec", "EXE", "#3a73e0", ["application-x-ms-dos-executable", "application-x-msi",
                                "application-x-msdownload", "application-vnd.microsoft.portable-executable"]),
    ("iso", "ISO", None, ["application-x-cd-image", "application-x-iso9660-image",
                          "application-x-raw-disk-image"]),
    ("font", "", None, ["font-x-generic", "font-ttf", "font-otf", "application-x-font-ttf",
                        "application-x-font-otf", "font-woff", "font-woff2"]),
    ("calendar", "ICS", None, ["text-calendar", "x-office-calendar"]),
    ("database", "DB", None, ["application-x-sqlite3", "application-vnd.sqlite3", "application-sql",
                              "text-x-sql"]),
]

# Source code: a </> glyph and a colored label per language.
CODE = [
    ("PY", "#3a73e0", ["text-x-python", "text-x-python3", "application-x-python-bytecode"]),
    ("SH", "#23a55a", ["application-x-shellscript", "text-x-script", "text-x-sh",
                       "application-x-sh"]),
    ("JS", "#d4a106", ["application-javascript", "text-javascript", "application-x-javascript"]),
    ("TS", "#3178c6", ["text-x-typescript", "application-x-typescript", "text-typescript"]),
    ("HTML", "#e8622c", ["text-html", "application-xhtml+xml"]),
    ("CSS", "#7b5cf0", ["text-css", "text-x-scss", "text-x-sass"]),
    ("JSON", "#6d7489", ["application-json", "application-x-ipynb+json", "application-geo+json"]),
    ("XML", "#6d7489", ["application-xml", "text-xml"]),
    ("YAML", "#c24e4e", ["application-x-yaml", "application-yaml", "text-x-yaml"]),
    ("TOML", "#9c6b3f", ["application-toml", "text-x-toml"]),
    ("MD", "#3a4152", ["text-markdown", "text-x-markdown"]),
    ("C", "#5b6fbf", ["text-x-csrc", "text-x-c", "text-x-chdr"]),
    ("C++", "#5b6fbf", ["text-x-c++src", "text-x-c++hdr", "text-x-cpp"]),
    ("RS", "#b7410e", ["text-rust", "text-x-rust"]),
    ("GO", "#00a7d0", ["text-x-go"]),
    ("JAVA", "#e76f00", ["text-x-java", "application-x-java", "application-x-java-archive"]),
    ("KT", "#8a4fe0", ["text-x-kotlin"]),
    ("RB", "#c2272d", ["application-x-ruby", "text-x-ruby"]),
    ("PHP", "#6f7bb6", ["application-x-php", "text-x-php"]),
    ("CS", "#7b3fb7", ["text-x-csharp"]),
    ("LUA", "#2c2d72", ["text-x-lua"]),
    ("DIFF", "#23a55a", ["text-x-patch", "text-x-diff"]),
    ("MAKE", "#6d7489", ["text-x-makefile", "text-x-cmake"]),
    ("DOCKER", "#1d91e6", ["text-x-dockerfile"]),
    ("LOG", "#8d95a8", ["text-x-log"]),
]

# ---------------------------------------------------------------------- output

INHERITS = {"Aurora": "Papirus,hicolor", "Aurora-Dark": "Papirus-Dark,Papirus,hicolor"}
CONTEXTS = {"apps": "Applications", "places": "Places", "mimetypes": "MimeTypes",
            "devices": "Devices"}


def index_theme(name):
    dirs = ",".join(f"scalable/{d}" for d in CONTEXTS)
    out = [f"[Icon Theme]\nName={name}\nComment=Aurora OS icons, with Papirus for symbolic icons\n"
           f"Inherits={INHERITS[name]}\nDirectories={dirs}\n"]
    for d, ctx in CONTEXTS.items():
        out.append(f"\n[scalable/{d}]\nContext={ctx}\nSize=128\nMinSize=8\nMaxSize=512\nType=Scalable\n")
    return "".join(out)


def write_set(base, context, names, svg):
    d = os.path.join(base, "scalable", context)
    os.makedirs(d, exist_ok=True)
    first = names[0]
    target = os.path.join(d, first + ".svg")
    if os.path.islink(target):  # an alias from an earlier set: replace, don't write through
        os.remove(target)
    with open(target, "w") as f:
        f.write(svg)
    for alias in names[1:]:
        link = os.path.join(d, alias + ".svg")
        if os.path.lexists(link):
            os.remove(link)
        os.symlink(first + ".svg", link)


def generate(out):
    base = os.path.join(out, "Aurora")
    for names, (c1, c2, glyph) in APPS.items():
        write_set(base, "apps", list(names), app(c1, c2, GLYPHS[glyph]))
    for names, emblem in EMBLEMS.items():
        write_set(base, "places", list(names), folder(emblem))
    write_set(base, "places", ["user-trash", "trash-empty"], trash(False))
    write_set(base, "places", ["user-trash-full", "trash-full"], trash(True))
    for names, kind in DEVICES.items():
        write_set(base, "devices", list(names), device(kind))
    for kind, label, color, names in FILES:
        glyph, default = FT[kind]
        write_set(base, "mimetypes", names, page(glyph, label, color or default or "#8d95a8"))
    for label, color, names in CODE:
        write_set(base, "mimetypes", names, page(code_glyph(color), label, color))
    with open(os.path.join(base, "index.theme"), "w") as f:
        f.write(index_theme("Aurora"))

    dark = os.path.join(out, "Aurora-Dark")
    os.makedirs(dark, exist_ok=True)
    link = os.path.join(dark, "scalable")
    if os.path.lexists(link):
        os.remove(link)
    os.symlink("../Aurora/scalable", link)
    with open(os.path.join(dark, "index.theme"), "w") as f:
        f.write(index_theme("Aurora-Dark"))


if __name__ == "__main__":
    generate(sys.argv[1])
