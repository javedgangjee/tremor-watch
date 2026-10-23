# Feature 7 validation: Commit checks, firmware base, and sensor task

Every command runs from the repo root. Checks 1 to 8 run on the laptop, and checks 1 to 5 need no toolbox. Check 9 runs on the watch and is judged by a script. Checks 10 and 11 need a person to look at the screen or touch it, so they wait for the user. The ESP-IDF shell comes from `. ~/.espressif/tools/activate_idf_v6.1.sh`, and SCRATCH means the session's scratch folder.

The table run in check 9 measures how often stretches end. Its pass checks test that the firmware works. The number of stretch ends of the second kind has no limit, because the user decides on a drift fix after this count. Feature 5's planning model of the time rule used feature 1's one-minute rates and made 6 stretches in twenty minutes, and the first five lasted 219, 156, 179, 262, and 306 seconds. These numbers are for information and are not limits.

## Automated checks

1. One make command runs the commit checks with no toolbox.
   - The commands are `rm -rf build firmware/build` and then `env -i HOME="$HOME" PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin make check > SCRATCH/check.log 2>&1`. The empty environment holds no venv and no ESP-IDF, so the Makefile must load ESP-IDF itself.
   - The expected result is exit code 0. The log shows CTest with 100% tests passed out of 9, the line "model hash matches", and ESP-IDF's "Project build complete" line, in that order.
   - The command `grep -nE '\.venv|paradigma|pytest|python|pads' Makefile` prints nothing.

2. The unit rule passes its C test. It runs inside check 1, and `ctest --test-dir build -R test_imu_units --output-on-failure` runs it alone. The cases in tests/imu_units/test_imu_units.c are below.
   1. IMU_GYRO_RANGE_DPS is 1024, and IMU_GYRO_COUNTS_PER_DPS is 32.
   2. imu_gyro_dps() gives exactly 0 for 0, 1 for 32, -1 for -32, 0.03125 for 1, 1023.96875 for 32767, and -1024 for -32768.
   3. For every count from -32768 to 32767, imu_gyro_dps() gives the same bits as `(float)raw / 32.0f`, and the result times 32.0f equals `(float)raw` exactly.

3. The hash check catches a wrong model file and a wrong header.
   1. `make hash` exits with code 0. It prints 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e twice and the line "model hash matches".
   2. `make hash MODEL=tests/converter/stretches.csv` exits with a code other than 0 and does not print "model hash matches".
   3. `sed 's/4be2ac2b511c/0be2ac2b511c/' core/detector_tables.h > SCRATCH/tables.h` and then `make hash TABLES=SCRATCH/tables.h` exits with a code other than 0 and does not print "model hash matches".
   4. `make hash TABLES=tests/converter/stretches.csv` exits with a code other than 0, because the file has no DET_MODEL_SHA256 line.

4. core/ builds as an ESP-IDF component with the right flags and no heap. Each command runs after check 1, in an ESP-IDF shell where it needs one.
   1. `python3 -c "import json,os;r=os.getcwd()+'/core/';e=[x for x in json.load(open('firmware/build/compile_commands.json')) if x['file'].startswith(r)];[print(x['file'][len(r):],all(f in x['command'] for f in ('-ffp-contract=off','KISS_FFT_MALLOC(n)=','KISS_FFT_FREE(p)=')),all(f in x['command'] for f in ('-Wextra','-Werror','-pedantic'))) for x in e]"` prints ten lines. They name detector.c, reading_time.c, converter.c, window.c, share.c, face.c, dose.c, imu_units.c, kissfft/kiss_fft.c, and kissfft/kiss_fftr.c. Every line has True in the first column. The eight project files have True in the second column, and the two KISS FFT files have False.
   2. `xtensa-esp32s3-elf-nm -u firmware/build/esp-idf/core/libcore.a | grep -wE 'malloc|calloc|realloc|free|aligned_alloc|posix_memalign'` prints nothing.
   3. `grep -rnE '#include *[<"](esp_|freertos/|driver/|sdkconfig)' core/` prints nothing.
   4. `grep -E '(firmware/main|/core/)[^ ]*: warning:' SCRATCH/check.log` prints nothing.
   5. `nm build/core/CMakeFiles/tremor_core.dir/imu_units.c.o | grep -E ' [bBdD] '` and `nm -u build/core/libtremor_core.a | grep -E '^_?(malloc|calloc|realloc|free|aligned_alloc|posix_memalign)$'` print nothing.

