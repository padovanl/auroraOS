"""An NTFS checkout's 0777 metadata must not become system permissions."""
from pathlib import Path
import stat
import subprocess


def test_overlay_permissions_are_independent_of_checkout(tmp_path):
    source, root = tmp_path / "overlay", tmp_path / "rootfs"
    for path, content in {"etc/app.conf": "setting=yes\n",
                          "usr/libexec/helper": "#!/bin/sh\nexit 0\n",
                          "etc/sudoers.d/aurora": "root ALL=(ALL) ALL\n"}.items():
        file = source / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)
        file.chmod(0o777)
    for directory in [source, *[p for p in source.rglob("*") if p.is_dir()]]:
        directory.chmod(0o777)
    (root / "etc/ssh").mkdir(parents=True)
    key = root / "etc/ssh/existing-private-key"
    key.write_text("existing private content")
    key.chmod(0o600)
    helper = Path(__file__).parents[2] / "build/install-overlay.sh"
    subprocess.run(["bash", str(helper), str(source), str(root)], check=True)
    mode = lambda p: stat.S_IMODE(p.stat().st_mode)
    assert mode(root / "etc") == mode(root / "usr/libexec") == 0o755
    assert mode(root / "etc/app.conf") == 0o644
    assert mode(root / "usr/libexec/helper") == 0o755
    assert mode(root / "etc/sudoers.d/aurora") == 0o440
    assert mode(key) == 0o600 and key.read_text() == "existing private content"
