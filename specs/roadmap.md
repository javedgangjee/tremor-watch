# Roadmap

The features follow the build order in context/tremor-log-plan.html. "Step" means a numbered step in that page's Build order section, and the other references name its sections.

1. Hardware bring-up
   - The goal is to prove the board works and to learn the real sensor rate before any code is written.
   - It covers the work before step 1. It flashes Waveshare's ESP-IDF demo, confirms the screen and touch, and measures the 112.1 Hz rate and its drift over twenty minutes. It does not check how long the battery runs the screen, by the user's decision, although the plan asks for that check. It also records the ESP-IDF and LVGL versions in specs/tech-stack.md.
   - The status is done.

2. Python reference
   - The goal is to set up the toolbox on the laptop as the reference the C port must match.
   - It covers steps 1 and 2 and the Test data and Repo layout sections. It moves the scripts from context/ into reference/, pins the requirements, confirms that compare.py still matches, and counts how often the toolbox fires on each PADS task in each group.
   - The status is done.

3. Generated tables
   - The goal is to write the detector's fixed numbers into a committed C header.
   - It covers step 3 and the Detector recipe section. tools/gen_tables.py writes the model numbers, both Hann windows, the filter table, the cosine table, and the model file's hash.
   - The status is done.

4. C detector and the PADS match
   - The goal is to port the detector to C and show that it agrees with the toolbox on saved windows and on every PADS file.
   - It covers steps 4 to 6, the Detector recipe section, and the replay program in the Shared C library section. It uses KISS FFT and 32-bit floats, and it saves a few hundred test windows with the toolbox's answers, including windows close to each cut-off. It produces the match report with the largest difference in the probability.
   - Feature 3 stores the model numbers in core/detector_tables.h as 64-bit values, and the 32-bit run of plain_detector.py scores the window against them in 64-bit floats. This feature chose 64-bit doubles for the C scoring step. Only the detector's C file includes the header, because the header holds static arrays.
   - This feature also adds the two tests that feature 3 left out. They give tools/gen_tables.py a model whose feature names are not mfcc_1 to mfcc_12, and a classifier that is not a logistic regression with one row of 12 weights, and each test checks that the script stops and writes no file. The toolbox stores the 12 weights as a flat array, and the script accepts that shape as one row.
   - The status is done.

5. Reading times and converter
   - The goal is to give each reading its time and convert the readings to 100 a second as the toolbox does.
   - It covers steps 7 and 8 and the Sensor and converter section. It saves converter cases, and the C converter must agree within 0.001 degrees per second outside window 0. Feature 1 measured 114.33 readings a second on this board, so no code or test may assume 112.1, and each stretch takes its rate from the reading times as the plan says.
   - Requirements 21, 22, and 24 in specs/features/05-reading-times-converter/requirements.md go beyond the build spec's words, and they wait for the user's review. Requirement 21 lets a stretch measure its own rate when the stretch before it lasted less than 10 seconds. Requirement 22 adds more ways to end a stretch. Requirement 24 drops a part block at the end of a stretch. The Results section of validation.md in the same folder explains each one.
   - The status is done.

6. Windows, share, and state rules
   - The goal is to build the rules that turn answers into the face state, the session share, and dose due timing.
   - It covers step 9 and the Windows, Response time, Firmware design, and Dose schedule sections. It includes the result codes, the two-in-a-row rule, and unit tests for every state change.
   - The face shows Waiting at once when a new stretch starts after a gap, because face_gap() in core/face.h sets it. The user chose this rule on 23 October 2026, because each new stretch gives only one warming up answer and one answer never changes the face.
   - The response time limits in tests/response/test_response.c are the build spec's numbers plus one answer step, which is one second. The build spec's own simulation in reference/demo_test.py has no two-in-a-row rule. With one more answer for the rule, its delays miss the build spec's words by about the same amounts as the C test's delays do. The Results section of specs/features/06-state-rules/validation.md gives the numbers.
   - Requirements 23 to 37 in specs/features/06-state-rules/requirements.md are the agent's choices, and they wait for the user's review. The Results section of validation.md in the same folder lists where the code goes beyond the build spec's words.
   - The status is done.