5. The firmware source follows the design.
   1. `ls firmware/main` lists CMakeLists.txt, idf_component.yml, main.c, tasks.h, power.h, power.cpp, sensor_task.c, pipeline_task.c, state_task.c, screen_task.c, and usb_task.c, and nothing else.
   2. `grep -lE 'lv_[a-z]|bsp_display_' firmware/main/*` prints only firmware/main/screen_task.c.
   3. `grep -lw printf firmware/main/*` prints only firmware/main/usb_task.c.
   4. `grep -rnE 'LV_USE_DEMO|lv_demo|LV_USE_SYSMON|LV_USE_PERF_MONITOR|Wno-format' firmware/CMakeLists.txt firmware/sdkconfig.defaults firmware/main` prints nothing, and `grep -nE '^CONFIG_LV_USE_DEMO_[A-Z_]*=y' firmware/sdkconfig` prints nothing.
   5. `grep -cE '"==2\.0\.0"|"==2\.0\.2"|"==9\.5\.0"' firmware/main/idf_component.yml` prints 3. firmware/dependencies.lock gives version 2.0.0 for waveshare/esp32_s3_touch_amoled_2_06, 2.0.2 for waveshare/qmi8658, and 9.5.0 for lvgl/lvgl.
   6. `diff -r ~/Documents/Projects/_esp32/waveshare-amoled-2.06/examples/esp-idf/01_AXP2101/components/XPowersLib firmware/components/XPowersLib` prints nothing. `git -C ~/Documents/Projects/_esp32/waveshare-amoled-2.06 status --short` prints only ` M examples/esp-idf/02_lvgl_demo_v9/main/main.c`, which feature 1 left, and its HEAD is still 30f3b23.
   7. `grep -rnE '112\.1|\b1121\b|112100' Makefile firmware/CMakeLists.txt firmware/sdkconfig.defaults firmware/main core/imu_units.h core/imu_units.c tests/imu_units tests/firmware tests/model/test_model_copy.py` prints nothing.
   8. `grep -rnE 'nvs_|esp_partition_write|spi_flash_write|fopen' firmware/main` prints nothing.

6. The Python tests pass.
   - The command is `reference/.venv/bin/python -m pytest tests -q`.
   - The 50 cases from features 2 to 6 run unchanged.
   - The cases in tests/model/test_model_copy.py are below.
     1. tests/model/tremor_detection_clf_package.pkl is the same byte for byte as tremor_detection_clf_package.pkl in the assets folder of the installed paradigma package, and tests/model/LICENSE is the same byte for byte as the licence in the paradigma-1.1.2 dist-info folder.
     2. The SHA-256 hash of the copy equals EXPECTED_SHA256 in tools/gen_tables.py and DET_MODEL_SHA256 in core/detector_tables.h.
   - The cases in tests/firmware/test_table_run.py are below. Each writes a made-up log to a temporary file and calls table_run.py's main() with `--log-only`, `--minutes 3`, and `--report` set to a temporary file.
     1. A clean log of 3 minutes gives exit code 0. It holds one START line, a SENSOR_SETUP line with good settings, a POWER line, five TASK lines, a first STRETCH line with kind=start, a RATE line of 114330200, two STRETCH lines of kind 2, and every minute line for minutes 1 to 3 with good values. The report counts 0 ends of the first kind and 2 of the second kind, and it gives the right length for each closed stretch.
     2. The same log with one more STRETCH line of kind 1 and reason overflow gives exit code 1. The report names the failed loss check, and every other check passes.
     3. The same log with a RATE line of 114456000, which is 1100 parts per million above 114330200, gives exit code 1. The same log with a second START line also gives exit code 1.
     4. Every function in table_run.py and test_model_copy.py has a type hint on each argument and on its return. The two files contain no `print(`, no `os.path`, and no `except Exception`. table_run.py has no line that starts with `import serial`.
   - The expected result is 56 passed.

