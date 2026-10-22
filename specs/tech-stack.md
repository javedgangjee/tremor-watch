# Tech stack

## Hardware

- The watch is the Waveshare ESP32-S3-Touch-AMOLED-2.06.
- The screen is a 410 by 502 AMOLED touch screen, and it stays on for the whole session.
- The IMU is the QMI8658. It runs at 112.1 readings a second with the gyroscope and the accelerometer both on, and the gyroscope range is ±1024 degrees per second.
- The board has a clock chip, a battery gauge, and an audio codec. It has no vibration motor and no Bluetooth in use.

## Watch firmware

- The firmware is written in C with ESP-IDF. The ESP-IDF version is the one that Waveshare's example package for this board targets. Feature 1 records the exact version here.
- The face uses LVGL, at the version in Waveshare's LVGL example for this board. Feature 1 records the exact version here.
- The font is Red Hat Display bold, converted for LVGL at 28, 40, 56, and 96 pixels only.
- The layout, colours, and icons come from the design file context/Tremor Watch Light.html, with the changes that the plan's Watch face section lists. The design's colours are #111315 for text, #5C6265 for second-level text, #1B2E42 for Tremor, #3F2559 for Dose due, #173A28 for the "Took it" button and Logged, and #C9CDD0 for empty blocks.
- The icons in the design file are Lucide icons. They must be converted to LVGL images.
- The firmware has five tasks, which are sensor, pipeline, state, screen, and USB. They talk through queues, and only the screen task uses LVGL.
- The dose schedule and the tone setting live in the chip's settings store. Answers and doses stay in memory, and nothing else is written to flash.

## Shared C library

- The library in core/ holds everything the watch computes. It builds as an ESP-IDF component for the watch and as a plain C library on the laptop.
- It includes no ESP-IDF headers and allocates no memory at run time.
- It uses 32-bit floats and builds with -ffp-contract=off on both sides.
- It uses KISS FFT, which has a BSD licence and handles the 400 and 200 point sizes. Feature 4 pins the KISS FFT commit here.
- The laptop build includes replay, a command-line program that reads a recording or a PADS file and prints an answer for every window.

## Reference and laptop tools

- The laptop is a Mac. It builds the code, runs the checks, sets the watch's clock and dose times, and saves recordings over USB.
- The Python reference runs in its own venv with Python 3.13, ParaDigMa 1.1.2, and scikit-learn 1.6.0. The toolbox's model file needs scikit-learn below 1.6.1.
- The pinned Python requirements live in reference/.
- The tools in tools/ are gen_tables.py, watch_cli.py, and compare_session.py.
- New Python code follows the user's Python rules. The scripts in reference/ stay as they are, because the measured results come from them.

## Tests and checks

- The C unit tests use Unity and run on the laptop through CTest.
- The Python tests for tools/ use pytest.
- A Makefile at the repo root holds the checks that run on every commit. They build core/ on the laptop, run the unit tests, the saved windows, and the saved converter cases, check the model file's hash against the committed tables, and build the firmware. None of them needs the toolbox.
- The full PADS match test needs the toolbox, so it runs before each release and not on every commit.
- The test data is PADS from PhysioNet, which holds 100 Hz gyroscope recordings in radians per second.

## Licences and credits

- ParaDigMa has an Apache 2.0 licence and needs a credit line. Its paper is Timmermans and colleagues, npj Parkinson's Disease, 2025.
- PADS has a non-commercial licence. Its paper is Varghese and colleagues, npj Parkinson's Disease, 2024, and the PhysioNet page asks for its own citation as well.
- KISS FFT has a BSD licence.
- Lucide icons have an ISC licence, and Red Hat Display has the SIL Open Font Licence.