7. Commit checks, firmware base, and sensor task
   - The goal is to run every check that needs no toolbox with one make command, strip Waveshare's example to the five tasks, and read the IMU into timed stretches.
   - It covers steps 10 to 12 and the Firmware design and Sensor and converter sections. The firmware build is one of the make checks. The hash check compares the model file's SHA-256 hash with DET_MODEL_SHA256 in core/detector_tables.h.
   - Feature 4 made the laptop CMake build, and its CTest run already checks the saved windows. This feature sets up core/ as an ESP-IDF component. The component must build with -ffp-contract=off and with the KISS_FFT_MALLOC and KISS_FFT_FREE options from core/CMakeLists.txt, so that KISS FFT never touches the heap on the watch.
   - The sensor task calls rt_burst() from core/reading_time.h once for each burst. It passes the first reading's number counted from power-on, the number of readings, the stamp taken inside the interrupt, and the overflow flag. It turns the raw gyroscope counts into degrees per second, as requirement 27 of feature 5 says.
   - This feature counts how often stretches end on the watch and how long they last, with the watch on a table only. It counts two kinds of stretch end apart. The first kind loses readings, because the sensor's buffer overflowed or a reading number was skipped. The second kind loses no readings and comes from the time rule alone, which points to drift. Feature 5 modelled the time rule with the measured drift of -80.8 parts per million, and the rule started a new stretch every 2.5 to 5 minutes. Since feature 6, every stretch end shows Waiting until two answers in the new stretch agree, which takes about 6 seconds, so frequent drift ends would make the face flicker. The user keeps the build spec's fixed-rate rule for now and decides on a drift fix after this count. Feature 12 makes the same count with the watch on the wrist.
   - The 30-minute table run on 23 October 2026 measured one drift end and no end that lost readings. Stretch 0 ended after 746.958 seconds with a stamp error of 4382.5 microseconds, and the limit of half a reading period was 4372.5 microseconds. Stretch 1 took its rate from the whole of stretch 0, and it had run for about 1053 seconds without an end when the run stopped. Feature 5's model gave a drift end every 2.5 to 5 minutes. This is one sample on a still table, and the user still decides on a drift fix. tests/firmware/table_report.md and the Results section of specs/features/07-firmware-base/validation.md hold the numbers.
   - Feature 8's 30-minute table run on 23 October 2026 had no drift end. Its one stretch took the rate 114351469 from its first 10 seconds, and it had run for about 1799 seconds without an end when the run stopped. So the two table runs give one drift end in about 60 minutes. The user still decides on a drift fix.
   - The accelerometer read 0.919 to 0.924 g at rest during the table run, which is about 8 percent under 1 g. The detector uses only the gyroscope, so this is for information only.
   - Requirements 19 to 34 in specs/features/07-firmware-base/requirements.md and the ten changes under "Changes during implement" in plan.md in the same folder are the agent's choices, and they wait for the user's review.
   - Manual checks 10 and 11 in specs/features/07-firmware-base/validation.md wait for the user. Check 10 looks at the holding screen, and check 11 taps the screen.
   - The status is done.

