#!/usr/bin/env python3
"""Import the downloaded wallpaper images, retaining source credits and hashes."""
import concurrent.futures
import hashlib
import json
from pathlib import Path

import requests
from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / 'tools/wallpaper-static-catalog.json'
WORK = ROOT / 'work/downloaded-wallpapers/static-downloads'
OUT = ROOT / 'branding/wallpapers/scenes'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(entry):
    original = WORK / entry['original']
    if not original.exists():
        response = requests.get(entry['download_url'], timeout=(20, 180))
        response.raise_for_status()
        temporary = original.with_suffix('.part')
        temporary.write_bytes(response.content)
        temporary.replace(original)
    if digest(original) != entry['original_sha256']:
        raise ValueError(f"Source checksum changed: {entry['id']}")
    output = OUT / (entry['id'] + '.png')
    with Image.open(original) as image:
        image = ImageOps.exif_transpose(image).convert('RGB')
        picture = ImageOps.fit(image, tuple(entry['size']), Image.Resampling.LANCZOS,
                               centering=tuple(entry.get('centering', [.5, .5])))
        picture.save(output)
    return dict(entry, file=output.name, sha256=digest(output),
                changes='16:9 centre crop and resize, PNG conversion; no generated content')


def main():
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as executor:
        entries = list(executor.map(prepare, catalog))
    (OUT / 'sources.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n')
    credits = [f'Aurora OS — {len(entries)} additional static wallpapers',
               'Downloaded still images. Each image retains its source license.\n']
    for entry in entries:
        credits.append('\n'.join((entry['title'], 'Author: ' + entry['author'],
                                  'Source: ' + entry['source_url'],
                                  'License: ' + entry['license'] + ' — ' + entry['license_url'],
                                  'Changes: ' + entry['changes'], '')))
    (OUT / 'CREDITS.txt').write_text('\n'.join(credits))
    print(f'Imported {len(entries)} static wallpapers')


if __name__ == '__main__':
    main()
