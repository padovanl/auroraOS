#!/usr/bin/env python3
"""Build seamless photo-motion loops; development dependencies: OpenCV, NumPy, ffmpeg.

Every output pixel is sampled from the original photograph. Motion fields move
its aurora, clouds, water and space textures, while landscape masks anchor rock
and shorelines. There are no drawn particles, light sprites or glow overlays.

Usage: python3 tools/animate-wallpapers.py --output branding/wallpapers/animated
       python3 tools/animate-wallpapers.py --width 960 --height 540 --output out/wallpaper-previews
"""
import argparse
import json
import math
from pathlib import Path
import subprocess
import time

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SCENES = ('northern-lights', 'wave', 'nebula', 'milky-way', 'sunrise', 'ringed-planet')
DURATION = 12
FPS = 30


def smooth(low, high, value):
    t = np.clip((value - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


def band(value, low, high, feather=.035):
    return smooth(low - feather, low + feather, value) * (1 - smooth(high - feather, high + feather, value))


def displacement(scene, x, y, phase):
    """Displacements in original photograph coordinates, with a twelve-second period."""
    dx, dy = np.zeros_like(x), np.zeros_like(y)
    if scene == 'northern-lights':
        skyline = np.interp(x, [0, .15, .3, .5, .65, .8, 1], [.47, .41, .56, .63, .58, .66, .63])
        sky = 1 - smooth(skyline - .12, skyline - .015, y)
        dx += sky * (.018 * np.sin(phase + y * 6 + x * 7) + .008 * np.sin(2 * phase - x * 10))
        dy += sky * (.024 * np.sin(phase - x * 9) + .009 * np.sin(2 * phase + x * 15 + y * 4))
        water = smooth(.80, .85, y)
        dx += water * .007 * np.sin(3 * phase - y * 48 + x * 6)
        dy += water * .005 * np.sin(2 * phase + y * 36 + x * 12)
    elif scene == 'wave':
        crest = np.interp(x, [0, .18, .4, .6, .78, 1], [.13, .12, .25, .45, .66, .72])
        water = smooth(crest - .015, crest + .08, y)
        # The breaking wave travels diagonally, with its crest rising and falling.
        dx += water * (.018 * np.sin(phase + x * 7 - y * 9) + .009 * np.sin(2 * phase + y * 19))
        dy += water * (.026 * np.sin(phase + x * 8 - y * 7) + .009 * np.sin(3 * phase + x * 12 + y * 16))
        sky = 1 - smooth(crest - .12, crest - .025, y)
        dx += sky * .006 * np.sin(phase + y * 6)
    elif scene == 'nebula':
        cx, cy = x - .53, y - .5
        radius = np.sqrt(cx * cx + cy * cy)
        swirl = .027 * np.sin(phase + radius * 7)
        dx += -cy * swirl + .010 * np.sin(phase + y * 7 + x * 4)
        dy += cx * swirl + .017 * np.sin(phase - x * 7 + y * 5)
        # Gas flows around several cores, rather than the whole photograph scaling.
        dx += .006 * np.sin(2 * phase + x * 12 - y * 8)
        dy += .008 * np.sin(2 * phase - x * 10 - y * 9)
    elif scene == 'milky-way':
        skyline = np.interp(x, [0, .15, .3, .5, .7, .85, 1], [.55, .46, .63, .67, .60, .47, .46])
        sky = 1 - smooth(skyline - .07, skyline - .005, y)
        dx += sky * (.005 * np.sin(phase) - (y - .25) * .014 * np.sin(phase))
        dy += sky * (x - .5) * .015 * np.sin(phase)
        # The lake occupies the middle of the foreground; rocks stay anchored.
        lake_top = .75 + .21 * np.abs(x - .5)
        lake_bottom = 1.05 - .8 * np.abs(x - .5)
        water = band(y, lake_top, lake_bottom, .025) * band(x, .15, .85)
        dx += water * .009 * np.sin(3 * phase - y * 44 + x * 8)
        dy += water * .010 * np.sin(2 * phase + x * 13 - y * 30)
    elif scene == 'sunrise':
        sky = 1 - smooth(.32, .48, y)
        dx += sky * .010 * np.sin(phase + y * 5)
        # Moving banks of the photographed cloud, separated from foreground rock.
        left = np.exp(-(((x - .20) / .26) ** 2 + ((y - .62) / .17) ** 2))
        right = np.exp(-(((x - .79) / .26) ** 2 + ((y - .51) / .10) ** 2))
        mist = np.maximum(left, right)
        dx += mist * .016 * np.sin(phase + y * 7)
        dy += mist * .013 * np.sin(phase + x * 10) + sky * .004 * np.sin(phase + x * 5)
    elif scene == 'ringed-planet':
        # Elliptical transport follows the rings around the planet. The planet and
        # the foreground asteroid are masked out instead of bending with the rings.
        cx, cy = x - .85, y - .39
        ring_y = cy - .32 * cx
        radius = np.sqrt((cx / .70) ** 2 + (ring_y / .39) ** 2)
        rings = band(radius, .35, 1.23, .09) * smooth(.29, .39, y)
        rings *= 1 - smooth(.62, .70, x)
        asteroid = np.exp(-(((x - .48) / .045) ** 2 + ((y - .84) / .09) ** 2))
        rings *= 1 - asteroid
        angle = .048 * np.sin(phase)
        dx += rings * (-ring_y / .39 * .70 * angle)
        dy += rings * (cx / .70 * .39 * angle + .32 * (-ring_y / .39 * .70 * angle))
    else:
        raise ValueError(scene)
    return dx, dy


class PhotoMotion:
    def __init__(self, scene, width, height):
        self.scene, self.width, self.height = scene, width, height
        self.photo = cv2.imread(str(ROOT / 'branding/wallpapers/scenes' / (scene + '.png')))
        if self.photo is None:
            raise FileNotFoundError(scene)
        self.ph, self.pw = self.photo.shape[:2]
        grid_width = 384
        grid_height = max(96, round(grid_width * height / width))
        gx, gy = np.meshgrid(np.linspace(0, width - 1, grid_width, dtype=np.float32),
                             np.linspace(0, height - 1, grid_height, dtype=np.float32))
        scale = max(width / self.pw, height / self.ph)
        self.x = (gx - width / 2) / (scale * self.pw)
        self.y = (gy - height / 2) / (scale * self.ph)

    def maps(self, phase):
        # A small orbit supplies depth; most movement comes from the local fields.
        zoom = 1.065 + .008 * math.sin(phase)
        x = self.x / zoom + .5 + .003 * math.sin(phase)
        y = self.y / zoom + .5 + .004 * math.sin(phase)
        dx, dy = displacement(self.scene, x, y, phase)
        map_x = cv2.resize(((x + dx) * self.pw).astype(np.float32), (self.width, self.height))
        map_y = cv2.resize(((y + dy) * self.ph).astype(np.float32), (self.width, self.height))
        return map_x, map_y

    def frame(self, phase):
        mx, my = self.maps(phase)
        return cv2.remap(self.photo, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)


def encode(scene, output, width, height, fps, duration):
    motion = PhotoMotion(scene, width, height)
    target = output / ('aurora-' + scene + '.mp4')
    temporary = target.with_suffix('.tmp.mp4')
    command = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-f', 'rawvideo',
               '-pixel_format', 'bgr24', '-video_size', f'{width}x{height}', '-framerate', str(fps),
               '-i', '-', '-an', '-c:v', 'libx264', '-preset', 'fast', '-threads', '2', '-crf', '18',
               '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(temporary)]
    started = time.monotonic()
    with subprocess.Popen(command, stdin=subprocess.PIPE) as encoder:
        try:
            for number in range(round(duration * fps)):
                frame = motion.frame(math.tau * number / (duration * fps))
                encoder.stdin.write(frame.tobytes())
        finally:
            encoder.stdin.close()
        if encoder.wait() != 0:
            raise RuntimeError(f'Video encoding failed: {scene}')
    temporary.replace(target)
    first, later = motion.frame(0), motion.frame(math.pi / 2)
    changed = np.abs(first.astype(np.float32) - later.astype(np.float32))
    stat = {'width': width, 'height': height, 'fps': fps, 'duration': duration,
            'mean_pixel_change': round(float(changed.mean()), 2),
            'seconds_to_render': round(time.monotonic() - started, 1)}
    cv2.imwrite(str(output / (scene + '.jpg')), first)
    print(scene, stat, flush=True)
    return stat


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / 'branding/wallpapers/animated')
    parser.add_argument('--width', type=int, default=1920)
    parser.add_argument('--height', type=int, default=1080)
    parser.add_argument('--fps', type=int, default=FPS)
    parser.add_argument('--duration', type=int, default=DURATION)
    parser.add_argument('--scene', choices=SCENES, action='append')
    args = parser.parse_args()
    if min(args.width, args.height, args.fps, args.duration) <= 0 or args.width % 2 or args.height % 2:
        parser.error('Positive dimensions, frame rate and duration required; dimensions must be even')
    cv2.setNumThreads(2)
    args.output.mkdir(parents=True, exist_ok=True)
    stats = {scene: encode(scene, args.output, args.width, args.height, args.fps, args.duration)
             for scene in args.scene or SCENES}
    (args.output / 'motion.json').write_text(json.dumps(stats, indent=2) + '\n')


if __name__ == '__main__':
    main()
