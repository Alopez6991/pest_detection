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
