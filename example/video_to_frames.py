#!/usr/bin/env python3
"""Split a video into numbered frames.

    example/video_to_frames.py clip.mp4

        clip.mp4
        clip/
            clip_00000.png
            clip_00001.png
            ...

Folder named after the video, beside it; frames carry the video's name too, so
they stay identifiable once copied somewhere else or mixed with another clip's.

The layout matches the Colab notebook deliberately - same folder name, same
filenames, same PNG, same five digits counting from zero - so frames from
either route are interchangeable and a glob written for one works on the other.

Several at once, and every Nth frame:

    example/video_to_frames.py *.mjpeg --every 5
    example/video_to_frames.py clip.mp4 --format jpg --outdir ~/datasets

Uses ffmpeg, which is already on the system - no venv, no pip install, and it
reads the .mjpeg and .gif that OpenMV IDE records as happily as .mp4.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def need(tool: str) -> str:
    path = shutil.which(tool)
    if path is None:
        sys.exit("%s not found. On Debian/Ubuntu: sudo apt install ffmpeg" % tool)
    return path


def count_frames(video: Path) -> int | None:
    """Exact frame count, or None if the container will not say.

    -count_frames decodes the whole file, which is slow for long clips but
    exact. The fallback is duration x rate, which is an estimate - and the only
    thing this is used for is how many digits to pad to, so an estimate that is
    out by one frame costs nothing.
    """
    try:
        out = subprocess.run(
            [need("ffprobe"), "-v", "error", "-count_frames",
             "-select_streams", "v:0",
             "-show_entries", "stream=nb_read_frames",
             "-of", "default=nokey=1:noprint_wrappers=1", str(video)],
            capture_output=True, text=True, timeout=300)
        n = out.stdout.strip()
        return int(n) if n.isdigit() else None
    except Exception:
        return None


def extract(video: Path, outdir: Path | None, every: int,
            fmt: str, quality: int, digits: int | None, dry: bool) -> int:
    if not video.is_file():
        print("  skip %s: not a file" % video)
        return 0

    stem = video.stem
    # Folder named after the video, no suffix - matching the Colab notebook.
    dest = (outdir or video.parent) / stem

    total = count_frames(video)
    kept = None if total is None else -(-total // every)   # ceil
    width = digits

    pattern = str(dest / ("%s_%%0%dd.%s" % (stem, width, fmt)))
    print("%s -> %s/%s_%s.%s  (%s frame%s%s)"
          % (video.name, dest.name, stem, "0" * width, fmt,
             kept if kept is not None else "?",
             "" if kept == 1 else "s",
             "" if every == 1 else ", every %d" % every))
    if dry:
        return 0

    dest.mkdir(parents=True, exist_ok=True)

    cmd = [need("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(video)]
    if every > 1:
        # select keeps 1 in every N; vsync 0 stops ffmpeg duplicating frames to
        # hold the original timebase, which would undo the thinning.
        cmd += ["-vf", "select=not(mod(n\\,%d))" % every, "-vsync", "0"]
    # ffmpeg's image2 muxer counts from 1; the notebook counts from 0.
    cmd += ["-start_number", "0"]
    if fmt in ("jpg", "jpeg"):
        cmd += ["-q:v", str(quality)]      # 2 = near-lossless, 31 = worst
    cmd += [pattern]

    r = subprocess.run(cmd, capture_output=True, text=True)
    written = sorted(dest.glob("%s_*.%s" % (stem, fmt)))
    if r.returncode != 0 or not written:
        if r.returncode != 0:
            print("  ffmpeg failed: %s"
                  % (r.stderr.strip().splitlines() or ["?"])[-1])
        else:
            print("  no frames written")
        # Do not leave an empty _frames folder behind to be mistaken for a
        # successful run later. Only if we created it and nothing is in it.
        try:
            dest.rmdir()
        except OSError:
            pass
        return 0

    size = sum(f.stat().st_size for f in written)
    print("  %d frames, %.1f MB" % (len(written), size / 1e6))
    return len(written)


def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video", nargs="+", help="video file(s)")
    ap.add_argument("--every", type=int, default=1, metavar="N",
                    help="keep 1 frame in every N (default 1 = all)")
    ap.add_argument("--format", default="png", choices=("jpg", "png"),
                    help="png matches the notebook and is lossless; "
                         "jpg is ~10x smaller (default png)")
    ap.add_argument("--quality", type=int, default=2, metavar="Q",
                    help="jpg quality, 2 = best, 31 = worst (default 2)")
    ap.add_argument("--digits", type=int, default=5, metavar="N",
                    help="zero-padding width (default 5, as the notebook)")
    ap.add_argument("--outdir", type=Path, default=None,
                    help="where the frame folders go (default: beside each video)")
    ap.add_argument("--dry-run", action="store_true", help="show, do not write")
    a = ap.parse_args()

    if a.every < 1:
        sys.exit("--every must be 1 or more")

    total = 0
    for v in a.video:
        total += extract(Path(v).expanduser(), a.outdir, a.every,
                         a.format, a.quality, a.digits, a.dry_run)
    if len(a.video) > 1:
        print("\n%d frames from %d videos" % (total, len(a.video)))


if __name__ == "__main__":
    main()
