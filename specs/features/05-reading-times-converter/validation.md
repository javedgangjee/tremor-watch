# Feature 5 validation: Reading times and converter

Every command runs from the repo root. Every check is automated, and every check runs on the laptop. Checks 1 and 2 need no toolbox. Check 3 needs the reference venv.

The one match limit comes from Build order step 8 of the plan. The C converter must agree with the toolbox within 0.001 degrees per second outside window 0 of each stretch, and requirement 28 applies it to every sample from sample 100 on. No other limit applies to the converter. The 60 second floor in check 1 case 10 comes from the plan's words that a stretch "is minutes long". A planning model of the converter on 22 October 2026 ran the same steps as requirement 25 in numpy float32 against the toolbox. From sample 100 on, its largest gap was 7.0e-6 on mixed signals at four rates from 50 to 150 readings a second, 3.1e-5 on noise at exactly 100 readings a second, 4.9e-5 on 45 and 55 Hz parts, 1.4e-4 on noise with a spread of 200, and 1.6e-4 on the clipped shake. These numbers are for information and are not limits.

## Automated checks

1. The time rule and the converter build and pass their C tests.
   - The command is `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure`.
   - test_detector runs unchanged.
   - The cases in tests/reading_time/test_reading_time.c are below. Each stream uses bursts of 11 readings that start at reading 0, and the first stamp is 1,000,000 microseconds. "Half a period" at 114330200 is 5e11 / 114330200, which is 4373.3 microseconds.
     1. A steady stream of 60 seconds at 114330200 makes one stretch. It has number 0, first reading 0, and t0 equal to the first stamp. Its rate is 0 until the first burst whose stamp is at least 10,000,000 microseconds after t0, and that burst returns RT_RATE_SET. The rate equals `floor(df * 1e12 / ds + 0.5)` from the first burst to that burst, and it lies within 10 of 114330200. No later burst returns a flag.
     2. Case 1 gives the same results at 50000000 and at 150000000, with the rate within 10 of each.
     3. A stream of 60 seconds at 114330200 runs steady for 30 seconds, and then every later stamp moves by a fixed shift. A shift of +4353 microseconds starts no stretch. A shift of +4393 or -4393 microseconds starts stretch 1 at the first moved burst, with that burst's first reading and t0 equal to its stamp.
     4. A steady stream at 114330200 has the overflow flag set on one burst at 30 seconds, with an on-time stamp. That burst starts stretch 1.
     5. A steady stream at 114330200 has a shift of 50,000 microseconds at 30 seconds. The first burst of stretch 1 returns both RT_NEW_STRETCH and RT_RATE_SET. Its rate equals `floor(df * 1e12 / ds + 0.5)` from the first burst to the last burst of stretch 0.
     6. Two streams at 114330200 check the 10 second rule of requirement 21. In the first, a shift of 50,000 microseconds at 5 seconds starts stretch 1 before stretch 0 has a rate, and stretch 1 has rate 0 until its own first 10 seconds pass. In the second, stretch 0 runs 30 seconds and stretch 1 runs 5 seconds, each ended by a shift of 50,000 microseconds. Stretch 2 then has rate 0 until its own first 10 seconds pass.
     7. A steady stream of 60 seconds at 114330200 has a shift of 50,000 microseconds at 0.5 seconds, before the stretch spans 1 second. That burst starts no stretch. The stream ends in a stretch that started before 25 seconds, lasts to the last burst, and has a rate within 10 of 114330200.
     8. In a steady stream at 114330200 with its rate known, a stamp equal to the stamp before starts a new stretch, a first reading number that skips one reading starts a new stretch, and a burst with no readings returns no flag and leaves the stretch unchanged.
     9. For a stretch with t0 of 5,000,000,000 microseconds, first reading 1000, and rate 114330200, rt_reading_time_us() gives exactly 5,000,000,000 for reading 1000 and exactly 1,005,000,000,000 for reading 114,331,200. It gives a value within 0.00001 of 5,000,008,746.5953877 for reading 1001. rt_sample_time_us() gives exactly 8,600,000,000 for sample 360,000.
     10. A stream of twenty minutes uses the twenty one-minute rates from firmware/bringup/rate_log.txt, with each rate held for its minute. Every burst that starts no stretch lies within half a period of its stretch's prediction, once that stretch has a rate. Every burst that starts a stretch, except the first, lies more than half a period from the prediction of the stretch before. Every stretch after the first takes its rate from the whole stretch before it, as requirement 21 says. Each stretch except the last lasts at least 60 seconds. The test prints the number of stretches and the length and rate of each one.
   - The cases in tests/converter/test_converter.c are below.
     1. conv_set_rate() returns false for 49999999 and for 150000001. It returns true for 50000000, and after conv_start() it returns true for 150000000. A second call in the same stretch returns false.
     2. At 114330200, conv_position() gives reading 0 and fraction 0 for sample 0, reading 14114 and the float nearest 0.06319 for sample 12345, and reading 1143302000 and fraction 0 for sample 1,000,000,000. At 50000000 it gives reading 1 and fraction 0.5 for sample 3.
     3. A stretch of 2000 zero readings at 114330200 gives only samples that are exactly 0. The number of blocks is the number of b from 0 up with `floor((100b + 99) * rate_uhz / 1e8) + 17` at most 1999.
     4. The test reads 8 stretches from tests/converter/stretches.csv, their readings from readings.csv, and the toolbox's samples from expected.csv. It runs every stretch through one conv_t in order, with conv_start() before each stretch and the rate set before the first reading. For each stretch, the number of blocks follows the rule in case 3 with the stretch's reading count, and no C sample lies past the toolbox's last sample. Every C sample from sample 100 on lies within 0.001 degrees per second of the toolbox's sample on each axis. The test prints the largest gap from sample 100 on, the largest gap before sample 100, and the number of samples compared.
     5. Stretch mix_114 runs three more times, through a new conv_t each time. The first run pushes bursts of 11 readings and calls conv_block() after each burst until it returns false. The second run pushes bursts of 1 to 13 readings in turn. The third run sets the rate only after the first 1200 readings. All three runs give the same samples as case 4, bit for bit.
     6. After conv_start() with no rate, 2048 calls to conv_push() return true and the next one returns false. With the rate set and no call to conv_block(), the same holds.
     7. A converter that takes the first 1000 readings of mix_114, then conv_start() and the whole of mix_50, gives the same samples for mix_50 as case 4, bit for bit.
   - The expected result is that the build prints no warning, and CTest reports 100% tests passed out of 3.

