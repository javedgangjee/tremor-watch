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
   9. `grep -cE '^CONFIG_ESP_CONSOLE_SECONDARY_NONE=y$' firmware/sdkconfig firmware/sdkconfig.defaults` gives 1 for each file, and `grep -c '^CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y' firmware/sdkconfig` gives 0. `git diff 57d4d39 -- firmware/sdkconfig | grep -E '^[-+]' | grep -vE '^(\+\+\+|---)' | grep -vxE '[-+]# default:' | grep -vE 'CONSOLE|USB_SERIAL_JTAG|USJ_'` prints nothing, so the console change moved only options about the console and the USB Serial/JTAG port. The filter `grep -vxE '[-+]# default:'` leaves out only the whole lines "# default:". ESP-IDF v6.1 writes such a marker line above each option that still has its default value, and a marker line holds no option, so it moves with the option it marks.
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
     8. A log with port_drops=3 in the last USB_MINUTE line has two gaps in the T numbers. The first is a gap at the close as item 6 of check 10 defines it. The `> CLOSE` line follows a T line, and the laptop loses every line from there to the middle of an R line two bursts later. So the first text after the `> OPEN` line is a `> PARTIAL` line with the rest of that R line. The second is the watch's own gap after the `> OPEN` line, with a B line and an S line between its two T lines. The log gives exit code 0. The report says that the watch dropped 3 lines and that the laptop lost the lines at the close.
     9. A log with port_drops=0 and one gap in the T numbers with no B line at the gap gives exit code 0. The report says that the watch dropped no line and that the lines were lost on the laptop's side.
     10. Seven changed copies of case 8's log each give exit code 1. One adds a second START line. One removes the B line at the watch's gap. One sets line_drops=2 in the last USB_MINUTE line. One lowers the window number of the first ANSWER line after the watch's gap by 30. One adds the half line "R,1234,5" after the `> OPEN` line. One removes the second R line after the `> PARTIAL` line, so the loss at the close does not end at the first text after the `> OPEN` line. One removes a T line and its R lines after the watch's gap, so the watch has two gaps of its own.
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
      6. The T numbers may have one gap at the close, which the laptop makes. When the script closes the port, the Mac throws away the bytes it already holds, so the lines from the `> CLOSE` line up to the first text after the `> OPEN` line never reach the log. That first text may be the rest of a line, which the script logs as a `> PARTIAL` line. A gap counts as the gap at the close when all of these hold. Its first T line is the last T line before the `> CLOSE` line. Its second T line is the first T line after the `> OPEN` line. No B line lies between its two T lines. From the first line after the `> OPEN` line up to its second T line, the R lines follow on with no missing number and end at the reading just before that T line. So the loss starts at the `> CLOSE` line and ends at the first text after the `> OPEN` line. The report gives the size of this gap and the first text after the `> OPEN` line. Apart from the gap at the close, the T numbers have at most one gap, which is the watch's own, and its second T line lies after the `> OPEN` line. When the last USB_MINUTE line gives port_drops above 0, the watch's gap exists, a B line and an S line equal to the stretch's latest S line lie between its two T lines, and restarts is at least 1. When port_drops is 0, the report says that the watch dropped no line and whether the laptop's side lost lines.
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

## Results, 2026-10-23

The validate stage ran on branch feature/09-usb-recording at commit 50899e6 with a clean tree. It first removed build/, firmware/build/, firmware/bringup/build/, and firmware/detector_check/build/, so every check ran from a clean build. The watch was flashed with the firmware/ build of check 3 before checks 8 to 10. The full watch runs ran at their full length.

Checks 1, 2, 3, 5, 6, 7, 8, and 9 passed. Check 4 failed on items 3 and 9, and check 10 failed on item 6. Checks 11 and 12 wait for the user. So the feature is not ready for review as written. The sections below give each failure and say whether it points at the code or at the check.

### Automated checks

