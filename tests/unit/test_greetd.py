"""The greeter's greetd client against a fake greetd speaking the real wire format."""

import json
import socket
import struct
import threading

from aurora.greeter.greetd import Greetd


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
