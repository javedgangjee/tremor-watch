"""Simulate the demo: rest, a 20 second wrist shake, then rest, through the watch pipeline.

The sensor runs near 112.1 Hz. The readings are converted to 100 Hz with the toolbox's
curve (a cubic spline over the recording, which the block fit matches to about 3e-6 deg/s),
and the detector runs every second on the last 4 seconds, as the plan says.
"""
import sys, os, warnings
import numpy as np
from scipy.interpolate import interp1d
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context.plain_detector import build_tables, detect
import paradigma
from paradigma.classification import ClassifierPackage

PKG = os.path.join(os.path.dirname(paradigma.__file__), "assets", "tremor_detection_clf_package.pkl")
pkg = ClassifierPackage.load(PKG)
model = dict(mean=pkg.scaler.mean_, scale=pkg.scaler.scale_, coef=np.ravel(pkg.classifier.coef_),
             intercept=float(np.ravel(pkg.classifier.intercept_)[0]), threshold=float(pkg.threshold))
T = build_tables()
RATE = 112.1
LAG = 16 / RATE + 0.1 + 0.05          # converter look-ahead, sensor burst, run and redraw allowance
REST1, SHAKE, REST2 = 30.0, 20.0, 30.0


def make_session(rng, f0=5.0, amp=150.0, sway=3.0, ramp=0.4):
    dur = REST1 + SHAKE + REST2
    t = np.arange(int(dur * RATE)) / RATE
    # resting arm: sensor noise, a little physiological tremor near 9 Hz, and slow drift
    y = rng.normal(0, 1.0, (len(t), 3))
    y += np.outer(np.sin(2 * np.pi * 9.0 * t), [0.5, 0.3, 0.3])
    y += np.outer(np.sin(2 * np.pi * 0.2 * t + 1), rng.uniform(0.5, 1.5, 3))
    # the shake: frequency and size wander a little, with soft start and stop
    on = np.clip((t - REST1) / ramp, 0, 1) * np.clip((REST1 + SHAKE - t) / ramp, 0, 1)
    freq = f0 + 0.4 * np.sin(2 * np.pi * 0.15 * t + rng.uniform(0, 6))
    phase = 2 * np.pi * np.cumsum(freq) / RATE
    size = amp * (1 + 0.25 * np.sin(2 * np.pi * 0.3 * t + rng.uniform(0, 6)))
    axes = np.array([1.0, 0.35, 0.2])
    y += np.outer(np.sin(phase) * size * on, axes)
    # forearm sway while shaking, from the rest of the arm
    y += np.outer(np.sin(2 * np.pi * 0.8 * t + 0.5) * sway * on, [0.4, 1.0, 0.6])
    return t, np.clip(y, -1024, 1024)


def run(t, y):
    grid = np.arange(0, t[-1], 0.01)
    y100 = interp1d(t, y, axis=0, kind="cubic")(grid)
    states = []
    for end in range(400, len(grid) + 1, 100):        # one answer per second
        r = detect(y100[end - 400:end], model, T, np.float32)
        s = "Tremor" if r["tremor"] else ("No tremor" if r["at_rest"] else "Arm moving")
        states.append((end / 100.0 + LAG, s))
    return states


def summarise(states):
    on, off = REST1, REST1 + SHAKE
    first = next((tt for tt, s in states if s == "Tremor" and tt > on), None)
    during = [s for tt, s in states if first and first <= tt <= off]
    drops = sum(1 for s in during if s != "Tremor")
    back = next((tt for tt, s in states if tt > off and s == "No tremor"), None)
    after = []
    for tt, s in states:
        if tt > off and (not after or after[-1] != s):
            after.append(s)
        if back and tt >= back:
            break
    before = sorted({s for tt, s in states if tt < on})
    return first, drops, len(during), back, after, before


cases = [
    ("forearm resting on a table, 5 Hz", dict()),
    ("forearm resting, 4 Hz", dict(f0=4.0)),
    ("forearm resting, 6 Hz", dict(f0=6.0)),
    ("forearm resting, gentle 60 deg/s", dict(amp=60.0)),
    ("forearm resting, hard 600 deg/s", dict(amp=600.0)),
    ("forearm lifted off the table, sway 15 deg/s", dict(sway=15.0)),
]
for name, kw in cases:
    shows, delays, holds, backs, paths = 0, [], [], [], {}
    for trial in range(10):
        rng = np.random.default_rng(100 + trial)
        st = run(*make_session(rng, **kw))
        first, drops, n, back, after, before = summarise(st)
        if first:
            shows += 1
            delays.append(first - REST1)
            holds.append(1 - drops / max(1, n))
        if back:
            backs.append(back - (REST1 + SHAKE))
        paths[" > ".join(after)] = paths.get(" > ".join(after), 0) + 1
    print(f"\n{name}")
    print(f"  shows Tremor in {shows}/10 runs" + (f", after {np.median(delays):.1f} s (worst {max(delays):.1f} s)" if delays else ""))
    if holds:
        print(f"  stays on Tremor for {np.mean(holds):.0%} of the shake once it appears")
    if backs:
        print(f"  back to No tremor {np.median(backs):.1f} s after the shake stops (worst {max(backs):.1f} s)")
    print(f"  states after the shake stops: " + "; ".join(f"{p} ({c}/10)" for p, c in paths.items()))
    print(f"  states during the rest before the shake: {before}")
