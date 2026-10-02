# OpenMV AE3 viewfinder: RGB video, the 8x8 ToF grid, and the IMU.
#
# Runs on the board. Open it in the OpenMV IDE and press play; the Frame Buffer
# shows live video with the depth map drawn in the corner, and the console
# carries the numbers.
#
# Every sensor is a switch at the top. Turn off what you are not looking at:
# each one costs frame rate, and a quiet console is easier to read than a busy
# one. With CAMERA off it is a headless logger.
#
# THE ONLY TEXT ON THE VIDEO IS THE MEDIAN DEPTH. Everything else goes to the
# console, so the recorded frames stay close to raw camera output - though the
# depth map in the corner is still burned in, so set SHOW_DEPTH_MAP = False if
# the footage is going to a detector or any other image pipeline.
#
# To record: run, then Record (top right of the Frame Buffer pane), pick a
# filename, click again to stop. The file lands on the PC, not the board.

import time

# ==========================================================================
# SWITCHES
# ==========================================================================

CAMERA = True             # live video. Off = headless: console only, no frames
TOF = True                # 8x8 depth sensor
IMU = True                # accelerometer + gyro

SHOW_DEPTH_MAP = True     # draw the 8x8 grid on the frame   (needs CAMERA+TOF)
SHOW_DEPTH_TEXT = True    # the median distance, the ONLY text on the frame

# ==========================================================================
# SETTINGS
# ==========================================================================

# None = auto exposure. A number locks it, in microseconds:
#   1000-5000 bright | 10000-30000 dim | 30000-100000 dark room with a torch
# Lock it when comparing two takes; leave it auto when the footage is meant to
# predict flight behaviour. Capped by frame rate: ~66000 us at 15 fps.
EXPOSURE_US = None
GAIN_DB = None

# A ToF read blocks for up to READ_TIMEOUT_MS and comes off the frame rate. The
# sensor only runs ~15 Hz anyway, so reading every other frame costs nothing.
TOF_EVERY = 2
READ_TIMEOUT_MS = 100     # the module default; 50 is under the ~66 ms frame

DEPTH_SCALE = 8           # pixels per zone: 8x8 zones -> 64x64 overlay
DEPTH_RANGE_MM = (0, 4000)

# Zones on this sensor FREEZE: one stops being measured and keeps re-serving
# its last value, bit-identical, for dozens of frames. Measured on an AE3: 37
# of 64 zones stale at once. Whatever was in front of the sensor when a zone
# froze is what it keeps reporting, so an object passing at 10 cm writes
# ~100 mm into half the grid and a median over the raw grid stays latched there
# long after the object has gone - 1.06 m reported against a wall at 3.05 m.
#
# A stale zone is directly observable: its value does not change. Real zones
# jitter by centimetres every frame, so a bit-identical repeat is not a
# measurement and can be dropped without knowing why it froze.
#
# The MAP shows the raw grid, because frozen zones are what you want to SEE
# when diagnosing. The MEDIAN uses only zones that are updating, and both
# counts are on the console line.
STALE_AFTER = 3
MIN_VALID_MM = 40
MAX_VALID_MM = 4500

# Frame rate cap. None = run as fast as the hardware manages.
#
#   CAMERA on   passed to csi.framerate(), which drops frames to hold the rate
#               at or below it, and is also enforced in software as a backstop
#   CAMERA off  the software pacing is all there is, so None falls back to
#               HEADLESS_FPS rather than free-running and hammering the ToF
#
# It is a CAP, not a target: asking for 30 on a sensor managing 16 gets 16.
# Lowering it can IMPROVE the image, because the driver may lengthen sensor
# exposure to fill the longer frame - but that also means it can fight
# auto_exposure on some sensors, so check the console line after changing it.
FPS = 15
HEADLESS_FPS = 20.0

PRINT_MS = 500            # console cadence; 0 = silent


# ==========================================================================
# BRING UP ONLY WHAT IS SWITCHED ON
# ==========================================================================

if not (CAMERA or TOF or IMU):
    raise SystemExit("every sensor is switched off - nothing to do")

csi0 = None
if CAMERA:
    import csi
    csi0 = csi.CSI()
    csi0.reset()
    csi0.pixformat(csi.RGB565)      # colour: the depth palette needs it
    csi0.framesize(csi.QVGA)
    if EXPOSURE_US is not None:
        csi0.auto_exposure(False, exposure_us=int(EXPOSURE_US))
    if GAIN_DB is not None:
        csi0.auto_gain(False, gain_db=float(GAIN_DB))
    if FPS is not None:
        try:
            csi0.framerate(int(FPS))
        except Exception as e:
            print("framerate(%s) not accepted (%s) - software pacing only"
                  % (FPS, e))
    csi0.snapshot(time=2000)        # let the AGC settle before the first frame
    try:
        _rate = csi0.framerate()
    except Exception:
        _rate = None
    print("camera %dx%d, exposure %s, framerate %s"
          % (csi0.width(), csi0.height(),
             "auto" if EXPOSURE_US is None else "%d us locked" % EXPOSURE_US,
             "uncapped" if _rate is None else "%s" % _rate))

tof = None
TW = TH = 0
if TOF:
    import tof as tof
    tof.init()
    TW, TH = tof.width(), tof.height()
    print("tof %dx%d (%d zones)" % (TW, TH, TW * TH))

imu = None
if IMU:
    import imu as imu
    print("imu up")

if CAMERA:
    print("hit Record in the Frame Buffer pane to capture")
print("")


# ==========================================================================
# TEXT -- draw_string's accepted argument forms have moved between firmware
# versions, so find one that works once rather than raising every frame.
# ==========================================================================

_form = None


