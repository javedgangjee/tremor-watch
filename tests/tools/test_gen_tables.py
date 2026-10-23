"""Tests for tools/gen_tables.py and core/detector_tables.h.

They need the toolbox, so they run in the reference venv with this command.

    reference/.venv/bin/python -m pytest tests/tools -q
"""
from __future__ import annotations

import ast
import copy
import hashlib
import importlib.util
import logging
import math
import re
import shutil
import subprocess
import sys
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from scipy.signal import get_window
from sklearn.linear_model import LogisticRegression
from sklearn.tree import DecisionTreeClassifier

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "reference"))
import plain_detector as plain  # noqa: E402

import paradigma  # noqa: E402
from paradigma.classification import ClassifierPackage  # noqa: E402
from paradigma.config import TremorConfig  # noqa: E402
from paradigma.feature_extraction import compute_mfccs  # noqa: E402
from paradigma.pipelines.tremor_pipeline import detect_tremor, extract_tremor_features  # noqa: E402

GEN = REPO / "tools" / "gen_tables.py"
HEADER = REPO / "core" / "detector_tables.h"
DUMP_SOURCE = REPO / "tests" / "tools" / "dump_tables.c"
MODEL = Path(paradigma.__file__).resolve().parent / "assets" / "tremor_detection_clf_package.pkl"
EXPECTED_SHA256 = "4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e"
CC_FLAGS = ["-std=c11", "-Wall", "-Wextra", "-Werror", "-pedantic", "-ffp-contract=off", "-I", str(REPO / "core")]
FS, N = 100, 400


@dataclass
class Dump:
    """The result of compiling and running dump_tables.c."""

    compile_output: str
    compile_code: int
    run_code: int
    text: dict[str, str]
    values: dict[str, np.ndarray]


def bits32(values: np.ndarray) -> np.ndarray:
    """Return the bit patterns of the values as 32-bit floats."""
    return np.asarray(values, dtype=np.float32).view(np.uint32)


@pytest.fixture(scope="session")
def dump(tmp_path_factory: pytest.TempPathFactory) -> Dump:
    """Compile dump_tables.c once, run it, and read back every value it prints."""
    program = tmp_path_factory.mktemp("dump") / "dump_tables"
    built = subprocess.run(
        ["cc", *CC_FLAGS, str(DUMP_SOURCE), "-o", str(program)], capture_output=True, text=True, check=False
    )
    assert built.returncode == 0, built.stderr
    ran = subprocess.run([str(program)], capture_output=True, text=True, check=False)
    text: dict[str, str] = {}
    items: dict[str, dict[int, float]] = {}
    for line in ran.stdout.splitlines():
        name, index, value = line.split(" ")
        if name.startswith("DET_"):
            text[name] = value
        else:
            items.setdefault(name, {})[int(index)] = float.fromhex(value)
    values = {name: np.array([found[i] for i in range(len(found))]) for name, found in items.items()}
    return Dump(built.stdout + built.stderr, built.returncode, ran.returncode, text, values)


@pytest.fixture(scope="session")
def package() -> ClassifierPackage:
    """Load the toolbox's model file."""
    return ClassifierPackage.load(MODEL)


def package_model(package: ClassifierPackage) -> dict[str, np.ndarray | float]:
    """Return the model numbers as reference/compare.py reads them."""
    sc, clf = package.scaler, package.classifier
    return dict(mean=sc.mean_, scale=sc.scale_, coef=np.ravel(clf.coef_),
                intercept=float(np.ravel(clf.intercept_)[0]), threshold=float(package.threshold))


def header_model(dump: Dump) -> dict[str, np.ndarray | float]:
    """Return the model numbers from the header."""
    v = dump.values
    return dict(mean=v["det_mean"], scale=v["det_scale"], coef=v["det_coef"],
                intercept=float(v["det_intercept"][0]), threshold=float(v["det_threshold"][0]))


def header_tables(dump: Dump) -> dict[str, np.ndarray]:
    """Return the four tables from the header as 32-bit floats."""
    v = dump.values
    return {
        "w_psd": v["det_w_psd"].astype(np.float32),
        "w_spg": v["det_w_spg"].astype(np.float32),
        "filters": v["det_filters"].reshape(15, 101).astype(np.float32),
        "dct": v["det_dct"].reshape(12, 15).astype(np.float32),
    }


