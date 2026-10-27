"""Write the tremor detector's fixed numbers into the C header core/detector_tables.h.

The four tables come from build_tables() in reference/plain_detector.py. The model
numbers come from the ParaDigMa toolbox's model file, which is read the way
reference/compare.py reads it. The script runs in the reference venv, because it
needs the toolbox.

Run it from the repo root with this command.

    reference/.venv/bin/python tools/gen_tables.py
"""
from __future__ import annotations

import argparse
import hashlib
import logging
import sys
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path
from typing import NoReturn

import numpy as np
import paradigma
from paradigma.classification import ClassifierPackage
from sklearn.linear_model import LogisticRegression

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "reference"))
import plain_detector as plain  # noqa: E402

logger = logging.getLogger("gen_tables")

DEFAULT_OUT = REPO / "core" / "detector_tables.h"
DEFAULT_MODEL = Path(paradigma.__file__).resolve().parent / "assets" / "tremor_detection_clf_package.pkl"
# The hash of the model file of ParaDigMa 1.1.2.
EXPECTED_SHA256 = "4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e"
FEATURE_NAMES = [f"mfcc_{i}" for i in range(1, plain.N_COEF + 1)]
COMMAND = "reference/.venv/bin/python tools/gen_tables.py"
VALUES_PER_LINE = 6


def fail(message: str) -> NoReturn:
    """Log the reason and stop the run with exit code 1."""
    logger.error(message)
    sys.exit(1)


def sha256_of(path: Path) -> str:
    """Return the SHA-256 hash of the file's bytes as 64 hex characters."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def double_literal(value: float) -> str:
    """Return the shortest C double literal that gives back the same float64 value."""
    number = float(value)
    if not np.isfinite(number):
        raise ValueError(f"the value {number} cannot be a C literal")
    text = repr(number)
    if float(text) != number:
        raise ValueError(f"the text {text} does not give back {number!r}")
    return text


def float_literal(value: float) -> str:
    """Return the shortest C float literal that gives back the same float32 value."""
    number = np.float32(value)
    if not np.isfinite(number):
        raise ValueError(f"the value {number} cannot be a C literal")
    positional = np.format_float_positional(number, unique=True, trim="0")
    scientific = np.format_float_scientific(number, unique=True, trim="-")
    text = positional if len(positional) <= len(scientific) else scientific
    if np.float32(text).view(np.uint32) != number.view(np.uint32):
        raise ValueError(f"the text {text} does not give back {number!r}")
    return text + "f"


def model_numbers(package: ClassifierPackage) -> dict[str, np.ndarray | float]:
    """Check the model's shape and names, then return its 37 numbers and its cut-off."""
    scaler, classifier = package.scaler, package.classifier
    if list(scaler.feature_names_in_) != FEATURE_NAMES:
        fail(f"the scaler's feature names are {list(scaler.feature_names_in_)}, not mfcc_1 to mfcc_12")
    if list(classifier.feature_names_in_) != FEATURE_NAMES:
        fail(f"the classifier's feature names are {list(classifier.feature_names_in_)}, not mfcc_1 to mfcc_12")
    if not isinstance(classifier, LogisticRegression):
        fail(f"the classifier is a {type(classifier).__name__}, not a LogisticRegression")
    coef = np.atleast_2d(np.asarray(classifier.coef_, dtype=np.float64))
    if coef.shape != (1, plain.N_COEF):
        fail(f"the classifier has weights of shape {coef.shape}, not one row of {plain.N_COEF}")
    intercept = np.ravel(np.asarray(classifier.intercept_, dtype=np.float64))
    if intercept.size != 1:
        fail(f"the classifier has {intercept.size} offsets, not 1")
    return {
        "mean": np.asarray(scaler.mean_, dtype=np.float64),
        "scale": np.asarray(scaler.scale_, dtype=np.float64),
        "coef": coef[0],
        "intercept": float(intercept[0]),
        "threshold": float(package.threshold),
    }


def array_lines(values: Sequence[str], indent: str) -> list[str]:
    """Split the literals into lines of VALUES_PER_LINE values each."""
    lines: list[str] = []
    for start in range(0, len(values), VALUES_PER_LINE):
        lines.append(indent + ", ".join(values[start:start + VALUES_PER_LINE]) + ",")
    return lines


def vector(ctype: str, name: str, size: str, literals: list[str]) -> list[str]:
    """Return the C lines for a one-dimensional array."""
    return [f"static const {ctype} {name}[{size}] = {{", *array_lines(literals, "    "), "};", ""]