7. The reference, the earlier code, and feature 1's record have not changed.
   - The command is `git diff 1b293e3 --stat -- reference/ context/ core/kissfft/ core/detector.h core/detector.c core/detector_tables.h core/reading_time.h core/reading_time.c core/converter.h core/converter.c core/window.h core/window.c core/share.h core/share.c core/face.h core/face.c core/dose.h core/dose.c core/replay.c tools/ tests/unity/ tests/detector/ tests/reading_time/ tests/converter/ tests/window/ tests/share/ tests/face/ tests/dose/ tests/response/ tests/pads/ tests/reference/ tests/tools/ firmware/bringup/`.
   - The command prints nothing.

8. The repo holds the right files.
   - The command is `git diff 1b293e3 --stat` on the feature branch after the validate commit.
   - The expected result lists Makefile, CMakeLists.txt, core/CMakeLists.txt, core/imu_units.h, core/imu_units.c, tests/CMakeLists.txt, tests/imu_units/test_imu_units.c, tests/model/tremor_detection_clf_package.pkl, tests/model/LICENSE, tests/model/test_model_copy.py, tests/firmware/table_run.py, tests/firmware/test_table_run.py, tests/firmware/table_log.txt, tests/firmware/table_report.md, firmware/CMakeLists.txt, firmware/sdkconfig.defaults, firmware/sdkconfig, firmware/dependencies.lock, the eleven files of check 5 item 1, the files of firmware/components/XPowersLib/, specs/tech-stack.md, specs/roadmap.md, and the three files in specs/features/07-firmware-base/. It lists no other file.

9. The watch reads the IMU into timed stretches on a table for 30 minutes.
   - The watch lies still on a table on USB power. The commands are `idf.py -C firmware -p /dev/cu.usbmodem101 flash` in an ESP-IDF shell, which must exit with code 0, and then `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/table_run.py`. The second command runs for about 31 minutes, so it runs in the background, and nothing else may use the port meanwhile.
   - The expected result is exit code 0, which means that every pass check below holds. The script writes tests/firmware/table_log.txt and tests/firmware/table_report.md.
     1. The log holds exactly one START line. After it, no line starts with "rst:" and no line holds "Guru Meditation", "abort()", or "SENSOR_ERROR".
     2. The SENSOR_SETUP line shows bits 0 and 1 of ctrl7 set, 0x6 in the low four bits of ctrl2 and of ctrl3, gyro_range_dps=1024, bits 2 and 3 of ctrl1 set, 0xD in the low four bits of fifo_ctrl, and fifo_wtm=11.
     3. The POWER line shows pmu=ok and vbus=1.
     4. The log holds one TASK line for each of sensor, pipeline, state, screen, and usb. The sensor task runs on core 1 and has the highest priority of the five, and the USB task has the lowest.
     5. The log holds a SENSOR_MINUTE, a PIPELINE_MINUTE, a SCREEN_MINUTE, and a USB_MINUTE line for every minute from 1 to the last minute.
     6. At the last minute, which is minute 30 in this run, SENSOR_MINUTE shows kind1_ends=0, overflow=0, full=0, read_error=0, stall=0, late=0, and msg_drops=0, PIPELINE_MINUTE shows breaks=0, and USB_MINUTE shows line_drops=0.
     7. At the last minute, the readings in PIPELINE_MINUTE differ from the readings in SENSOR_MINUTE by at most 32.
     8. At the last minute, bursts_at_wtm is at least 95% of bursts, largest_burst is at most 22, and largest_delay_us is under 50000.
     9. The log holds at least one RATE line, and every RATE line gives a rate from 114215870 to 114444530, which is 114330200 plus or minus 1000 parts per million.
     10. The first STRETCH line has kind=start, and the stretch numbers count up from 0 by one.
     11. Every STRETCH line of kind 2 with an error value has an error larger in size than 5e11 / prev_rate_uhz microseconds.
     12. In every PIPELINE_MINUTE line, each gyroscope mean lies from -10 to 10 degrees per second, each gyroscope spread is under 1 degree per second, and the length of the accelerometer mean lies from 3686.4 to 4505.6 counts, which is 4096 counts for 1 g plus or minus 10%.
     13. At the last minute, SCREEN_MINUTE shows at least 0.9 × 60 updates for each minute of the run, which is 1620 for 30 minutes.
   - The Results section records the measurements below from the report, with no limit. They are the number of stretches, the number of ends of each kind, the length of each stretch, the shortest, median, and longest length of the closed stretches, each rate and the change from each rate to the next in parts per million, and the stamp error at each end of the second kind.