@pytest.fixture(scope="session")
def windows() -> tuple[list[np.ndarray], list[str]]:
    """Make the 200 windows of reference/compare.py with seed 1. This copies its generator."""
    rng = np.random.default_rng(1)
    t = np.arange(N) / FS

    def make(kind: str) -> np.ndarray:
        noise = rng.normal(0, 1.5, (N, 3))
        if kind == "rest":
            return noise
        if kind == "tremor":
            f = rng.uniform(4, 6); a = rng.uniform(20, 80, 3)  # noqa: E702
            return noise + np.outer(np.sin(2 * np.pi * f * t + rng.uniform(0, 6)), a) * rng.choice([-1, 1], 3)
        if kind == "small_tremor":
            f = rng.uniform(4, 6); a = rng.uniform(3, 8, 3)  # noqa: E702
            return noise + np.outer(np.sin(2 * np.pi * f * t), a)
        if kind == "walk":
            f = rng.uniform(0.8, 2.0); a = rng.uniform(40, 150, 3)  # noqa: E702
            return noise + np.outer(np.sin(2 * np.pi * f * t + 1), a)
        if kind == "walk_plus_tremor":
            return make("walk") + make("tremor")
        raise ValueError(kind)

    found, labels = [], []
    for kind in ["rest", "tremor", "small_tremor", "walk", "walk_plus_tremor"]:
        for _ in range(40):
            found.append(make(kind))
            labels.append(kind)
    return found, labels


def test_1_header_is_made_again_byte_for_byte(tmp_path: Path) -> None:
    out = tmp_path / "detector_tables.h"
    subprocess.run([sys.executable, str(GEN), "--out", str(out)], check=True, capture_output=True)
    assert out.read_bytes() == HEADER.read_bytes()


def test_2_header_compiles_with_no_warning(dump: Dump) -> None:
    assert dump.compile_code == 0
    assert dump.compile_output == ""
    assert dump.run_code == 0


def test_3_size_macros(dump: Dump) -> None:
    assert dump.text["DET_N_COEF"] == "12"
    assert dump.text["DET_N_FILT"] == "15"
    assert dump.text["DET_N_BINS"] == "101"
    assert dump.text["DET_PSD_SEG"] == "300"
    assert dump.text["DET_SPG_SEG"] == "200"


def test_4_model_numbers_match_toolbox_exactly(dump: Dump, package: ClassifierPackage) -> None:
    v = dump.values
    np.testing.assert_array_equal(v["det_mean"], package.scaler.mean_)
    np.testing.assert_array_equal(v["det_scale"], package.scaler.scale_)
    np.testing.assert_array_equal(v["det_coef"], np.ravel(package.classifier.coef_))
    np.testing.assert_array_equal(v["det_intercept"], np.ravel(package.classifier.intercept_))
    count = sum(v[name].size for name in ["det_mean", "det_scale", "det_coef", "det_intercept"])
    assert count == 37
    assert v["det_scale"][0] == pytest.approx(2.541389, abs=1e-6)
    assert v["det_coef"][0] == pytest.approx(0.84610178, abs=1e-8)
    assert v["det_intercept"][0] == pytest.approx(-5.8764059, abs=1e-7)


def test_5_cut_off_matches_package(dump: Dump, package: ClassifierPackage) -> None:
    threshold = dump.values["det_threshold"][0]
    assert threshold == float(package.threshold)
    assert threshold == 0.029570239921802
    assert abs(threshold - 0.0296) <= 0.00005


def test_6_symmetric_hann(dump: Dump) -> None:
    w = dump.values["det_w_psd"]
    np.testing.assert_array_equal(bits32(w), bits32(plain.hann_symmetric(300)))
    np.testing.assert_allclose(w, get_window("hann", 300, fftbins=False), rtol=0, atol=1e-7)
    assert w[0] == 0 and w[299] == 0
    assert w[149] == w[150]
    assert w[149] == pytest.approx(0.9999724, abs=1e-7)


def test_7_periodic_hann(dump: Dump) -> None:
    w = dump.values["det_w_spg"]
    np.testing.assert_array_equal(bits32(w), bits32(plain.hann_periodic(200)))
    np.testing.assert_allclose(w, get_window("hann", 200), rtol=0, atol=1e-7)
    assert w[0] == 0
    assert w[100] == 1
    assert w[1] == w[199]


