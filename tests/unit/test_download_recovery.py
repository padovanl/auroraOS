"""Verified download recovery without external network or large models."""
from pathlib import Path
from types import SimpleNamespace

import pytest
from aurora.ai import download
from test_ai_and_system import FakeResponse, item_for


def test_complete_part_is_verified_and_promoted_without_a_range_request(tmp_path):
    data = b"complete download"
    destination = str(tmp_path / "model")
    Path(destination + ".part").write_bytes(data)

    def no_request(*args, **kwargs):
        pytest.fail("a complete part would trigger HTTP 416 on a range request")
    assert download.fetch(item_for(data), destination, opener=no_request) == destination
    assert Path(destination).read_bytes() == data
    assert not Path(destination + ".part").exists()


def test_existing_file_of_the_right_size_still_requires_a_valid_checksum(tmp_path):
    data = b"good data"
    destination = str(tmp_path / "model")
    Path(destination).write_bytes(b"bad! data")
    download.fetch(item_for(data), destination, opener=lambda *a, **k: FakeResponse(data))
    assert Path(destination).read_bytes() == data


def test_ignored_range_rechecks_space_before_truncating_the_partial_file(tmp_path, monkeypatch):
    data = b"0123456789"
    destination = str(tmp_path / "model")
    partial = Path(destination + ".part")
    partial.write_bytes(data[:8])
    total = 100 * 1024 ** 3
    monkeypatch.setattr(download.shutil, "disk_usage", lambda _path: SimpleNamespace(
        total=total, free=download.reserve_for(total) + 3))
    with pytest.raises(download.DownloadError, match="disk space"):
        download.fetch(item_for(data), destination, opener=lambda *a, **k: FakeResponse(data))
    assert partial.read_bytes() == data[:8] and not Path(destination).exists()


def test_short_response_keeps_its_partial_file_for_the_next_attempt(tmp_path):
    data = b"0123456789"
    destination = str(tmp_path / "model")
    with pytest.raises(download.DownloadError):
        download.fetch(item_for(data), destination,
                       opener=lambda *a, **k: FakeResponse(data[:5]))
    assert Path(destination + ".part").read_bytes() == data[:5]
    requests = []

    def resumed(request, **kwargs):
        requests.append(request.get_header("Range"))
        return FakeResponse(data[5:], status=206)
    download.fetch(item_for(data), destination, opener=resumed)
    assert requests == ["bytes=5-"] and Path(destination).read_bytes() == data
