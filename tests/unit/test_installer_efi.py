"""Bootloader failures must reach Calamares instead of reporting success."""

import importlib.util
from pathlib import Path
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize("name", ["aurora-secureboot", "aurora-efi-fallback"])
@pytest.mark.parametrize("efi,rc", [(False, 0), (True, 0), (True, 1)])
def test_bootloader_failure_is_fatal(monkeypatch, name, efi, rc):
    utils = SimpleNamespace(target_env_call=Mock(return_value=rc), debug=Mock())
    monkeypatch.setitem(sys.modules, "libcalamares", SimpleNamespace(utils=utils))
    path = (Path(__file__).resolve().parents[2] / "overlay/usr/lib/calamares/modules"
            / name / "main.py")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module.os.path, "isdir", lambda path: efi)
    result = module.run()
    if not efi:
        utils.target_env_call.assert_not_called()
        assert result is None
    elif rc:
        assert len(result) == 2
        assert "failed" in " ".join(result).lower()
    else:
        assert result is None