## Manual checks

10. The screen stays on and shows the holding screen.
    - Look at the watch during check 9 or right after it.
    - The expected result is that the screen shows "Tremor log" and the uptime, the uptime counts up once a second, and the screen has stayed on.

11. The touch works.
    - Run `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/table_run.py --minutes 1 --log SCRATCH/touch_log.txt --report SCRATCH/touch_report.md`. While it runs, tap the screen once near each corner and once in the middle. The script's exit code does not matter here, because the taps move the watch.
    - The expected result is that `grep -c '^TOUCH' SCRATCH/touch_log.txt` prints 5, and each TOUCH line gives a point near the place tapped, with x from 0 to 409 and y from 0 to 501.

## Requirement coverage

Requirement 1 is covered by checks 1 and 2. Requirement 2 is covered by check 3. Requirement 3 is covered by check 1, whose grep finds no pads in the Makefile. Requirement 4 is covered by checks 1 and 4. Requirement 5 is covered by check 5 items 1 to 4 and 6, check 9 items 2 and 3, and check 11. Requirement 6 is covered by check 5 item 5. Requirement 7 is covered by check 5 items 1 to 3 and check 9 items 4 and 13. Requirement 8 is covered by checks 1 and 8. Requirement 9 is covered by check 9 item 2. Requirement 10 is covered by check 9 items 2 and 8. Requirement 11 is covered by check 9 items 9 to 11. Requirement 12 is covered by check 2 and check 9 item 12. Requirement 13 is covered by check 9 items 3 and 6 and check 11. Requirement 14 is covered by check 9 item 13 and check 10. Requirement 15 is covered by check 5 item 8. Requirement 16 is covered by check 9 and its measurements. Requirement 17 is covered by check 5 item 7. Requirement 18 is covered by check 7. Requirement 19 is covered by checks 1 and 3. Requirement 20 is covered by checks 3 and 6. Requirement 21 is covered by check 8, which lists no hook or CI file. Requirement 22 is covered by checks 1 and 4. Requirement 23 is covered by checks 5, 7, and 8. Requirement 24 is covered by check 5 item 6 and check 9 item 3. Requirement 25 is covered by check 9 items 2 and 8. Requirement 26 is covered by check 9 item 6 and check 6 case 2. Requirement 27 is covered by check 2. Requirement 28 is covered by check 9 items 6 and 7. Requirement 29 is covered by check 5 items 2 and 3 and check 9 items 4, 5, and 13. Requirement 30 is covered by check 9 item 4. Requirement 31 is covered by check 6 cases 1 and 2 and check 9 items 10 and 11. Requirement 32 is covered by checks 6 and 9. Requirement 33 is covered by check 9 items 6 and 9. Requirement 34 is covered by check 8 and a reading of specs/tech-stack.md.

## Results

The checks ran on 23 October 2026 on branch feature/07-firmware-base at commit f9e986c. The laptop build/ folder and firmware/build/ were removed before check 1. Every automated check passed. Checks 10 and 11 wait for the user, because nobody could look at the screen or touch the watch during this run. The USB port answered the whole time, so the reset helper was not needed.