8. Pipeline and state tasks
   - The goal is to run the converter and the detector on the watch and hold the state for the session.
   - It covers steps 13 and 14 and the Windows and Firmware design sections. It measures how long each detector run takes on the chip.
   - Feature 4 checked the numpy-order float32 sums and the 64-bit scoring step on the laptop only. This feature runs the saved windows in tests/detector/ on the chip and checks them with the same rule as tests/detector/test_detector.c. The chip has no hardware for doubles, so the measured run time includes the 64-bit scoring step in software.
   - Feature 7 wrote holding versions of firmware/main/pipeline_task.c and firmware/main/state_task.c, and this feature replaces them. The pipeline task takes sensor_msg_t messages from firmware/main/tasks.h, and only the first message of a burst carries the time rule's flags.
   - The pipeline task is the only task that calls the detector, because the detector's work buffers are static. It calls det_init() once before the first window.
   - The pipeline task owns a conv_t from core/converter.h. It calls conv_start() at each new stretch and conv_set_rate() when the time rule gives the stretch its rate. When conv_push() returns false, the stretch must end, and the pipeline task asks the sensor task to end it through a queue of one stretch number, as specs/tech-stack.md says.
   - The pipeline task owns a win_t from core/window.h. It calls win_start() at each new stretch and gives each answer its result code with res_from_answer().
   - The state task owns a share_t, a face_t, and a dose_t from core/share.h, core/face.h, and core/dose.h. It passes every answer's code unchanged to share_add() and face_answer(), and it calls dose_tick() at least once a second. It calls face_gap() at each new stretch after a gap, so the face shows Waiting while the watch warms up. The first stretch after power-on or a new session needs no call.
   - The pipeline task sends a sensor fault answer when no sensor message has arrived for 2 seconds, and then once a second until a message arrives. The face shows Waiting at the second fault answer, which is about 3 seconds after the sensor stops, because two answers in a row must agree before the face changes.
   - The saved windows ran on the chip on 23 October 2026 and passed the rule of tests/detector/test_detector.c. The largest difference from the toolbox was 3.66e-06 in the 12 numbers and 2.66e-07 in the probability, and no answer differed. tests/firmware/chip_windows_report.md holds the numbers.
   - The 30-minute table run on 23 October 2026 gave 1796 answers, one each second, with no tremor answer, no sensor fault, and no drop. It had one stretch, so the gap path and the sensor task's side of the end request did not run on the watch. The laptop tests cover both, and the entries for features 9 and 12 say how the watch checks them later. tests/firmware/pipeline_report.md and the Results section of specs/features/08-pipeline-state/validation.md hold the numbers.
   - Requirements 20 to 33 in specs/features/08-pipeline-state/requirements.md and the nine changes under "Changes during implement" in plan.md in the same folder are the agent's choices, and they wait for the user's review.
   - Case 5 of tests/session/test_session.c is a weak test, and it waits for the user's review. It would still pass if sess_answer() ignored has_window, because share_add() never counts a fault code. The firmware never sends a code from 0 to 2 without a window, so this weakness has no effect now.
   - Manual checks 10 and 11 in specs/features/08-pipeline-state/validation.md wait for the user. Check 10 looks for the face state on the holding screen, and check 11 shakes the watch to show Tremor.
   - The status is done.

9. USB recording and commands
   - The goal is to write every reading and answer to the laptop and accept the laptop's commands.
   - It covers step 15 and the USB recording section. It adds the recording format document to core/, the boot line, and the commands for the clock, the dose schedule, a new session, and the tone. The table hash in the boot line is DET_MODEL_SHA256 from core/detector_tables.h, which is the model file's SHA-256 hash.
   - The S line writes the rate as the whole number of millionths of a reading per second that the time rule holds, as requirement 18 of feature 5 says. A first stretch has no rate until its first 10 seconds of stamps pass, so this feature decides when the S line of such a stretch goes out.
   - The W line writes the result codes 0 to 4 from core/window.h, and the F line writes the face states 0 to 4 from core/face.h, as requirements 24 and 28 of feature 6 say. The D line writes the scheduled time that dose_took_it() answers, as requirement 32 says. The clock command sets the dose clock with dose_set_clock() from core/dose.h.
   - Feature 7 found that ESP-IDF's own log lines reach the serial port from other tasks at level INFO. It also found that printf goes to UART0 at 115200 baud as the main console, and that the USB Serial/JTAG port is the second console. This feature must make the USB task the only writer on the port that carries the recording, and it must check that this port can carry the full recording.
   - The build spec says that the USB task drops the recording lines when no laptop is plugged in. Feature 7 did not test this rule, so this feature tests it.
   - tests/firmware/table_run.py reads the lines that feature 7 writes, such as STRETCH and SENSOR_MINUTE. This feature keeps those lines or updates the script.
   - Feature 8 added the lines ANSWER, GAP, FACE, END_REQUEST, TONE, and STATE_MINUTE for its own checks, and tests/firmware/pipeline_run.py reads them. This feature decides the recording lines from them, and it keeps feature 8's lines or updates the script. It also decides how the W line writes a sensor fault answer, which has no window number and no detector numbers.
   - The new session command calls sess_new_session() from core/session.h. The dose clock and the schedule stay unset on the watch until this feature's commands set them, and this feature adds the settings store that keeps the schedule.
   - In feature 8's table run, the pipeline task kept 2240 of its 4096 bytes of stack free, and the state task kept 2488. If this feature makes either task format recording lines, it measures the free stack of that task again.
   - No stretch ended in feature 8's table run, so the gap path with face_gap() and the sensor task's side of the end request never ran on the watch. This feature decides whether a test command forces a stretch end through the end request queue, so that one check on the watch runs both. Such a command goes beyond the four commands in the build spec, so it waits for the user's review.
   - The status is planned.

