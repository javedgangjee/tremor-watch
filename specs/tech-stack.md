# Tech stack

## Hardware

- The watch is the Waveshare ESP32-S3-Touch-AMOLED-2.06.
- The screen is a 410 by 502 AMOLED touch screen, and it stays on for the whole session.
- The IMU is the QMI8658. It uses rate code 0x06 with the gyroscope and the accelerometer both on, and the gyroscope range is ±1024 degrees per second. The datasheet gives 112.1 readings a second for this code, but feature 1 measured 114.33 on this board over twenty minutes, with a drift of -80.8 parts per million. Feature 7's 30-minute table run measured 114350493 and 114351161 millionths of a reading per second with the time rule, which is about 180 parts per million above feature 1's 114330200.
- The board has a clock chip, a battery gauge, and an audio codec. It has no vibration motor and no Bluetooth in use.

## Watch firmware

- The firmware is written in C with ESP-IDF v6.1. Its version macros give ESP-IDF v6.1.0. Waveshare tests its examples on v5.5.5 and v6.0.2 only, so a build problem in a Waveshare example may come from the version.
- The firmware starts from Waveshare's repo github.com/waveshareteam/ESP32-S3-Touch-AMOLED-2.06 at commit 30f3b23b3d4bb38d32f7d0cddffb66759668a855. It uses the board support package waveshare/esp32_s3_touch_amoled_2_06 at version 2.0.0 and the QMI8658 driver waveshare/qmi8658 at version 2.0.2. The screen task starts the display with bsp_display_new() and lvgl_port_add_disp() and the touch with bsp_touch_new() and lvgl_port_add_touch(). It does not call bsp_display_start(), because that function in version 2.0.0 adds the SH8601 panel as an RGB panel and corrupts the heap.
- The face uses LVGL 9.5.0, which is the version in Waveshare's LVGL example for this board.
- The font is Red Hat Display bold, converted for LVGL at 28, 40, 56, and 96 pixels only.
- The layout, colours, and icons come from the design file context/Tremor Watch Light.html, with the changes that the plan's Watch face section lists. The design's colours are #111315 for text, #5C6265 for second-level text, #1B2E42 for Tremor, #3F2559 for Dose due, #173A28 for the "Took it" button and Logged, and #C9CDD0 for empty blocks.
- The icons in the design file are Lucide icons. They must be converted to LVGL images.
- The firmware has five tasks, which are sensor, pipeline, state, screen, and USB. They talk through queues, and only the screen task uses LVGL.
- firmware/ holds the ESP-IDF project for the watch, and the five tasks live in firmware/main/. firmware/bringup/ stays as feature 1's record.
- The power driver is an unchanged copy of XPowersLib from Waveshare's examples/esp-idf/01_AXP2101/components/XPowersLib/ in firmware/components/XPowersLib/.
- The IMU raises its buffer interrupt on INT1, which the board wires to GPIO21.
- The console is UART0 at 115200 baud, and the firmware has no second console, because CONFIG_ESP_CONSOLE_SECONDARY_NONE is set. ESP-IDF's own log runs at level INFO and goes to UART0 only, and so does its crash text. The USB task also removes the ROM printf's channel to the USB Serial/JTAG port at its start, so ESP-IDF's early log and its log from interrupts stay on UART0 too. The chip's ROM still writes its boot text to the USB port before the firmware starts, so a reader skips every line before the first B line. Flashing and the reset by script still work over the USB port.
- The USB task is the only writer on the USB Serial/JTAG port, and no task writes to stdout. It uses ESP-IDF's usb_serial_jtag driver with a send buffer of 4096 bytes and a receive buffer of 512 bytes. The recording and the diagnostic lines need about 4,200 bytes a second.
- The USB task puts each line into the send buffer with no wait, and the driver takes a whole line or none of it. A line that does not fit is dropped and counted, so no task waits on a laptop that is gone or not reading. After a drop, the next line that fits first brings the B line and the latest S line again.
- The sensor task sends the USB task a copy of each burst part through a record queue of 32 items in PSRAM, with no wait. The queue lives in PSRAM, because the display's transfers need the internal memory that it would take.
- The dose schedule and the tone setting live in ESP-IDF's NVS in the nvs partition. The namespace is "tremor", the key "schedule" holds a version byte and a dose_schedule_t, and the key "tone" holds one byte. firmware/main/settings.c is the only file that writes it. With nothing stored, the schedule is off and the tone is on.
- The dose clock lives in memory only. A restart leaves it unset until the laptop's CLOCK command sets it, and the firmware does not use the board's clock chip.
- ESP-IDF loads with `. ~/.espressif/tools/activate_idf_v6.1.sh`, because the plain export.sh fails on this laptop unless IDF_TOOLS_PATH is `~/.espressif/tools`.
- The dose schedule and the tone setting live in the chip's settings store. Answers and doses stay in memory, and nothing else is written to flash.
- The pipeline task asks the sensor task to end a stretch through a queue of one stretch number. It asks when a stretch loses readings, loses its first message, or fills the converter's ring. The sensor task then ends the stretch with the overflow flag, and the STRETCH line gives reason=pipeline.
- A sensor fault answer comes when no sensor message has arrived for 2 seconds, and then once a second until a message arrives.
- The detector takes about 6.6 milliseconds a window on the chip at ESP-IDF's default -Og level, with the 64-bit scoring step in software. Inside the watch firmware it takes about 6.9 milliseconds, because the other tasks share the chip. Feature 8 measured both.
- Each answer comes about 113 milliseconds after its window's last 100 Hz sample, and feature 8's table run gave 65 to 162 milliseconds from window 10 on. The wait comes from the converter, which needs 16 extra readings after each block, and from the bursts of 11 readings.
- firmware/detector_check/ is a separate ESP-IDF project. It runs the saved windows of tests/detector/ on the chip, so the chip's numbers can be checked with the rule of tests/detector/test_detector.c.

