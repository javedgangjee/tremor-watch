# Feature 8 validation: Pipeline and state tasks

Every command runs from the repo root. Checks 1 to 7 run on the laptop, and checks 1 to 4 need no toolbox. Checks 8 and 9 run on the watch and are judged by a script. Checks 10 and 11 need a person to look at the screen or move the watch, so they wait for the user. The ESP-IDF shell comes from `. ~/.espressif/tools/activate_idf_v6.1.sh`, and SCRATCH means the session's scratch folder.

The watch lies still on a table during this loop. So the watch checks cannot show a real tremor answer or the response time with a real shake. Feature 12 measures both on the wrist, and check 11 lets the user try one shake sooner. The sensor fault rule, the end request, and the dose due path cannot be made to happen on a still watch, so checks 1 and 5 test them on the laptop.

The limits in check 8 come from Build order step 5, as test_detector.c uses them. The answer gap in check 9 item 4 comes from feature 7's measured burst of 11 readings at about 114.35 readings a second. A window completes once every 100 samples, which is about 114.35 readings, so the wait between two answers is 10 or 11 bursts. That is 0.962 or 1.058 seconds, and the limit of 0.9 to 1.1 seconds leaves about 40 milliseconds on each side for the read and the run. Feature 7 measured the largest read delay at 5.6 milliseconds. The detector run time has no limit, because the build spec gives none.

## Automated checks

1. The new rules build and pass their C tests.
   - The command is `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure`.
   - The nine tests from features 4 to 7 run unchanged.
   - In the cases in tests/pipeline/test_pipeline.c, reading i on axis a is the float ((7i + 13a) mod 101) / 8 - 6, which needs no maths library. Stream A is stretch 0 with first reading 0, t0 5,000,000 microseconds, and 3,427 readings in 149 bursts of 23. Each burst goes in two parts of 16 and 7 readings, and only the first part carries flags. The first part has RT_NEW_STRETCH. The parts carry rate 0 until the first burst whose first reading is at least 1,144, which carries RT_RATE_SET and rate 114330200 on its first part, and every later part carries that rate.
     1. PIPE_FAULT_AFTER_US is 2000000, PIPE_FAULT_EVERY_US is 1000000, and PIPE_STRETCH, PIPE_END, and PIPE_DROP are 1, 2, and 4.
     2. Stream A goes through pipe_part(), pipe_push(), and pipe_window() after each part. Only the first part returns PIPE_STRETCH, and no call returns PIPE_END or PIPE_DROP. A reference run calls conv_start(), conv_set_rate(114330200), conv_push() for every reading, and conv_block() with win_push_block() until no block is left. The pipe gives the same number of windows as the reference, which is at least 25, with the same numbers in the same order, and every value equal bit for bit. The time of window n is 5,000,000 + 10,000 × (100n + 399).
     3. After stream A, a part with RT_NEW_STRETCH and RT_RATE_SET for stretch 1, first reading 3,441, t0 50,000,000, and rate 114330200 returns PIPE_STRETCH. pipe_stretch() gives number 1, first reading 3,441, t0 50,000,000, and rate 114330200. After 1,495 more readings in 65 bursts in the same pattern, the windows start again at 0, they equal a reference run of those 1,495 readings bit for bit, and window n has the time 50,000,000 + 10,000 × (100n + 399).
     4. In stream A, the part that should start at reading 575 starts at reading 598 instead. That part returns PIPE_END and PIPE_DROP, pipe_end_stretch() gives 0, and pipe_end_reason() gives PIPE_REASON_BREAK. Every later part of stretch 0 returns PIPE_DROP alone, and pipe_window() gives no window. A part with RT_NEW_STRETCH for stretch 1 then returns PIPE_STRETCH, and its stream gives windows again.
     5. After the parts of stream A up to reading 230, a part for stretch 1 without RT_NEW_STRETCH returns PIPE_END and PIPE_DROP, pipe_end_stretch() gives 1, and pipe_end_reason() gives PIPE_REASON_MISSED_START. A second such part returns PIPE_DROP alone. A part with RT_NEW_STRETCH for stretch 2 returns PIPE_STRETCH.
     6. A stretch whose parts all carry rate 0 takes 2,048 readings, and each pipe_push() returns 0. The next pipe_push() returns PIPE_END, and pipe_end_reason() gives PIPE_REASON_RING_FULL. The push after that returns 0, and the next part returns PIPE_DROP.
     7. A stretch whose parts all carry rate 40000000 gives no window, the refused rate count is 1, and the 2,049th reading returns PIPE_END with PIPE_REASON_RING_FULL.
     8. After pipe_init() at 1,000,000, pipe_next_fault_us() gives 3,000,000. pipe_fault_due() is false at 2,999,999, true at 3,000,000, false at 3,000,000 again and at 3,999,999, and true at 4,000,000. A part at 4,500,000 moves the next fault time to 6,500,000, and pipe_fault_due() is false at 6,499,999 and true at 6,500,000. A part that returns PIPE_DROP also moves the fault time.
   - The cases in tests/session/test_session.c are below. Session time starts at 1,000,000 microseconds, and window n of a stretch with t0 T has the time T + 10,000 × (100n + 399).
     1. After sess_init(), the shown state is Waiting, share_percent() returns false, and every count is 0.
     2. In stretch 0 with t0 2,000,000, window 0 has code warming up and windows 1 to 12 have code no tremor. Only window 2's call returns SESS_FACE_CHANGED, and the shown state is then No tremor. SESS_COUNTED comes for windows 4, 8, and 12 only. The share is 0.0 from 3 still windows.
     3. A list of 40 codes that cycles through 0 to 4, with windows 0 to 39, goes to a sess_t and to a share_t and a face_t that are driven directly with share_add() and face_answer(). After each call, the shown state, the detector state, the share counts, and the last tremor time agree.
     4. From No tremor, sess_stretch(s, 1) returns SESS_FACE_CHANGED, the shown state is Waiting, and gaps is 1. On a new sess_t, sess_stretch(s, 0) returns 0, and gaps stays 0. After the gap, window 0 with warming up and window 1 with no tremor leave Waiting, and window 2 with no tremor shows No tremor.
     5. From No tremor, a first fault answer with no window returns 0, and a second returns SESS_FACE_CHANGED and shows Waiting. A fault answer passed with window 4 and has_window false is not counted. answers[RES_SENSOR_FAULT] is 2, and the share counts do not change.
     6. The clock offset, the schedule "Levodopa" at 08:00, and the times follow test_dose.c. The test calls dose_set_clock() and dose_set_schedule() on the session's dose_t at 06:00:00 and calls sess_tick() at every whole second from 07:59:58 to 08:15:01. The tick at 08:00:00 returns SESS_FACE_CHANGED and SESS_TONE, and the shown state is Dose due. Two tremor answers at 08:01 keep Dose due on show, return no SESS_FACE_CHANGED, and set the detector state to Tremor. The tick at 08:15:00 returns SESS_FACE_CHANGED alone, and the shown state is Tremor. No other tick returns a flag.
     7. After case 6, a dose taken with dose_took_it() at 08:20:00, and sess_new_session() at 08:30:00, the shown state is Waiting, share_percent() returns false, the answer counts are 0, and dose_count() is 0. dose_next() at 08:30:00 gives 08:00 on the next day, so the schedule and the clock stay.
   - The expected result is that the build prints no warning, and CTest reports 100% tests passed out of 11.