1. Check 1 passed. The build printed no warning, and CTest reported "100% tests passed out of 12". The eleven tests from features 4 to 8 passed unchanged. test_record ran its 14 cases, one for each case of the check, and all passed. A reading of tests/record/test_record.c found the lines and values that the check names.
2. Check 2 passed. All five commands printed nothing.
3. Check 3 passed. In item 1 the clean `make check` exited with code 0, and the log shows "100% tests passed out of 12" on line 94, "model hash matches" on line 99, and "Project build complete" on line 2517. In item 2 the detector_check build exited with code 0. In item 3 each of the two compile_commands.json files gave thirteen lines with True in the first column. The eleven project files, which include record.c, had True in the second column, and the two KISS FFT files had False. Items 4 and 5 printed nothing.
4. Check 4 failed on items 3 and 9 as written. Items 1, 2, 4, 5, 6, 7, 8, and 10 passed. Item 1 listed the eleven files of feature 8 and settings.c and settings.h. Item 10 printed five lines of firmware/main/CMakeLists.txt and found no copy of the hash.
   - Item 3 failed. The grep printed firmware/main/usb_task.c. The match is a comment on line 252 that starts "The ROM's printf also writes to this port". No code in firmware/main calls printf, puts, putchar, fputs, or fwrite, so no task writes to stdout, and check 8 item 3 showed that no ESP-IDF log line reached the port. But plan step 9 says that no file in firmware/main names these words even in a comment, and change 4 in the plan says that item 3 prints nothing. The comment came with change 2. This failure points at the code, and rewording the comment fixes it.
   - Item 9 failed as written. Its first two commands gave 1 for each file and 0. The third command printed four lines that read "# default:", three with a minus sign and one with a plus sign. The full diff shows that every option line that changed names CONSOLE or USB_SERIAL_JTAG. The removed lines set CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG and CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED and left CONFIG_ESP_CONSOLE_SECONDARY_NONE unset. The added lines set CONFIG_ESP_CONSOLE_SECONDARY_NONE, unset CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG, and add the unset option CONFIG_ESP_TRACE_TRANSPORT_USB_SERIAL_JTAG. Each "# default:" line is a marker that ESP-IDF v6.1 writes above an option that still has its default value, and the four marker lines move with the options they mark. This stage also made a new sdkconfig from firmware/sdkconfig.defaults in a scratch folder with `idf.py -C firmware -B <scratch>/build -D SDKCONFIG=<scratch>/sdkconfig reconfigure`, and it is the same as the committed firmware/sdkconfig byte for byte. So the console change moved only options about the console and the USB Serial/JTAG port, which is what the check is meant to prove. The failure points at the check, because its filter does not allow the marker lines.
5. Check 5 passed. pytest reported 75 passed. The 65 cases from features 2 to 8 passed unchanged. A reading of the three new test files found the changed copies that cases 2, 6, and 10 name, eleven, eleven, and five of them. The three scripts hold no `print(`, no `os.path`, no `except Exception`, and no line that starts with `import serial`.
6. Check 6 passed. The command printed nothing.
7. Check 7 passed. With the six output files and validation.md staged, `git diff --cached 57d4d39 --stat` listed 33 files. They are the 27 files the check names and the six output files of checks 8 to 10. firmware/dependencies.lock did not appear, and no other file did. The stage ran the command of the check again after the commit.
8. Check 8 passed. record_run.py exited with code 0 after about 31 minutes. All 13 pass checks of table_run.py and all 8 pass checks of pipeline_run.py held, and all 8 record line checks held.
   - The log holds one B line, `B,4097841975,11,9,4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e`, and 107 lines came before it.
   - No line from the B line on broke the format, and no ESP-IDF log line reached the port.
   - The log holds 2 stretches, each with its S lines, and 18733 T lines that cover 206052 readings with no gap and no overlap.
   - The log holds 1795 W lines for 1795 ANSWER lines, and 3 F lines for 3 FACE lines. It holds no D line and no A line.
   - At minute 30 record_drops, line_drops, port_drops, restarts, and commands were all 0.
   - USB_MINUTE gives 4419 bytes a second over 30 minutes, and the log gives 4419 bytes a second and 127 lines a second. specs/tech-stack.md says about 4,200 bytes a second and requirement 23 says about 4,500. No check covers that number.
   - The largest gap between two line arrivals on the laptop after the first minute was 0.101 seconds.
   - The pipeline task's free stack was 2528 bytes at minute 1, 2368 bytes at minutes 2 to 6, and 2320 bytes at minutes 7 to 30. The state task's free stack was 2252 bytes at every minute. The USB task's free stack was 2700 bytes at minutes 1 and 2 and 2636 bytes at minutes 3 to 30.
   - The detector run time was 6776 microseconds at the least, 6868 as the median, and 8874 at the most. The delay from the burst's stamp to the end of the run had a median of 12696 microseconds and a maximum of 60049. Stretch 0 gave its window 0 answer 10.020 seconds after its t0, and stretch 1 gave its window 0 answer 4.149 seconds after its t0.
   - The time rule ended stretch 0 by itself at about 1637 seconds, with kind 2 and reason=time. So the watch wrote a GAP line with changed=1, an F line with state 3, and a second stretch whose S line had the new rate, and the face went back to state 1 about 6 seconds later. The gap path with face_gap() therefore ran once on the watch, although no check asked for it. The sensor task's side of the end request still did not run on the watch.