## Shared C library

- The library in core/ holds everything the watch computes. It builds as an ESP-IDF component for the watch and as a plain C library on the laptop.
- core/CMakeLists.txt also registers core/ as the ESP-IDF component core, with the same flags as the laptop build.
- core/imu_units.h holds the gyroscope's unit rule. A raw count divided by 32 gives degrees a second at the range of plus or minus 1024 degrees a second.
- It includes no ESP-IDF headers and allocates no memory at run time.
- It uses 32-bit floats and builds with -ffp-contract=off on both sides.
- It uses KISS FFT, which has a BSD licence and handles the 400 and 200 point sizes. The copy in core/kissfft/ is release tag 131.2.0, which is commit 7bce4153c6bc8aba2db0e889e576f9d00505cbe1 of github.com/mborgerding/kissfft, and its files stay unchanged.
- The detector runs every step in 32-bit floats except the scoring step, which runs in 64-bit doubles as the 32-bit run of plain_detector.py does.
- The detector adds its two window sums and its low-frequency sum in the order numpy 2.5.4 uses. numpy adds blocks of up to 128 values in eight running sums and splits longer arrays in two. It multiplies the coarse spectrum by the float 1 / (sum of the window), because numpy divides that way. These two choices give the same floats as plain_detector.py, so a numpy update in the reference venv could change the last bit of a value.
- KISS FFT builds with KISS_FFT_MALLOC and KISS_FFT_FREE set as compiler options that do nothing, and det_init() builds both FFT setups in fixed static buffers.
- The detector keeps its work buffers in static memory, so only one task may call it. That task is the pipeline task.
- The generated tables are in core/detector_tables.h, and the command `reference/.venv/bin/python tools/gen_tables.py` makes them. The model numbers in it are 64-bit values, and the tables are 32-bit values.
- The laptop build includes replay, a command-line program that reads a recording or a PADS file and prints an answer for every window.
- The time rule lives in core/reading_time.h and core/reading_time.c, and the converter lives in core/converter.h and core/converter.c. The caller owns the state of each, so neither file has static data that changes. The time rule ends a stretch when a burst's stamp lies more than half a reading period from the stretch's prediction or the sensor's buffer overflowed, and every rate comes from at least 10 seconds of stamps. Requirements 21 and 22 of feature 5 add rules that go beyond the build spec's words, and they wait for the user's review.
- A rate is a whole number of millionths of a reading per second, held as a `uint32_t`. For example, 114.3302 readings a second is 114330200.
- Each converter block makes 100 samples at 100 Hz and fits its natural cubic spline over its readings plus 16 extra readings on each side. A block holds at most 192 readings. The converter keeps readings in a ring of 2048, and it accepts rates from 50 to 150 readings a second. At the end of a stretch it drops a block whose readings are not all in, as requirement 24 of feature 5 says, and that requirement waits for the user's review too.
- core/window.h holds the result codes and the window rule. core/share.h holds the session share and the Session screen's blocks. core/face.h holds the face state, the two-in-a-row rule, and the gap rule, which shows Waiting at once when a new stretch starts after a gap. core/dose.h holds the dose schedule and the due rule. The caller owns the state of each, so none of these files has static data that changes. On the watch the pipeline task owns the window rule, and the state task owns the share, the face, and the doses.
- core/pipeline.h holds the pipeline task's rules for the stretches, the converter, the windows, and the sensor fault answers. core/session.h holds the state task's rules, which join the share, the face, and the doses. The caller owns the state of each, so neither file has static data that changes.
- core/record.h holds the recording line format and the command parser, and core/recording_format.md describes the lines, the commands, and the answers. The W line writes the probability and the low-frequency sum as the shortest text that reads back as the same double, which is what the watch's picolibc gives for %.17g.

