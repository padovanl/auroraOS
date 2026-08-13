#!/usr/bin/env python3
"""Serve the Aurora OS website (docs/) locally.

Usage: tools/serve-site.py [--port 4173] [--lan] [--open]

GitHub Pages publishes the same docs/ folder, so what you see here is what
visitors will see. By default only this computer can open it; --lan makes it
reachable from other devices on your network (phones, another PC). If the port is
taken, the next free one is used.
"""

import argparse
import errno
import functools
import http.server
import os
import socket
import sys
import webbrowser

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")


def lan_address():
    """The address other devices on the network reach this computer at."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("192.0.2.1", 9))  # no packet is sent; this only picks the route
            return s.getsockname()[0]
        except OSError:
            return socket.gethostname()


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=4173,
                    help="port to use (the next free one if it is taken)")
    ap.add_argument("--bind", default="127.0.0.1", help="address to listen on")
    ap.add_argument("--lan", action="store_true",
                    help="listen on every interface, for other devices on your network")
    ap.add_argument("--open", action="store_true", help="open the site in your browser")
    args = ap.parse_args()
    bind = "0.0.0.0" if args.lan else args.bind

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SITE)
    server = None
    for port in range(args.port, args.port + 50):
        try:
            server = http.server.ThreadingHTTPServer((bind, port), handler)
            break
        except OSError as err:
            if err.errno != errno.EADDRINUSE:
                raise
            print(f"Port {port} is used by another program, trying {port + 1}.")
    if server is None:
        sys.exit(f"No free port between {args.port} and {args.port + 49}; choose one with --port.")
    with server:
        url = f"http://{'127.0.0.1' if bind == '0.0.0.0' else bind}:{port}/"
        print(f"Serving {SITE}")
        print(f"  on this computer: {url}")
        if bind == "0.0.0.0":
            print(f"  on your network:  http://{lan_address()}:{port}/")
        print("Ctrl+C to stop.")
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
