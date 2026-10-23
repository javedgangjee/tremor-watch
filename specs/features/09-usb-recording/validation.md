# Feature 9 validation: USB recording and commands

Every command runs from the repo root. Checks 1 to 7 run on the laptop, and checks 1 to 4 need no toolbox. Checks 8 to 10 run on the watch and are judged by a script. Checks 11 and 12 need a person to unplug the cable or look at the screen, so they wait for the user. The ESP-IDF shell comes from `. ~/.espressif/tools/activate_idf_v6.1.sh`, and SCRATCH means the session's scratch folder. Checks 8, 9, and 10 run one after the other, because each needs the port alone.

The watch lies still on a table during this loop. No stretch ends on purpose, so the gap path and the sensor task's side of the end request stay untested on the watch, as requirement 22 says. A still watch never stops its sensor, so the W line of a fault answer is tested on the laptop only. Nothing calls dose_took_it() before feature 11, so the D line is tested on the laptop only.

The limits come from these sources. The answer spacing of 0.9 to 1.1 seconds and the rule of at most one answer a second come from feature 8's checks and table run. The state task ticks the doses once a second, so a dose time becomes due at the first tick at or after it, which is less than 1 second later. The due limits add 0.1 seconds for the state task's wait for its tick, and the Results give the measured delays. The clock limit of 1 second lies far above the USB latency of a few milliseconds, and far below the error of at least 60 seconds that a wrong unit or sign in the clock arithmetic would give. The free stack has no limit, because the build spec gives none, and a stack overflow stops the chip, which the checks see as a second boot.

## Automated checks

