"""Software VM displays must not run Wayfire's GLES path by default."""

import os
import subprocess
from pathlib import Path

import pytest


RENDER_ENV = Path(__file__).resolve().parents[2] / "desktop/libexec/aurora-render-env"


@pytest.mark.parametrize(
    ("vendor", "render_node", "hyperv"),
    [("0x1414", False, True), ("0x1414", True, True),
     ("0x1af4", False, False), ("0x1002", True, False)],
)
def test_renderer_selection(tmp_path, vendor, render_node, hyperv):
    drm = tmp_path / "sys" / "card0" / "device"
    drm.mkdir(parents=True)
    (drm / "vendor").write_text(vendor)
    dri = tmp_path / "dev"
    dri.mkdir()
    if render_node:
        (dri / "renderD128").touch()
    env = os.environ.copy()
    for name in ("WLR_RENDERER", "GSK_RENDERER", "AURORA_HYPERV_SOFTWARE"):
        env.pop(name, None)
    env.update(AURORA_DRM_SYSFS=str(drm.parent.parent),
               AURORA_DRI_DEVICES=str(dri))
    result = subprocess.run(
        ["/bin/sh", "-c",
         '. "$1"; printf "%s|%s|%s" "${WLR_RENDERER:-}" "${GSK_RENDERER:-}" '
         '"${AURORA_HYPERV_SOFTWARE:-}"',
         "sh", str(RENDER_ENV)],
        env=env, check=True, text=True, capture_output=True)
    expected = "pixman|cairo" if vendor != "0x1002" or not render_node else "|"
    assert result.stdout == expected + ("|1" if hyperv else "|")


@pytest.mark.parametrize(("hyperv", "choice"), [(False, None), (True, None), (True, "labwc")])
def test_compositor_on_software_display(tmp_path, hyperv, choice):
    """Wayfire on software displays, with synchronous llvmpipe on Hyper-V (its
    driver copies each frame when it is committed); "labwc" in
    ~/.config/aurora/compositor picks labwc."""
    script = Path(__file__).resolve().parents[2] / "desktop/bin/aurora-session"
    session = tmp_path / "session"
    session.write_text(script.read_text().replace(
        ". /usr/libexec/aurora-render-env", ":"))
    session.chmod(0o755)
    home = tmp_path / "home"
    binaries = home / ".local/bin"
    binaries.mkdir(parents=True)
    config = home / ".config/labwc"
    config.mkdir(parents=True)
    (config / "rc.xml").touch()
    gtk = home / ".config/gtk-4.0"
    gtk.mkdir(parents=True)
    (gtk / "gtk.css").touch()
    if choice:
        (home / ".config/aurora").mkdir(parents=True)
        (home / ".config/aurora/compositor").write_text(choice + "\n")
    for command, body in (
        ("labwc", "#!/bin/sh\nprintf 'labwc|%s|%s|%s' \"$*\" \"$AURORA_COMPOSITOR\" "
         "\"$WLR_RENDERER\" > \"$AURORA_TEST_LOG\"\n"),
        ("aurora-wayfire-config", "#!/bin/sh\necho /tmp/test-wayfire.ini\n"),
        ("wayfire", "#!/bin/sh\nprintf '%s|%s|%s|%s|%s' \"$*\" "
         "\"$AURORA_COMPOSITOR\" \"${WLR_DRM_NO_MODIFIERS:-}\" "
         "\"$WLR_RENDERER\" \"${LP_NUM_THREADS:-}\" > \"$AURORA_TEST_LOG\"\n"),
    ):
        executable = binaries / command
        executable.write_text(body)
        executable.chmod(0o755)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    log = tmp_path / "compositor-args"
    env = os.environ.copy()
    env.pop("LP_NUM_THREADS", None)
    env.update(HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
               XDG_STATE_HOME=str(tmp_path / "state"),
               AURORA_TEST_LOG=str(log), WLR_RENDERER="pixman",
               AURORA_HYPERV_SOFTWARE="1" if hyperv else "0")
    subprocess.run([str(session), "wayfire"], env=env, check=True, timeout=10)
    if choice == "labwc":
        started, _args, compositor, renderer = log.read_text().split("|")
        assert (started, compositor, renderer) == ("labwc", "labwc", "pixman")
        return
    args, compositor, modifiers, renderer, threads = log.read_text().split("|")
    assert args.startswith("-R -c ") if hyperv else args.startswith("-c ")
    assert compositor == "wayfire"
    assert modifiers == ("1" if hyperv else "")
    assert renderer == "gles2"
    assert threads == ("0" if hyperv else "")
