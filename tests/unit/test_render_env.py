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
               AURORA_DRI_DEVICES=str(dri),
               AURORA_DMI_ROOT=str(tmp_path / "dmi"))
    result = subprocess.run(
        ["/bin/sh", "-c",
         '. "$1"; printf "%s|%s|%s" "${WLR_RENDERER:-}" "${GSK_RENDERER:-}" '
         '"${AURORA_HYPERV_SOFTWARE:-}"',
         "sh", str(RENDER_ENV)],
        env=env, check=True, text=True, capture_output=True)
    expected = "pixman|cairo" if vendor != "0x1002" or not render_node else "|"
    assert result.stdout == expected + ("|1" if hyperv else "|")


def test_hyperv_vmbus_without_pci_vendor(tmp_path):
    dmi = tmp_path / "dmi"
    dmi.mkdir()
    (dmi / "sys_vendor").write_text("Microsoft Corporation\n")
    (dmi / "product_name").write_text("Virtual Machine\n")
    dri = tmp_path / "dri"
    dri.mkdir()
    env = os.environ.copy()
    for name in ("WLR_RENDERER", "GSK_RENDERER", "AURORA_HYPERV_SOFTWARE"):
        env.pop(name, None)
    env.update(AURORA_DRM_SYSFS=str(tmp_path / "empty"),
               AURORA_DRI_DEVICES=str(dri), AURORA_DMI_ROOT=str(dmi))
    result = subprocess.run(
        ["/bin/sh", "-c", '. "$1"; printf "%s|%s|%s" "$WLR_RENDERER" '
         '"$GSK_RENDERER" "$AURORA_HYPERV_SOFTWARE"', "sh", str(RENDER_ENV)],
        env=env, check=True, text=True, capture_output=True)
    assert result.stdout == "pixman|cairo|1"


@pytest.mark.parametrize("hyperv", [False, True])
def test_wayfire_is_launched_on_software_display(tmp_path, hyperv):
    """Hyper-V changes Wayfire's redraw mode, never preemptively starts labwc."""
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
    for command, body in (
        ("aurora-wayfire-config", "#!/bin/sh\necho /tmp/test-wayfire.ini\n"),
        ("wayfire", "#!/bin/sh\nprintf '%s|%s|%s|%s|%s' \"$*\" "
         "\"$AURORA_COMPOSITOR\" \"${WLR_DRM_NO_MODIFIERS:-}\" "
         "\"$WLR_RENDERER\" \"${WLR_DRM_NO_ATOMIC:-}\" > \"$AURORA_TEST_LOG\"\n"),
    ):
        executable = binaries / command
        executable.write_text(body)
        executable.chmod(0o755)
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    log = tmp_path / "wayfire-args"
    env = os.environ.copy()
    env.update(HOME=str(home), XDG_RUNTIME_DIR=str(runtime),
               XDG_STATE_HOME=str(tmp_path / "state"),
               AURORA_TEST_LOG=str(log), WLR_RENDERER="pixman",
               AURORA_HYPERV_SOFTWARE="1" if hyperv else "0")
    subprocess.run([str(session), "wayfire"], env=env, check=True, timeout=10)
    args, compositor, modifiers, renderer, legacy = log.read_text().split("|")
    assert args.startswith("-R -c ") if hyperv else args.startswith("-c ")
    assert compositor == "wayfire"
    assert modifiers == ("1" if hyperv else "")
    assert renderer == "gles2"
    assert legacy == ("1" if hyperv else "")
