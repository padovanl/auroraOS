"""Settings must report failed mutations and SSH must work with the default firewall."""

import os
from pathlib import Path
import subprocess

import pytest

from aurora.settingsapp import util


@pytest.mark.parametrize("error", [FileNotFoundError("missing tool"),
                                  subprocess.TimeoutExpired("tool", 10)])
def test_checked_commands_report_execution_errors(monkeypatch, error):
    def fail(*args, **kwargs):
        raise error
    monkeypatch.setattr(util.subprocess, "run", fail)
    with pytest.raises(RuntimeError):
        util.run(["tool"], check=True)
    assert util.run(["tool"]) == ""


def test_checked_commands_report_exit_failure(monkeypatch):
    monkeypatch.setattr(util.subprocess, "run", lambda *a, **kw:
                        subprocess.CompletedProcess(a[0], 1, "", "invalid mode"))
    with pytest.raises(RuntimeError, match="invalid mode"):
        util.run(["wlr-randr"], check=True)


@pytest.mark.parametrize("action,start_fails,still_active,expected", [
    ("on", False, False, 0), ("on", True, False, 1),
    ("off", False, False, 0), ("off", False, True, 1)])
def test_ssh_firewall_lifecycle(tmp_path, action, start_fails, still_active, expected):
    calls = tmp_path / "calls"
    for name in ("ufw", "systemctl"):
        stub = tmp_path / name
        stub.write_text("#!/bin/sh\n"
                        'echo "' + name + ' $*" >> "$CALLS"\n'
                        'case "$1" in\n'
                        '  enable) exit "$START_FAILS";;\n'
                        '  is-active) exit "$NOT_ACTIVE";;\n'
                        'esac\nexit 0\n')
        stub.chmod(0o755)
    env = dict(os.environ, PATH=f"{tmp_path}:{os.environ['PATH']}", CALLS=str(calls),
               START_FAILS=str(int(start_fails)), NOT_ACTIVE=str(int(not still_active)))
    script = Path(__file__).parents[2] / "desktop/libexec/aurora-admin"
    result = subprocess.run(["bash", str(script), "ssh", action], env=env,
                            capture_output=True, text=True)
    assert result.returncode == expected
    lines = calls.read_text().splitlines()
    if action == "on":
        assert lines[:2] == ["ufw allow Aurora SSH", "systemctl enable --now ssh.service"]
        assert ("ufw --force delete allow Aurora SSH" in lines) == start_fails
    else:
        assert "systemctl disable --now ssh.socket" in lines
        assert ("ufw --force delete allow Aurora SSH" in lines) == (not still_active)
    assert all("OpenSSH" not in line for line in lines)