1. The recording rules build and pass their C tests.
   - The command is `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure`.
   - The eleven tests from features 4 to 8 run unchanged.
   - In the cases in tests/record/test_record.c, H is the text of DET_MODEL_SHA256, which is "4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e". Each line function's return value is the length of the text it writes.
     1. REC_LINE_MAX is 128 and REC_COMMAND_MAX is 127. REC_CLOCK_MIN_US is 1577836800000000, REC_CLOCK_END_US is 4102444800000000, REC_OFFSET_MIN is -720, and REC_OFFSET_MAX is 840. The rec_cmd_t values are 0 to 5 and the rec_result_t values are 0 to 5, in the order of plan step 1.
     2. rec_boot() with 305419896, 11, 9, and H gives "B,305419896,11,9,H" with H written out. With 4294967295, 0, 9, and H it gives "B,4294967295,0,9,H".
     3. rec_stretch() with 0, 0, 238216, 0, and 1024 gives "S,0,0,238216,0,1024". With 1, 3441, 50000000, 114330200, and 1024 it gives "S,1,3441,50000000,114330200,1024".
     4. rec_burst() with 1099511627776, 11, and 9007199254740993 gives "T,1099511627776,11,9007199254740993". With 0, 11, and -5 it gives "T,0,11,-5".
     5. rec_reading() with 17, the gyroscope counts -32768, 0, and 32767, and the accelerometer counts -146, -24, and -3773 gives "R,17,-32768,0,32767,-146,-24,-3773".
     6. rec_window() with stretch 0, a window, window 2, RES_NO_TREMOR, 0.00014912065608801541, 0.6326332688331604, and 21.25f gives "W,0,2,1,0.00014912065608801541,0.6326332688331604,21.25". This is the text of window 2's ANSWER line in tests/firmware/pipeline_log.txt. Window 0 with RES_WARMING_UP, 0.0002778472679054648, 0.5469731092453003, and 19.75f gives "W,0,0,3,0.0002778472679054648,0.5469731092453003,19.75". Window 12 with RES_NO_TREMOR, 7.817677252158094e-05, 0.572318971157074, and 8.0f gives "W,0,12,1,7.817677252158094e-05,0.572318971157074,8". For each of the three lines, strtod() of fields 5 and 6 gives the input doubles bit for bit, and strtof() of field 7 gives the input float bit for bit.
     7. rec_window() with stretch 3, no window, window 0, RES_SENSOR_FAULT, 0.5, 10.0, and 5.0f gives "W,3,,4,,,".
     8. rec_face() with 10276255 and FACE_NO_TREMOR gives "F,10276255,1", and with 0 and FACE_DOSE_DUE it gives "F,0,4".
     9. rec_dose() with a dose_entry_t of 4500000000 and 1761206400000000 gives "D,4500000000,1761206400000000". With 4500000000 and DOSE_NONE it gives "D,4500000000,".
     10. rec_reply() gives "A,2,0" for REC_CMD_SCHEDULE and REC_DONE, "A,0,1" for REC_CMD_UNKNOWN and REC_UNKNOWN, and "A,4,5" for REC_CMD_TONE and REC_BUSY.
     11. For the first line of each of cases 2 to 10, a size equal to the line's length makes the function return 0. A size one larger makes it return the length and write the same text.
     12. rec_parse_command() returns REC_DONE for each line below and fills the fields shown.
         - "CLOCK,1761206400000000,60" gives REC_CMD_CLOCK with utc_us 1761206400000000 and offset_min 60.
         - "CLOCK,1577836800000000,-720" and "CLOCK,4102444799999999,840" give REC_CMD_CLOCK with those values.
         - "SCHEDULE,Levodopa,480,720,1200" gives REC_CMD_SCHEDULE with the name "Levodopa", count 3, and the minutes 480, 720, and 1200 in that order.
         - "SCHEDULE,Sinemet-CR.25/100+,600" gives the name "Sinemet-CR.25/100+" with count 1 and minute 600.
         - "SCHEDULE,ABCDEFGHIJKLMNOPQRST,0,1,2,3,4,1439" gives the 20-character name and count 6.
         - "SCHEDULE,Levodopa" gives the name with count 0, and "SCHEDULE" gives an empty name with count 0.
         - "SCHEDULE,Levodopa,480,480" gives count 2. dose_set_schedule() on a new dose_t then returns false.
         - "SESSION" gives REC_CMD_SESSION.
         - "TONE,0" gives REC_CMD_TONE with tone_on false, and "TONE,1" and "TONE,1\r" give tone_on true.
         - "" and "\r" give REC_CMD_EMPTY.
     13. rec_parse_command() refuses each line below with the kind and the result shown.
         - "HELLO", "clock,1761206400000000,60", "CLOCKS,1", "TONE 1", and "SESSION " give REC_CMD_UNKNOWN and REC_UNKNOWN.
         - "CLOCK", "CLOCK,1761206400000000", "CLOCK,1761206400000000,60,1", "CLOCK,abc,60", "CLOCK,,60", "CLOCK,+1761206400000000,60", "CLOCK,1761206400000000,6 0", and "CLOCK,17612064000000000000,0" give REC_CMD_CLOCK and REC_BAD_FORMAT.
         - "CLOCK,1577836799999999,0", "CLOCK,4102444800000000,0", "CLOCK,1761206400000000,841", and "CLOCK,1761206400000000,-721" give REC_CMD_CLOCK and REC_REFUSED.
         - "SCHEDULE,", "SCHEDULE,,480", "SCHEDULE,Levo dopa,480", "SCHEDULE,Levodopa,8am", "SCHEDULE,Levodopa,480,", and "SCHEDULE,L\xc3\xa9vodopa" give REC_CMD_SCHEDULE and REC_BAD_FORMAT.
         - "SCHEDULE,ABCDEFGHIJKLMNOPQRSTU", "SCHEDULE,Levodopa,1440", "SCHEDULE,Levodopa,-1", and "SCHEDULE,Levodopa,1,2,3,4,5,6,7" give REC_CMD_SCHEDULE and REC_REFUSED.
         - "SESSION,1" and "SESSION," give REC_CMD_SESSION and REC_BAD_FORMAT.
         - "TONE", "TONE,", "TONE,1,1", and "TONE,x" give REC_CMD_TONE and REC_BAD_FORMAT, and "TONE,2" and "TONE,-1" give REC_CMD_TONE and REC_REFUSED.
         - A line of 128 "A" characters gives REC_CMD_UNKNOWN and REC_BAD_FORMAT.
     14. rec_clock_offset_us() gives 1761209995000000 for 1761206400000000, 60, and 5000000. It gives 1761163200000000 for 1761206400000000, -720, and 0, and 1577880000000000 for 1577836800000000, 840, and 7200000000.
   - The expected result is that the build prints no warning, and CTest reports 100% tests passed out of 12.

