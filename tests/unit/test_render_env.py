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
