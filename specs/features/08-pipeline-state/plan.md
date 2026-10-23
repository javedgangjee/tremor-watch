# Feature 8 plan: Pipeline and state tasks

The steps run in this order. Every command runs from the repo root. Load ESP-IDF in each shell with `. ~/.espressif/tools/activate_idf_v6.1.sh`. The watch is on USB at /dev/cu.usbmodem101 and lies on a table. Nobody can look at its screen or touch it during the loop. If the port stops answering, run the USB reset helper that the stage prompt names.

No step changes a file in reference/, context/, core/kissfft/, tests/unity/, tools/, firmware/bringup/, or firmware/components/. No step changes an existing .c or .h file in core/, the Makefile, or an existing file in tests/ other than tests/CMakeLists.txt. tests/firmware/table_run.py, tests/firmware/test_table_run.py, tests/firmware/table_log.txt, and tests/firmware/table_report.md stay as they are. No new file may hold the rate 112.1 in any form. Never change a limit or a case in validation.md to make a case pass. If a case can pass only that way, stop and report it.

1. Write core/pipeline.h and core/pipeline.c as in requirements 20, 21, and 23.
   - The header includes reading_time.h, converter.h, and window.h. It defines PIPE_FAULT_AFTER_US (2000000) and PIPE_FAULT_EVERY_US (1000000). It defines the flags PIPE_STRETCH (1), PIPE_END (2), and PIPE_DROP (4), and the reasons PIPE_REASON_NONE, PIPE_REASON_BREAK, PIPE_REASON_MISSED_START, and PIPE_REASON_RING_FULL.
   - `pipe_part_t` holds the stretch number, the flags, the rate, the stamp, the first reading number, and the count of one sensor message. `pipe_t` holds the conv_t, the win_t, the current rt_stretch_t, whether a stretch has started, whether the pipe is in sync, the next reading number, whether the stretch has asked to end, the reason and the stretch number of the last request, the time of the last part, the next fault time, a 100 by 3 block buffer, and counts of stretches, end requests, refused rates, and fault answers.
   - `void pipe_init(pipe_t *p, int64_t now_us)` clears the pipe and sets the next fault time to now plus PIPE_FAULT_AFTER_US.
   - `unsigned pipe_part(pipe_t *p, const pipe_part_t *m, int64_t now_us)` applies requirement 21. It sets the time of the last part to now and the next fault time to now plus PIPE_FAULT_AFTER_US for every part. In sync, it calls conv_set_rate() once in each stretch, at the first part whose rate is not 0, and it counts a refusal.
   - `unsigned pipe_push(pipe_t *p, const float reading[CONV_AXES])` adds one reading and returns 0, or PIPE_END once when the ring is full. Out of sync it does nothing and returns 0.
   - `bool pipe_window(pipe_t *p, float window[DET_WINDOW_LEN][DET_AXES], uint32_t *number, int64_t *time_us)` calls conv_block() and win_push_block() until a window is complete or no block is left.
   - `bool pipe_fault_due(pipe_t *p, int64_t now_us)` returns true and moves the next fault time on by PIPE_FAULT_EVERY_US when now has reached it. `int64_t pipe_next_fault_us(const pipe_t *p)` gives the next fault time.
   - `const rt_stretch_t *pipe_stretch(const pipe_t *p)`, `uint32_t pipe_end_stretch(const pipe_t *p)`, and `unsigned pipe_end_reason(const pipe_t *p)` give the current stretch and the last request.
   - Add pipeline.c to tremor_core and to the ESP-IDF source list in core/CMakeLists.txt with the warning flags of the other project files.
   - Write tests/pipeline/test_pipeline.c with the cases in validation.md check 1, and add test_pipeline to tests/CMakeLists.txt in the way test_window is added.

2. Write core/session.h and core/session.c as in requirements 24 to 26.
   - The header includes share.h, face.h, and dose.h. It defines SESS_FACE_CHANGED (1), SESS_COUNTED (2), and SESS_TONE (4), and `sess_t` with share, face, dose, `uint32_t answers[RES_COUNT]`, `gaps`, and `face_changes`.
   - The functions are `void sess_init(sess_t *s, int64_t now_us)`, `void sess_new_session(sess_t *s, int64_t now_us)`, `unsigned sess_stretch(sess_t *s, uint32_t number)`, `unsigned sess_answer(sess_t *s, bool has_window, uint32_t window, res_code_t code, int64_t time_us)`, and `unsigned sess_tick(sess_t *s, int64_t now_us)`. sess_tick() calls face_set_dose_due(true) on DOSE_BECAME_DUE and returns SESS_TONE, and it calls face_set_dose_due(false) on DOSE_DUE_ENDED alone.
   - Add session.c to core/CMakeLists.txt as in step 1. Write tests/session/test_session.c with the cases in validation.md check 1, and add test_session to tests/CMakeLists.txt.

