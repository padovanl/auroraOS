"""Developer-file icons shared by Files and desktop icons.

MIME detection is inconsistent for ambiguous extensions (notably .ts and
.tsx), so the file name wins for formats whose meaning is clear in Aurora.
"""

import os

from gi.repository import Gio


EXTENSIONS = {
    ".py": "text-x-python", ".pyw": "text-x-python",
    ".js": "application-javascript", ".mjs": "application-javascript",
    ".cjs": "application-javascript", ".jsx": "application-javascript",
    ".ts": "text-x-typescript", ".tsx": "text-x-typescript",
    ".html": "text-html", ".htm": "text-html", ".css": "text-css",
    ".scss": "text-css", ".sass": "text-css",
    ".json": "application-json", ".jsonc": "application-json",
    ".ipynb": "application-json", ".yaml": "application-x-yaml",
    ".yml": "application-x-yaml", ".toml": "application-toml",
    ".md": "text-markdown", ".markdown": "text-markdown",
    ".c": "text-x-csrc", ".h": "text-x-csrc",
    ".cc": "text-x-c++src", ".cpp": "text-x-c++src",
    ".hpp": "text-x-c++src", ".rs": "text-rust", ".go": "text-x-go",
    ".java": "text-x-java", ".kt": "text-x-kotlin",
    ".rb": "application-x-ruby", ".php": "application-x-php",
    ".cs": "text-x-csharp", ".lua": "text-x-lua",
    ".sh": "application-x-shellscript", ".bash": "application-x-shellscript",
    ".sql": "application-sql", ".xml": "application-xml",
    ".diff": "text-x-patch", ".patch": "text-x-patch",
    ".vue": "text-x-vue", ".svelte": "text-x-svelte",
    ".proto": "text-x-protobuf", ".tf": "text-x-terraform",
}

SPECIAL_NAMES = {
    "dockerfile": "text-x-dockerfile", "containerfile": "text-x-dockerfile",
    "makefile": "text-x-makefile", "gnumakefile": "text-x-makefile",
    "cmakelists.txt": "text-x-makefile",
}


def icon_for(info):
    """Prefer a specific code icon, with the MIME icon as theme fallback."""
    fallback = info.get_icon() or Gio.ThemedIcon.new("text-x-generic")
    if info.get_file_type() == Gio.FileType.DIRECTORY:
        return fallback
    name = info.get_name().lower()
    preferred = SPECIAL_NAMES.get(name) or EXTENSIONS.get(os.path.splitext(name)[1])
    if not preferred:
        return fallback
    names = [preferred]
    if isinstance(fallback, Gio.ThemedIcon):
        names.extend(fallback.get_names())
    names.append("text-x-generic")
    return Gio.ThemedIcon.new_from_names(list(dict.fromkeys(names)))
