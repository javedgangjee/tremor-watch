# Feature 3 validation: Generated tables

Every command runs from the repo root. Every check is automated.

## Automated checks

1. The header matches the toolbox and plain_detector.py.
   - The command is `reference/.venv/bin/python -m pytest tests/tools -q`.
   - The tests compile tests/tools/dump_tables.c with core/detector_tables.h and read back every value it prints. "The header values" below means these values read back from the compiled program.
   - The test cases are below.
     1. A header made by tools/gen_tables.py with `--out` set to a temporary file is the same byte for byte as the committed core/detector_tables.h.
     2. The command `cc -std=c11 -Wall -Wextra -Werror -pedantic -ffp-contract=off -I core` compiles dump_tables.c with no warning, and the program exits with code 0.
     3. The size macros are DET_N_COEF 12, DET_N_FILT 15, DET_N_BINS 101, DET_PSD_SEG 300, and DET_SPG_SEG 200.
     4. The 12 means, 12 spreads, 12 weights, and the offset in the header equal the toolbox's scaler.mean_, scaler.scale_, classifier.coef_, and classifier.intercept_ exactly as 64-bit floats. They count 37 numbers. The first spread is about 2.541389, the first weight is about 0.84610178, and the offset is about -5.8764059.
     5. The header's cut-off equals the package's threshold exactly as a 64-bit float, which is 0.029570239921802. It lies within 0.00005 of 0.0296.
     6. The 300 values of det_w_psd equal the float32 rounding of hann_symmetric(300) from plain_detector.py bit for bit. Each lies within 1e-7 of scipy get_window("hann", 300, fftbins=False). Values 0 and 299 are 0, and values 149 and 150 are equal and about 0.9999724.
     7. The 200 values of det_w_spg equal the float32 rounding of hann_periodic(200) from plain_detector.py bit for bit. Each lies within 1e-7 of scipy get_window("hann", 200). Value 0 is 0, value 100 is 1, and value 1 equals value 199.
     8. The 15 by 101 values of det_filters equal the float32 rounding of build_tables()["filters"] bit for bit. The 17 edge points are 1, 3, 5, 7, 10, 12, 15, 18, 21, 24, 27, 30, 34, 38, 42, 46, and 51. Filter j is above zero at steps p[j] to p[j+2] − 1 and is zero at every other step, which gives 93 values above zero. Each filter sums to 2 within 1e-6. The largest value of filter 0 is 0.75, and the largest value of filter 14 is 0.4, each within 1e-7.
     9. The 12 by 15 values of det_dct equal the float32 rounding of build_tables()["dct"] bit for bit. Every value in row 0 equals the float32 rounding of 1 / sqrt(15), which is about 0.2581989. Row 1 at column 0 lies within 1e-7 of cos(π / 30) × sqrt(2 / 15), which is about 0.36314806.
     10. The toolbox's own filter bank agrees with the header. The input is 50 seeded random coarse spectra, each of 101 steps by 6 slices with values from 0 to 500. paradigma.feature_extraction.compute_mfccs runs on them with total_power_type "spectrogram", rounding_method "round", multiplication_factor 1, and a TremorConfig set to 100 readings a second. The header's filter and cosine tables run on the same input in float64. The 12 numbers agree within 1e-6. The planning run measured 1.3e-7.
     11. DET_MODEL_SHA256 equals the SHA-256 hash of the installed model file, and both equal 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e.
     12. The header gives plain_detector.py the same answers as its own tables. The input is 200 windows made as reference/compare.py makes them, with seed 1 and 40 windows of each of rest, tremor, small tremor, walk, and walk with tremor. detect() runs in float32 once with the header's tables and model numbers and once with build_tables() and the package's model numbers. The 12 numbers, the probability, the peak, the low-frequency sum, and the tremor answer are equal on all 200 windows.
     13. The header gives answers that match the toolbox. The input is the 200 windows from case 12. The toolbox runs on them as one recording, as in reference/compare.py, and detect() runs in float32 with the header's tables and model numbers. The 12 numbers differ by at most 1.5e-6, the probability differs by at most 7e-7, and the tremor answer agrees on 200 of 200 windows. These limits come from the plan's Measured so far section.
     14. A copy of the model file with its last byte changed, given with `--model`, makes tools/gen_tables.py exit with a code other than 0. Its log names the hash it found, and it writes no file at the `--out` path.
     15. The comment at the top of core/detector_tables.h contains "tools/gen_tables.py", the command `reference/.venv/bin/python tools/gen_tables.py`, "ParaDigMa 1.1.2", "scikit-learn 1.6.0", "Apache 2.0", "Timmermans", and the model file's hash. It contains no date.
     16. Every function in tools/gen_tables.py has a type hint on each argument and on its return. The file contains no `print(`, no `os.path`, and no `except Exception`.
   - The expected result is 16 passed.

