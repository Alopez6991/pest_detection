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
example.mp4 -> example_frames/example_000.jpg  (277 frames)
  277 frames, 2.2 MB
```

### 3. What you get

The frames land in a folder **next to the video**, named after it:

```
example/
├── example.mp4
├── example_frames/          <- created for you
│   ├── example_001.jpg
│   ├── example_002.jpg
│   ├── ...
│   └── example_277.jpg
└── video_to_frames.py
```

Both the folder and the frames carry the video's name, so they stay
identifiable once they are copied somewhere else or mixed with another clip's.
Zero-padding is sized to the frame count, so the names sort correctly in a file
browser and in a shell glob.

`example_frames/` is **gitignored**. It is generated, exactly reproducible from
the video beside it, and two and a half times the size of it — so it is not committed,
and you regenerate it by running the command above.

### 4. Run it on your own video

Put the video anywhere and point the script at it. The `_frames` folder is
created beside the video, not beside the script, so nothing lands in the repo
unless the video is in the repo:

```bash
python3 example/video_to_frames.py ~/recordings/hive_01.mjpeg
#   -> ~/recordings/hive_01_frames/hive_01_001.jpg ...
```

To collect several videos' frames in one place instead, use `--outdir`:

```bash
python3 example/video_to_frames.py ~/recordings/*.mjpeg --outdir ~/datasets/raw
#   -> ~/datasets/raw/hive_01_frames/...
#      ~/datasets/raw/hive_02_frames/...
```

### 5. Options

| | |
|---|---|
| `--every N` | keep 1 frame in every N. A 60 s clip at 16 fps is ~960 frames; `--every 8` makes that 120 |
| `--format png` | lossless, roughly 10x bigger. Use for anything that will be re-encoded |
| `--quality Q` | jpg quality, 2 = best (default), 31 = worst |
| `--digits N` | fix the zero-padding width instead of sizing it to the frame count |
| `--outdir DIR` | put the `_frames` folders somewhere else |
| `--dry-run` | print what it would write, touch nothing |

```bash
python3 example/video_to_frames.py example/example.mp4 --every 10 --dry-run
```

```
example.mp4 -> example_frames/example_00.jpg  (28 frames, every 10)
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

### It names things differently from the local script

Same frames, different filenames — worth knowing if you use both:

| | folder | first frame |
|---|---|---|
| Colab | `example/` | `example_00000.png` |
| `video_to_frames.py` | `example_frames/` | `example_001.jpg` |

The notebook writes PNG, which is lossless and several times larger; the local
script defaults to JPEG and takes `--format png` if you want the same.

### Which one to use

| | |
|---|---|
| **Colab** | nothing to install, works on any machine, good for a one-off or for showing someone |
| **`video_to_frames.py`** | no upload, no session limits, handles a whole folder of videos at once, and the frames are already on the machine you will process them on |

For a few clips Colab is the quicker path. For a recording session that
produced thirty files, the local script will be less work.