9. Check 9 passed. command_run.py exited with code 0 after about 23 minutes, and all 12 pass checks held.
   - Boot 1's B line had boot ID 317511800 and boot 2's had 3421497796. Both had version 9 and the table hash.
   - The nine bad commands got the nine answers in order. The scheduled minute was 303. Boot 2's SETTINGS line kept tone=0, times=303, and name=TestDose, and its first STATE_MINUTE line gave clock=0 and schedule=1.
   - The clock difference was 0 microseconds.
   - The due F line came 0.876 seconds after T, and the F line that ended the due state came 0.876 seconds after T + 900 seconds.
   - Boot 2's reset cause was 11.
   - The time from a command to its answer on the laptop had a median of 0.011 seconds and a maximum of 0.021 seconds over 16 commands.
   - The state task's free stack was 2268 bytes at the first minute and 2252 bytes after. The USB task's free stack was 2700 bytes at the first minute and 2636 bytes after.
   - The script put back boot 1's settings with `SCHEDULE` and `TONE,1`, and they got A,2,0 and A,4,0.
10. Check 10 failed on item 6 as written. drop_run.py exited with code 1. Items 1 to 5 passed. The log holds one START line and one boot ID, and every line from the B line on is whole. 730 T lines came before the `> CLOSE` line and 1568 after the `> OPEN` line. line_drops, msg_drops, record_drops, answer_drops, faults, and screen_drops were all 0. The widest pair of answers spanned 62 windows with every step from 0.9 to 1.1 seconds.
    - Item 6 failed because the T numbers show two gaps after the B line. The last USB_MINUTE line gives port_drops=7483 and restarts=1. The USB_MINUTE line of minute 2 is missing, because the watch dropped it while the port was closed.
    - The first gap lies at the close. The script read `T,8019,11,70362012`, wrote `> CLOSE`, and closed the port. After the `> OPEN` line the first text was the rest of a line, `-29,-3771`, which the script logged as `> PARTIAL -29,-3771`. Then came `R,8049` to `R,8051` and `T,8052`. So the R lines of readings 8019 to 8048 and the T lines of 8030 and 8041 never reached the log. The size of this gap in T numbers is 22 readings, and the R lines of 30 readings are missing.
    - The second gap is the watch's own. After `R,8137` come `B,3297436761,...`, which is the same boot, and `S,0,0,234331,114348715,1024`, which equals the latest S line, and then `T,14883`. This gap spans 6743 readings, which is about 59 seconds.
    - The lines lost at the close were lost on the laptop's side. The watch puts each line into its buffer whole or not at all, so the half line after the open can only come from bytes the laptop threw away. And the drop rule makes the watch write the B and S lines before the next line after any drop, but no B line lies between `T,8019` and `T,8052`. So the watch wrote those lines and the laptop dropped them when the script closed the port. The 98 lines from before the close that arrived after the `> OPEN` line, from the half line to `R,8137`, are the lines that sat in the watch's send buffer.
    - The code meets what item 6 is meant to prove. The watch dropped lines while nobody read, counted them, never made a task wait, and brought back the B line and the latest S line at its own gap, with restarts=1. The check fails because it allows one gap and does not allow for the laptop's loss at the close. This failure points at the check. A fix could leave out a gap whose first T line is the last T line before the `> CLOSE` line.

### Manual checks

