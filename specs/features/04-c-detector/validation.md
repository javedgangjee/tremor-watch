# Feature 4 validation: C detector and the PADS match

Every command runs from the repo root. Every check is automated. Checks 1 and 2 need no toolbox. Checks 3 and 4 need the reference venv, and check 4 also needs PADS in data/pads/. Check 5 needs the network.

The match limits come from Build order step 5 of the plan. They are 0.0001 for each of the 12 numbers and for the probability, and the three near-cut-off conditions excuse an answer. Requirement 29 adds that the peak is equal outside near ties. No other limit applies. A planning run on 22 October 2026 put every PADS window through the float32 run of plain_detector.py. Its largest probability difference from pads_windows.csv was 4.6e-7, its largest relative difference in the low-frequency sum was 3.9e-7, and the answers and the peak agreed on all 26,264 windows. 23 windows were within 0.0001 of the probability cut-off or within 0.005 of 50. These numbers are for information and are not limits.

## Automated checks

1. The C detector builds and matches the saved windows.
   - The command is `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure`.
   - The test cases in tests/detector/test_detector.c are below.
     1. det_init() returns true on the first call and on a second call.
     2. A 400 point KISS FFT of cos(2π × 20 × i / 400) for i from 0 to 399 gives a magnitude within 0.001 of 200 at step 20 and below 0.001 at each of the other 200 steps.
     3. A 200 point KISS FFT of cos(2π × 10 × i / 200) for i from 0 to 199 gives a magnitude within 0.001 of 100 at step 10 and below 0.001 at each of the other 100 steps.
     4. det_run() on a window of zeros gives a peak of 1.0 Hz, a low-frequency sum of 0, the arm at rest, and no tremor. The toolbox gives the same answers for this window, with a probability of about 2.3e-10.
     5. The test reads 322 windows from tests/detector/windows.csv and 322 rows from tests/detector/answers.csv. On every window, each of the 12 numbers and the probability differ from the toolbox by 0.0001 or less. On every window that is not near a cut-off under requirement 27, the tremor answer and the arm at rest answer equal the toolbox's. On every window that is not near a peak tie, the peak equals the toolbox's freq_peak. The test prints the largest differences and the number of windows near a cut-off.
   - The expected result is that the build prints no warning, and CTest reports 100% tests passed.

2. The core library uses no heap and no ESP-IDF header.
   - The commands are below, and each one runs after check 1.
     1. `nm -u build/core/libtremor_core.a | grep -E '^_?(malloc|calloc|realloc|free|aligned_alloc|posix_memalign)$'` prints nothing.
     2. `grep -rnE '#include *[<"](esp_|freertos/|driver/|sdkconfig)' core/` prints nothing.
     3. `grep -rl 'detector_tables.h' core/ --include='*.c'` prints only core/detector.c.
     4. `cmake --build build --clean-first 2>&1 | grep -i warning` prints nothing.

