# Feature 3 requirements: Generated tables

## From the project documents

1. tools/gen_tables.py writes the detector's fixed numbers into a C header, and the header is committed. This comes from the plan's Build order step 3 and its Repo layout section.
2. The header holds the 12 means, the 12 spreads, the 12 weights, the offset, and the cut-off. These are the 37 stored numbers of the model plus its one cut-off, and the cut-off is about 0.0296. This comes from Build order step 3, the plan's Detector section, and its Detector recipe section.
3. The header holds the symmetric Hann window of 300 values, which is scipy get_window("hann", 300, fftbins=False). This comes from Build order step 3 and the fine spectrum step of the Detector recipe.
4. The header holds the periodic Hann window of 200 values, which is scipy get_window("hann", 200). This comes from Build order step 3 and the coarse spectrum step of the Detector recipe.
5. The header holds the 15 by 101 filter table. Its 17 edge points are spaced evenly on the scale 64.875 × log10(1 + f / 17.5) from 0 to 25 Hz and turned into step numbers with round(2 × f) + 1. Filter j is scipy triang(p[j+2] − p[j]) placed from step p[j] up to step p[j+2], and each filter is divided by 0.5 times its own sum. This comes from Build order step 3 and the band step of the Detector recipe.
6. The header holds the 12 by 15 cosine table. Row 0 is 1 / sqrt(15) everywhere, and row i at column k is cos(i × (2k + 1) × π / 30) × sqrt(2 / 15). This comes from Build order step 3 and the Detector recipe.
7. The header holds the SHA-256 hash of the toolbox's model file. This comes from Build order step 3 and the plan's Shared C library section.
8. The tables match what the toolbox does, because the C detector follows reference/plain_detector.py step for step and counts as correct only while it matches the toolbox. This comes from CLAUDE.md and the opening of the plan.
9. Nobody retrains the detector or changes its stored numbers. This comes from CLAUDE.md and the opening of the plan.
10. The C code never rebuilds the tables, because they come from tools/gen_tables.py. This comes from the Detector recipe section.
11. The header builds as plain C with -ffp-contract=off, and it allocates no memory at run time, because core/ has these rules. This comes from the plan's Shared C library section and specs/tech-stack.md.
12. The toolbox's Apache 2.0 licence needs a credit line. This comes from the plan's Detector section.
13. New Python code follows the user's Python rules, and the Python tests for tools/ use pytest. This comes from specs/tech-stack.md.

## Not covered by the project documents

Each item below is a choice the build spec and the existing code leave open.

14. The header is core/detector_tables.h. It is one header with an include guard, and it holds `static const` arrays, so only one C file in each program includes it. In the firmware and in replay that file is the detector's C file. The names follow plain_detector.py with a `det_` prefix, which gives det_mean, det_scale, det_coef, det_intercept, det_threshold, det_w_psd, det_w_spg, det_filters, and det_dct. The sizes are the macros DET_N_COEF (12), DET_N_FILT (15), DET_N_BINS (101), DET_PSD_SEG (300), and DET_SPG_SEG (200). The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

15. The 37 model numbers and the cut-off are stored as 64-bit `double` values, and each literal gives back the toolbox's float64 value exactly. The four tables are stored as 32-bit `float` values, and each one is the float32 rounding of the value from build_tables() in reference/plain_detector.py. This follows plain_detector.py step for step, because its 32-bit run rounds the tables to float32 and keeps the model numbers in float64. That 32-bit run gave the error that the plan's Measured so far section reports. Storing the model numbers as 64-bit values also keeps the stored numbers unchanged. Feature 4 decides whether the C scoring step runs in 64-bit or 32-bit floats. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

16. tools/gen_tables.py takes the four tables from build_tables() in reference/plain_detector.py, so the C tables and the Python reference have one source. It takes the model numbers from the toolbox's ClassifierPackage in the way reference/compare.py does. It runs in the reference venv, because it needs the toolbox. It does not change any file in reference/. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

17. tools/gen_tables.py takes `--out` with a default of core/detector_tables.h and `--model` with a default of the model file inside the installed toolbox. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

18. tools/gen_tables.py stops with an error and writes no file in three cases. The first case is a model file whose SHA-256 hash is not 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e, which feature 2 confirmed as the ParaDigMa 1.1.2 file. The second case is a scaler or a classifier whose feature names are not mfcc_1 to mfcc_12 in that order. The third case is a classifier that is not a logistic regression with one row of 12 weights. This keeps a different model from reaching the watch. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

19. The header is the same byte for byte each time the script runs. It holds no date, user name, or machine path, so a check can make it again and compare. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

20. The comment at the top of the header says that tools/gen_tables.py made it and that nobody edits it by hand. It gives the command that makes it again, the ParaDigMa version 1.1.2, the scikit-learn version 1.6.0, the model file's hash, and the credit line for ParaDigMa with its Apache 2.0 licence and the paper by Timmermans and colleagues, npj Parkinson's Disease, 2025. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

21. The header holds one hash, which is the model file's SHA-256. The plan's boot line and Status screen name a "table hash", and this feature treats it as the same hash. The hash is on one line in the form `#define DET_MODEL_SHA256 "<64 hex characters>"`, so the boot line and the commit check in feature 7 can read it. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

22. The header holds only the items that Build order step 3 lists. The C detector computes the sum of each Hann window and the sum of its squares at run time, as plain_detector.py does. The other recipe numbers, such as 1e-10, 50, and the 3 to 7 Hz band, live in the C detector in feature 4. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

23. The tests are tests/tools/test_gen_tables.py, and they run with pytest in the reference venv. They need the toolbox, so they are not one of the commit checks in feature 7. They compile tests/tools/dump_tables.c with the laptop's `cc`, and that program prints every value in the header so the tests can compare it with the toolbox and with plain_detector.py. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.

24. specs/tech-stack.md gains a line that names core/detector_tables.h, the command that makes it, and the types of its values. The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.