2. The new C code uses no heap, no ESP-IDF header, no changing static data, and no 112.1.
   1. `nm -u build/core/libtremor_core.a | grep -E '^_?(malloc|calloc|realloc|free|aligned_alloc|posix_memalign)$'` prints nothing.
   2. `grep -rnE '#include *[<"](esp_|freertos/|driver/|sdkconfig)' core/` prints nothing.
   3. `nm build/core/CMakeFiles/tremor_core.dir/pipeline.c.o build/core/CMakeFiles/tremor_core.dir/session.c.o | grep -E ' [bBdD] '` prints nothing.
   4. `grep -rnE '112\.1|\b1121\b|112100' core/pipeline.* core/session.* tests/pipeline tests/session tests/firmware/*.py firmware/main firmware/detector_check/main firmware/detector_check/CMakeLists.txt firmware/detector_check/sdkconfig.defaults` prints nothing.
   5. `cmake --build build --clean-first 2>&1 | grep -i warning` prints nothing.

3. The commit checks and both ESP-IDF projects build.
   1. The commands are `rm -rf build firmware/build firmware/detector_check/build` and then `env -i HOME="$HOME" PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin make check > SCRATCH/check.log 2>&1`. The exit code is 0. The log shows "100% tests passed out of 11", then "model hash matches", then "Project build complete", in that order.
   2. In an ESP-IDF shell, `idf.py -C firmware/detector_check build` exits with code 0.
   3. The command of feature 7's check 4 item 1, run once on firmware/build/compile_commands.json and once on firmware/detector_check/build/compile_commands.json, prints twelve lines each time. They add pipeline.c and session.c to feature 7's ten names. Every line has True in the first column, the ten project files have True in the second column, and the two KISS FFT files have False.
   4. `xtensa-esp32s3-elf-nm -u firmware/build/esp-idf/core/libcore.a | grep -wE 'malloc|calloc|realloc|free|aligned_alloc|posix_memalign'` prints nothing.
   5. `grep -E '(firmware/main|firmware/detector_check/main|/core/)[^ ]*: warning:' SCRATCH/check.log` prints nothing.