3. The Python tests pass.
   - The command is `reference/.venv/bin/python -m pytest tests -q`.
   - The 9 cases in tests/reference/test_pads_counts.py and cases 1 to 16 in tests/tools/test_gen_tables.py run unchanged.
   - The new cases in tests/tools/test_gen_tables.py are below. Each case writes the changed package with ClassifierPackage.save to a temporary file, loads tools/gen_tables.py as a module, sets its EXPECTED_SHA256 to the hash of that file, and calls main() with `--model` set to the file and `--out` set to a temporary path.
     17. The scaler's and the classifier's feature names are mfcc_12 down to mfcc_1. main() exits with code 1, the log names the feature names it found, and no file exists at the `--out` path.
     18. The classifier is a scikit-learn DecisionTreeClassifier fitted on 20 seeded rows with the feature names mfcc_1 to mfcc_12. main() exits with code 1, the log names DecisionTreeClassifier, and no file exists at the `--out` path.
     19. The classifier is a LogisticRegression fitted on 30 seeded rows with three classes and the feature names mfcc_1 to mfcc_12, so its weights have the shape (3, 12). main() exits with code 1, the log names the shape (3, 12), and no file exists at the `--out` path.
   - The cases in tests/detector/test_make_windows.py are below.
     1. make_windows.py with `--out` set to a temporary folder writes a windows.csv and an answers.csv that are the same byte for byte as the committed files.
     2. windows.csv holds 128,800 readings, which is 322 windows of 400. Every value gives back the same text after a round trip through float32. answers.csv holds 322 rows with the group sizes in requirement 30.
     3. Every tuned window in answers.csv lies in its target band from requirement 30, measured with the toolbox's numbers in answers.csv.
     4. The welch spectrum of requirement 28 has its largest step at freq_peak on all 322 windows, and every peak gap is 0 or more.
     5. Every function in make_windows.py has a type hint on each argument and on its return. The file contains no `print(`, no `os.path`, and no `except Exception`.
   - The cases in tests/pads/test_pads_match.py are below. Cases 1 to 7 call match_window() with one toolbox row and one C row. Unless a case says otherwise, the toolbox row has a probability of 0.5, a low-frequency sum of 10, a peak of 5.0 Hz, a peak gap of 0.5, the arm at rest, and tremor.
     1. A C row equal to the toolbox row passes.
     2. A C row whose probability is 0.00015 higher fails.
     3. A C row whose mfcc_7 is 0.00015 higher fails.
     4. The toolbox probability is the cut-off plus 0.00005, and the C row differs only in the tremor answer. The row passes.
     5. The toolbox probability is the cut-off plus 0.0005, and the C row differs only in the tremor answer. The row fails.
     6. The C row differs only in the arm at rest answer and the tremor answer. It passes when the toolbox sum is 50.004 and fails when the toolbox sum is 50.006.
     7. The C row has a peak of 8.0 Hz and no tremor. It passes when the toolbox peak gap is 0.00005 and fails when the gap is 0.0002.
     8. The input is a made-up file in the PADS format with 1050 rows, made with seed 8 from a 5 Hz shake of 0.5 radians per second plus noise. Replay prints the header from requirement 32 and windows 0 to 6. Replay windows 0 and 4 pass match_window() against the toolbox's windows 0 and 1, which the test gets with read_gyroscope and cut_start from reference/pads_counts.py and the toolbox call that pads_match.py uses.
     9. Every function in pads_match.py has a type hint on each argument and on its return. The file contains no `print(`, no `os.path`, and no `except Exception`.
   - The expected result is 42 passed.

4. The C detector matches the toolbox on every PADS file.
   - The command is `reference/.venv/bin/python tests/pads/pads_match.py`, run after check 1.
   - The expected result is exit code 0 and a report at tests/pads/pads_match.md that states the items below.
     1. The run compared 10,318 files and 26,264 windows, and no file was missing.
     2. The toolbox run gave the same probability, low-frequency sum, peak, and answers as reference/results/pads_windows.csv on all 26,264 windows.
     3. Replay gave a window whose number divides by 4 for each of the 26,264 toolbox windows, and no extra one.
     4. The largest difference in the 12 numbers and the largest difference in the probability are each 0.0001 or less, and the report gives both values.
     5. Every window where an answer differs is near a cut-off under requirement 27, and every window where the peak differs is near a peak tie. The report lists each such window.
     6. The C counts equal reference/results/pads_counts.csv in every one of the 99 rows, or each row that differs is explained by windows listed under item 5.