def matrix(name: str, rows: str, cols: str, table: np.ndarray) -> list[str]:
    """Return the C lines for a float table, with one table row on each line."""
    lines = [f"static const float {name}[{rows}][{cols}] = {{"]
    for row in table:
        lines.append("    { " + ", ".join(float_literal(v) for v in row) + " },")
    return [*lines, "};", ""]


def header_text(model: dict[str, np.ndarray | float], tables: dict[str, np.ndarray], digest: str) -> str:
    n_bins = plain.SPG_NFFT // 2 + 1
    comment = [
        "/*",
        " * detector_tables.h holds the fixed numbers of the tremor detector.",
        " *",
        " * tools/gen_tables.py made this file. Nobody edits it by hand.",
        " * This command makes it again from the repo root.",
        " *",
        f" *     {COMMAND}",
        " *",
        f" * The numbers come from ParaDigMa {version('paradigma')} with scikit-learn {version('scikit-learn')}.",
        " * The model file has this SHA-256 hash.",
        " *",
        f" *     {digest}",
        " *",
        " * The model numbers are 64-bit doubles and keep the toolbox's values exactly.",
        " * The tables are 32-bit floats and come from build_tables() in",
        " * reference/plain_detector.py. Only one C file in each program includes this",
        " * header, because it holds static arrays.",
        " *",
        " * The tremor detector comes from ParaDigMa by the Radboud Parkinson's group,",
        " * which has an Apache 2.0 licence. The source paper is Timmermans and",
        " * colleagues, npj Parkinson's Disease, 2025.",
        " */",
        "",
    ]
    lines = [
        *comment,
        "#ifndef DETECTOR_TABLES_H",
        "#define DETECTOR_TABLES_H",
        "",
        f'#define DET_MODEL_SHA256 "{digest}"',
        "",
        f"#define DET_N_COEF {plain.N_COEF}",
        f"#define DET_N_FILT {plain.N_FILT}",
        f"#define DET_N_BINS {n_bins}",
        f"#define DET_PSD_SEG {plain.PSD_SEG}",
        f"#define DET_SPG_SEG {plain.SPG_SEG}",
        "",
        *vector("double", "det_mean", "DET_N_COEF", [double_literal(v) for v in model["mean"]]),
        *vector("double", "det_scale", "DET_N_COEF", [double_literal(v) for v in model["scale"]]),
        *vector("double", "det_coef", "DET_N_COEF", [double_literal(v) for v in model["coef"]]),
        f"static const double det_intercept = {double_literal(model['intercept'])};",
        f"static const double det_threshold = {double_literal(model['threshold'])};",
        "",
        *vector("float", "det_w_psd", "DET_PSD_SEG", [float_literal(v) for v in tables["w_psd"]]),
        *vector("float", "det_w_spg", "DET_SPG_SEG", [float_literal(v) for v in tables["w_spg"]]),
        *matrix("det_filters", "DET_N_FILT", "DET_N_BINS", tables["filters"]),
        *matrix("det_dct", "DET_N_COEF", "DET_N_FILT", tables["dct"]),
        "#endif /* DETECTOR_TABLES_H */",
    ]
    return "\n".join(lines) + "\n"


def check_tables(tables: dict[str, np.ndarray]) -> None:
    """Stop the run if a table from plain_detector.py has an unexpected shape."""
    n_bins = plain.SPG_NFFT // 2 + 1
    shapes = {
        "w_psd": (plain.PSD_SEG,),
        "w_spg": (plain.SPG_SEG,),
        "filters": (plain.N_FILT, n_bins),
        "dct": (plain.N_COEF, plain.N_FILT),
    }
    for name, shape in shapes.items():
        if tables[name].shape != shape:
            fail(f"the table {name} has shape {tables[name].shape}, not {shape}")


def parse_args(argv: Sequence[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the detector's fixed numbers into a C header.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="the header to write")
    parser.add_argument("--model", type=Path, default=DEFAULT_MODEL, help="the toolbox's model file")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Check the model file, build the header text, and write it."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    args = parse_args(argv)

    digest = sha256_of(args.model)
    if digest != EXPECTED_SHA256:
        fail(f"the model file {args.model} has SHA-256 {digest}, not {EXPECTED_SHA256}")

    model = model_numbers(ClassifierPackage.load(args.model))
    tables = plain.build_tables()
    check_tables(tables)
    text = header_text(model, tables, digest)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="ascii", newline="\n")
    logger.info("wrote %s", args.out)
    logger.info("model file SHA-256 %s", digest)


if __name__ == "__main__":
    main()