4. The firmware source follows the design.
   1. `ls firmware/main` lists the same eleven files as in feature 7.
   2. `grep -lE 'lv_[a-z]|bsp_display_' firmware/main/*` prints only firmware/main/screen_task.c, and `grep -rlE 'lv_[a-z]|bsp_' firmware/detector_check/main` prints nothing.
   3. `grep -lw printf firmware/main/*` prints only firmware/main/usb_task.c.
   4. `grep -lE '\bdet_(init|run)\(' firmware/main/*` prints only firmware/main/pipeline_task.c, and so does `grep -lE '\bpipe_[a-z_]+\(' firmware/main/*`.
   5. `grep -lE '\bsess_[a-z_]+\(' firmware/main/*` prints only firmware/main/state_task.c.
   6. `grep -nE '\b(conv|win)_[a-z_]+\(|\b(share_add|share_start|face_answer|face_gap|face_init|face_set_dose_due|dose_init|dose_tick|dose_new_session)\(' firmware/main/*` prints nothing, so the firmware changes the state only through core/pipeline.c and core/session.c.
   7. `grep -rnE 'nvs_|esp_partition_write|spi_flash_write|fopen' firmware/main firmware/detector_check/main` prints nothing.

5. The Python tests pass.
   - The command is `reference/.venv/bin/python -m pytest tests -q`.
   - The 56 cases from features 2 to 7 run unchanged.
   - The cases in tests/firmware/test_chip_windows.py are below.
     1. windows_bytes() on tests/detector/windows.csv gives 1,545,600 bytes. They equal `np.loadtxt(path, delimiter=",", skiprows=1, dtype=np.float64).astype("<f4").tobytes()`. With numpy, the test finds every value whose 64-bit value lies within two 64-bit steps of the halfway point between its 32-bit float and either neighbour. For each such value it checks with fractions.Fraction that the 32-bit float is the nearest to the text. The test logs how many values it checked this way.
     2. The rule function gets one toolbox row and one chip row. Unless a part says otherwise, the toolbox row has a probability of 0.5, a low-frequency sum of 10, a peak of 5.0 Hz, a peak gap of 0.5, the arm at rest, and tremor. A chip row equal to it passes. A probability 0.00015 higher fails, and so does an mfcc_7 0.00015 higher. With the toolbox probability at the cut-off plus 0.00005, a chip row that differs only in the tremor answer passes, and at the cut-off plus 0.0005 it fails. A chip row that differs only in both answers passes when the toolbox sum is 50.004 and fails when it is 50.006. A chip row with a peak of 8.0 Hz and no tremor passes when the toolbox peak gap is 0.00005 and fails when it is 0.0002.
     3. A made-up log has a CHECK_CRC line with 0xcbf43926, a CHECK_START line with the CRC-32 of the bytes of part 1, two passes of 322 CHECK_WINDOW lines with the toolbox's own numbers from answers.csv, and a CHECK_END line. chip_windows.py's main() with `--log-only` exits with code 0 and writes a report.
     4. Four changed copies of that log each give exit code 1. One misses window 17 in pass 2, one has a different probability text for window 5 in pass 2, one has a wrong CRC-32 on CHECK_START, and one has 0x00000000 on CHECK_CRC.
     5. Every function in windows_bin.py, chip_windows.py, and pipeline_run.py has a type hint on each argument and on its return. The three files contain no `print(`, no `os.path`, and no `except Exception`, and no line in them starts with `import serial`.
   - The cases in tests/firmware/test_pipeline_run.py are below. Each writes a made-up log to a temporary file and calls pipeline_run.py's main() with `--log-only`, `--minutes 3`, and `--report` set to a temporary file. The clean log holds feature 7's lines for a clean 3-minute run as in test_table_run.py case 1 with no stretch end, a DETECTOR_INIT line with ok=1, ANSWER lines for windows 0 to 5 at 10.1 seconds after t0 and then one each second up to the last minute line, with code 3 for window 0 and code 1 for the rest, one FACE line with state 1 after window 2, and STATE_MINUTE and SCREEN_MINUTE lines whose counts match.
     1. The clean log gives exit code 0, and the report gives the run time and the delay measurements.
     2. Six changed copies each give exit code 1. One repeats window 40, one gives window 50 code 2, one gives the FACE line state 0, one adds an END_REQUEST line, one moves an answer so that it comes 1.3 seconds after the one before, and one adds 1 to share_still in the last STATE_MINUTE line.
     3. A log with a stretch end of the second kind at 100 seconds, a GAP line for stretch 1, a FACE line with state 3, answers for stretch 1 from window 0, and a FACE line with state 1 after its window 2 gives exit code 0. The report says that the gap path ran on the watch. The same log without the GAP line gives exit code 1.
     4. Every function in pipeline_run.py and the two test files has a type hint on each argument and on its return.
   - The expected result is 65 passed.

