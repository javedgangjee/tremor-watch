"""Run the toolbox and the plain rebuild on the same windows and compare."""
import sys, os, warnings
import numpy as np, pandas as pd
warnings.filterwarnings("ignore")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from context.plain_detector import build_tables, detect
import paradigma
from paradigma.config import TremorConfig
from paradigma.classification import ClassifierPackage
from paradigma.pipelines.tremor_pipeline import extract_tremor_features, detect_tremor

PKG = os.path.join(os.path.dirname(paradigma.__file__), "assets", "tremor_detection_clf_package.pkl")
pkg = ClassifierPackage.load(PKG)
sc, clf = pkg.scaler, pkg.classifier
names = list(clf.feature_names_in_)
print("scaled features:", list(sc.feature_names_in_) == names, len(names), "threshold", pkg.threshold)
model = dict(mean=sc.mean_, scale=sc.scale_, coef=np.ravel(clf.coef_), intercept=float(np.ravel(clf.intercept_)[0]),
             threshold=float(pkg.threshold))
print("numbers in model:", len(sc.mean_) + len(sc.scale_) + len(np.ravel(clf.coef_)) + 1, "+ threshold")

rng = np.random.default_rng(1)
FS, N = 100, 400
t = np.arange(N) / FS

def make(kind):
    noise = rng.normal(0, 1.5, (N, 3))
    if kind == "rest":
        return noise
    if kind == "tremor":
        f = rng.uniform(4, 6); a = rng.uniform(20, 80, 3)
        return noise + np.outer(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)), a) * rng.choice([-1, 1], 3)
    if kind == "small_tremor":
        f = rng.uniform(4, 6); a = rng.uniform(3, 8, 3)
        return noise + np.outer(np.sin(2 * np.pi * f * t), a)
    if kind == "walk":
        f = rng.uniform(0.8, 2.0); a = rng.uniform(40, 150, 3)
        return noise + np.outer(np.sin(2 * np.pi * f * t + 1), a)
    if kind == "walk_plus_tremor":
        return make("walk") + make("tremor")

kinds = ["rest", "tremor", "small_tremor", "walk", "walk_plus_tremor"]
windows, labels = [], []
for k in kinds:
    for _ in range(40):
        windows.append(make(k)); labels.append(k)

# Toolbox: one long recording of back-to-back windows at exactly 100 Hz.
data = np.concatenate(windows)
df = pd.DataFrame(data, columns=["gyroscope_x", "gyroscope_y", "gyroscope_z"])
df.insert(0, "time", np.arange(len(df)) / FS)
cfg = TremorConfig()
feat = extract_tremor_features(df, cfg)
out = detect_tremor(feat, cfg, PKG)
print("toolbox windows:", len(out), "plain windows:", len(windows))

tables = build_tables()
for dtype in (np.float64, np.float32):
    dm, dp, dpk, dbl, agree, n_tremor = 0, 0, 0, 0, 0, 0
    for i, w in enumerate(windows):
        r = detect(w, model, tables, dtype)
        row = out.iloc[i]
        m_ref = row[[f"mfcc_{j}" for j in range(1, 13)]].to_numpy(float)
        dm = max(dm, np.max(np.abs(r["mfcc"] - m_ref)))
        dp = max(dp, abs(r["prob"] - row["pred_tremor_proba"]))
        dpk = max(dpk, abs(r["peak"] - row["freq_peak"]))
        dbl = max(dbl, abs(r["below"] - row["below_tremor_power"]) / max(1e-9, abs(row["below_tremor_power"])))
        agree += int(r["tremor"] == bool(row["pred_tremor_checked"])) + 0
        agree += 0
        n_tremor += int(row["pred_tremor_checked"])
    print(f"{np.dtype(dtype).name}: largest diff mfcc {dm:.2e}, prob {dp:.2e}, peak {dpk:.2f} Hz, "
          f"low power rel {dbl:.2e}; tremor label agrees {agree}/{len(windows)}; toolbox tremor windows {n_tremor}")

by = pd.Series(out["pred_tremor_checked"].to_numpy(), index=labels).groupby(level=0).mean()
print("toolbox tremor share by kind:\n", by.round(2).to_string())
