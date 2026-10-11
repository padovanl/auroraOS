"""Remote commands reach the existing shell without importing its rendering code."""
import os
from pathlib import Path
import subprocess
import pytest

SCRIPT = Path(__file__).parents[2] / "desktop/bin/aurora-shell"


def test_command_without_shell_reports_missing_instance():
    result = subprocess.run(["dbus-run-session", "--", "python3", str(SCRIPT), "windows"],
                            capture_output=True, text=True, timeout=10,
                            env=dict(os.environ, AURORA_LIBDIR="/nonexistent-desktop-library"))
    assert result.returncode == 1 and "shell is not running" in result.stderr
    assert "Traceback" not in result.stderr


def test_remote_command_needs_no_desktop_imports():
    if not os.environ.get("WAYLAND_DISPLAY"):
        pytest.skip("needs the headless desktop session")
    result = subprocess.run(["python3", str(SCRIPT), "windows"],
                            capture_output=True, text=True, timeout=10,
                            env=dict(os.environ, AURORA_LIBDIR="/nonexistent-desktop-library"))
    assert result.returncode == 0, result.stderr
    assert "Traceback" not in result.stderr