10. Laptop tools
    - The goal is to drive the watch from the laptop and compare each session with replay and the toolbox.
    - It covers steps 16 and 17. It writes tools/watch_cli.py and tools/compare_session.py, and it adds recording input to replay.
    - replay gives each reading its time with core/reading_time.c from the T lines. compare_session.py gives the toolbox the reading times as n * 1e6 / rate_uhz seconds counted from each stretch's t0 with no rounding, as requirement 30 of feature 5 says. The build spec's T line holds no overflow flag, so this feature decides how replay finds a stretch that an overflow ended.
    - Feature 8 times each answer at its window's last 100 Hz sample, which is t0 + 10000 × (100n + 399) microseconds. compare_session.py can give the share the same times, so it can check the same blocks and the same last tremor time.
    - The status is planned.

11. Watch face
    - The goal is to build the four screens, the state circle, and the dose flow for a wearer with tremor.
    - It covers steps 18 and 19 and the Watch face section. It starts from context/Tremor Watch Light.html and makes the changes that the Watch face section lists. It also picks the No tremor green and the Waiting outline colour, which the design file does not have.
    - The three second lock after a dose also lives in dose_took_it() from core/dose.h, and the dose flow uses its refusal, as requirement 32 of feature 6 says. The Session screen draws the blocks that share_block() in core/share.h gives, and share_block_hollow() says which block is hollow.
    - This feature builds on feature 7's screen task in firmware/main/screen_task.c. That task starts the display with bsp_display_new() and lvgl_port_add_disp() and the touch with bsp_touch_new() and lvgl_port_add_touch(). It does not call bsp_display_start(), because that function in board support package 2.0.0 adds the SH8601 panel as an RGB panel and corrupts the heap. This feature must not call bsp_display_start() either.
    - Feature 7's manual checks of the screen and the touch wait for the user, so nothing yet shows that a tap reaches the screen task.
    - Feature 8's holding screen shows the name of the face state from face_name(), and this feature replaces it with the face. The state task writes a TONE line when a dose becomes due, and this feature plays the tone.
    - The status is planned.

12. Wrist tests, demo, and deliverables
    - The goal is to measure false alarms, response time, and readability with the builder wearing the watch, then record the demo and produce the deliverables.
    - It covers steps 20 to 24 and the Response time and What you deliver sections. It includes the demo video, the session report, the results table, the results page, and the credit lines. It has no write-up, by the user's decision, although the plan asks for one.
    - This feature counts how often stretches end and how long they last with the watch on the wrist. It counts the same two kinds of stretch end apart as feature 7 does on the table.
    - If feature 9 adds no command that forces a stretch end, this feature checks on the watch that a new stretch after a gap shows Waiting. The sensor task's side of the end request then stays untested on the watch, and the user decides whether that is enough.
    - The power chip reported no battery during feature 7's table run. The user chose not to check how long the battery runs the screen, so the battery needs a check before the demo.
    - The status is planned.
