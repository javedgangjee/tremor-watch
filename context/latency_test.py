"""How long from the start of a shake until the detector says tremor, and which shakes it accepts."""
import sys, os, warnings
import numpy as np
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
FS = 100
rng = np.random.default_rng(3)


def still(n):
    # resting arm: sensor noise plus a little slow drift
    t = np.arange(n) / FS
    return rng.normal(0, 1.0, (n, 3)) + np.outer(np.sin(2 * np.pi * 0.3 * t), rng.uniform(0.5, 2, 3))


def shake(n, f=5.0, amp=200.0, sway=0.0, sway_f=1.0, clip=1024):
    t = np.arange(n) / FS
    axes = np.array([1.0, 0.35, 0.2]) * amp
    y = np.outer(np.sin(2 * np.pi * f * t), axes)
    if sway:
        y += np.outer(np.sin(2 * np.pi * sway_f * t + 0.7), np.array([0.4, 1.0, 0.6]) * sway)
    y += rng.normal(0, 1.0, (n, 3))
    return np.clip(y, -clip, clip)


def label(w):
    r = detect(w, model, T)
    if r["tremor"]:
        return "tremor"
    return "rest-no" if r["at_rest"] else "moving"


print("1. Which shakes does the detector accept? (whole 4 s window shaking)")
cases = [
    ("gentle 5 Hz, 50 deg/s", dict(f=5, amp=50)),
    ("firm 5 Hz, 200 deg/s", dict(f=5, amp=200)),
    ("hard 5 Hz, 600 deg/s", dict(f=5, amp=600)),
    ("very hard 5 Hz, 1500 deg/s, clipped at 1024", dict(f=5, amp=1500)),
    ("slow 2.5 Hz, 200 deg/s", dict(f=2.5, amp=200)),
    ("fast 8 Hz, 200 deg/s", dict(f=8, amp=200)),
    ("5 Hz with forearm sway 30 deg/s", dict(f=5, amp=200, sway=30)),
    ("5 Hz with forearm sway 100 deg/s", dict(f=5, amp=200, sway=100)),
]
for name, kw in cases:
    labs = [label(shake(400, **kw)) for _ in range(20)]
    print(f"   {name:45s} tremor {labs.count('tremor')}/20, arm moving {labs.count('moving')}/20")

print("\n2. How much of a window must be shaking?")
for secs in (0.5, 1, 1.5, 2, 2.5, 3, 4):
    k = int(secs * FS)
    hits = 0
    for _ in range(20):
        w = still(400)
        w[400 - k:] = shake(k, f=5, amp=200)
        hits += label(w) == "tremor"
    print(f"   last {secs:3.1f} s shaking: tremor {hits}/20")

print("\n3. Delay from shake start to the first tremor answer")
COMPUTE = 0.05   # generous allowance for converting, detecting and redrawing on the watch
for step in (4.0, 1.0, 0.5):
    delays = []
    for trial in range(40):
        onset = 20 + rng.uniform(0, 4)
        dur = 60.0
        n = int(dur * FS)
        x = still(n)
        a = int(onset * FS)
        x[a:] = shake(n - a, f=5, amp=200)
        first = None
        end = 4.0
        while end <= dur:
            e = int(end * FS)
            if label(x[e - 400:e]) == "tremor" and end > onset:
                first = end; break
            end = round(end + step, 3)
        delays.append(first - onset + COMPUTE if first else np.nan)
    d = np.array(delays)
    print(f"   new window every {step:3.1f} s: median {np.nanmedian(d):.1f} s, worst {np.nanmax(d):.1f} s, missed {np.isnan(d).sum()}/40")

print("\n4. Delay from shake stop to leaving the tremor state")
for step in (4.0, 1.0):
    delays = []
    for trial in range(40):
        stop = 30 + rng.uniform(0, 4)
        n = 60 * FS
        x = still(n)
        x[10 * FS:int(stop * FS)] = shake(int(stop * FS) - 10 * FS, f=5, amp=200)
        end, first = 4.0, None
        while end <= 60:
            e = int(end * FS)
            if end > stop and label(x[e - 400:e]) != "tremor":
                first = end; break
            end = round(end + step, 3)
        delays.append(first - stop + COMPUTE)
    d = np.array(delays)
    print(f"   new window every {step:3.1f} s: median {np.median(d):.1f} s, worst {d.max():.1f} s")
