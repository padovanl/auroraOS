"""Keep bundled MP4s small enough for normal GitHub repositories."""
import json
import os
from pathlib import Path
import subprocess
import tempfile

MAX_BYTES = 48 * 1024 ** 2


def fit_video(path):
    """Return True after reducing an oversized clip to silent Full HD H.264.

    Keep the original until a complete, size-checked output exists. Try constant
    quality first; use two-pass encoding if the content still exceeds the budget.
    Timing and frame rate are preserved.
    """
    path = Path(path)
    if path.stat().st_size <= MAX_BYTES:
        return False
    info = json.loads(subprocess.check_output([
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'json', str(path)]))
    duration = float(info['format']['duration'])
    if duration <= 0:
        raise ValueError(f'Invalid video duration: {path}')
    with tempfile.TemporaryDirectory(prefix='aurora-video-', dir=path.parent) as folder:
        output = Path(folder) / 'output.mp4'
        base = ['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y', '-threads', '2',
                '-i', str(path), '-map', '0:v:0', '-an', '-filter_threads', '1', '-vf',
                'scale=1920:1080:force_original_aspect_ratio=decrease,'
                'pad=1920:1080:(ow-iw)/2:(oh-ih)/2,setsar=1',
                '-c:v', 'libx264', '-threads', '2', '-preset', 'medium', '-pix_fmt', 'yuv420p']
        subprocess.run(base + ['-crf', '23', '-movflags', '+faststart', str(output)], check=True)
        if output.stat().st_size > MAX_BYTES:
            bitrate = max(1, int(MAX_BYTES * 0.94 * 8 / duration))
            passes = ['-b:v', str(bitrate), '-passlogfile', str(Path(folder) / 'passes')]
            subprocess.run(base + passes + ['-pass', '1', '-f', 'null', os.devnull], check=True)
            subprocess.run(base + passes + ['-pass', '2', '-movflags', '+faststart', str(output)],
                           check=True)
        if not 0 < output.stat().st_size <= MAX_BYTES:
            raise RuntimeError(f'Video still exceeds the size budget: {path}')
        output.replace(path)
    return True