6. The reference, the earlier code, and the earlier records have not changed.
   - The command is `git diff 2940181 --stat -- reference/ context/ core/kissfft/ core/detector.h core/detector.c core/detector_tables.h core/reading_time.h core/reading_time.c core/converter.h core/converter.c core/window.h core/window.c core/share.h core/share.c core/face.h core/face.c core/dose.h core/dose.c core/imu_units.h core/imu_units.c core/replay.c tools/ tests/unity/ tests/detector/ tests/reading_time/ tests/converter/ tests/window/ tests/share/ tests/face/ tests/dose/ tests/response/ tests/pads/ tests/reference/ tests/tools/ tests/imu_units/ tests/model/ tests/firmware/table_run.py tests/firmware/test_table_run.py tests/firmware/table_log.txt tests/firmware/table_report.md firmware/bringup/ firmware/components/ Makefile`.
   - The command prints nothing.

7. The repo holds the right files.
   - The command is `git diff 2940181 --stat` on the feature branch after the validate commit.
   - The expected result lists .gitignore, specs/roadmap.md, specs/tech-stack.md, the three files in specs/features/08-pipeline-state/, core/CMakeLists.txt, core/pipeline.h, core/pipeline.c, core/session.h, core/session.c, tests/CMakeLists.txt, tests/pipeline/test_pipeline.c, tests/session/test_session.c, firmware/main/tasks.h, firmware/main/main.c, firmware/main/sensor_task.c, firmware/main/pipeline_task.c, firmware/main/state_task.c, firmware/main/screen_task.c, the files of firmware/detector_check/ other than its build/ folder, tests/firmware/windows_bin.py, tests/firmware/chip_windows.py, tests/firmware/test_chip_windows.py, tests/firmware/pipeline_run.py, tests/firmware/test_pipeline_run.py, tests/firmware/chip_windows_log.txt, tests/firmware/chip_windows_report.md, tests/firmware/pipeline_log.txt, and tests/firmware/pipeline_report.md. firmware/sdkconfig and firmware/dependencies.lock may appear only if the build changed them. The list holds no other file.

8. The saved windows run on the chip and match the toolbox.
   - The commands are `idf.py -C firmware/detector_check -p /dev/cu.usbmodem101 flash` in an ESP-IDF shell, which must exit with code 0, and then `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/chip_windows.py`. Nothing else may use the port meanwhile.
   - The expected result is exit code 0, which means that every pass check below holds. The script writes tests/firmware/chip_windows_log.txt and tests/firmware/chip_windows_report.md.
     1. The log holds one CHECK_CRC line with 0xcbf43926, which is the CRC-32 of "123456789" in Python's zlib. So the chip's CRC follows the same rule as zlib.
     2. The log holds one CHECK_START line with windows=322, bytes=1545600, and the CRC-32 that zlib gives for windows_bytes() of tests/detector/windows.csv.
     3. The log holds 644 CHECK_WINDOW lines, and each pass holds windows 0 to 321 once. A CHECK_END line with runs=644 follows them. After CHECK_CRC no line starts with "rst:" and no line holds "Guru Meditation" or "abort()".
     4. In pass 1, on every window, each of the 12 numbers and the probability differ from answers.csv by 0.0001 or less. On every window that is not near a cut-off, the tremor answer and the arm at rest answer equal the toolbox's. On every window that is not near a peak tie, the peak equals the toolbox's freq_peak. Near a cut-off and near a peak tie mean what they mean in test_detector.c.
     5. In pass 2, every number and answer has the same text as in pass 1.
   - The Results section records these measurements from the report with no limit. They are the largest difference in the 12 numbers and in the probability, the largest relative difference in the low-frequency sum, the counts of windows near a cut-off, near a peak tie, with a different answer, and with a different peak, and the minimum, median, and maximum run time of each pass. It also gives the laptop's numbers that test_detector prints, for comparison.
   - After this check, `idf.py -C firmware -p /dev/cu.usbmodem101 flash` puts the watch firmware back, and it must exit with code 0.

