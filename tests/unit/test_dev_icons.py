"""Source file icons stay meaningful even when MIME guessing is ambiguous."""

import pytest
from gi.repository import Gio

from aurora.files.icons import icon_for


@pytest.mark.parametrize("name,expected", [
    ("main.py", "text-x-python"), ("app.js", "application-javascript"),
    ("index.html", "text-html"), ("style.css", "text-css"),
    ("app.ts", "text-x-typescript"), ("component.tsx", "text-x-typescript"),
    ("view.jsx", "application-javascript"), ("App.vue", "text-x-vue"),
    ("App.svelte", "text-x-svelte"), ("schema.proto", "text-x-protobuf"),
    ("main.tf", "text-x-terraform"), ("Dockerfile", "text-x-dockerfile"),
])
def test_code_icon_overrides_ambiguous_mime(name, expected):
    info = Gio.FileInfo()
    info.set_name(name)
    info.set_file_type(Gio.FileType.REGULAR)
    info.set_icon(Gio.ThemedIcon.new("application-octet-stream"))
    assert icon_for(info).get_names()[0] == expected


def test_directory_uses_folder_icon():
    info = Gio.FileInfo()
    info.set_name("project.py")
    info.set_file_type(Gio.FileType.DIRECTORY)
    info.set_icon(Gio.ThemedIcon.new("folder"))
    assert icon_for(info).get_names()[0] == "folder"
