#!/usr/bin/env python3
"""Import downloaded animations from wallpaper-video-catalog.json.

Requires requests, ffmpeg/ffprobe and yt-dlp for the CC0 YouTube source.
Originals stay in work. No generated effects or watermark removal.
"""
import argparse
import concurrent.futures
import hashlib
import json
import subprocess
import time
import math
from pathlib import Path

import requests
from wallpaper_video_limits import fit_video

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'work/downloaded-wallpapers'
OUT = ROOT / 'branding/wallpapers/animated'
CATALOG = ROOT / 'tools/wallpaper-video-catalog.json'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def motion_copy(entry, original, start, length, width=1920, height=1080):
    """Interpolate overlapping sections in parallel at the source resolution."""
    recipe = entry['recipe']
    speed = recipe['slowdown']
    settings = json.dumps([entry['original_sha256'], start, length, recipe, width, height], sort_keys=True)
    cache = WORK / 'motion-cache' / entry['id'] / hashlib.sha256(settings.encode()).hexdigest()[:16]
    cache.mkdir(parents=True, exist_ok=True)
    result = cache / 'motion.mp4'
    if result.exists():
        return result
    total_frames = math.floor(length * speed * 30)
    count = 4

    def section(index):
        first = total_frames * index // count
        last = total_frames * (index + 1) // count
        begin = first / 30 / speed
        end = last / 30 / speed
        left, right = max(0, begin - .25), min(length, end + .25)
        clip = cache / f'{index}.mp4'
        if clip.exists():
            return clip
        filters = (f'scale={width}:{height}:force_original_aspect_ratio=increase,'
                   f'crop={width}:{height},setsar=1,tpad=stop_mode=clone:stop_duration=0.15,'
                   f'setpts={speed}*(PTS-STARTPTS),'
                   'minterpolate=fps=30:mi_mode=mci:mc_mode=obmc:'
                   'me_mode=bidir:me=hexbs:mb_size=16:search_param=4:vsbmc=0:scd=none,'
                   f'trim=start={round((begin-left)*speed, 8)},setpts=PTS-STARTPTS')
        temporary = clip.with_suffix('.tmp.mp4')
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-threads', '2', '-ss', str(start + left), '-t', str(right - left),
                        '-i', str(original), '-filter_threads', '1', '-vf', filters,
                        '-frames:v', str(last - first), '-an', '-pix_fmt', 'yuv420p',
                        '-c:v', 'libx264', '-threads', '2', '-preset', 'veryfast', '-crf', '18',
                        str(temporary)], check=True)
        temporary.replace(clip)
        print(f"Motion: {entry['title']} section {index + 1}/{count}", flush=True)
        return clip

    with concurrent.futures.ThreadPoolExecutor(max_workers=count) as executor:
        clips = list(executor.map(section, range(count)))
    listing = cache / 'concat.txt'
    listing.write_text(''.join(f"file '{clip.name}'\n" for clip in clips))
    temporary = result.with_suffix('.tmp.mp4')
    subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'concat',
                    '-safe', '1', '-i', str(listing), '-an', '-c:v', 'copy',
                    str(temporary)], check=True)
    temporary.replace(result)
    return result