3. Change firmware/main/tasks.h and firmware/main/main.c.
   - tasks.h adds `state_msg_t` with a kind of STATE_MSG_STRETCH or STATE_MSG_ANSWER and the fields of requirement 27. It adds `uint8_t face` to screen_msg_t. It declares g_state_queue and g_end_queue. The header comment no longer says that feature 8 adds the converter and the detector.
   - main.c makes g_state_queue with 8 items and g_end_queue with 1 uint32_t before any task starts. The state stack becomes 4096 bytes, because the state task formats doubles. The task priorities and cores stay as they are.

4. Change firmware/main/sensor_task.c as in requirement 22. Add LOSS_PIPELINE with the name "pipeline" after LOSS_LATE. Before take_burst(), read g_end_queue with no wait. When the number is the current stretch and the flag is not already set, set the overflow flag and the reason to LOSS_PIPELINE and count it. Add `pipeline=<n>` at the end of SENSOR_MINUTE. Nothing else in the file changes.

5. Rewrite firmware/main/pipeline_task.c as in requirements 1, 8 to 11, 20 to 23, 27, and 28.
   - At start it sends the TASK line, calls det_init(), and sends `DETECTOR_INIT ok=<0|1>`. If det_init() fails, it sends `PIPELINE_ERROR detector_init` and deletes itself. It then calls pipe_init().
   - The pipe_t, the window, and the sensor message are static in the file. The task waits on the sensor queue until the earlier of the next minute mark and pipe_next_fault_us().
   - For each message it keeps feature 7's counts, breaks, and minute sums unchanged. It then calls pipe_part(). On PIPE_STRETCH it sends a stretch message to the state task. On PIPE_END it writes the stretch number to g_end_queue with xQueueOverwrite() and sends END_REQUEST. Without PIPE_DROP it calls pipe_push() for each reading, and a PIPE_END there is handled in the same way.
   - After each message it calls pipe_window() until it returns false. For each window it reads the timer, calls det_run(), reads the timer again, and sends an answer message with res_from_answer(), the run time, the end time, and the end time minus the message's stamp.
   - While pipe_fault_due() returns true, it sends a fault answer message with code RES_SENSOR_FAULT and no window.
   - PIPELINE_MINUTE keeps its fields and adds `windows=<total> faults=<total> end_requests=<total> answer_drops=<total> rate_refused=<total> run_us_max=<max> delay_us_max=<max> stack_free=<bytes>` at its end. The totals count from boot, and stack_free comes from uxTaskGetStackHighWaterMark().

6. Rewrite firmware/main/state_task.c as in requirements 12 to 14, 24 to 27, and 30.
   - At start it sends the TASK line and calls sess_init() with the timer value. It waits on g_state_queue until the next whole second of its tick clock.
   - For a stretch message it calls sess_stretch(). For a number above 0 it sends `GAP stretch=<n> changed=<0|1>`.
   - For an answer message it calls sess_answer() and sends `ANSWER stretch=<s> window=<w|none> code=<c> prob=<%.17g|none> below=<%.17g|none> peak=<%.9g|none> time_us=<t> at_us=<t> run_us=<r> delay_us=<d> counted=<0|1> face=<shown>`.
   - Each second it calls sess_tick() with the timer value. A SESS_TONE result sends `TONE` for feature 11 to play.
   - Each time a call returns SESS_FACE_CHANGED, it sends `FACE at_us=<t> state=<n>` and a screen message. It also sends a screen message once a second with the uptime and the shown state, with no wait, and it counts dropped screen messages.
   - Once a minute it sends `STATE_MINUTE minute=<m> answers=<total> tremor=<n> no_tremor=<n> moving=<n> warming=<n> fault=<n> share_tremor=<n> share_still=<n> share_moving=<n> share=<%.6f|none> face=<n> face_changes=<n> gaps=<n> blocks=<n> screen_drops=<n> stack_free=<bytes>`. The first five counts are the answers by code, and the share counts come from share_t.

7. Change firmware/main/screen_task.c as in requirement 30. Add a label under the uptime, in Montserrat 28, with face_name() of the message's face. Count the messages whose face differs from the one before, and add `face=<n> face_changes=<n>` at the end of SCREEN_MINUTE. Nothing else in the file changes.