2. The new C code uses no heap, no ESP-IDF header, no changing static data, and no 112.1.
   1. `nm -u build/core/libtremor_core.a | grep -E '^_?(malloc|calloc|realloc|free|aligned_alloc|posix_memalign)$'` prints nothing.
   2. `grep -rnE '#include *[<"](esp_|freertos/|driver/|nvs|sdkconfig)' core/` prints nothing.
   3. `nm build/core/CMakeFiles/tremor_core.dir/record.c.o | grep -E ' [bBdD] '` prints nothing.
   4. `grep -rnE '112\.1|\b1121\b|112100' core/record.* core/recording_format.md tests/record tests/firmware/record_run.py tests/firmware/command_run.py tests/firmware/drop_run.py tests/firmware/test_record_run.py tests/firmware/test_command_run.py tests/firmware/test_drop_run.py firmware/main firmware/sdkconfig.defaults` prints nothing.
   5. `cmake --build build --clean-first 2>&1 | grep -i warning` prints nothing.

3. The commit checks and both ESP-IDF projects build.
   1. The commands are `rm -rf build firmware/build firmware/detector_check/build` and then `env -i HOME="$HOME" PATH=/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin make check > SCRATCH/check.log 2>&1`. The exit code is 0. The log shows "100% tests passed out of 12", then "model hash matches", then "Project build complete", in that order.
   2. In an ESP-IDF shell, `idf.py -C firmware/detector_check build` exits with code 0.
   3. The command of feature 7's check 4 item 1, run once on firmware/build/compile_commands.json and once on firmware/detector_check/build/compile_commands.json, prints thirteen lines each time. They add record.c to feature 8's twelve names. Every line has True in the first column, the eleven project files have True in the second column, and the two KISS FFT files have False.
   4. `xtensa-esp32s3-elf-nm -u firmware/build/esp-idf/core/libcore.a | grep -wE 'malloc|calloc|realloc|free|aligned_alloc|posix_memalign'` prints nothing.
   5. `grep -E '(firmware/main|firmware/detector_check/main|/core/)[^ ]*: warning:' SCRATCH/check.log` prints nothing.