def text(img, x, y, s):
    global _form
    if _form is False:
        return
    white = (255, 255, 255)
    forms = (
        lambda: img.draw_string(x, y, s, color=white, scale=2),
        lambda: img.draw_string(x, y, s, color=white),
        lambda: img.draw_string((x, y), s, color=white),
        lambda: img.draw_string(x, y, s),
    )
    if _form is not None:
        try:
            forms[_form]()
        except Exception:
            _form = False
        return
    for i in range(len(forms)):
        try:
            forms[i]()
            _form = i
            return
        except Exception:
            continue
    _form = False
    print("no working draw_string form - text overlay disabled")


# ==========================================================================
# LOOP
# ==========================================================================

prev = [None] * (TW * TH) if TOF else []
age = [0] * (TW * TH) if TOF else []
depth = None
fresh = stale = 0
dist_m = None
ax = ay = az = gx = gy = gz = 0.0

# Integrated from the gyro, because there is no magnetometer on this board and
# imu.roll()/pitch() snap to 0/90/180/270 - they detect orientation, they do not
# measure attitude. So this DRIFTS, without bound and without warning: it is
# here to see whether a turn registered at all, not to navigate by.
yaw_deg = 0.0

# clock.fps() is NOT the loop rate. OpenMV's clock accumulates the time from
# tick() to the fps() call, and fps() is only reached inside the print block -
# before the pacing sleep at the bottom. So it reports how fast the loop COULD
# run with no cap, which looks exactly like a cap that is not working. Count
# iterations against the wall clock instead.
clock = time.clock() if CAMERA else None
# One pacing rule for both cases. Without a camera nothing else times the loop,
# so headless always gets a period even when FPS is None.
_target = FPS if FPS else (None if CAMERA else HEADLESS_FPS)
period_ms = int(1000.0 / _target) if _target else 0
n = 0
since_print = 0           # iterations since the last console line
last_print = time.ticks_ms()
t_prev = time.ticks_ms()

while True:
    t0 = time.ticks_ms()
    if clock:
        clock.tick()
    n += 1

    dt = time.ticks_diff(t0, t_prev) / 1000.0
    t_prev = t0
    since_print += 1

    img = csi0.snapshot() if CAMERA else None

    # --- IMU: cheap, every pass --------------------------------------------
    if IMU:
        try:
            ax, ay, az = [v / 1000.0 for v in imu.acceleration_mg()]      # -> g
            gx, gy, gz = [v / 1000.0 for v in imu.angular_rate_mdps()]    # -> dps
            yaw_deg += gz * dt
        except Exception as e:
            if n == 1:
                print("imu read failed:", e)

    # --- ToF: throttled ----------------------------------------------------
    if TOF and n % TOF_EVERY == 0:
        try:
            depth, _lo, _hi = tof.read_depth(timeout=READ_TIMEOUT_MS)
            live = []
            stale = 0
            for i in range(TW * TH):
                d = depth[i]
                age[i] = age[i] + 1 if (prev[i] is not None and d == prev[i]) else 0
                prev[i] = d
                if age[i] >= STALE_AFTER:
                    stale += 1
                elif MIN_VALID_MM <= d <= MAX_VALID_MM:
                    live.append(d)
            fresh = len(live)
            live.sort()
            dist_m = live[len(live) // 2] / 1000.0 if live else None
        except Exception as e:
            depth, dist_m = None, None
            fresh = stale = 0
            if n < 5:
                print("tof read failed:", e)

    # --- overlay: the map, and the median. Nothing else. -------------------
    if img is not None:
        if TOF and SHOW_DEPTH_MAP and depth is not None:
            ox = img.width() - TW * DEPTH_SCALE - 4
            try:
                tof.draw_depth(img, depth, x=ox, y=4,
                               x_scale=DEPTH_SCALE, y_scale=DEPTH_SCALE,
                               scale=DEPTH_RANGE_MM)
                img.draw_rectangle(ox - 1, 3, TW * DEPTH_SCALE + 2,
                                   TH * DEPTH_SCALE + 2, color=(255, 255, 255))
            except Exception as e:
                if n < 5:
                    print("draw_depth failed:", e)
        if TOF and SHOW_DEPTH_TEXT:
            text(img, 4, img.height() - 20,
                 "--" if dist_m is None else "%.2f m" % dist_m)

    # --- console: everything else ------------------------------------------
    if PRINT_MS and time.ticks_diff(t0, last_print) > PRINT_MS:
        elapsed = time.ticks_diff(t0, last_print)
        measured = since_print * 1000.0 / elapsed if elapsed else 0.0
        since_print = 0
        last_print = t0
        parts = []
        if CAMERA:
            # measured = the real loop rate. work = what clock.fps() reports,
            # i.e. the rate with the cap removed - useful for seeing how much
            # headroom the cap is leaving, and nothing else.
            parts.append("fps %4.1f (work %4.1f)" % (measured, clock.fps()))
        elif PRINT_MS:
            parts.append("hz %4.1f" % measured)
        if TOF:
            parts.append("d %6s  fresh %2d stale %2d"
                         % ("--" if dist_m is None else "%.3f" % dist_m,
                            fresh, stale))
        if IMU:
            parts.append("a %+5.2f %+5.2f %+5.2f g" % (ax, ay, az))
            parts.append("g %+7.1f %+7.1f %+7.1f dps" % (gx, gy, gz))
            parts.append("yaw %+7.1f" % yaw_deg)
        print(" | ".join(parts))

    # snapshot() paces the loop when the camera is on and FPS is None; any
    # explicit cap is enforced here as well, since csi.framerate() is advisory
    # and does nothing at all when CAMERA is off.
    if period_ms:
        wait = period_ms - time.ticks_diff(time.ticks_ms(), t0)
        if wait > 0:
            time.sleep_ms(wait)
