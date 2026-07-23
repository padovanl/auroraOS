#!/usr/bin/env python3
"""Serve the Aurora OS website (docs/) locally.

Usage: tools/serve-site.py [--port 8000] [--open]

GitHub Pages publishes the same docs/ folder, so what you see here is what
visitors will see.
"""

import argparse
import functools
import http.server
import os
import webbrowser

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--bind", default="127.0.0.1")
    ap.add_argument("--open", action="store_true", help="open the site in your browser")
    args = ap.parse_args()

    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SITE)
    with http.server.ThreadingHTTPServer((args.bind, args.port), handler) as server:
        url = f"http://{args.bind}:{args.port}/"
        print(f"Serving {SITE} at {url}  (Ctrl+C to stop)")
        if args.open:
            webbrowser.open(url)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