4. The firmware source follows the design.
   1. `ls firmware/main` lists the eleven files of feature 8 and settings.c and settings.h.
   2. `grep -lE 'lv_[a-z]|bsp_display_' firmware/main/*` prints only firmware/main/screen_task.c.
   3. `grep -lwE 'printf|puts|putchar|fputs|fwrite' firmware/main/*` prints nothing, so no task writes to stdout.
   4. `grep -lE '\busb_serial_jtag_' firmware/main/*` prints only firmware/main/usb_task.c, and so does `grep -lE '\brec_(parse_command|boot|stretch|burst|reading)\(' firmware/main/*`.
   5. `grep -lE '\brec_(window|face|clock_offset_us)\(|\bdose_set_(clock|schedule)\(|\bsettings_(load|save_schedule|save_tone)\(' firmware/main/*.c` prints only firmware/main/settings.c and firmware/main/state_task.c, and settings.c appears only because it defines the settings functions.
   6. `grep -lE '\bdet_(init|run)\(|\bpipe_[a-z_]+\(' firmware/main/*` prints only firmware/main/pipeline_task.c, and `grep -lE '\bsess_[a-z_]+\(' firmware/main/*` prints only firmware/main/state_task.c.
   7. `grep -nE '\b(conv|win)_[a-z_]+\(|\b(share_add|share_start|face_answer|face_gap|face_init|face_set_dose_due|dose_init|dose_tick|dose_new_session|dose_took_it)\(' firmware/main/*` prints nothing.
   8. `grep -rlE 'nvs_(set|erase|commit|open)' firmware/main` prints only firmware/main/settings.c. `grep -rlE 'nvs_flash_(init|erase)' firmware/main` prints only firmware/main/main.c. `grep -rnE 'esp_partition_write|spi_flash_write|fopen' firmware/main firmware/detector_check/main` prints nothing.
   9. `grep -cE '^CONFIG_ESP_CONSOLE_SECONDARY_NONE=y$' firmware/sdkconfig firmware/sdkconfig.defaults` gives 1 for each file, and `grep -c '^CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y' firmware/sdkconfig` gives 0. `git diff 57d4d39 -- firmware/sdkconfig | grep -E '^[-+]' | grep -vE '^(\+\+\+|---)' | grep -vE 'CONSOLE|USB_SERIAL_JTAG|USJ_'` prints nothing, so the console change moved only options about the console and the USB Serial/JTAG port.
   10. `grep -n 'DET_MODEL_SHA256' firmware/main/CMakeLists.txt` prints at least one line, and `grep -rn '4be2ac2b' firmware/main` prints nothing, so the hash comes from core/detector_tables.h and is not copied.

5. The Python tests pass.
   - The command is `reference/.venv/bin/python -m pytest tests -q`.
   - The 65 cases from features 2 to 8 run unchanged.
   - In tests/firmware/test_record_run.py, each case writes a made-up gzip log to a temporary file and calls record_run.py's main() with `--log-only`, `--minutes 3`, and `--report` set to a temporary file. The clean log is the clean log of test_pipeline_run.make_log(False) with these changes. Its SENSOR_MINUTE lines end with record_drops=0, and its USB_MINUTE lines end with port_drops=0 restarts=0 bytes=900000 commands=0 bad_commands=0 stack_free=2000. A B line with boot ID 305419896, reset cause 11, version 9, and the hash from core/detector_tables.h comes right before START. An S line with rate 0 follows the STRETCH line, and a second S line with rate 114330200 follows the RATE line. T lines of 11 readings each start at reading 0 and t0 and follow every 96,200 microseconds, each with its 11 R lines, until they cover the readings of the last SENSOR_MINUTE line. A W line with the same values follows each ANSWER line, and an F line with the same time and state follows each FACE line.
     1. The clean log gives exit code 0, and the report gives the bytes per second and the free stack of each task.
     2. Eleven changed copies each give exit code 1. One drops an R line. One changes a T line's count from 11 to 10. One changes the probability text of a W line. One changes the state of an F line. One adds "I (1140) QMI8658: QMI8658 initialized successfully" after the B line. One adds a second B line with another boot ID. One changes the hash of the B line. One sets record_drops=1 in the last SENSOR_MINUTE line. One sets port_drops=1 in the last USB_MINUTE line. One changes the rate of the second S line. One removes a W line.
     3. The clean log with the first ten lines of tests/firmware/pipeline_log.txt before the B line gives exit code 0, and the report counts 10 lines before the B line.
     4. Every function in record_run.py, command_run.py, drop_run.py, and the three test files has a type hint on each argument and on its return. The three scripts contain no `print(`, no `os.path`, and no `except Exception`, and no line in them starts with `import serial`.
   - In tests/firmware/test_command_run.py, the clean log is a made-up log of every step of check 9 in order, with the commands as `> ` lines, the watch's answers, and a few T and R lines in each boot. The scheduled minute is 600, the offset is 60 minutes, and the CLOCK command's UTC time is 08:57:00 on 23 October 2026.
     5. The clean log gives exit code 0.
     6. Eleven changed copies each give exit code 1. One answers `TONE,2` with A,4,0. One gives tone=1 in the SETTINGS line of boot 2. One puts the F line with state 4 2 seconds after the scheduled time. One removes that F line. One puts the F line that ends the due state 899 seconds after the scheduled time. One gives face=1 to an ANSWER line inside the due state. One gives boot 2 the boot ID of boot 1. One puts the CLOCK line's local_us 3 seconds from the command's time. One adds a second TONE line to boot 2. One gives answers=500 in the first STATE_MINUTE line after the SESSION line. One adds an F line with state 4 to boot 2 before the CLOCK command.
     7. restore_commands() gives ["SCHEDULE", "TONE,1"] for the fields of `SETTINGS source=boot store=empty tone=1 times=none name=`. It gives ["SCHEDULE,Levodopa,480,1200", "TONE,0"] for the fields of `SETTINGS source=boot store=ok tone=0 times=480,1200 name=Levodopa`.
   - In tests/firmware/test_drop_run.py, each case writes a made-up gzip log with the `> CLOSE` and `> OPEN` lines and calls drop_run.py's main() with `--log-only`.
     8. A log with port_drops=3 in the last USB_MINUTE line, one gap in the T numbers after the `> OPEN` line, and a B line and an S line between the two T lines at the gap gives exit code 0. The report says that the watch dropped 3 lines.
     9. A log with port_drops=0 and one gap in the T numbers with no B line at the gap gives exit code 0. The report says that the watch dropped no line and that the lines were lost on the laptop's side.
     10. Five changed copies of case 8's log each give exit code 1. One adds a second START line. One removes the B line at the gap. One sets line_drops=2 in the last USB_MINUTE line. One lowers the window number of the first ANSWER line after the gap by 30. One adds the half line "R,1234,5" after the `> OPEN` line.
   - The expected result is 75 passed.

