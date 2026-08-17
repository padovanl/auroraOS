#!/usr/bin/env python3
"""Send expressions to tests/interact/serve.py, one after another."""

import socket
import sys

for expr in sys.argv[1:]:
    s = socket.socket(socket.AF_UNIX)
    s.connect("/tmp/aurora-interact.sock")
    s.sendall(expr.encode() + b"\n")
    data = b""
    while not data.endswith(b"\n"):
        chunk = s.recv(65536)
        if not chunk:
            break
        data += chunk
    print(f"{expr} -> {data.decode().strip()}")
    s.close()
