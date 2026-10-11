"""The greeter's greetd client against a fake greetd speaking the real wire format."""

import json
import socket
import struct
import threading

import pytest

from aurora.greeter.greetd import Greetd, GreetdError


def fake_greetd(path, script):
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(path)
    srv.listen(1)
    seen = []

    def serve():
        conn, _ = srv.accept()
        for reply in script:
            (n,) = struct.unpack("=I", conn.recv(4))
            seen.append(json.loads(conn.recv(n)))
            data = json.dumps(reply).encode()
            conn.sendall(struct.pack("=I", len(data)) + data)
        conn.close()
        srv.close()
    threading.Thread(target=serve, daemon=True).start()
    return seen


def test_login_conversation(tmp_path):
    path = str(tmp_path / "greetd.sock")
    seen = fake_greetd(path, [
        {"type": "auth_message", "auth_message_type": "secret", "auth_message": "Password:"},
        {"type": "success"},
        {"type": "success"},
    ])
    g = Greetd(path)
    assert g.create_session("alice")["type"] == "auth_message"
    assert g.respond("hunter2")["type"] == "success"
    assert g.start_session(["aurora-session"])["type"] == "success"
    assert seen[0] == {"type": "create_session", "username": "alice"}
    assert seen[1] == {"type": "post_auth_message_response", "response": "hunter2"}
    assert seen[2]["cmd"] == ["aurora-session"]
    g.close()


@pytest.mark.parametrize('payload', [b'[]', b'{', b'{"type":"unknown"}'])
def test_invalid_reply_becomes_a_login_error(payload):
    client, peer = socket.socketpair()
    g = Greetd.__new__(Greetd)
    g.sock = client
    client.settimeout(.5)
    try:
        peer.sendall(struct.pack('=I', len(payload)) + payload)
        with pytest.raises(GreetdError):
            g.create_session('alice')
    finally:
        g.close()
        peer.close()


def test_oversized_reply_is_rejected_without_waiting_for_body():
    client, peer = socket.socketpair()
    g = Greetd.__new__(Greetd)
    g.sock = client
    client.settimeout(.5)
    try:
        peer.sendall(struct.pack('=I', 2 * 1024 * 1024))
        with pytest.raises(GreetdError, match='too large'):
            g.create_session('alice')
    finally:
        g.close()
        peer.close()
