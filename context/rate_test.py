"""What happens when the gyroscope runs at 112.1 Hz instead of 100 Hz."""
import sys, os, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context.plain_detector import build_tables, detect
import paradigma
from paradigma.config import TremorConfig, IMUConfig
from paradigma.classification import ClassifierPackage
from paradigma.preprocessing import preprocess_imu_data
from paradigma.pipelines.tremor_pipeline import extract_tremor_features, detect_tremor

PKG = os.path.join(os.path.dirname(paradigma.__file__), "assets", "tremor_detection_clf_package.pkl")
pkg = ClassifierPackage.load(PKG)
model = dict(mean=pkg.scaler.mean_, scale=pkg.scaler.scale_, coef=np.ravel(pkg.classifier.coef_),
             intercept=float(np.ravel(pkg.classifier.intercept_)[0]), threshold=float(pkg.threshold))
tables = build_tables()
rng = np.random.default_rng(7)
COLS = ["gyroscope_x", "gyroscope_y", "gyroscope_z"]

# A smooth signal defined at any time: background motion plus tremor bursts.
DUR = 400.0
comps = []
for _ in range(60):   # background: many small components up to 20 Hz
    comps.append((rng.uniform(0.2, 20), rng.uniform(0.5, 2.5, 3), rng.uniform(0, 6.28, 3), None))
bursts = [(s, s + rng.uniform(20, 60), rng.uniform(4, 6), rng.uniform(5, 60, 3)) for s in np.arange(10, DUR - 60, 70)]

def signal_at(tt):
    y = np.zeros((len(tt), 3))
    for f, a, ph, _ in comps:
        y += np.sin(2 * np.pi * f * tt[:, None] + ph) * a
    for s, e, f, a in bursts:
        on = ((tt >= s) & (tt < e)).astype(float)
        y += np.sin(2 * np.pi * f * tt)[:, None] * a * on[:, None]
    return y

def toolbox(fs_in, resample_to=None):
    tt = np.arange(0, DUR, 1 / fs_in)
    df = pd.DataFrame(signal_at(tt), columns=COLS); df.insert(0, "time", tt)
    if resample_to:
        ic = IMUConfig(); ic.resampling_frequency = resample_to
        df = preprocess_imu_data(df, ic, sensor="gyroscope", watch_side="right")
    cfg = TremorConfig()
    out = detect_tremor(extract_tremor_features(df, cfg), cfg, PKG)
    return out, cfg.sampling_frequency

ref, _ = toolbox(100.0)
raw, fs_used = toolbox(112.1)
res, _ = toolbox(112.1, resample_to=100)
print("toolbox working rate when fed 112.1 Hz:", fs_used)

def window_times(out):
    return out["time"].to_numpy()

def compare(name, other):
    # match windows by start time to the 100 Hz reference
    n = min(len(ref), len(other))
    a = ref.iloc[:n]; b = other.iloc[:n]
    dt = np.max(np.abs(a["time"].to_numpy() - b["time"].to_numpy()))
    dp = np.abs(a["pred_tremor_proba"].to_numpy() - b["pred_tremor_proba"].to_numpy())
    agree = np.mean(a["pred_tremor_checked"].to_numpy() == b["pred_tremor_checked"].to_numpy())
    print(f"{name}: windows {len(other)} vs {len(ref)}, start shift {dt:.2f} s, "
          f"median prob diff {np.median(dp):.3f}, max {dp.max():.3f}, tremor label agrees {agree:.1%}, "
          f"tremor windows {int(b['pred_tremor_checked'].sum())} vs {int(a['pred_tremor_checked'].sum())}")

compare("112.1 Hz run at 112 Hz (toolbox default)", raw)
compare("112.1 Hz resampled to 100 Hz by toolbox", res)

# A watch-style resampler: local cubic (Catmull-Rom) from 112.1 Hz onto a 100 Hz grid.
tt_in = np.arange(0, DUR, 1 / 112.1)
y_in = signal_at(tt_in)
tt_out = np.arange(0, tt_in[-2], 1 / 100.0)
pos = tt_out * 112.1
i = np.floor(pos).astype(int); u = (pos - i)[:, None]
i = np.clip(i, 1, len(tt_in) - 3)
p0, p1, p2, p3 = y_in[i - 1], y_in[i], y_in[i + 1], y_in[i + 2]
y_cr = 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u ** 2 + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3)
y_lin = p1 + (p2 - p1) * u
for name, y in [("local cubic", y_cr), ("straight line", y_lin)]:
    nwin = len(y) // 400
    probs, labs = [], []
    for k in range(min(nwin, len(ref))):
        r = detect(y[k * 400:(k + 1) * 400], model, tables, np.float32)
        probs.append(r["prob"]); labs.append(r["tremor"])
    a = ref.iloc[:len(probs)]
    dp = np.abs(np.array(probs) - a["pred_tremor_proba"].to_numpy())
    agree = np.mean(np.array(labs) == a["pred_tremor_checked"].to_numpy().astype(bool))
    print(f"watch-style {name} 112.1 to 100 Hz, float32: median prob diff {np.median(dp):.4f}, max {dp.max():.4f}, "
          f"tremor label agrees {agree:.1%}")