6. The reference, the earlier code, and the earlier records have not changed.
   - The command is `git diff 57d4d39 --stat -- reference/ context/ core/kissfft/ core/detector.h core/detector_tables.h core/reading_time.h core/converter.h core/window.h core/share.h core/face.h core/dose.h core/imu_units.h core/pipeline.h core/session.h core/detector.c core/reading_time.c core/converter.c core/window.c core/share.c core/face.c core/dose.c core/imu_units.c core/pipeline.c core/session.c core/replay.c tools/ tests/unity/ tests/detector/ tests/reading_time/ tests/converter/ tests/window/ tests/share/ tests/face/ tests/dose/ tests/response/ tests/pads/ tests/reference/ tests/tools/ tests/imu_units/ tests/model/ tests/pipeline/ tests/session/ tests/firmware/table_run.py tests/firmware/test_table_run.py tests/firmware/table_log.txt tests/firmware/table_report.md tests/firmware/pipeline_run.py tests/firmware/test_pipeline_run.py tests/firmware/pipeline_log.txt tests/firmware/pipeline_report.md tests/firmware/chip_windows.py tests/firmware/test_chip_windows.py tests/firmware/chip_windows_log.txt tests/firmware/chip_windows_report.md tests/firmware/windows_bin.py firmware/main/pipeline_task.c firmware/main/screen_task.c firmware/bringup/ firmware/components/ firmware/detector_check/ Makefile CMakeLists.txt`.
   - The command prints nothing.

7. The repo holds the right files.
   - The command is `git diff 57d4d39 --stat` on the feature branch after the validate commit.
   - The expected result lists specs/roadmap.md, specs/tech-stack.md, the three files in specs/features/09-usb-recording/, core/CMakeLists.txt, core/record.h, core/record.c, core/recording_format.md, tests/CMakeLists.txt, tests/record/test_record.c, firmware/sdkconfig.defaults, firmware/sdkconfig, firmware/main/CMakeLists.txt, firmware/main/tasks.h, firmware/main/main.c, firmware/main/sensor_task.c, firmware/main/state_task.c, firmware/main/usb_task.c, firmware/main/settings.h, firmware/main/settings.c, tests/firmware/record_run.py, tests/firmware/test_record_run.py, tests/firmware/command_run.py, tests/firmware/test_command_run.py, tests/firmware/drop_run.py, tests/firmware/test_drop_run.py, and the six output files of checks 8 to 10. firmware/dependencies.lock may appear only if the build changed it. The list holds no other file.