2. The header can be made again from the command line.
   - The command is `d=$(mktemp -d) && reference/.venv/bin/python tools/gen_tables.py --out "$d/detector_tables.h" && cmp core/detector_tables.h "$d/detector_tables.h" && echo same`.
   - The expected result is exit code 0 and the single word same.

3. The Python reference has not changed.
   - The command is `git diff main --stat -- reference/ context/ && reference/.venv/bin/python reference/compare.py`.
   - The git command prints nothing.
   - compare.py gives the same float64 and float32 lines as feature 2 validation check 3, and the tremor label agrees on 200 of 200 windows in both.

4. The repo holds the right files.
   - The command is `git diff main --stat` on the feature branch after the implement commit.
   - The expected result lists core/detector_tables.h, tools/gen_tables.py, tests/tools/dump_tables.c, tests/tools/test_gen_tables.py, specs/tech-stack.md, specs/roadmap.md, and the three files in specs/features/03-generated-tables/. It lists no other file.

## Requirement coverage

Requirement 1 is covered by checks 1 (case 1), 2, and 4. Requirement 2 is covered by check 1 cases 4 and 5. Requirement 3 is covered by check 1 case 6. Requirement 4 is covered by check 1 case 7. Requirement 5 is covered by check 1 cases 8 and 10. Requirement 6 is covered by check 1 cases 9 and 10. Requirement 7 is covered by check 1 case 11. Requirement 8 is covered by check 1 cases 6 to 13. Requirement 9 is covered by check 1 cases 4, 5, and 14, and by check 3. Requirement 10 is covered by check 1 cases 12 and 13. Requirement 11 is covered by check 1 case 2. Requirement 12 is covered by check 1 case 15. Requirement 13 is covered by check 1 case 16 and by check 1 itself. Requirement 14 is covered by check 1 cases 2 and 3. Requirement 15 is covered by check 1 cases 4 to 9. Requirement 16 is covered by check 1 cases 6 to 9 and 12, and by check 3. Requirement 17 is covered by check 1 cases 1 and 14. Requirement 18 is covered by check 1 case 14. Requirement 19 is covered by check 1 case 1 and check 2. Requirement 20 is covered by check 1 case 15. Requirement 21 is covered by check 1 case 11. Requirement 22 is covered by check 1 cases 3 and 12. Requirement 23 is covered by check 1. Requirement 24 is covered by check 4.

## Results

The checks ran on 22 October 2026 on branch feature/03-generated-tables at commit 3409f66. Every check passed.

1. Check 1 passed. pytest reported 16 passed, and it gave the same result again after the test cache was cleared. Each of the 16 tests matches its case as written. Case 10 uses seed 10 for its random spectra, as plan.md records.
2. Check 2 passed. The script wrote the header to a temporary folder, logged the hash 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e, and printed same with exit code 0.
3. Check 3 passed. The git command printed nothing. compare.py gave the same lines as feature 2 check 3. In float64 the largest mfcc difference was 3.55e-15 and the largest prob difference was 8.88e-16. In float32 they were 1.24e-06 and 2.02e-07. The tremor label agreed on 200 of 200 windows in both.
4. Check 4 passed. The stat lists core/detector_tables.h, tools/gen_tables.py, tests/tools/dump_tables.c, tests/tools/test_gen_tables.py, specs/tech-stack.md, specs/roadmap.md, and the three files in specs/features/03-generated-tables/. It lists no other file.

Every item in requirements.md has at least one passing check. Requirement 18 names three cases that stop the run, and check 1 case 14 tests only the first one, which is the wrong hash. A reading of tools/gen_tables.py shows that it also stops on wrong feature names and on a classifier that is not a logistic regression with one row of 12 weights, but no test runs those two cases. A reading of the header shows no date, user name, or machine path, which supports requirement 19.