def test_8_filter_table(dump: Dump) -> None:
    fb = dump.values["det_filters"].reshape(15, 101)
    np.testing.assert_array_equal(bits32(fb), bits32(plain.build_tables()["filters"]))
    lo, hi = plain.melscale(0.0), plain.melscale(25.0)
    mels = [lo + (hi - lo) * i / 16 for i in range(17)]
    points = [int(np.round(2 * plain.inverse_melscale(m))) + 1 for m in mels]
    expected_points = [1, 3, 5, 7, 10, 12, 15, 18, 21, 24, 27, 30, 34, 38, 42, 46, 51]
    assert points == expected_points
    mask = np.zeros((15, 101), dtype=bool)
    for j in range(15):
        mask[j, expected_points[j]:expected_points[j + 2]] = True
    np.testing.assert_array_equal(fb > 0, mask)
    np.testing.assert_array_equal(fb[~mask], 0)
    assert int((fb > 0).sum()) == 93
    np.testing.assert_allclose(fb.sum(axis=1), 2.0, rtol=0, atol=1e-6)
    assert fb[0].max() == pytest.approx(0.75, abs=1e-7)
    assert fb[14].max() == pytest.approx(0.4, abs=1e-7)


def test_9_cosine_table(dump: Dump) -> None:
    dct = dump.values["det_dct"].reshape(12, 15)
    np.testing.assert_array_equal(bits32(dct), bits32(plain.build_tables()["dct"]))
    np.testing.assert_array_equal(bits32(dct[0]), bits32(np.full(15, 1 / math.sqrt(15))))
    assert dct[0][0] == pytest.approx(0.2581989, abs=1e-7)
    assert dct[1][0] == pytest.approx(math.cos(math.pi / 30) * math.sqrt(2 / 15), abs=1e-7)
    assert dct[1][0] == pytest.approx(0.36314806, abs=1e-7)


def test_10_toolbox_filter_bank_agrees(dump: Dump) -> None:
    rng = np.random.default_rng(10)
    spectra = rng.uniform(0, 500, (50, 101, 6))
    cfg = TremorConfig()
    cfg._set_sampling_frequency_detected(100)
    cfg.mfcc_low_frequency = cfg.fmin_mfcc
    cfg.mfcc_high_frequency = cfg.fmax_mfcc
    cfg.mfcc_n_dct_filters = cfg.n_dct_filters_mfcc
    cfg.mfcc_n_coefficients = cfg.n_coefficients_mfcc
    toolbox = compute_mfccs(spectra, cfg, total_power_type="spectrogram", rounding_method="round",
                            multiplication_factor=1)
    fb = dump.values["det_filters"].reshape(15, 101)
    dct = dump.values["det_dct"].reshape(12, 15)
    bands = np.einsum("jf,wfs->wsj", fb, spectra)
    ours = (np.log10(bands + 1e-10) @ dct.T).mean(axis=1)
    assert toolbox.shape == ours.shape == (50, 12)
    assert np.max(np.abs(toolbox - ours)) <= 1e-6


def test_11_model_hash(dump: Dump) -> None:
    found = hashlib.sha256(MODEL.read_bytes()).hexdigest()
    assert dump.text["DET_MODEL_SHA256"] == found == EXPECTED_SHA256


def test_12_header_gives_plain_detector_the_same_answers(
    dump: Dump, package: ClassifierPackage, windows: tuple[list[np.ndarray], list[str]]
) -> None:
    ours_model, ours_tables = header_model(dump), header_tables(dump)
    ref_model, ref_tables = package_model(package), plain.build_tables()
    for w in windows[0]:
        a = plain.detect(w, ours_model, ours_tables, np.float32)
        b = plain.detect(w, ref_model, ref_tables, np.float32)
        np.testing.assert_array_equal(a["mfcc"], b["mfcc"])
        assert a["prob"] == b["prob"]
        assert a["peak"] == b["peak"]
        assert a["below"] == b["below"]
        assert a["tremor"] == b["tremor"]


def test_13_header_matches_toolbox(dump: Dump, windows: tuple[list[np.ndarray], list[str]]) -> None:
    found = windows[0]
    df = pd.DataFrame(np.concatenate(found), columns=["gyroscope_x", "gyroscope_y", "gyroscope_z"])
    df.insert(0, "time", np.arange(len(df)) / FS)
    cfg = TremorConfig()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        out = detect_tremor(extract_tremor_features(df, cfg), cfg, str(MODEL))
    assert len(out) == len(found) == 200
    model, tables = header_model(dump), header_tables(dump)
    worst_mfcc, worst_prob, agree = 0.0, 0.0, 0
    for i, w in enumerate(found):
        r = plain.detect(w, model, tables, np.float32)
        row = out.iloc[i]
        ref = row[[f"mfcc_{j}" for j in range(1, 13)]].to_numpy(float)
        worst_mfcc = max(worst_mfcc, float(np.max(np.abs(r["mfcc"] - ref))))
        worst_prob = max(worst_prob, abs(r["prob"] - row["pred_tremor_proba"]))
        agree += int(r["tremor"] == bool(row["pred_tremor_checked"]))
    assert worst_mfcc <= 1.5e-6
    assert worst_prob <= 7e-7
    assert agree == 200