8. Make firmware/detector_check/ and tests/firmware/windows_bin.py as in requirement 29.
   - tests/firmware/windows_bin.py follows the user's Python rules and uses only the standard library, because it runs with the ESP-IDF Python. `windows_bytes(path: Path) -> bytes` checks the header and the count of 128,800 rows and gives the values as little-endian 32-bit floats in file order. `main()` takes `--csv` and `--out`.
   - firmware/detector_check/CMakeLists.txt adds core/ with EXTRA_COMPONENT_DIRS and calls `project(detector_check)`. sdkconfig.defaults holds CONFIG_IDF_TARGET, the flash mode and size, the CPU frequency, the cache line, and FREERTOS_HZ lines from firmware/sdkconfig.defaults, and CONFIG_PARTITION_TABLE_CUSTOM=y with partitions.csv. partitions.csv holds nvs, phy_init, and a factory app of 3M. sdkconfig is committed after the first build.
   - main/CMakeLists.txt registers detector_check.c with PRIV_REQUIRES core esp_timer esp_rom. It runs windows_bin.py with ESP-IDF's Python in a custom command that depends on tests/detector/windows.csv and the script, and it embeds the output with target_add_binary_data().
   - main/detector_check.c starts a task on core 1 at priority 8 with an 8192 byte stack. It sends `CHECK_CRC value=0x<crc>` with esp_rom_crc32_le(0, ...) of the 9 bytes "123456789", and `CHECK_START windows=322 bytes=<n> crc32=0x<crc>` for the embedded data. It calls det_init() once. For pass 1 and pass 2 it copies each window into an aligned static buffer, times det_run() alone with esp_timer_get_time(), and sends `CHECK_WINDOW pass=<p> window=<n> run_us=<r> mfcc=<12 values with %.9g, comma-separated> prob=<%.17g> below=<%.17g> peak=<%.9g> logreg=<0|1> at_rest=<0|1> tremor=<0|1>`. It calls vTaskDelay(1) after each window, so the idle task feeds the watchdog. It ends with `CHECK_END runs=644`. It uses printf, because this project has no USB task.

9. Write tests/firmware/chip_windows.py and tests/firmware/test_chip_windows.py with the cases in validation.md checks 5 and 8.
   - The options are `--port` with a default of /dev/cu.usbmodem101, `--log` with a default of tests/firmware/chip_windows_log.txt, `--report` with a default of tests/firmware/chip_windows_report.md, and `--log-only`. Without `--log-only` it resets the watch as table_run.py does and saves every line with the laptop time until CHECK_END arrives or 5 minutes pass.
   - It reads tests/detector/answers.csv with the csv module and applies the rule of test_detector.c with its constants. These are LIMIT 0.0001, CUT_OFF 0.029570239921802, PROB_NEAR 0.0001, BELOW_NEAR 0.005, and GAP_NEAR 0.0001. It writes the report with each pass check, the largest differences, the window counts near a cut-off, and the minimum, median, and maximum run time of each pass. It exits with code 0 only when every pass check holds.

10. Write tests/firmware/pipeline_run.py and tests/firmware/test_pipeline_run.py with the cases in validation.md checks 5 and 9.
    - It imports table_run.py from its own folder and uses its parse_log(), judge(), reopen(), and fields_of(). Its own capture waits for the minute lines of table_run.py and for STATE_MINUTE. The options match table_run.py, with the defaults tests/firmware/pipeline_log.txt and tests/firmware/pipeline_report.md.
    - Its face model maps codes 0, 1, and 2 to faces 0, 1, and 2 and codes 3 and 4 to face 3. A GAP line sets face 3 and clears the answer before. An answer sets the face to its own face when the answer before has the same face. The model has no dose due, because the clock is never set in this run.
    - The report holds table_run.py's checks, this feature's checks, and the measurements of validation.md check 9.

11. Build and run every check.
    - Run `make check`, then the commands in validation.md checks 1 to 6.
    - Run `idf.py -C firmware/detector_check -p /dev/cu.usbmodem101 flash` and `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/chip_windows.py --log <scratch file> --report <scratch file>` as a trial. Fix the code until the trial passes.
    - Run `idf.py -C firmware -p /dev/cu.usbmodem101 flash` and `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/pipeline_run.py --minutes 2 --log <scratch file> --report <scratch file>` as a trial. Fix the firmware until the trial passes. The full runs belong to the validate stage, and the trial files are not committed. Leave the watch flashed with firmware/.
    - Run `reference/.venv/bin/python -m pytest tests -q`.

12. Update specs/tech-stack.md as in requirement 33. Under Shared C library, add that core/pipeline.h holds the pipeline task's stretch, converter, window, and fault rules, and that core/session.h holds the state task's rules. Under Watch firmware, add that the pipeline task asks the sensor task to end a stretch through a queue of one stretch number, that a sensor fault answer comes after 2 seconds with no sensor message and then once a second, and that firmware/detector_check/ runs the saved windows on the chip. Under Tests and checks, add the commands of validation.md checks 8 and 9 and change the CTest count where it is named.

13. Set the status of feature 8 to in progress in specs/roadmap.md, and add `firmware/.cache/` to .gitignore. This step is done in plan mode.
