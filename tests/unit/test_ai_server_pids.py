"""A stale PID file cannot stop a different process or an entire process group."""
import io
from unittest.mock import patch
import pytest
from aurora.ai import server

@pytest.mark.parametrize('pid', [-1, 0, 1, 'damaged', 12345])
def test_unrelated_or_invalid_pid_is_not_signalled(tmp_path, monkeypatch, pid):
    path = tmp_path / 'chat.pid'
    path.write_text(str(pid))
    monkeypatch.setattr(server, '_pidfile', lambda kind: str(path))
    monkeypatch.setattr(server.components, 'server_binary', lambda: '/engine/llama-server')
    signals = []
    monkeypatch.setattr(server.os, 'kill', lambda *a: signals.append(a))
    real_open = open
    def read(path, *a, **kw):
        if str(path).startswith('/proc/'):
            return io.BytesIO(b'/usr/bin/labwc\0')
        return real_open(path, *a, **kw)
    with patch('builtins.open', read):
        assert not server.running('chat')
        server.stop('chat')
    assert signals == [] and not path.exists()


def test_server_identity_requires_its_binary_and_port(tmp_path):
    path = tmp_path / 'chat.pid'
    path.write_text('12345')
    real_open = open
    def read(path, *a, **kw):
        if str(path).startswith('/proc/'):
            return io.BytesIO(b'\0'.join([b'/engine/llama-server', b'--model', b'/model.gguf', b'--port', b'47651', b'']))
        return real_open(path, *a, **kw)
    with patch('builtins.open', read):
        assert server._owned_pid(path, ['/engine/llama-server', '--port', '47651']) == 12345
        assert server._owned_pid(path, ['/engine/llama-server', '--port', '47652']) is None