1. Check 1 passed. `make check` in the empty environment exited with code 0 after about 50 seconds. The log shows "100% tests passed out of 9", then "model hash matches", then "Project build complete", in that order. The grep of the Makefile printed nothing.
2. Check 2 passed. test_imu_units ran inside check 1, and `ctest -R test_imu_units` reported 100% tests passed out of 1. A reading of tests/imu_units/test_imu_units.c found that its three cases match their text here.
3. Check 3 passed. `make hash` printed 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e twice and "model hash matches", and it exited with code 0. Items 2, 3, and 4 each printed "model hash does not match" and exited with code 2. In item 4 the tables hash was empty.
4. Check 4 passed. Item 1 printed the ten lines with True in the first column, True in the second column for the eight project files, and False for the two KISS FFT files. Items 2, 3, and 4 printed nothing. Item 5 printed nothing when it ran in a plain shell. In the ESP-IDF shell, the nm on the path does not read the laptop's Mach-O files and prints "file format not recognized" instead. The check says to use the ESP-IDF shell only where a command needs one, and item 5 does not.
5. Check 5 passed. Item 1 listed the eleven files and nothing else. Item 2 printed only screen_task.c, and item 3 printed only usb_task.c. Items 4, 7, and 8 printed nothing. Item 5 printed 3, and firmware/dependencies.lock gives 2.0.0, 2.0.2, and 9.5.0 for the three packages. In item 6 the diff printed nothing, Waveshare's clone shows only the change to 02_lvgl_demo_v9/main/main.c, and its HEAD is 30f3b23b3d4bb38d32f7d0cddffb66759668a855.
6. Check 6 passed. pytest reported 56 passed. The two cases of test_model_copy.py and the four cases of test_table_run.py passed.
7. Check 7 passed. The command printed nothing.
8. Check 8 passed. After the validate commit, `git diff 1b293e3 --stat` lists 49 files. They are the files the check names, with 15 files under firmware/components/XPowersLib/, and no other file. The untracked folder firmware/.cache/ holds an editor cache, and this stage did not commit it.
9. Check 9 passed. The flash exited with code 0, and table_run.py exited with code 0. All 13 pass checks held, and the measured values are below.
   - The log holds one START line and no reset, crash, or SENSOR_ERROR line after it.
   - SENSOR_SETUP read back ctrl1=0x6C, ctrl2=0x26, ctrl3=0x66, ctrl7=0x03, fifo_ctrl=0x0D, fifo_wtm=11, gyro_range_dps=1024, and int1_level=0.
   - POWER read pmu=ok and vbus=1. It also read battery=0, battery_mv=0, and battery_percent=-1, so the power chip found no battery. No check covers the battery.
   - The sensor task ran on core 1 at priority 12. The pipeline task ran on core 1 at priority 8, the state task on core 0 at 6, the screen task on core 0 at 5, and the USB task on core 0 at 3.
   - Every minute line from 1 to 30 arrived. At minute 30 every loss count was 0, breaks was 0, and line_drops was 0.
   - The sensor task took 205821 readings in 18711 bursts. Every burst held 11 readings, and the largest delay from stamp to the end of the read was 5566 microseconds. The pipeline's count at minute 30 was 11 lower, because its minute line went out one burst before the sensor task's line.
   - The screen task made 1799 updates in 30 minutes.

### Table run measurements

| Stretch | Start (s) | Length (s) | Rate (uHz) | Ended by | Stamp error (us) |
|---|---|---|---|---|---|
| 0 | 0.000 | 746.958 | 114351161 | kind 2, time rule | 4382.5 |
| 1 | 747.054 | open, about 1053 at the end of the run | 114350493 | open | none |

- The run had 2 stretches. It had 0 ends of the first kind and 1 end of the second kind.
- The only closed stretch lasted 746.958 seconds, so the shortest, the median, and the longest closed length are all 746.958 seconds. Stretch 1 had not ended when the run stopped about 1053 seconds after it started.
- The first rate came from the first 10 seconds of stamps. The second rate came from the whole of stretch 0. The change from the first rate to the second is -5.8 parts per million. The two rates lie 183.3 and 177.5 parts per million above feature 1's rate of 114330200.
- The one end of the second kind had a stamp error of 4382.5 microseconds. Half a reading period at the old rate is 4372.5 microseconds, so the error passed the limit by 10 microseconds.
- Over all 30 minutes the largest gyroscope mean was 3.29 degrees per second in size, on the y axis. The largest gyroscope spread was 0.631 degrees per second, on the z axis in minute 1, and the z axis spread stayed from 0.50 to 0.63 in every minute. The accelerometer mean had a length of 3765 to 3786 counts, which is 0.919 to 0.924 g. This is inside the check's 10% band, but it sits 8% under 1 g.