8. The watch writes the full recording for 30 minutes.
   - The watch lies still on a table on USB power with firmware/ flashed. The command is `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/record_run.py`. It runs for about 31 minutes, so it runs in the background, and nothing else may use the port meanwhile.
   - The expected result is exit code 0, which means that every pass check below holds. The script writes tests/firmware/record_log.txt.gz and tests/firmware/record_report.md.
     1. All 13 pass checks of tests/firmware/table_run.py and all 8 pass checks of tests/firmware/pipeline_run.py hold on the diagnostic lines of the log with 30 minutes.
     2. The log holds one B line, and it comes before the START line. Its boot ID and reset cause are whole numbers, its version is 9, and its hash equals DET_MODEL_SHA256 in core/detector_tables.h. The lines before it come from the chip's ROM and bootloader, and the report counts them.
     3. From the B line on, every line is a record line that matches its pattern in core/recording_format.md, or a diagnostic line whose first word has at least three upper-case letters, digits, or underscores and no comma. No line from the B line on starts with "I (", "W (", "E (", "D (", or "V (", so no ESP-IDF log line reaches the port.
     4. Each stretch has one S line, or two when the first gives rate 0. Its S lines have the number, first reading, and t0 of its STRETCH line and the range 1024, and the last of them gives the rate of its RATE line. The first S line of a stretch comes before the stretch's first T line, and that T line's stamp equals t0.
     5. The T lines cover the reading numbers from 0 with no gap and no overlap, and their stamps rise. Each T line is followed by exactly its count of R lines, numbered in order, before the next T line. Every R value lies from -32768 to 32767. The last R number plus 1 is at least the readings field of SENSOR_MINUTE minute 30.
     6. The log holds one W line for each ANSWER line, in the same order. Each W line has the stretch, window, and code of its ANSWER line and the same text for prob, below, and peak.
     7. The log holds one F line for each FACE line, in the same order, with the FACE line's at_us as its time and the same state.
     8. The log holds no D line and no A line.
     9. At minute 30, SENSOR_MINUTE shows record_drops=0, and USB_MINUTE shows line_drops=0, port_drops=0, restarts=0, and commands=0.
   - The Results section records these measurements from the report with no limit. They are the bytes per second from USB_MINUTE and from the log, the lines per second, the largest gap between two line arrivals on the laptop after the first minute, the number of lines before the B line, the free stack of the pipeline, state, and USB tasks at each minute, and pipeline_run.py's run time and delay measurements.