9. The watch runs the pipeline and the state task on a table for 30 minutes.
   - The watch lies still on a table on USB power with firmware/ flashed. The command is `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/pipeline_run.py`. It runs for about 31 minutes, so it runs in the background, and nothing else may use the port meanwhile.
   - The expected result is exit code 0, which means that every pass check below holds. The script writes tests/firmware/pipeline_log.txt and tests/firmware/pipeline_report.md.
     1. All 13 pass checks of tests/firmware/table_run.py hold on the same log with 30 minutes.
     2. The log holds one DETECTOR_INIT line, and it has ok=1. No line starts with PIPELINE_ERROR or END_REQUEST.
     3. In each stretch the ANSWER window numbers count up from 0 by one. Window 0 has code 3. Every other answer has code 0 or 1, because the arm is at rest on a table and a wrong unit would make the arm at rest check fire on everything or on nothing. No answer has code 4 or window=none.
     4. In each stretch, for each two answers in a row that both have an at_us at least 15 seconds after the stretch's t0, the second at_us minus the first lies from 900,000 to 1,100,000 microseconds. The 15 seconds leave out the first stretch's catch-up after its rate comes at 10 seconds. At least one ANSWER line has an at_us from 1,798,900,000 to 1,800,000,000 microseconds, so the answers kept coming up to minute 30. This part does not apply when a stretch started in the last 15 seconds.
     5. Each STRETCH line after stretch 0 is followed by one GAP line with its number, and the GAP line comes before the first ANSWER line of that stretch.
     6. The face model of plan step 10, run over the GAP and ANSWER lines in log order, gives the face field of every ANSWER line and the state of every FACE line in the same order. No FACE line comes without a change in the model.
     7. At every STATE_MINUTE line, share_tremor, share_still, and share_moving equal the counts of the ANSWER lines before it that the share counts, which are windows above 0 whose number divides by 4 with code 0, 1, or 2. Those answers have counted=1, and every other answer has counted=0. share is none when share_still is 0, and otherwise it is share_tremor / share_still × 100 to 6 places.
     8. At minute 30, PIPELINE_MINUTE shows faults=0, end_requests=0, and answer_drops=0, STATE_MINUTE shows screen_drops=0, and SENSOR_MINUTE shows pipeline=0.
     9. At minute 30, SCREEN_MINUTE shows the face of the last FACE line before it, and its face_changes equals the number of FACE lines before it or one fewer.
   - The Results section records these measurements from the report with no limit. They are the minimum, median, and maximum run_us over all answers, the median and maximum delay_us, the time from each stretch's t0 to its window 0 answer, the counts of answers by code, the share at the end, the number of face changes, the stack_free values, and whether a stretch end let the gap path run on the watch. A tremor answer on a still table is a false alarm, and the count goes in the Results for information.

## Manual checks

10. The holding screen shows the face state.
    - Look at the watch during check 9 or right after it.
    - The expected result is that the screen shows "Tremor log", the uptime, and "No tremor" under them. In the first few seconds after a reset it shows "Waiting".

11. A shake shows Tremor.
    - Run `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/pipeline_run.py --minutes 2 --log SCRATCH/shake_log.txt --report SCRATCH/shake_report.md`. Wear the watch, rest the forearm on a table, wait for "No tremor", then shake the hand from the wrist 4 to 6 times a second for 20 seconds, as the plan's Response time section says. The script's exit code does not matter here, because the shake breaks the still checks.
    - The expected result is that the screen shows "Tremor" during the shake and "No tremor" again within about 6.5 seconds after it stops. `grep -c 'code=0' SCRATCH/shake_log.txt` prints a number above 0, and the log holds a FACE line with state 0. Feature 12 measures the response time properly.

## Requirement coverage