11. Check 11 waits for the user. The watch needs a charged battery, because the power chip reported no battery in feature 7 and the watch turns off without USB power. Run `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/drop_run.py --unplug --log SCRATCH/unplug_log.txt.gz --report SCRATCH/unplug_report.md`. When the script asks, unplug the USB cable, wait about 60 seconds, and plug it back. The expected result is exit code 0 with port_drops above 0, and the report shows a B line and an S line at the gap. The same laptop loss at the close may give a second gap here too, so item 6 may fail for the reason of check 10.
12. Check 12 waits for the user. Run check 9 again and look at the watch between T and T + 900 seconds. The expected result is that the screen shows "Dose due" under the uptime, and "No tremor" again after T + 900 seconds.

### Requirement coverage

Every requirement has at least one passing check, apart from requirements 17, 22, and 39.

- Requirement 17 has no passing check as written. Check 10 fails on item 6 for the reason given above, and check 11 waits for the user. Items 1 to 5 of check 10 pass, and the watch's side of item 6 holds.
- Requirement 22 has no check on the watch by design, and it waits for the user. Check 8 shows that the gap path with face_gap() ran once on the watch through a time rule end, but the sensor task's side of the end request did not run.
- Requirement 39 has no passing check as written for the same reason as requirement 17.

Requirements 16, 23, and 24 list check 4 items 3 and 9, which failed, but each also has passing items in check 4 item 4 and check 8 items 3 and 9. Requirement 12 has check 9 and waits for check 12. A reading of core/recording_format.md found every part that plan step 2 names, which covers requirement 15 with checks 1 and 2. A reading of specs/tech-stack.md found the console change, the usb_serial_jtag driver, core/record.h, core/recording_format.md, the settings store, and the three script commands, which covers requirement 40 with check 7.

### State of the watch

The watch is left flashed with the firmware/ build of commit 50899e6. Its last boot, in check 10's log, read `SETTINGS source=boot store=ok tone=1 times=none name=`, so the schedule is off and the tone is on.

### Decisions in this stage

The user asked for this run to go on with no input and to commit even with failing checks. So this stage committed validation.md and the six output files. It did not change the text of any check, any code, or any script. The user decides whether to fix the comment in usb_task.c, whether to change the filters of check 4 item 9 and check 10 item 6, and whether the gap path run of check 8 is enough for requirement 22. The agent decided this on 23 October 2026, and the user has not reviewed it yet.

## Results of the second run, 2026-10-23

This second validate stage ran on branch feature/09-usb-recording at commit 2c961e0, which rewords the comment in usb_task.c that check 4 item 3 found. The tree was clean. The stage first removed build/, firmware/build/, firmware/bringup/build/, and firmware/detector_check/build/, so every check ran from a clean build. The watch was flashed with the firmware/ build of check 3 before checks 8 to 10, and the three watch runs ran at their full length. The first Results section above stays as it was.

Checks 1 to 9 passed. Check 4 passed apart from item 9, which failed as written for the same reason as in the first run. Check 10 failed on item 6 as written for the same reason as in the first run. Checks 11 and 12 wait for the user. So the feature is still not ready for review as written. Both failures point at the check, and the user decides whether to change their filters.

### Automated checks