9. The watch takes the four commands, keeps its settings over a restart, and makes a dose due.
   - The watch lies still on a table on USB power with firmware/ flashed. The command is `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/command_run.py`. It runs for about 23 minutes, so it runs in the background, and nothing else may use the port meanwhile.
   - The script runs these steps in order, and the expected result is exit code 0, which means that every pass check holds. The script writes tests/firmware/command_log.txt.gz and tests/firmware/command_report.md.
     1. It resets the watch and waits for the first FACE line with state 1. Boot 1 has one B line before START with version 9 and the table hash, and one SETTINGS line with source=boot.
     2. It sends nine bad commands, and they get these answers in this order. `HELLO` gets A,0,1. `TONE` gets A,4,2. `TONE,2` gets A,4,3. `CLOCK,abc,0` gets A,1,2. `CLOCK,1761206400000000,900` gets A,1,3. `SCHEDULE,Levodopa,1440` gets A,2,3. `SCHEDULE,Levodopa,480,480` gets A,2,3. `SESSION,1` gets A,3,2. A line of 200 "X" characters gets A,0,2. No CLOCK line, SESSION line, or SETTINGS line with source=command comes before the last of these answers.
     3. `TONE,0` gets A,4,0, and a SETTINGS line with source=command, store=ok, and tone=0 comes before the answer.
     4. The script takes T as the laptop's local time 240 seconds later, rounded up to the next whole minute, and m as T's minute of the local day. `SCHEDULE,TestDose,<m>` gets A,2,0, and a SETTINGS line with source=command, store=ok, times=<m>, and name=TestDose comes before the answer.
     5. It resets the watch. Boot 2 has one B line with version 9 and the table hash, and its boot ID differs from boot 1's. Its SETTINGS line with source=boot gives store=ok, tone=0, times=<m>, and name=TestDose. The script waits for STATE_MINUTE minute 1, and that line gives clock=0 and schedule=1. So the restart kept the schedule and the tone and left the clock unset.
     6. `CLOCK,<utc_us>,<offset_min>` with the laptop's UTC time and local offset gets A,1,0. The CLOCK line before the answer has a local_us within 1 second of utc_us + offset_min × 60,000,000. The next STATE_MINUTE line gives clock=1.
     7. The script waits until 10 seconds after T. Boot 2 holds exactly one F line with state 4. Its local time, which is its time plus the CLOCK line's offset_us, lies from T to T + 1.1 seconds. Boot 2 holds exactly one TONE line, with enabled=0, and it lies between the last ANSWER line before that F line and the first ANSWER line after it.
     8. The script waits until 910 seconds after T. Every ANSWER line between the F line with state 4 and the next F line has face=4. That next F line has state 1, and its local time lies from T + 900 to T + 901.1 seconds. Every STATE_MINUTE line between the two F lines gives due=1.
     9. `SESSION` gets A,3,0. Before the answer come a SESSION line with changed=1 and an F line with state 3. The first two ANSWER lines after the SESSION line have code 1, and an F line with state 1 comes after the second of them and before the third. The first STATE_MINUTE line after the SESSION line gives answers of at most 61 and doses=0, and the last STATE_MINUTE line before it gives answers above 61.
     10. `TONE,1` gets A,4,0, and a SETTINGS line with tone=1 comes before the answer.
     11. The commands that restore_commands() gives for boot 1's SETTINGS line get A,2,0 and A,4,0.
     12. In both boots, every line from the B line on follows the format rule of check 8 item 3, apart from the script's own lines that start with "> " and the ROM lines between the reset and boot 2's B line. Each boot holds exactly one START line.
   - The Results section records these measurements from the report with no limit. They are the delay from T to the due F line, the delay from T + 900 seconds to the F line that ends the due state, the clock difference, boot 2's reset cause, the time from each command to its answer on the laptop, and the free stack of the state and USB tasks.

10. The watch keeps working while nobody reads the port.
    - The watch lies still on a table on USB power with firmware/ flashed. The command is `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/drop_run.py`. It runs for about 5 minutes, and nothing else may use the port meanwhile.
    - The expected result is exit code 0, which means that every pass check below holds. The script writes tests/firmware/drop_log.txt.gz and tests/firmware/drop_report.md.
      1. The log holds one START line, and every B line in it has the same boot ID, reset cause, version, and hash. So closing and opening the port did not reset the watch.
      2. Every line from the first B line on follows the format rule of check 8 item 3, apart from the script's own lines that start with "> ". So every line that arrived is whole.
      3. At least 50 T lines come before the `> CLOSE` line, and at least 50 come after the `> OPEN` line.
      4. The last USB_MINUTE line gives line_drops=0, the last SENSOR_MINUTE line gives msg_drops=0 and record_drops=0, the last PIPELINE_MINUTE line gives answer_drops=0 and faults=0, and the last STATE_MINUTE line gives screen_drops=0. So no task waited on the closed port.
      5. For each two ANSWER lines in a row in the log that have the same stretch and an at_us at least 15 seconds after its t0, the second at_us minus the first lies from 0.9 to 1.1 seconds for each step in the window number. At least one such pair spans 50 or more windows, so the answers went on while the port was closed.
      6. The T numbers have at most one gap, and the second T line at the gap lies after the `> OPEN` line. When the last USB_MINUTE line gives port_drops above 0, the gap exists, and a B line and an S line equal to the stretch's latest S line lie between the two T lines at the gap, and restarts is at least 1. When port_drops is 0, the report says that the watch dropped no line and whether the laptop's side lost lines.
    - The Results section records port_drops, restarts, the size of the gap in reading numbers, and the number of lines that arrived after the `> OPEN` line from before the close. If port_drops is 0, it says that this check showed only that the watch never waited on the port, and that check 11 must show the drop.