Requirement 1 is covered by checks 4 and 9. Requirement 2 is covered by check 1 test_pipeline cases 2 and 3 and check 9 item 3. Requirement 3 is covered by check 9 item 4. Requirement 4 is covered by check 1 test_session case 2 and check 9 item 7. Requirement 5 is covered by check 1 test_session cases 3 and 5 and check 9 items 3 and 7. Requirement 6 is covered by the run time measurements of checks 8 and 9. Requirement 7 is covered by check 8. Requirement 8 is covered by check 4 item 4 and check 9 item 2. Requirement 9 is covered by check 1 test_pipeline cases 2, 3, 6, and 7 and check 9 item 8. Requirement 10 is covered by check 1 test_pipeline cases 2 and 3 and check 9 item 3. Requirement 11 is covered by check 1 test_pipeline cases 2 to 5. Requirement 12 is covered by check 1 test_session and check 4 item 5. Requirement 13 is covered by check 1 test_session cases 3 and 6 and check 9 items 6 and 7. Requirement 14 is covered by check 1 test_session case 4 and check 9 items 5 and 6. Requirement 15 is covered by check 1 test_pipeline case 8 and test_session case 5. Requirement 16 is covered by check 4 items 2 to 6 and check 9 item 9. Requirement 17 is covered by check 4 item 7. Requirement 18 is covered by checks 2 and 3. Requirement 19 is covered by checks 2 and 6. Requirements 20 and 21 are covered by check 1 test_pipeline cases 2 to 7. Requirement 22 is covered by check 1 test_pipeline cases 4 to 6 and check 9 item 8. Requirement 23 is covered by check 1 test_pipeline case 8 and test_session case 5. Requirements 24 to 26 are covered by check 1 test_session cases 1 to 7. Requirement 27 is covered by check 9 items 1 and 6 to 8. Requirement 28 is covered by checks 8 and 9 and their measurements. Requirement 29 is covered by check 5 cases 1 to 4 of test_chip_windows.py and check 8. Requirement 30 is covered by check 9 item 9 and check 10. Requirement 31 is covered by check 5 and check 9. Requirement 32 is covered by check 3. Requirement 33 is covered by check 7 and a reading of specs/tech-stack.md.

## Results

The checks ran on 23 October 2026 on branch feature/08-pipeline-state at commit 940a6ac. The laptop build/ folder was removed before check 1, and check 3 removed build/, firmware/build/, and firmware/detector_check/build/ as it says. Every automated check passed. Checks 10 and 11 wait for the user, because nobody could look at the screen or touch the watch during this run. The USB port answered the whole time, so the reset helper was not needed. Check 8 ran before check 9, and the watch ran firmware/ during check 9 and stays flashed with it.

1. Check 1 passed. The build printed no warning, and CTest reported 100% tests passed out of 11. The nine earlier tests ran unchanged. A reading of tests/pipeline/test_pipeline.c and tests/session/test_session.c found that their cases match their text here, with changes 6 and 7 of plan.md as the readings of session case 5 and pipeline case 3.
2. Check 2 passed. Items 1 to 5 printed nothing. In item 3, nm read both object files, and they hold no data or bss symbol.
3. Check 3 passed. `make check` in the empty environment exited with code 0 after about 41 seconds. The log shows "100% tests passed out of 11", then "model hash matches", then "Project build complete", in that order. `idf.py -C firmware/detector_check build` exited with code 0. Item 3 printed twelve lines for each project, with True in the first column on every line, True in the second column for the ten project files, and False for the two KISS FFT files. Items 4 and 5 printed nothing.
4. Check 4 passed. Item 1 listed the eleven files of feature 7. Item 2 printed only screen_task.c, and its second grep printed nothing. Item 3 printed only usb_task.c. Item 4 printed only pipeline_task.c both times, and item 5 printed only state_task.c. Items 6 and 7 printed nothing.
5. Check 5 passed. pytest reported 65 passed. The halfway point search in case 1 of test_chip_windows.py found 0 values, so the exact fraction step did not run on any value. The CSV holds values that make_windows.py wrote as 32-bit floats, so this is expected.
6. Check 6 passed. The command printed nothing.
7. Check 7 passed. With the validate files staged, `git diff --cached 2940181 --stat` lists 35 files, which equals the diff after the validate commit. They are the 31 files that the check names apart from the four output files, and the four output files. firmware/sdkconfig and firmware/dependencies.lock did not change, and the list holds no other file.
8. Check 8 passed. The flash of firmware/detector_check exited with code 0, and chip_windows.py exited with code 0 after about 17 seconds. All five pass checks held. The flash of firmware/ afterwards exited with code 0.
   - CHECK_CRC gave 0xcbf43926, and CHECK_START gave windows=322, bytes=1545600, and crc32=0x841aeb95. A separate run of zlib on windows_bytes() gave 0x841aeb95.
   - The log holds 644 CHECK_WINDOW lines and CHECK_END runs=644. The only "rst:" line is the boot line before CHECK_CRC.
   - A separate script read pass 1 against answers.csv and found the same largest differences as the report.