Feature 5's planning model gave stretches of 156 to 306 seconds. This run gave one drift end in 30 minutes, after about 12.5 minutes. The first rate from 10 seconds of stamps was already within about 6 parts per million of the rate over the whole stretch. The run is one 30-minute sample on a still table with a watch that had run before the flash, so it says nothing yet about drift on the wrist or from a cold start. Feature 12 makes the wrist count.

A second reading of the log checked the time rule against the minute lines. For every minute from 1 to 30, the time that the stretch's t0 and rate predict for the last burst counted in SENSOR_MINUTE lies from 4 milliseconds before to 85 milliseconds after the minute mark. A burst takes about 96 milliseconds, and the task finishes a read about 5.6 milliseconds after its stamp, so this is the window the counts allow. The minute counts therefore agree with the stretch rates in both stretches.

### Manual checks

10. Check 10 waits for the user. The log shows that the screen task made 1799 updates and that no line reported a display error, but nobody looked at the screen.
11. Check 11 waits for the user. The table run log holds no TOUCH line, which fits a watch that nobody touched. Nothing yet shows that a tap gives a TOUCH line.

### Requirement coverage

Every item in requirements.md has at least one passing check. Requirement 5 says that the firmware keeps the touch driver, and only check 11 shows that touch works, so that part of requirement 5 waits for the user. Requirement 14 says that the screen stays on, and check 9 item 13 shows only that the screen task kept updating its label. Check 10 waits for the user. Requirement 34 holds, because specs/tech-stack.md records every item that it lists.

### Against the build spec

A reading of firmware/main/ beside the build spec's Sensor and converter and Firmware design sections finds that the firmware follows these rules for the parts that this feature builds.

- The sensor runs rate code 0x06 with the gyroscope and the accelerometer both on, and the gyroscope range is ±1024 degrees per second. The SENSOR_SETUP line read this back from the chip.
- The buffer raises its interrupt at 11 readings. The interrupt handler takes esp_timer_get_time() and does nothing else, so each burst carries a 64-bit microsecond stamp taken inside the interrupt.
- Reading numbers are 64-bit counts and stamps are 64-bit microseconds. No time is kept as 32-bit seconds.
- The sensor task passes every burst to rt_burst() from core/, so the time rule lives in the shared library. A lost burst sets the overflow flag on the next good burst, and that ends the stretch.
- The five tasks exist and talk through queues. No task waits on a full queue.
- The firmware writes nothing to flash.

The firmware goes beyond the build spec or leaves gaps in these places. None of them fails a check.

- ESP-IDF's own log lines also reach the serial port from other tasks. The run shows lines from the QMI8658 driver, the board support package, the LVGL port, and the GPIO driver in the first second after START. Requirement 29 says that the USB task is the only task that writes to the serial port, and the build spec says that the USB task writes the recording. The project's own files keep that rule, but ESP-IDF's log does not. The log level is INFO, so feature 9 should lower it or route it, or a driver line could land between recording lines.
- printf goes to UART0 at 115200 baud as the main console and to the USB Serial/JTAG port as the second console. The UART limits how fast the USB task can write. Feature 9 writes every reading, so it should check this limit.
- The board support package's LVGL port task runs LVGL's timers and the tap callback, and the screen task holds the port's lock for every change. So two tasks touch LVGL under one lock. Requirement 29 states this, and it is the board support package's own design, but it is not the build spec's words "the screen task owns LVGL" read strictly.
- The build spec's rule "When no laptop is plugged in, it drops the recording lines" is not tested in this feature. Feature 9 adds the recording.
- The largest delay in SENSOR_MINUTE is measured after the wait for INT1 to drop, which can add up to 1 millisecond. Plan step 8 says that the delay ends at the end of the buffer read. The difference does not change any check.

None of the ten changes in plan.md's "Changes during implement" goes against the build spec. Change 1 starts the display with the board support package's own functions in place of bsp_display_start(), and it keeps the display and touch drivers that Build order step 11 asks to keep. Change 2 adds a sensor reset and the CTRL8 handshake setting, and change 3 adds the 1 millisecond wait for INT1. Changes 4 to 10 are build settings, a line length, and the order of start-up calls, and the build spec says nothing about them. Each change waits for the user's review.