1. Check 1 passed. The build printed no warning, and CTest reported "100% tests passed out of 12". The eleven tests from features 4 to 8 passed unchanged, and test_record ran its 14 cases with 0 failures.
2. Check 2 passed. All five commands printed nothing.
3. Check 3 passed. In item 1 the clean `make check` exited with code 0, and the log shows "100% tests passed out of 12" on line 94, "model hash matches" on line 99, and "Project build complete" on line 2517. In item 2 the detector_check build exited with code 0. In item 3 each of the two compile_commands.json files gave thirteen lines with True in the first column. The eleven project files, which include record.c, had True in the second column, and the two KISS FFT files had False. Items 4 and 5 printed nothing.
4. Check 4 failed on item 9 as written. Items 1 to 8 and item 10 passed.
   - Item 1 listed the eleven files of feature 8 and settings.c and settings.h.
   - Item 3 now passes. The grep printed nothing, so the reworded comment fixed the failure of the first run.
   - Item 5 printed settings.c and state_task.c. The three matches in settings.c are the lines that define settings_load(), settings_save_schedule(), and settings_save_tone().
   - Item 10 printed five lines of firmware/main/CMakeLists.txt and found no copy of the hash.
   - Item 9 failed as written for the same reason as in the first run. Its first two commands gave 1 for each file and 0. The third command printed four lines that read "# default:", three with a minus sign and one with a plus sign. The full diff shows that every option line that changed names CONSOLE or USB_SERIAL_JTAG. The removed option lines are CONFIG_ESP_CONSOLE_SECONDARY_NONE unset, CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG=y, and CONFIG_ESP_CONSOLE_USB_SERIAL_JTAG_ENABLED=y. The added option lines are CONFIG_ESP_CONSOLE_SECONDARY_NONE=y, CONFIG_ESP_CONSOLE_SECONDARY_USB_SERIAL_JTAG unset, and CONFIG_ESP_TRACE_TRANSPORT_USB_SERIAL_JTAG unset. Each "# default:" line is a marker that ESP-IDF v6.1 writes above an option that still has its default value, and the four marker lines move with the options they mark. This stage made a new sdkconfig from firmware/sdkconfig.defaults in a scratch folder with `idf.py -C firmware -B <scratch>/build -D SDKCONFIG=<scratch>/sdkconfig reconfigure`, and cmp found it the same as the committed firmware/sdkconfig byte for byte. So the code meets what the item is meant to prove, which is that the console change moved only options about the console and the USB Serial/JTAG port. The failure points at the check, because its filter does not allow the marker lines.
5. Check 5 passed. pytest reported 75 passed. The 65 cases from features 2 to 8 passed unchanged. All 122 functions in the three scripts and the three test files have a type hint on each argument and on their return. The three scripts hold no `print(`, no `os.path`, no `except Exception`, and no line that starts with `import serial`.
6. Check 6 passed. The command printed nothing.
7. Check 7 passed. With the six output files and validation.md staged, `git diff --cached 57d4d39 --stat` listed 33 files. They are the 27 files the check names and the six output files of checks 8 to 10. firmware/dependencies.lock did not appear, and no other file did. The stage ran the command of the check again after the commit.
8. Check 8 passed. record_run.py exited with code 0 after about 31 minutes. All 13 pass checks of table_run.py, all 8 pass checks of pipeline_run.py, and all 8 record line checks held.
   - The log holds one B line, `B,2274443476,11,9,4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e`, and 103 lines came before it.
   - No line from the B line on broke the format, and no ESP-IDF log line reached the port.
   - The log holds 1 stretch with its two S lines, and 18732 T lines that cover 206041 readings with no gap and no overlap.
   - The log holds 1798 W lines for 1798 ANSWER lines, and 1 F line for 1 FACE line. It holds no D line and no A line.
   - At minute 30 record_drops, line_drops, port_drops, restarts, and commands were all 0.
   - USB_MINUTE gives 4439 bytes a second over 30 minutes, and the log gives 4439 bytes a second and 127 lines a second.
   - The largest gap between two line arrivals on the laptop after the first minute was 0.103 seconds.
   - The pipeline task's free stack was 2528 bytes at minute 1, 2368 bytes at minute 2, and 2240 bytes at minutes 3 to 30. That is 80 bytes less than the 2320 of the first run. The state task's free stack was 2268 bytes at minutes 1 and 2 and 2252 bytes at minutes 3 to 30. The USB task's free stack was 2700 bytes at minute 1 and 2636 bytes at minutes 2 to 30.
   - The detector run time was 6787 microseconds at the least, 6868 as the median, and 8857 at the most. The delay from the burst's stamp to the end of the run had a median of 12697 microseconds and a maximum of 60076. Stretch 0 gave its window 0 answer 10.020 seconds after its t0.
   - No stretch ended in this run, so the gap path did not run on the watch this time.