9. Check 9 passed. pipeline_run.py exited with code 0 after about 31 minutes. All 13 pass checks of table_run.py and all 8 pass checks of this feature held.
   - The log holds one DETECTOR_INIT line with ok=1, and no PIPELINE_ERROR, END_REQUEST, GAP, or TONE line.
   - The run had one stretch. Stretch 0 started at t0 238216 microseconds, took the rate 114351469 from its first 10 seconds, and had not ended when the run stopped. So no drift end came in 30 minutes, and the gap path did not run on the watch. Item 5 holds only because no later stretch exists.
   - The answers ran from window 0 to window 1795 with no gap in the numbers. The last at_us was 1,799,378,537 microseconds. After the first 15 seconds, the wait between two answers lay from 961,902 to 1,058,186 microseconds.
   - At minute 30, PIPELINE_MINUTE gave windows=1796, faults=0, end_requests=0, answer_drops=0, and rate_refused=0. STATE_MINUTE gave screen_drops=0, and SENSOR_MINUTE gave pipeline=0. Every loss count was 0, and USB_MINUTE gave line_drops=0.
   - SCREEN_MINUTE at minute 30 gave updates=1800, face=1, and face_changes=1.

### Table run measurements

| Measure | Value |
|---|---|
| Detector run time, minimum, median, and maximum | 6769, 6869, and 8803 microseconds |
| Delay from the burst's stamp to the end of the run, median and maximum | 12422 and 62675 microseconds |
| Time from t0 to the window 0 answer | 10.020 seconds |
| Answers by code | 0 tremor, 1795 no tremor, 0 arm moving, 1 warming up, 0 sensor fault |
| Share at minute 30 | 0.000000 from 448 still windows |
| Face changes | 1, from Waiting to No tremor at 10.28 seconds after boot |
| Pipeline task free stack | 2576 bytes at minute 1, 2368 at minute 2, and 2240 from minute 3 to minute 30 |
| State task free stack | 2536 bytes at minute 1, 2520 at minute 2, and 2488 from minute 3 to minute 30 |

- No tremor answer came on the still table, so the run had no false alarm. The largest probability was 0.00127. The low-frequency sum lay from 0.48 to 0.69, which is far below 50, so the arm at rest check held on every window.
- Windows 0 to 9 waited for the rate at 10 seconds and then ran one after the other. The largest run time of 8803 microseconds and the largest delay of 62675 microseconds both came in this catch-up, on windows 3 and 5. After it, the run times lay near 6870 microseconds.
- From window 10 on, each answer came 65 to 162 milliseconds after the time of its window's last 100 Hz sample, with a median of 113 milliseconds. The wait comes from the converter, which needs 16 extra readings after each block, and from the bursts of 11 readings. The time rule gives each burst's stamp to its first reading, so the later readings of a burst arrive before their rule times, and this makes the wait shorter than the 140 milliseconds that 16 readings take.

### Saved windows on the chip

| Measure | Chip, pass 1 | Laptop, test_detector |
|---|---|---|
| Largest difference in the 12 numbers | 3.66e-06 | 3.6e-06 |
| Largest difference in the probability | 2.66e-07 | 2.71e-07 |
| Largest relative difference in the low-frequency sum | 1.1e-06 | 1.1e-06 |
| Windows near a cut-off, and of them near a peak tie | 31 and 11 | 31 and 11 |
| Windows with a different answer, and with a different peak | 0 and 0 | 0 and 0 |

| Pass | Minimum run time | Median run time | Maximum run time |
|---|---|---|---|
| 1 | 6603 microseconds | 6612.5 microseconds | 6803 microseconds |
| 2 | 6603 microseconds | 6619 microseconds | 6646 microseconds |

The largest run time in pass 1 came on window 0, the first run after start. The detector takes about 6.6 milliseconds on the chip with the 64-bit scoring step in software and the -Og build. Inside the watch firmware it takes about 6.9 milliseconds, because the other tasks share the chip. Both are under 1 percent of the 1 second between answers.

### Manual checks

10. Check 10 waits for the user. The log shows that the screen task took 1800 messages and that its face field matches the last FACE line, but nobody looked at the screen.
11. The screen part of check 11 passed on 2026-10-23. The user rested the forearm on a table, shook the hand from the wrist, and the screen showed "Tremor". A first try that moved the whole arm showed "Arm moving", as the build spec says it should. The log part of check 11 did not run, and the user moved it to feature 12, which measures the shake response on the wrist with logs.

### Requirement coverage

Every item in requirements.md has at least one passing check, with these limits.

- Requirement 14 says that the state task calls face_gap() at each new stretch after a gap. Session case 4 passes on the laptop, but no stretch ended during the table run, so the gap path did not run on the watch.
- Requirement 15 and requirement 23 say how a failed sensor reaches the face. Only the laptop cases test them, because a still watch never stops its sensor.
- Requirement 22 has two halves. Pipeline cases 4 to 6 test the pipe's end request on the laptop. The sensor task's half, which reads the end queue and ends the stretch with reason=pipeline, did not run in any check, because no end request came on the watch. Check 9 item 8 shows only that pipeline=0.
- Requirement 30 says that the holding screen shows the face state. Check 9 item 9 shows that the screen task took the face, and check 10 waits for the user.
- Requirement 33 holds, because specs/tech-stack.md records every item that it lists.