5. The copied libraries match their pinned commits.
   - The command is below.

     ```
     d=$(mktemp -d)
     git clone -q https://github.com/mborgerding/kissfft.git "$d/kissfft"
     git -C "$d/kissfft" checkout -q 7bce4153c6bc8aba2db0e889e576f9d00505cbe1
     for f in kiss_fft.c kiss_fft.h kiss_fftr.c kiss_fftr.h _kiss_fft_guts.h kiss_fft_log.h COPYING LICENSES/BSD-3-Clause; do cmp "$d/kissfft/$f" "core/kissfft/$f"; done
     git clone -q https://github.com/ThrowTheSwitch/Unity.git "$d/unity"
     git -C "$d/unity" checkout -q cbcd08fa7de711053a3deec6339ee89cad5d2697
     for f in unity.c unity.h unity_internals.h; do cmp "$d/unity/src/$f" "tests/unity/$f"; done
     cmp "$d/unity/LICENSE.txt" tests/unity/LICENSE.txt && echo same
     ```

   - The expected result is exit code 0 and the single word same.

6. The reference and the tables have not changed.
   - The command is `git diff ff97364 --stat -- reference/ context/ core/detector_tables.h tools/gen_tables.py && d=$(mktemp -d) && reference/.venv/bin/python tools/gen_tables.py --out "$d/detector_tables.h" && cmp core/detector_tables.h "$d/detector_tables.h" && echo same`.
   - The git command prints nothing, and the last line is the single word same.

7. The repo holds the right files.
   - The command is `git diff ff97364 --stat` on the feature branch after the implement commit.
   - The expected result lists .gitignore, CMakeLists.txt, core/CMakeLists.txt, core/detector.h, core/detector.c, core/replay.c, the eight files in core/kissfft/, tests/CMakeLists.txt, the four files in tests/unity/, tests/detector/make_windows.py, tests/detector/windows.csv, tests/detector/answers.csv, tests/detector/test_detector.c, tests/detector/test_make_windows.py, tests/pads/pads_match.py, tests/pads/test_pads_match.py, tests/pads/pads_match.md, tests/tools/test_gen_tables.py, specs/tech-stack.md, specs/roadmap.md, and the three files in specs/features/04-c-detector/. It lists no other file.

## Requirement coverage

Requirement 1 is covered by check 1 case 5 and check 4. Requirement 2 is covered by checks 1 and 4, which run the float32 code. Requirement 3 is covered by check 1 cases 2 and 3 and by check 5. Requirement 4 is covered by check 2 item 3 and check 6. Requirement 5 is covered by check 1 cases 4 and 5 and by check 4. Requirement 6 is covered by check 1 case 5 and check 3 test_pads_match case 8. Requirement 7 is covered by check 2 and by check 1, which builds on the laptop. Requirement 8 is covered by check 3 test_make_windows cases 1 to 4. Requirement 9 is covered by check 1 case 5. Requirement 10 is covered by check 3 test_pads_match case 8 and by check 4. Requirement 11 is covered by check 3 test_pads_match case 8 and by check 4 item 2. Requirement 12 is covered by check 4. Requirement 13 is covered by check 4 items 1 and 4. Requirement 14 is covered by check 4 items 2 and 6. Requirement 15 is covered by check 1. Requirement 16 is covered by check 6. Requirement 17 is covered by check 3 test_gen_tables cases 17 to 19. Requirement 18 is covered by requirement 20 and by check 1 case 5. Requirement 19 is covered by check 3 test_make_windows case 5 and test_pads_match case 9. Requirement 20 is covered by check 1 case 5. Requirement 21 is covered by check 5. Requirement 22 is covered by check 1 case 1 and check 2 item 1. Requirement 23 is covered by check 5. Requirement 24 is covered by check 1. Requirement 25 is covered by checks 1 and 7. Requirement 26 is covered by check 1 and check 2 item 4. Requirements 27 and 29 are covered by check 1 case 5, check 3 test_pads_match cases 1 to 7, and check 4. Requirement 28 is covered by check 3 test_make_windows case 4. Requirements 30 and 31 are covered by check 3 test_make_windows cases 1 to 3. Requirement 32 is covered by check 3 test_pads_match case 8. Requirements 33 and 34 are covered by check 4. Requirement 35 is covered by check 3 test_gen_tables cases 17 to 19 and check 6. Requirement 36 is covered by check 7.