## Reference and laptop tools

- The laptop is a Mac. It builds the code, runs the checks, sets the watch's clock and dose times, and saves recordings over USB.
- The Python reference runs in its own venv with Python 3.13, ParaDigMa 1.1.2, and scikit-learn 1.6.0. The toolbox's model file needs scikit-learn below 1.6.1.
- The pinned Python requirements live in reference/.
- The tools in tools/ are gen_tables.py, watch_cli.py, and compare_session.py.
- The Python tests in tests/ need the toolbox, so they run in the reference venv with `reference/.venv/bin/python -m pytest tests -q`.
- New Python code follows the user's Python rules. The scripts in reference/ stay as they are, because the measured results come from them. In feature 2, compare.py, rate_test.py, latency_test.py, spline_test.py, and demo_test.py changed their import line to `from plain_detector import build_tables, detect` when they moved from context/, and nothing else changed.
- reference/pads_counts.py runs the toolbox on every PADS recording. Its results in reference/results/ are pads_windows.csv, pads_counts.csv, and pads_counts.md, and they are committed as the counts the C port must reproduce.
- PADS 1.0.0 lives in data/pads/ and is never committed.

## Tests and checks

- The C unit tests use Unity v2.6.1, which is commit cbcd08fa7de711053a3deec6339ee89cad5d2697 of github.com/ThrowTheSwitch/Unity, and they run on the laptop through CTest. Unity has an MIT licence, and its files in tests/unity/ stay unchanged.
- The command `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure` builds core/ and replay on the laptop and runs the C unit tests.
- The command `build/core/replay --pads FILE` runs the C detector on one PADS recording and prints one answer for every window.
- The command `reference/.venv/bin/python tests/pads/pads_match.py` runs the full PADS match after the C build and writes tests/pads/pads_match.md.
- The Python tests for tools/, the saved windows, and the PADS match use pytest.
- The command `reference/.venv/bin/python tests/detector/make_windows.py` makes the 322 saved windows in tests/detector/windows.csv and tests/detector/answers.csv. The C unit tests read these files, so they need no toolbox.
- The command `reference/.venv/bin/python tests/converter/make_cases.py` makes the saved converter cases in tests/converter/. The C unit tests read these files, so they need no toolbox.
- The command `make check` runs the checks for every commit from the Makefile at the repo root. Its three parts are `make laptop`, which builds core/ and replay and runs the C unit tests with the saved windows and the saved converter cases, `make hash`, which compares the SHA-256 hash of the model file copy with DET_MODEL_SHA256 in core/detector_tables.h, and `make firmware`, which builds firmware/. None of them needs the toolbox, and nothing runs them by itself.
- tests/model/ holds an unchanged copy of the ParaDigMa 1.1.2 model file and its licence, so the hash check needs no toolbox. tests/model/test_model_copy.py checks the copy against the toolbox's file.
- The command `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/table_run.py` runs the 30-minute table run on the watch and judges it.
- The command `idf.py -C firmware/detector_check -p /dev/cu.usbmodem101 flash` and then `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/chip_windows.py` run the saved windows on the chip and judge them. The watch firmware must be flashed again afterwards.
- The command `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/pipeline_run.py` runs the pipeline and the state task on a table for 30 minutes and judges the log.
- The command `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/record_run.py` runs the full recording on a table for 30 minutes and judges the log.
- The command `caffeinate -i ~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/command_run.py` sends the four commands, restarts the watch, and waits for a dose to become due and to end, which takes about 23 minutes.
- The command `~/.espressif/tools/python/v6.1/venv/bin/python tests/firmware/drop_run.py` closes the port for 60 seconds and opens it again without a reset, which takes about 5 minutes.
- The full PADS match test needs the toolbox, so it runs before each release and not on every commit.
- The test data is PADS from PhysioNet, which holds 100 Hz gyroscope recordings in radians per second.

## Licences and credits

- ParaDigMa has an Apache 2.0 licence and needs a credit line. Its paper is Timmermans and colleagues, npj Parkinson's Disease, 2025.
- PADS has a non-commercial licence. Its paper is Varghese and colleagues, npj Parkinson's Disease, 2024, and the PhysioNet page asks for its own citation as well.
- KISS FFT has a BSD licence.
- Lucide icons have an ISC licence, and Red Hat Display has the SIL Open Font Licence.