### Judgments

Change 6 reads session case 5 in the right way. The case text names a first fault answer, a second fault answer, and a fault answer with window 4, and it then says that answers[RES_SENSOR_FAULT] is 2. Only one reading lets every sentence hold, which is that the second fault answer is the one passed with window 4 and has_window false. The test asserts exactly that, and the return value SESS_FACE_CHANGED with no SESS_COUNTED shows that the answer was not counted. The case is weaker than it looks, because share_add() never counts a fault code. So it would still pass if sess_answer() ignored has_window. The firmware never sends a code from 0 to 2 without a window, so this has no effect now.

The free stack of the pipeline task is not a risk in this feature. The task has 4096 bytes and used at most 1856 of them, so 2240 bytes, which is 55 percent, stayed free. The deepest call is usb_send() with the PIPELINE_MINUTE line, because it holds a 320-byte line on the stack and runs vsnprintf() with doubles. That call ran every minute. The paths that did not run, which are END_REQUEST and the fault answer, call the same usb_send() with fewer values or send a smaller message. The free stack fell from 2576 to 2240 bytes over the first 3 minutes and then stayed at 2240 for 27 minutes. So the peak depends a little on timing, probably through interrupts that land in deep calls, and a margin of 2240 bytes covers that. The firmware also builds with the FreeRTOS stack canary, which stops the chip with an error if a stack overflows. Feature 9 adds the recording lines, and if the pipeline task formats them, its free stack needs a new reading. The state task kept 2488 of 4096 bytes free.

### Against the build spec

A reading of core/pipeline.c, core/session.c, and firmware/main/ beside the build spec's Windows, Response time, and Firmware design sections finds that the code follows these rules for the parts that this feature builds.

- The pipeline task runs the detector only after a sensor message, on each window that the converter completes. So the runs follow the readings and never a timer. Window n holds samples 100n to 100n + 399, and its time is t0 + 10,000 × (100n + 399) microseconds.
- Every answer goes to the face, so the face gets a new answer each second. The share counts only windows above 0 whose number divides by 4, and it counts only tremor, no tremor, and arm moving. Window 0 has the code warming up.
- Every answer carries one code from core/window.h. The state task passes the code unchanged to share_add() and face_answer(), so the two-in-a-row rule changes only what the face shows.
- The pipeline task is the only caller of det_init() and det_run(). It calls det_init() once before the first window. The state task owns the share, the face, and the doses through core/session.c, and core/ has unit tests for both new files.
- The tasks talk through queues and never wait on a full queue. The detector runs on core 1, and the screen task runs on core 0. The screen task took 1800 messages in 30 minutes with no drop, so the detector runs did not hold up the screen.
- The firmware writes nothing to flash, and answers stay in memory.

The code goes beyond the build spec's words or leaves gaps in these places. None of them fails a check.

- The build spec says that the detector runs on window n as soon as reading 100n + 399 exists. The converter makes a block only when its 16 extra readings after the block are in, so each answer comes about 113 milliseconds after its window's last sample by the time rule's clock. In the first stretch no window runs until the rate comes at 10 seconds, and then windows 0 to 9 run one after the other. Both waits come from the build spec's own converter and time rule, so they follow the build spec.
- The build spec says that Waiting shows when the sensor has failed, and it gives no time. Requirement 23 sends the first fault answer after 2 seconds with no sensor message, so the face shows Waiting about 3 seconds after the sensor stops. This is the agent's choice.
- The session share starts when the state task starts, and requirement 25 times each answer at its window's last sample. The build spec gives neither rule.
- The holding screen calls face_name() from core/face.h to turn the state number into a word. The screen task still draws only the state that the state task sends.
- ESP-IDF's own log lines at level INFO still reach the serial port, as feature 7 found. Feature 9 handles this.

None of the nine changes in plan.md's "Changes during implement" goes against the build spec. Changes 1 to 5 set a line length, a flag that stops repeated rate tries, the out of sync rule for windows, the fields of a fault answer, and which counts a new session clears. The build spec says nothing about them. Changes 6 and 7 are readings of the test cases, and the judgment above covers change 6. Changes 8 and 9 are build settings and a note on specs/tech-stack.md. The user accepted each change on 27 October 2026.
