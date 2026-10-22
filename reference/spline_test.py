"""Fit the toolbox's curve one block at a time, the way the watch would, and compare.

The toolbox converts 112.1 Hz readings to 100 Hz with scipy interp1d(kind="cubic"),
which fits one cubic spline through the whole recording. The watch cannot wait for
the whole recording, so it fits a spline over each 1 second block plus MARGIN extra
readings on each side, and keeps only the middle. A reading's pull on the curve
shrinks about 3.7 times per reading of distance, so a wide enough margin makes the
block fit match the whole-recording fit.
"""
import sys, os, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plain_detector import build_tables, detect
import paradigma
from paradigma.config import TremorConfig, IMUConfig
from paradigma.classification import ClassifierPackage
from paradigma.preprocessing import preprocess_imu_data
from paradigma.pipelines.tremor_pipeline import extract_tremor_features, detect_tremor

PKG = os.path.join(os.path.dirname(paradigma.__file__), "assets", "tremor_detection_clf_package.pkl")
pkg = ClassifierPackage.load(PKG)
model = dict(mean=pkg.scaler.mean_, scale=pkg.scaler.scale_, coef=np.ravel(pkg.classifier.coef_),
             intercept=float(np.ravel(pkg.classifier.intercept_)[0]), threshold=float(pkg.threshold))
T = build_tables()
COLS = ["gyroscope_x", "gyroscope_y", "gyroscope_z"]
RATE, OUT = 112.1, 100.0
rng = np.random.default_rng(11)

# A smooth test signal with background motion and tremor bursts, as in rate_test.py.
DUR = 600.0
comps = [(rng.uniform(0.2, 20), rng.uniform(0.5, 2.5, 3), rng.uniform(0, 6.28, 3)) for _ in range(60)]
bursts = [(s, s + rng.uniform(20, 60), rng.uniform(4, 6), rng.uniform(5, 60, 3)) for s in np.arange(10, DUR - 60, 70)]
def signal_at(tt):
    y = np.zeros((len(tt), 3))
    for f, a, ph in comps:
        y += np.sin(2 * np.pi * f * tt[:, None] + ph) * a
    for s, e, f, a in bursts:
        on = ((tt >= s) & (tt < e)).astype(float)
        y += np.sin(2 * np.pi * f * tt)[:, None] * a * on[:, None]
    return y

n_in = int(DUR * RATE)
idx = np.arange(n_in)
t_in = idx / RATE
y_in = signal_at(t_in)

# Toolbox conversion: one spline through the whole recording.
df = pd.DataFrame(y_in, columns=COLS); df.insert(0, "time", t_in)
ic = IMUConfig(); ic.resampling_frequency = OUT
ref = preprocess_imu_data(df, ic, sensor="gyroscope", watch_side="left")
t_ref = ref["time"].to_numpy(); y_ref = ref[COLS].to_numpy()


def natural_spline_block(y, h, dtype):
    """Second derivatives of a natural cubic spline on evenly spaced points (Thomas algorithm)."""
    n = len(y)
    y = y.astype(dtype)
    rhs = np.zeros_like(y)
    rhs[1:-1] = (y[2:] - 2 * y[1:-1] + y[:-2]) * dtype(6.0 / (h * h))
    m = np.zeros_like(y)
    c = np.zeros(n, dtype=dtype); d = np.zeros_like(y)
    for i in range(1, n - 1):                      # forward sweep, diagonal 4, off-diagonals 1
        denom = dtype(4.0) - (c[i - 1] if i > 1 else dtype(0.0))
        c[i] = dtype(1.0) / denom
        d[i] = (rhs[i] - (d[i - 1] if i > 1 else 0)) / denom
    for i in range(n - 2, 0, -1):                  # back substitution
        m[i] = d[i] - c[i] * m[i + 1]
    return m


def convert_blocks(margin, dtype):
    """Watch-style conversion. Time is kept as whole reading counts, never as float seconds."""
    h = 1.0 / RATE
    out_t, out_y = [], []
    block = 112
    k = 0                                          # index of the next 100 Hz output sample
    for start in range(0, n_in, block):
        end = min(start + block, n_in)
        lo, hi = max(0, start - margin), min(n_in, end + margin)
        yb = y_in[lo:hi]
        m = natural_spline_block(yb, h, dtype)
        # outputs whose time falls in [start, end) readings, computed from integers:
        # position in readings = k * RATE / OUT, done in 64-bit as a fraction of whole numbers
        while True:
            pos = k * 1121 / 1000.0                # k * 112.1 / 100 exactly, as a rational
            if pos >= end - 1 or pos >= n_in - 1:
                break
            i = int(np.floor(pos)); u = dtype(pos - i)
            j = i - lo
            hh = dtype(h); a = dtype(1) - u
            yv = (m[j] * a ** 3 + m[j + 1] * u ** 3) * (hh * hh / 6) + (yb[j] - m[j] * hh * hh / 6) * a + (yb[j + 1] - m[j + 1] * hh * hh / 6) * u
            out_t.append(k / OUT); out_y.append(yv)
            k += 1
    return np.array(out_t), np.array(out_y, dtype=float)


def detector_compare(y_watch):
    """Run the plain detector on watch-converted data and the toolbox on its own conversion."""
    cfg = TremorConfig()
    out = detect_tremor(extract_tremor_features(ref, cfg), cfg, PKG)
    n = min(len(out), len(y_watch) // 400)
    probs = np.array([detect(y_watch[w * 400:(w + 1) * 400], model, T, np.float32)["prob"] for w in range(n)])
    labs = np.array([detect(y_watch[w * 400:(w + 1) * 400], model, T, np.float32)["tremor"] for w in range(n)])
    rp = out["pred_tremor_proba"].to_numpy()[:n]; rl = out["pred_tremor_checked"].to_numpy()[:n].astype(bool)
    return np.abs(probs - rp), labs == rl, n


print(f"toolbox output samples {len(t_ref)}, first time {t_ref[0]:.4f}, step {np.median(np.diff(t_ref)):.6f}")
for margin in (4, 8, 16):
    for dtype in (np.float64, np.float32):
        tw, yw = convert_blocks(margin, dtype)
        n = min(len(tw), len(t_ref))
        assert np.allclose(tw[:n], t_ref[:n], atol=1e-6), "grid times differ"
        skip = int(OUT)                            # leave out the first second of the recording
        diff = np.abs(yw[skip:n] - y_ref[skip:n])
        scale = np.abs(y_ref[skip:n]).max()
        dp, agree, nw = detector_compare(yw[:n])
        print(f"margin {margin:2d}, {np.dtype(dtype).name}: largest value gap {diff.max():.2e} deg/s "
              f"({diff.max() / scale:.1e} of the largest value); windows {nw}, "
              f"largest probability gap {dp[1:].max():.2e}, tremor answer agrees {agree[1:].mean():.1%}")

# Why time must be counted in whole readings: float32 seconds after two hours.
t = np.float32(7200.0)
print(f"\nfloat32 step at 7200 s: {np.spacing(t) * 1000:.3f} ms (one reading lasts {1000 / RATE:.2f} ms)")
