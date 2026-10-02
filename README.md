# pest_detection

Sensor tooling for an **OpenMV AE3** (Alif Ensemble E3: dual NPU, PAG7936 1 MP
global-shutter sensor, VL53L8CX 8x8 time-of-flight, LSM6DSM IMU).

## record_all.py

A viewfinder that puts the camera, the ToF grid and the IMU on one timeline, so
"why did it do that at 4.2 seconds" is one recording rather than three logs.

Open it in the OpenMV IDE and press play. The Frame Buffer shows live video
with the 8x8 depth map in the corner; the console carries the numbers:

```
fps 15.0 (work 22.9) | d  1.795  fresh 64 stale  0 | a +0.02 -0.01 +0.99 g | ...
```

To record, use the **Record** button at the top right of the Frame Buffer pane.
The file lands on the PC, so length is limited by disk rather than the board's
8 MB flash.

### Switches

Every sensor is a boolean at the top. Each one costs frame rate, so turn off
what you are not looking at:

| | |
|---|---|
| `CAMERA` | live video; off = headless logger |
| `TOF` | the 8x8 depth sensor |
| `IMU` | accelerometer and gyro |
| `SHOW_DEPTH_MAP` | draw the grid on the frame |
| `SHOW_DEPTH_TEXT` | median distance — the only text on the frame |

`FPS` caps the loop. It is a cap, not a target: asking for 30 on a sensor
managing 16 gets 16. Lowering it can improve the image, since the driver may
lengthen sensor exposure to fill the longer frame.

### Two things the console tells you

**`fps N (work M)`** — `fps` is the real loop rate, `work` is what it would run
at with the cap removed. The gap is your headroom. `clock.fps()` reports only
the second, which is why a working `FPS` cap can look like it does nothing.

**`fresh N stale M`** — ToF zones on this sensor freeze and re-serve their last
value, bit-identical, for dozens of frames; 37 of 64 at once has been measured.
An object passing close writes its distance into half the grid and a median
over the raw grid stays latched there long after it has gone (1.06 m reported
against a wall at 3.05 m). The median here uses only zones that are updating.
Watch `fresh`: it collapses as returns weaken, so a reading backed by 9 zones
and one backed by 40 are not the same claim.

## example/video_to_frames.py

Splits a video into numbered frames. There is a worked example in `example/`
you can run as-is.

### 1. Check you have ffmpeg

```bash
ffmpeg -version
```

Nothing to install if that prints a version. If it does not:

```bash
sudo apt install ffmpeg          # Debian / Ubuntu
brew install ffmpeg              # macOS
```

There is no venv and no `pip install` — the script shells out to ffmpeg, which
also means it reads the `.mjpeg` and `.gif` that OpenMV IDE records as happily
as `.mp4`.

### 2. Run the worked example

From the **root of the repo**:

```bash
python3 example/video_to_frames.py example/example.mp4
```

```
example.mp4 -> example/example_00000.png  (277 frames)
  277 frames, 26.8 MB
```

### 3. What you get

The frames land in a folder **next to the video**, named after it:

```
example/
├── example.mp4
├── example/                 <- created for you
│   ├── example_00000.png
│   ├── example_00001.png
│   ├── ...
│   └── example_00276.png
└── video_to_frames.py
```

Both the folder and the frames carry the video's name, so they stay
identifiable once they are copied somewhere else or mixed with another clip's.

**This is the same layout the Colab notebook produces** — same folder name,
same filenames, same PNG, same five digits counting from zero — so frames from
either route are interchangeable and a glob written for one works on the other.

The generated folder is **gitignored**. It is exactly reproducible from the
video beside it, and far larger: `example.mp4` is 896 KB, its 277 PNG frames
are 27 MB. Regenerate it by running the command above.

### 4. Run it on your own video

Put the video anywhere and point the script at it. The frame folder is
created beside the video, not beside the script, so nothing lands in the repo
unless the video is in the repo:

```bash
python3 example/video_to_frames.py ~/recordings/hive_01.mjpeg
#   -> ~/recordings/hive_01/hive_01_00000.png ...
```

To collect several videos' frames in one place instead, use `--outdir`:

```bash
python3 example/video_to_frames.py ~/recordings/*.mjpeg --outdir ~/datasets/raw
#   -> ~/datasets/raw/hive_01/...
#      ~/datasets/raw/hive_02/...
```

### 5. Options

| | |
|---|---|
| `--every N` | keep 1 frame in every N. A 60 s clip at 16 fps is ~960 frames; `--every 8` makes that 120 |
| `--format jpg` | ~10x smaller than the default PNG. 277 frames: 2.2 MB as jpg, 27 MB as png |
| `--quality Q` | jpg quality, 2 = best (default), 31 = worst |
| `--digits N` | zero-padding width (default 5, as the notebook) |
| `--outdir DIR` | put the frame folders somewhere else |
| `--dry-run` | print what it would write, touch nothing |

```bash
python3 example/video_to_frames.py example/example.mp4 --every 10 --dry-run
```

```
example.mp4 -> example/example_00000.png  (28 frames, every 10)
```

Start with `--dry-run` on a long recording: it tells you the frame count and
the filenames before anything is written.

## Running it in the browser instead

There is a Colab version — **[video extractor code](https://colab.research.google.com/drive/10X0riZ2-m8GeExDOb1mULzG68ReJNGag?usp=sharing)** — if you would rather not install anything, or you are on a machine where you cannot. Nothing runs on your own computer.

### Make your own copy first

The link is read-only. Editing or running it needs a copy in your own Drive:

1. Open the **[video extractor code](https://colab.research.google.com/drive/10X0riZ2-m8GeExDOb1mULzG68ReJNGag?usp=sharing)** link
2. Sign in to a Google account if you are not already
3. **File → Save a copy in Drive**
4. A new tab opens titled *Copy of ...* — that one is yours, and it lands in
   `My Drive/Colab Notebooks/`

Work in the copy. Changes to it are private to you and cannot affect the
original, so there is nothing to break.

### Run the three cells in order

Use the **▶** button on each, or `Ctrl+F9` to run them all. The first run warns
that the notebook was not written by you, which is expected.

1. **Install OpenCV** — `pip install opencv-python`. Takes a few seconds, or
   says it is already satisfied
2. **Upload your video** — a **Choose Files** button appears. Pick the video
   from your own machine and wait for `100% done`; a large file over a slow
   connection is the slowest part of the whole process
3. **Extract frames** — reads the video, makes a folder named after it, and
   writes every frame as a `.png`

```
Created directory: example/
Successfully extracted 277 frames to the 'example' directory.
```

### Download them before you close the tab

The frames are in Colab's session storage, **not on your computer**, and all of
it is deleted when the session ends.

Open the **folder icon** in the left sidebar, find the folder it just made,
then the **⋮** menu beside it → **Download**. Colab zips it first, so a few
hundred PNGs take a moment.

### It produces the same layout as the local script

Same folder name, same filenames, same PNG, same five digits from zero. Frames
from either route are interchangeable, and a glob written for one works on the
other.

### Which one to use

| | |
|---|---|
| **Colab** | nothing to install, works on any machine, good for a one-off or for showing someone |
| **`video_to_frames.py`** | no upload, no session limits, handles a whole folder of videos at once, and the frames are already on the machine you will process them on |

For a few clips Colab is the quicker path. For a recording session that
produced thirty files, the local script will be less work.
