"""Minimal client for the greetd IPC protocol (length-prefixed JSON over a socket)."""

import json
import os
import socket
import struct


class GreetdError(Exception):
    pass


class Greetd:
    def __init__(self, path=None):
        path = path or os.environ.get("GREETD_SOCK")
        if not path:
            raise GreetdError("GREETD_SOCK is not set")
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(30)
        try:
            self.sock.connect(path)
        except OSError:
            self.sock.close()
            raise

    def close(self):
        self.sock.close()

    def _recv_exact(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.sock.recv(n - len(buf))
            if not chunk:
                raise GreetdError("greetd closed the connection")
            buf += chunk
        return buf

    def request(self, payload):
        data = json.dumps(payload).encode()
        self.sock.sendall(struct.pack("=I", len(data)) + data)
        (length,) = struct.unpack("=I", self._recv_exact(4))
        if length > 1024 * 1024:
            raise GreetdError("greetd response is too large")
        try:
            reply = json.loads(self._recv_exact(length))
        except (ValueError, UnicodeError) as err:
            raise GreetdError("Invalid greetd response") from err
        if not isinstance(reply, dict) or reply.get("type") not in (
                "success", "error", "auth_message"):
            raise GreetdError("Invalid greetd response")
        return reply

    def create_session(self, username):
        return self.request({"type": "create_session", "username": username})

    def respond(self, response):
        return self.request({"type": "post_auth_message_response", "response": response})

    def start_session(self, cmd, env=()):
        return self.request({"type": "start_session", "cmd": cmd, "env": list(env)})

    def cancel(self):
        return self.request({"type": "cancel_session"})