2. The new C code uses no heap, no ESP-IDF header, no changing static data, and no 112.1.
   - The commands are below, and each one runs after check 1.
     1. `nm -u build/core/libtremor_core.a | grep -E '^_?(malloc|calloc|realloc|free|aligned_alloc|posix_memalign)$'` prints nothing.
     2. `grep -rnE '#include *[<"](esp_|freertos/|driver/|sdkconfig)' core/` prints nothing.
     3. `nm build/core/CMakeFiles/tremor_core.dir/reading_time.c.o build/core/CMakeFiles/tremor_core.dir/converter.c.o | grep -E ' [bBdD] '` prints nothing.
     4. `grep -nE '112\.1|\b1121\b|112100' core/*.c core/*.h tests/reading_time/*.c tests/converter/*.c tests/converter/*.py` prints nothing.
     5. `cmake --build build --clean-first 2>&1 | grep -i warning` prints nothing.

3. The Python tests pass.
   - The command is `reference/.venv/bin/python -m pytest tests -q`.
   - The 42 cases from features 2 to 4 run unchanged.
   - The cases in tests/converter/test_make_cases.py are below.
     1. make_cases.py with `--out` set to a temporary folder writes a stretches.csv, a readings.csv, and an expected.csv that are the same byte for byte as the committed files.
     2. stretches.csv holds the 8 stretches of requirement 29 with their names and rates. readings.csv holds `floor(30 * rate_uhz / 1e6)` readings for each stretch. Every reading times 32 is a whole number from -32768 to 32767, and the zeros stretch holds only zeros.
     3. For each stretch, expected.csv numbers its samples from 0 up, and their count equals the length of `np.arange(0, t_last, 0.01)`, where t_last is `(readings - 1) * 1e6 / rate_uhz`.
     4. In stretch mix_100, every expected sample equals the reading with the same number within 1e-9 degrees per second.
     5. Every function in make_cases.py has a type hint on each argument and on its return. The file contains no `print(`, no `os.path`, and no `except Exception`.
   - The expected result is 47 passed.

4. The reference, the detector, and the tables have not changed.
   - The command is `git diff d4834b9 --stat -- reference/ context/ core/detector.h core/detector.c core/detector_tables.h core/replay.c tools/ tests/detector/ tests/pads/ tests/reference/ tests/tools/`.
   - The command prints nothing.

5. The repo holds the right files.
   - The command is `git diff d4834b9 --stat` on the feature branch after the implement commit.
   - The expected result lists core/CMakeLists.txt, core/reading_time.h, core/reading_time.c, core/converter.h, core/converter.c, tests/CMakeLists.txt, tests/reading_time/test_reading_time.c, tests/converter/make_cases.py, tests/converter/stretches.csv, tests/converter/readings.csv, tests/converter/expected.csv, tests/converter/test_converter.c, tests/converter/test_make_cases.py, specs/tech-stack.md, specs/roadmap.md, and the three files in specs/features/05-reading-times-converter/. It lists no other file.

## Requirement coverage

Requirement 1 is covered by check 1 test_reading_time cases 1 and 9. Requirement 2 is covered by test_reading_time cases 1, 5, and 10. Requirement 3 is covered by test_reading_time cases 3, 4, and 10. Requirement 4 is covered by test_reading_time case 9 and by the types in requirement 19, which check 1 builds. Requirement 5 is covered by check 1, which builds the time rule into tremor_core. Requirement 6 is covered by check 2 item 4 and by test_reading_time cases 1, 2, and 10. Requirement 7 is covered by test_converter cases 3 and 4. Requirement 8 is covered by test_converter cases 4 and 7. Requirement 9 is covered by test_converter case 4 on stretch above_50hz. Requirement 10 is covered by check 2 and by check 1, which builds on the laptop. Requirement 11 is covered by test_converter case 4 and check 3 cases 1 to 4. Requirement 12 is covered by test_converter case 4, which reads only CSV files. Requirement 13 is covered by check 3 case 3. Requirement 14 is covered by test_converter case 4. Requirement 15 is covered by checks 1 and 3. Requirement 16 is covered by check 4. Requirement 17 is covered by check 2 item 3 and test_converter cases 5 and 7. Requirements 18 and 19 are covered by test_reading_time cases 1, 3, 5, and 9. Requirement 20 is covered by test_reading_time case 1. Requirement 21 is covered by test_reading_time cases 5 and 6. Requirement 22 is covered by test_reading_time cases 4, 6, 7, and 8. Requirement 23 is covered by test_converter cases 2 to 5. Requirement 24 is covered by test_converter cases 3, 4, and 7. Requirement 25 is covered by test_converter case 4. Requirement 26 is covered by test_converter cases 1, 5, and 6. Requirement 27 is covered by test_converter case 4. Requirement 28 is covered by test_converter case 4. Requirements 29 and 30 are covered by check 3 cases 1 to 4. Requirement 31 is covered by test_reading_time case 10. Requirement 32 is covered by check 5.