def test_14_changed_model_file_stops_the_run(tmp_path: Path) -> None:
    model = tmp_path / "model.pkl"
    shutil.copyfile(MODEL, model)
    data = bytearray(model.read_bytes())
    data[-1] ^= 0xFF
    model.write_bytes(bytes(data))
    found = hashlib.sha256(bytes(data)).hexdigest()
    out = tmp_path / "detector_tables.h"
    ran = subprocess.run([sys.executable, str(GEN), "--model", str(model), "--out", str(out)],
                         capture_output=True, text=True, check=False)
    assert ran.returncode != 0
    assert found in ran.stderr
    assert not out.exists()


def test_15_header_comment() -> None:
    text = HEADER.read_text(encoding="ascii")
    comment = text[text.index("/*"):text.index("*/")]
    for needed in ["tools/gen_tables.py", "reference/.venv/bin/python tools/gen_tables.py", "ParaDigMa 1.1.2",
                   "scikit-learn 1.6.0", "Apache 2.0", "Timmermans", EXPECTED_SHA256]:
        assert needed in comment
    months = "January|February|March|April|May|June|July|August|September|October|November|December"
    assert not re.search(r"\d{4}-\d{2}-\d{2}", text)
    assert not re.search(rf"\b\d{{1,2}} ({months})\b|\b({months}) \d{{1,2}}\b", text)


def test_16_python_rules() -> None:
    source = GEN.read_text(encoding="utf-8")
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = node.args
            every = [*args.posonlyargs, *args.args, *args.kwonlyargs]
            every += [a for a in (args.vararg, args.kwarg) if a is not None]
            for arg in every:
                assert arg.annotation is not None, f"{node.name} argument {arg.arg}"
            assert node.returns is not None, node.name
    assert "print(" not in source
    assert "os.path" not in source
    assert "except Exception" not in source


def run_main_on(package: ClassifierPackage, tmp_path: Path, caplog: pytest.LogCaptureFixture) -> tuple[int, Path]:
    """Save the package, run gen_tables.main() on it with its hash expected, and return the exit code and --out."""
    model = tmp_path / "model.pkl"
    package.save(model)
    out = tmp_path / "detector_tables.h"
    spec = importlib.util.spec_from_file_location("gen_tables_under_test", GEN)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.EXPECTED_SHA256 = hashlib.sha256(model.read_bytes()).hexdigest()
    with caplog.at_level(logging.INFO), pytest.raises(SystemExit) as stopped:
        module.main(["--model", str(model), "--out", str(out)])
    return int(stopped.value.code), out


def seeded_rows(n: int, seed: int) -> pd.DataFrame:
    """Return n seeded rows with the feature names mfcc_1 to mfcc_12."""
    rng = np.random.default_rng(seed)
    return pd.DataFrame(rng.normal(0, 1, (n, 12)), columns=[f"mfcc_{i}" for i in range(1, 13)])


def test_17_wrong_feature_names_stop_the_run(
    package: ClassifierPackage, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    changed = copy.deepcopy(package)
    names = np.array([f"mfcc_{i}" for i in range(12, 0, -1)], dtype=object)
    changed.scaler.feature_names_in_ = names
    changed.classifier.feature_names_in_ = names.copy()
    code, out = run_main_on(changed, tmp_path, caplog)
    assert code == 1
    assert str(list(names)) in caplog.text
    assert not out.exists()


def test_18_other_classifier_stops_the_run(
    package: ClassifierPackage, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    changed = copy.deepcopy(package)
    rows = seeded_rows(20, 18)
    changed.classifier = DecisionTreeClassifier(random_state=18).fit(rows, np.arange(20) % 2)
    code, out = run_main_on(changed, tmp_path, caplog)
    assert code == 1
    assert "DecisionTreeClassifier" in caplog.text
    assert not out.exists()


def test_19_three_rows_of_weights_stop_the_run(
    package: ClassifierPackage, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    changed = copy.deepcopy(package)
    rows = seeded_rows(30, 19)
    with warnings.catch_warnings():
        # scikit-learn 1.6.0 passes an option that newer scipy no longer knows, and scipy warns about it.
        warnings.simplefilter("ignore")
        changed.classifier = LogisticRegression().fit(rows, np.arange(30) % 3)
    assert changed.classifier.coef_.shape == (3, 12)
    code, out = run_main_on(changed, tmp_path, caplog)
    assert code == 1
    assert "(3, 12)" in caplog.text
    assert not out.exists()
