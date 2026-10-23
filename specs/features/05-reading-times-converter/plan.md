# Feature 5 plan: Reading times and converter

The steps run in this order. Every command runs from the repo root. No step changes a file in reference/ or context/, core/detector.h, core/detector.c, core/detector_tables.h, core/replay.c, or tools/gen_tables.py. No source file in core/ or in the new test folders may hold the rate 112.1 in any form. Never change the 0.001 limit, a toolbox call, or a saved case to make a case pass. If a case can pass only that way, stop and report it.

1. Write core/reading_time.h and core/reading_time.c as in requirements 17 to 22.
   - The header defines rt_stretch_t with `uint32_t number`, `uint64_t first_reading`, `int64_t t0_us`, and `uint32_t rate_uhz`, where a rate of 0 means the rate is not known yet. It defines rt_state_t, which holds the current stretch, the first and the last burst of the current stretch, and the first and the last burst of the stretch before.
   - It defines the flags RT_NEW_STRETCH and RT_RATE_SET and the functions below.
     - `void rt_init(rt_state_t *s)` clears the state, so the next burst starts stretch 0.
     - `unsigned rt_burst(rt_state_t *s, uint64_t first_reading, uint32_t count, int64_t stamp_us, bool overflow)` applies the rule to one burst and returns the flags. A burst that starts a stretch and sets its rate at once returns both flags.
     - `const rt_stretch_t *rt_current(const rt_state_t *s)` gives the current stretch.
     - `double rt_reading_time_us(const rt_stretch_t *st, uint64_t reading)` gives the time of a reading as in requirement 19.
     - `int64_t rt_sample_time_us(const rt_stretch_t *st, uint64_t sample)` gives the time of a 100 Hz sample as in requirement 19.
   - Each fixed number, such as the 10 second rate span, the 1 second span of requirement 22, and 1e12, is a named constant at the top of reading_time.c with a comment that names its place in the plan's Sensor and converter section or in requirements.md.

2. Write core/converter.h and core/converter.c as in requirements 23 to 27.
   - The header defines CONV_AXES (3), CONV_OUT_HZ (100), CONV_MARGIN (16), CONV_BLOCK_SAMPLES (100), CONV_RING_LEN (2048), CONV_MAX_BLOCK (192), CONV_RATE_MIN_UHZ (50000000), and CONV_RATE_MAX_UHZ (150000000). It defines conv_t, which holds the ring, the rate, the stretch's reading count, the next block number, and the work arrays for one block.
   - It defines the functions below.
     - `void conv_start(conv_t *c)` starts a new stretch. It drops every reading, the rate, and any part block. It must run before the first use.
     - `bool conv_set_rate(conv_t *c, uint32_t rate_uhz)` sets the stretch's rate once. It returns false for a rate outside the range or a second call in the same stretch.
     - `bool conv_push(conv_t *c, const float reading[CONV_AXES])` adds the stretch's next reading. It returns false and keeps nothing when the ring has no free place.
     - `bool conv_block(conv_t *c, float out[CONV_BLOCK_SAMPLES][CONV_AXES], uint64_t *first_sample)` makes the next block when the rate is known and all its readings are in. It returns false and writes nothing otherwise.
     - `void conv_position(uint32_t rate_uhz, uint64_t sample, uint64_t *reading, float *frac)` gives the position of a sample as in requirement 23.
   - The solve and the curve follow requirement 25 in 32-bit floats. A reading leaves the ring only when no later block needs it.

3. Add reading_time.c and converter.c to tremor_core in core/CMakeLists.txt, with the TREMOR_WARNINGS flags that detector.c has.

4. Write tests/converter/make_cases.py as in requirements 29 and 30.
   - It follows the user's Python rules and builds each signal with numpy arrays and no loop over readings. It takes `--out` with a default of tests/converter/.
   - stretches.csv has the columns stretch, name, rate_uhz, and readings. A stretch holds `floor(30 * rate_uhz / 1e6)` readings.
   - readings.csv has the columns stretch, gyroscope_x, gyroscope_y, and gyroscope_z, with the readings of each stretch in order.
   - expected.csv has the columns stretch, sample, gyroscope_x, gyroscope_y, and gyroscope_z, with every sample the toolbox gives.
   - Before it writes, it checks that the toolbox's sample k of every stretch lies at k × 0.01 seconds within 1e-9 seconds. It stops with an error and writes no file if the check fails.
   - Run `reference/.venv/bin/python tests/converter/make_cases.py` to make the three files.

5. Write tests/reading_time/test_reading_time.c with the cases in validation.md check 1. A helper in the test builds a burst stream from a list of rates and stamp shifts. It uses bursts of 11 readings and stamps each burst at the time of its eleventh reading, rounded to a whole microsecond.

6. Write tests/converter/test_converter.c with the cases in validation.md check 1. It reads the three CSV files, runs every stretch through one conv_t in order with conv_start() before each stretch, and prints the largest gap from sample 100 on, the largest gap before sample 100, and the number of samples compared.

7. Add test_reading_time and test_converter to tests/CMakeLists.txt in the way test_detector is added. test_converter gets the path of tests/converter/ as a compile definition.

8. Write tests/converter/test_make_cases.py with the cases in validation.md check 3.

9. Build and run every check.
   - Run `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure`.
   - Run `reference/.venv/bin/python -m pytest tests -q`.
   - Run checks 2, 4, and 5 in validation.md.
   - If a case fails, fix the C code or the test code, and run the checks again.

10. Update specs/tech-stack.md as in requirement 32. Under Shared C library, add that the time rule and the converter live in core/, that a rate is a whole number of millionths of a reading per second, and the converter's block, margin, ring, and rate range. Under Tests and checks, add the command `reference/.venv/bin/python tests/converter/make_cases.py`, which makes the saved converter cases in tests/converter/.

11. Set the status of feature 5 to in progress in specs/roadmap.md. This step is done in plan mode.

## Changes during implement

The plan left a few details open, and the agent filled them as below.

- The first burst after rt_init() returns RT_NEW_STRETCH, because it starts stretch 0. Validation check 1 case 10 already counts it as the first burst that starts a stretch.
- reading_time.h also defines rt_burst_t, which holds one burst's first reading number, reading count, and stamp. rt_state_t holds a flag that says whether the first burst has come.
- A measured rate that rounds to 0 or does not fit in a `uint32_t` leaves the rate unknown. Real sensor rates never come near these ends.
- rt_reading_time_us() returns NAN for a stretch with no rate.
- In make_cases.py, the 45 Hz and 55 Hz parts of stretch above_50hz each have a seeded size from 50 to 100 degrees per second on each axis, the tremor burst in each mix stretch starts at phase 0, and stretch number i uses seed i + 1.

The agent decided this on 22 October 2026, and the user has not reviewed it yet.
