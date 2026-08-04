#!/usr/bin/env python3
"""Fail if a page in docs/ links to a local file or an on-page anchor that doesn't exist."""

import glob
import os
import re
import sys

DOCS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
bad = []
for page in glob.glob(os.path.join(DOCS, "*.html")):
    html = open(page).read()
    name = os.path.basename(page)
    for ref in re.findall(r'(?:src|href)="([^"#:]+)(?:#[^"]*)?"', html):
        if not os.path.exists(os.path.join(DOCS, ref)):
            bad.append(f"{name}: {ref}")
    for anchor in re.findall(r'href="#([^"]+)"', html):
        if anchor != "top" and f'id="{anchor}"' not in html:
            bad.append(f"{name}: #{anchor}")
print("\n".join(bad) if bad else "site links ok")
sys.exit(1 if bad else 0)