9. Check 9 passed. command_run.py exited with code 0 after about 23 minutes, and all 12 pass checks held.
   - Boot 1's B line had boot ID 3162426297 and boot 2's had 505078862. Both had version 9 and the table hash.
   - The nine bad commands got the nine answers in order. The scheduled minute was 366. Boot 2's SETTINGS line kept tone=0, times=366, and name=TestDose, and its first STATE_MINUTE line gave clock=0 and schedule=1.
   - The clock difference was 0 microseconds.
   - The due F line came 0.073 seconds after T, and the F line that ended the due state came 0.073 seconds after T + 900 seconds.
   - Boot 2's reset cause was 11.
   - The time from a command to its answer on the laptop had a median of 0.011 seconds and a maximum of 0.021 seconds over 16 commands.
   - The state task's free stack was 2284 bytes at the first minute, 2268 bytes at the second, and 2252 bytes after. The USB task's free stack was 2700 bytes at the first five minutes and 2636 bytes after.
   - The script put back boot 1's settings with `SCHEDULE` and `TONE,1`, and they got A,2,0 and A,4,0.
10. Check 10 failed on item 6 as written, for the same reason as in the first run. drop_run.py exited with code 1. Items 1 to 5 passed. The log holds one START line and one boot ID, and every line from the B line on is whole. 730 T lines came before the `> CLOSE` line and 1569 after the `> OPEN` line. line_drops, msg_drops, record_drops, answer_drops, faults, and screen_drops were all 0. The widest pair of answers spanned 62 windows with every step from 0.9 to 1.1 seconds.
    - The last USB_MINUTE line gives port_drops=7482 and restarts=1. The USB_MINUTE line of minute 2 is missing, because the watch dropped it while the port was closed.
    - Item 6 failed because the T numbers show two gaps after the B line.
    - The first gap lies at the close. The script read `T,8019,11,70361868`, wrote `> CLOSE`, and closed the port. After the `> OPEN` line the first text was the end of a line, `766`, which the script logged as `> PARTIAL 766`. Then came `R,8051` and `T,8052`. So the R lines of readings 8019 to 8049, the whole text of R line 8050, and the T lines of 8030 and 8041 never reached the log. The gap in T numbers spans 22 readings.
    - The second gap is the watch's own. After `R,8138` come `B,2208397704,...`, which is the same boot, and `S,0,0,234312,114348886,1024`, which equals the latest S line, and then `T,14883`. This gap spans 6743 readings, which is about 59 seconds. R line 8139, the last reading of the burst at 8129, is the first line the watch dropped.
    - The lines lost at the close were lost on the laptop's side. The watch puts each line into its buffer whole or not at all, so the half line after the open can only come from bytes the laptop threw away when the script closed the port. The drop rule makes the watch write the B and S lines before the next line after any drop, and no B line lies between `T,8019` and `T,8052`. So the watch sent those lines and the laptop dropped them. The 97 lines from before the close that arrived after the `> OPEN` line, from the half line to `R,8138`, are the lines that sat in the watch's send buffer.
    - The code meets what item 6 is meant to prove. The watch dropped lines while nobody read, counted them, never made a task wait, and brought back the B line and the latest S line at its own gap, with restarts=1. The check fails because it allows one gap and does not allow for the laptop's loss at the close. This failure points at the check.

### Manual checks

11. Check 11 waits for the user. The watch needs a charged battery, because the power chip reported no battery in feature 7 and the watch turns off without USB power. Run `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/drop_run.py --unplug --log SCRATCH/unplug_log.txt.gz --report SCRATCH/unplug_report.md`. When the script asks, unplug the USB cable, wait about 60 seconds, and plug it back. The expected result is exit code 0 with port_drops above 0, and the report shows a B line and an S line at the gap. The laptop may lose lines at the close here too, so item 6 may fail for the reason of check 10.
12. Check 12 waits for the user. Run `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/command_run.py` with the watch in view. T is the local clock time that the script's `SCHEDULE,TestDose,<m>` command names as minute m of the day. It lies 4 to 5 minutes after that command. Look at the watch between T and T + 900 seconds. The expected result is that the screen shows "Dose due" under the uptime, and "No tremor" again after T + 900 seconds.

### Requirement coverage

Every requirement has at least one passing check, apart from requirements 17, 22, and 39.

- Requirement 17 has no passing check as written. Check 10 fails on item 6 for the reason given above, and check 11 waits for the user. Items 1 to 5 of check 10 pass, and the watch's side of item 6 holds.
- Requirement 22 has no check on the watch by design, and it waits for the user. In this run no stretch ended, so the gap path did not run on the watch. The first run saw it run once through a time rule end. The sensor task's side of the end request has not run on the watch.
- Requirement 39 has no passing check as written for the same reason as requirement 17.