## Manual checks

11. The watch drops lines while the cable is out and recovers when it is back.
    - This check needs a charged battery in the watch, because the power chip reported no battery in feature 7 and the watch turns off without USB power.
    - Run `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/drop_run.py --unplug --log SCRATCH/unplug_log.txt.gz --report SCRATCH/unplug_report.md`. When the script asks, unplug the USB cable, wait about 60 seconds, and plug it back.
    - The expected result is exit code 0 with port_drops above 0. The report shows a B line and an S line at the gap.

12. The holding screen shows Dose due.
    - Look at the watch during check 9, between T and T + 900 seconds.
    - The expected result is that the screen shows "Dose due" under the uptime, and "No tremor" again after T + 900 seconds.

## Requirement coverage

Requirement 1 is covered by checks 8 and 10. Requirement 2 is covered by check 1 cases 2 to 10 and check 8 items 3 and 5. Requirement 3 is covered by check 1 case 2, check 4 item 10, and check 8 item 2. Requirement 4 is covered by check 1 case 3 and check 8 item 4. Requirements 5 and 6 are covered by check 1 cases 4 and 5 and check 8 item 5. Requirement 7 is covered by check 1 cases 6 and 7 and check 8 item 6. Requirement 8 is covered by check 1 case 8 and check 8 item 7. Requirement 9 is covered by check 1 case 9 only, as requirement 37 says. Requirement 10 is covered by check 1 cases 12 to 14 and check 9 items 2 to 11. Requirement 11 is covered by check 9 items 5 and 6. Requirement 12 is covered by check 9 items 4, 7, and 8 and check 12. Requirement 13 is covered by check 4 item 8 and check 9 item 5. Requirement 14 is covered by check 8 item 2 and check 9 items 5 and 9. Requirement 15 is covered by checks 1 and 2 and a reading of core/recording_format.md. Requirement 16 is covered by check 4 items 3, 4, and 9 and check 8 items 3, 5, and 9. Requirement 17 is covered by check 10 and check 11. Requirement 18 is covered by check 6 and check 8 item 1. Requirement 19 is covered by the free stack measurements of checks 8 and 9. Requirement 20 is covered by checks 2 and 3. Requirement 21 is covered by checks 2 and 6. Requirement 22 has no check on the watch, and it waits for the user. Requirements 23 and 24 are covered by check 4 items 3, 4, and 9, check 8 items 3 and 9, and checks 10 and 11. Requirement 25 is covered by check 8 items 5 and 9. Requirements 26 and 27 are covered by check 1 cases 2 to 11 and check 8 items 4 to 7. Requirement 28 is covered by check 1 case 2, check 4 item 10, and check 8 item 2. Requirement 29 is covered by check 6 and check 8 items 1 and 3. Requirements 30 and 31 are covered by check 1 cases 12 and 13 and check 9 item 2. Requirement 32 is covered by check 1 case 14 and check 9 items 5 and 6. Requirement 33 is covered by check 4 item 8 and check 9 items 3 to 5 and 11. Requirement 34 is covered by check 1 cases 12 and 13. Requirement 35 is covered by check 9 items 3, 7, and 10. Requirement 36 is covered by checks 1 and 2. Requirement 37 is covered by check 1 case 9 and check 4 item 7. Requirement 38 is covered by checks 5 and 8 to 10. Requirement 39 is covered by checks 10 and 11. Requirement 40 is covered by check 7 and a reading of specs/tech-stack.md.