def prepare(entry, force=False):
    original = WORK / entry['original']
    if not original.exists():
        if not entry.get('download_url'):
            raise FileNotFoundError(f'Restore the user-provided source to {original}')
        if entry.get('download_format'):
            subprocess.run(['yt-dlp', '--no-playlist', '-f', entry['download_format'],
                            '-o', str(original), entry['download_url']], check=True)
        else:
            temporary = original.with_suffix(original.suffix + '.part')
            for attempt in range(4):
                with requests.get(entry['download_url'], stream=True, timeout=(20, 180),
                                  headers={'User-Agent': 'AuroraOS-WallpaperImporter/0.1 (https://github.com/padovanl/auroraOS)'}) as response:
                    if response.status_code == 429 and attempt < 3:
                        retry = response.headers.get('Retry-After', '60')
                        delay = int(retry) if retry.isdigit() else 60
                        print(f"Rate limit: waiting {delay}s for {entry['id']}", flush=True)
                        response.close()
                        time.sleep(delay)
                        continue
                    response.raise_for_status()
                    with temporary.open('wb') as output:
                        for chunk in response.iter_content(1024 * 1024):
                            output.write(chunk)
                    break
            temporary.replace(original)
    checksum = digest(original)
    if entry['original_sha256'] is None:
        entry['original_sha256'] = checksum
    if checksum != entry['original_sha256']:
        raise ValueError(f'Source checksum changed: {original}')
    info = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(original)]))
    source = next(stream for stream in info['streams'] if stream['codec_type'] == 'video')
    # Preserve real UHD sources; never enlarge a Full HD source to claim 4K.
    width, height = (3840, 2160) if source['width'] >= 3840 and source['height'] >= 2160 else (1920, 1080)
    recipe = entry['recipe']
    if recipe.get('fullhd_export'):
        width, height = 1920, 1080
    full_duration = float(info['format']['duration'])
    length = min(recipe['length'] or full_duration, full_duration - recipe['start'])
    start = recipe['start']
    if recipe.get('legacy'):
        start = max(0, (full_duration - length) / 2)
    duration = length * recipe['slowdown']
    video, poster = (OUT / (entry['id'] + ext) for ext in ('.mp4', '.png'))
    if video.exists() and not force:
        existing = json.loads(subprocess.check_output([
            'ffprobe', '-v', 'error', '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height', '-of', 'json', str(video)]))['streams'][0]
        force = (existing['width'], existing['height']) != (width, height)
    if force or not video.exists():
        # Optical flow supplies intermediate frames for clips that visibly
        # stutter when slowed. Other sources retain their frame blending.
        if recipe.get('interpolation') == 'motion':
            input_video = motion_copy(entry, original, start, length, width, height)
            input_start, input_length, timing = 0, duration, 1
            frames = 'fps=30'
        else:
            input_video = original
            input_start, input_length, timing = start, length, recipe['slowdown']
            frames = ('minterpolate=fps=30:mi_mode=blend:scd=none'
                      if recipe.get('frame_blending', True) else 'fps=30')
        base = (f"trim=duration={input_length},setpts={timing}*(PTS-STARTPTS),"
                f'scale={width}:{height}:force_original_aspect_ratio=increase,'
                f'crop={width}:{height},setsar=1,'
                f'{frames},format=yuv420p,settb=AVTB')
        if recipe['native_loop']:
            filters = base + '[out]'
        else:
            fade = 1 if recipe.get('legacy') else 2
            filters = (base + ',split=2[start][rest];'
                       f'[start]trim=duration={fade},setpts=PTS-STARTPTS[head];'
                       f'[rest]trim=start={fade},setpts=PTS-STARTPTS[body];'
                       f'[body][head]xfade=transition=fade:duration={fade}:'
                       f'offset={duration-2*fade}[out]')
        temporary = video.with_suffix('.tmp.mp4')
        unchanged = (recipe['native_loop'] and recipe['slowdown'] == 1 and start == 0
                     and length == full_duration and source['codec_name'] == 'h264'
                     and source.get('pix_fmt') == 'yuv420p'
                     and source['width'] == width and source['height'] == height
                     and source.get('avg_frame_rate') == '30/1')
        command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-threads', '2', '-ss', str(input_start), '-t', str(input_length), '-i', str(input_video),
                        '-filter_complex_threads', '1', '-filter_complex', filters,
                        '-map', '[out]', '-an', '-pix_fmt', 'yuv420p',
                        '-c:v', 'libx264', '-threads', '2',
                        '-preset', 'veryfast', '-crf', '22', '-movflags', '+faststart',
                        '-t', str(duration if recipe['native_loop'] else duration - fade),
                        str(temporary)]
        if unchanged:
            command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-i', str(original),
                       '-map', '0:v:0', '-an', '-c:v', 'copy', '-movflags', '+faststart', str(temporary)]
        subprocess.run(command, check=True)
        temporary.replace(video)
    compact = fit_video(video)
    if compact:
        width, height = 1920, 1080
        recipe['fullhd_export'] = True
    if force or compact or not poster.exists():
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-threads', '1', '-ss', '2', '-i', str(video), '-frames:v', '1',
                        '-update', '1', str(poster)], check=True)
    result = dict(entry, file=video.name, poster=poster.name, sha256=digest(video))
    result['width'], result['height'] = width, height
    result['source_width'], result['source_height'] = source['width'], source['height']
    result['changes'] = (f'Silent H.264 conversion, {width}x{height} centre crop, 30 fps, '
                         f"{recipe['slowdown']}x slower, poster extraction"
                         + (f"; excerpt with a {1 if recipe.get('legacy') else 2}-second loop dissolve"
                            if not recipe['native_loop'] else '; complete source loop'))
    if recipe.get('interpolation') == 'motion':
        result['changes'] += '; optical-flow frame interpolation'
    if recipe.get('fullhd_export'):
        result['changes'] += '; Full HD export kept below 48 MiB for GitHub'
    print(f"Ready: {entry['title']} ({video.stat().st_size/1024**2:.1f} MiB)", flush=True)
    return result


def main():
    global OUT, CATALOG
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true', help='Rebuild existing clips')
    parser.add_argument('--rebuild', action='append', default=[], metavar='ID',
                        help='Rebuild a selected clip (repeat for multiple clips)')
    parser.add_argument('--catalog', type=Path, default=CATALOG)
    parser.add_argument('--output', type=Path, default=OUT)
    parser.add_argument('--jobs', type=int, default=2, choices=range(1, 5),
                        help='Number of simultaneous imports (default: 2)')
    args = parser.parse_args()
    CATALOG, OUT = args.catalog.resolve(), args.output.resolve()
    WORK.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    catalog = json.loads(CATALOG.read_text())
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as executor:
        entries = list(executor.map(
            lambda item: prepare(item, args.force or item['id'] in args.rebuild), catalog))
    # Importing never deletes existing wallpapers. Selection is user controlled.
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + '\n')
    (OUT / 'sources.json').write_text(json.dumps(entries, ensure_ascii=False, indent=2) + '\n')
    credits = [f'Aurora OS — {len(entries)} animated wallpapers\n',
               'Downloaded animations selected for Aurora OS.',
               'Videos and posters retain the source licenses below.',
               'CC BY-SA adaptations are distributed under the same version of CC BY-SA.',
               'Original audio removed. No endorsement by the authors is implied.\n']
    for entry in entries:
        credits.append('\n'.join((entry['title'], 'Author: ' + entry['author'],
                                  'Source: ' + entry['source_url'],
                                  'License: ' + entry['license'] + ' — ' + entry['license_url'],
                                  'Changes: ' + entry['changes'], '')))
    (OUT / 'CREDITS.txt').write_text('\n'.join(credits))


if __name__ == '__main__':
    main()