Requirements 16, 23, and 24 list check 4 item 9, which failed as written, but each also has passing checks in check 4 items 3 and 4 and check 8 items 3 and 9. Requirement 12 has check 9 and waits for check 12. Requirements 15 and 40 rest on the readings of core/recording_format.md and specs/tech-stack.md that the first run recorded. Neither file changed since then.

### State of the watch

The watch is left flashed with the firmware/ build of commit 2c961e0. Its last boot, in check 10's log, read `SETTINGS source=boot store=ok tone=1 times=none name=`, so the schedule is off and the tone is on.

### Decisions in this stage

The run went on with no input from the user and committed with failing checks, as the user asked. This stage did not change the text of any check, any code, or any script. The user decides whether to change the filters of check 4 item 9 and check 10 item 6, and whether the first run's gap path on the watch is enough for requirement 22. The agent decided this on 23 October 2026, and the user has not reviewed it yet.

## Note on the reworded checks, 2026-10-23

The user ruled that check 4 item 9 and check 10 item 6 were worded wrong, because both failed as written while the code met what each check is meant to prove. The user had both reworded. This note does not change the two Results sections above.

Check 4 item 9 now adds the filter `grep -vxE '[-+]# default:'` to its third command, before the filter for CONSOLE, USB_SERIAL_JTAG, and USJ_. It leaves out only the whole marker lines "# default:" that ESP-IDF v6.1 writes above options still at their default value. Every option line still goes through the old filter. On branch feature/10-laptop-tools at commit 91576f1, the first two commands gave 1 for each file and 0, and the third command printed nothing. So item 9 now passes.

Check 10 item 6 now allows one gap at the close, which the laptop makes. Its first T line is the last T line before the `> CLOSE` line, its second T line is the first T line after the `> OPEN` line, no B line lies between them, and the R lines from the first line after the `> OPEN` line follow on up to that T line. So the loss starts at the `> CLOSE` line and ends at the first text after the `> OPEN` line, which may be a `> PARTIAL` line, and the report gives it. Apart from this gap, the watch still has at most one gap of its own, and when port_drops is above 0 it must have a B line and the latest S line, with restarts at least 1. tests/firmware/drop_run.py and its pytest cases follow the new wording. Check 5 cases 8 and 10 now describe the changed cases. Case 8's log has the loss at the close, and case 10 has seven changed copies. The two new copies break the loss at the close and add a second gap of the watch's own. pytest still reports 75 cases for features 2 to 9, and the full suite reports 105 passed.

The rerun of check 10 on 2026-10-23 used the watch on USB with feature 9's firmware, at the full length of about 5 minutes. drop_run.py exited with code 0, and it wrote tests/firmware/drop_log.txt.gz and tests/firmware/drop_report.md again. Items 1 to 6 passed. The log holds one START line and one boot ID, 3492590314, and every line from the B line on is whole. 730 T lines came before the `> CLOSE` line and 1569 after the `> OPEN` line. line_drops, msg_drops, record_drops, answer_drops, faults, and screen_drops were all 0, and the widest pair of answers spanned 62 windows. The last USB_MINUTE line gives port_drops=7488 and restarts=1.

- The gap at the close runs from `T,8019,11,70361095` to `T,8052`. The first text after the `> OPEN` line was `> PARTIAL 9,-854`, then `R,8047` to `R,8051` came in order. The gap spans 22 readings in the T numbers, and the R lines of 28 readings are missing.
- The watch's own gap runs from the T line at reading 8129 to `T,14883`, and it spans 6743 readings. `B,3492590314,...` and `S,0,0,234278,114350143,1024`, which equals the latest S line, lie between its two T lines.
- 95 lines from before the close arrived after the `> OPEN` line.

So requirements 17 and 39 now have a passing check through check 10. Check 11 still waits for the user, and it may show the same loss at the close, which item 6 now allows. The watch's last boot read `SETTINGS source=boot store=ok tone=1 times=none name=`, so the schedule is off and the tone is on.
