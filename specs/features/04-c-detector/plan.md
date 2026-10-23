# Feature 4 plan: C detector and the PADS match

The steps run in this order. Every command runs from the repo root. No step changes a file in reference/ or context/, core/detector_tables.h, or tools/gen_tables.py. Never change plain_detector.py, the model file, a stored number, or a match limit to make a case pass. If a case can pass only that way, stop and report it.

1. Copy KISS FFT into core/kissfft/.
   - Take the files in requirement 21 from github.com/mborgerding/kissfft at commit 7bce4153c6bc8aba2db0e889e576f9d00505cbe1, which is tag 131.2.0. Do not change them.
   - The files are core/kissfft/kiss_fft.c, kiss_fft.h, kiss_fftr.c, kiss_fftr.h, _kiss_fft_guts.h, kiss_fft_log.h, COPYING, and LICENSES/BSD-3-Clause.

2. Copy Unity into tests/unity/.
   - Take src/unity.c, src/unity.h, src/unity_internals.h, and LICENSE.txt from github.com/ThrowTheSwitch/Unity at commit cbcd08fa7de711053a3deec6339ee89cad5d2697, which is tag v2.6.1. Do not change them.

3. Write core/detector.h and core/detector.c with the interface in requirement 24.
   - detector.c is the only file in core/ that includes detector_tables.h. It checks with a static assert that DET_MFCC_COUNT equals DET_N_COEF and that DET_WINDOW_LEN is 400.
   - det_init() asks kiss_fftr_alloc for the size it needs for 400 and for 200, checks that each fits in a fixed static buffer, and builds each configuration in its buffer. It returns false if a size does not fit. It can run more than once.
   - det_run() follows detect() in reference/plain_detector.py in the float32 case, line by line. The fine spectrum uses the scale (float)(1.0 / (100.0 × the float sum of the window squared)), squares each FFT value, multiplies by the scale, doubles steps 1 to 199, divides by 2, and adds the result into the fine spectrum. The coarse spectrum divides each FFT value by the float sum of the window, takes the square root of the sum of squares, multiplies by 100, and adds the three axes. The bands use the filter table, log10f(band + 1e-10f), the cosine table, and a division by 6. The score uses doubles as in requirement 20. The peak is the first largest step from 4 to 100, which is 1 to 25 Hz, and peak_hz is the step times 0.25. The low-frequency sum adds steps 2 to 11 in float and multiplies the sum by 0.25 as a double. The arm is at rest when the sum is 50 or less. The tremor answer needs the model's yes, a peak from 3 to 7 Hz with both ends included, and the arm at rest.
   - Each recipe number that the header does not hold, such as 1e-10, 50, 0.25, and the 3 to 7 Hz band, is a named constant at the top of detector.c with a comment that names its toolbox setting in TremorConfig.

4. Write core/replay.c as in requirement 32.
   - It reads a PADS file line by line with strtod into a static buffer of 4096 rows. Every PADS file holds 1024 or 2048 rows. A longer file stops replay with an error message and exit code 1.
   - It exits with code 1 and a message on stderr when the file cannot be read, a line has fewer than 7 values, or det_init() fails. A file with fewer than 450 rows prints the header and no window.

5. Write the CMake files from requirement 25 with the flags from requirement 26.
   - CMakeLists.txt at the root sets C11, enables CTest, and adds core/ and tests/.
   - core/CMakeLists.txt builds the static library tremor_core from detector.c, kissfft/kiss_fft.c, and kissfft/kiss_fftr.c, and links the maths library. It sets `KISS_FFT_MALLOC(n)=((void *)0)` and `KISS_FFT_FREE(p)=((void)0)` as compile definitions on the library. It builds replay from replay.c.
   - tests/CMakeLists.txt builds Unity and tests/detector/test_detector.c and registers the test with CTest. It passes the path of tests/detector/ to the test as a compile definition.
   - Add `/build/` to .gitignore.

6. Write tests/detector/make_windows.py as in requirements 28, 30, and 31.
   - It follows the user's Python rules. It copies the window maker from reference/compare.py, as tests/tools/test_gen_tables.py does, and does not import compare.py.
   - It rounds every window to float32 before the toolbox sees it. It tunes each window near a cut-off by bisection on one amplitude, and each step of the bisection runs the toolbox on the rounded window.
   - It then runs the toolbox once on all 322 windows as one recording, as reference/compare.py does, and writes the answers from that run. It checks that every tuned window still lies in its target band in that run and that the welch peak equals freq_peak on every window. It stops with an error and writes no file if a check fails.
   - It takes `--out` with a default of tests/detector/.
   - Run `reference/.venv/bin/python tests/detector/make_windows.py` to make windows.csv and answers.csv.

