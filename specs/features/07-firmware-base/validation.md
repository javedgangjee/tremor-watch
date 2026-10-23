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