7. Write tests/detector/test_detector.c with the cases in validation.md check 1. It prints the largest difference in the 12 numbers, the probability, and the low-frequency sum on the saved windows, and the count of windows near a cut-off.

8. Write tests/detector/test_make_windows.py with the cases in validation.md check 3.

9. Write tests/pads/pads_match.py as in requirements 33 and 34.
   - It imports read_gyroscope, cut_start, load_groups, TASKS, WRISTS, and MODEL_FILE from reference/pads_counts.py and does not copy them.
   - It takes `--data` with a default of data/pads, `--replay` with a default of build/core/replay, and `--out` with a default of tests/pads/pads_match.md.
   - The report states the run date, the ParaDigMa and scikit-learn versions, the model file's hash, DET_MODEL_SHA256 from core/detector_tables.h, the KISS FFT commit, the files and windows compared, the largest difference in the 12 numbers and in the probability, the largest relative difference in the low-frequency sum, the number of windows near a cut-off, every window where an answer or the peak differs, and every count row that differs from pads_counts.csv.
   - The rule is one function, match_window(), so the tests can call it directly.

10. Write tests/pads/test_pads_match.py with the cases in validation.md check 3.

11. Add cases 17, 18, and 19 from validation.md check 3 to tests/tools/test_gen_tables.py as in requirement 35.

12. Build and run every check.
    - Run `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure`.
    - Run `reference/.venv/bin/python -m pytest tests -q`.
    - Run `reference/.venv/bin/python tests/pads/pads_match.py` and commit the report it writes.
    - If a case fails, fix the C code or the test code, and run the checks again.

13. Update specs/tech-stack.md as in requirement 36. Under Shared C library, replace the line "Feature 4 pins the KISS FFT commit here" with the tag and commit, and add that the scoring step runs in 64-bit doubles. Under Tests and checks, add the Unity version, the CMake and CTest command, the replay command, and the PADS match command.

14. Set the status of feature 4 to in progress in specs/roadmap.md. This step is done in plan mode.

## Changes during implement

- numpy adds a float32 array in blocks of eight running sums, so `.sum()` in plain_detector.py does not add in plain order. core/detector.c copies that order in numpy_sum() for the two window sums and the low-frequency sum, so these sums give the same float as plain_detector.py. A plain loop gave a window sum of 112.12504 where numpy gives 112.125. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- numpy divides a complex64 value by a number as a multiply by the float 1 / number. The coarse spectrum in core/detector.c multiplies each FFT value by the float 1 / (sum of the window) for that reason, where step 3 says it divides. A plain divide differed in the last bit on 28 of 101 test values. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- CMake drops function-style macros from compile definitions. core/CMakeLists.txt passes `-DKISS_FFT_MALLOC(n)=((void *)0)` and `-DKISS_FFT_FREE(p)=((void)0)` as compiler options on tremor_core. The KISS FFT files stay unchanged. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- The log floor 1e-10 and the coarse gain of 100 are not TremorConfig settings. Their comments in core/detector.c name the toolbox function that holds them. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- Unity builds with UNITY_INCLUDE_DOUBLE, so the C tests can compare 64-bit values. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- windows.csv has the header gyroscope_x,gyroscope_y,gyroscope_z and one reading per row. answers.csv names each group as rest, tremor, small_tremor, walk, walk_plus_tremor, near_prob_tight, near_prob_above, near_prob_below, near_below_tight, near_below_above, near_below_below, peak_tie_tight, peak_tie_wide, peak_3.0, peak_7.0, peak_7.25, peak_2.75, zeros, or clipped. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- In make_windows.py, the tight windows alternate between the two sides of their cut-off. In the peak tie groups, the inside peak is larger in even windows and the outside peak in odd ones. A tuned window or a peak band window must also lie clear of every cut-off other than its own, so that only its own cut-off decides its answer. The all-zeros window has a peak gap of 0, because every step ties. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- A lone sine at 3.0 Hz or 2.75 Hz never made the model say yes. Each peak band window adds a second sine near 5 Hz at 85 to 97 percent of the main amplitude, so the model says yes and the main peak stays largest. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- pads_match.py also imports count_windows from reference/pads_counts.py, so the C counts use the same counting code. It imports fine_spectrum() and peak_gaps() from tests/detector/make_windows.py, so the welch copy of requirement 28 lives in one place. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
- The made-up PADS file in test_pads_match.py case 8 shakes at 0.5, 0.2, and 0.1 radians per second on the three axes, with noise of 0.02 radians per second. Validation names only the 0.5 radians per second shake. The agent decided this on 22 October 2026, and the user has not reviewed it yet.
