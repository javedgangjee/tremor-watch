# Changelog

This file records each change to Tremor log that a person who reads or runs the project needs to know.

## Unreleased

### Added

- The project documents are in context/, and they include the build spec, the watch face design, and the Python toolbox scripts.
- The constitution in specs/ gives the mission, the tech stack, and a roadmap of twelve features, and CLAUDE.md tells agents to follow it.
- Feature 1 adds a rate program in firmware/bringup/ that turns on the screen, sets the QMI8658 to rate code 0x06 with a gyroscope range of ±1024 degrees per second, and prints the measured reading rate each minute for twenty minutes.
- Feature 1 adds firmware/bringup/rate_log.txt, which shows a 20-minute rate of 114.33 readings a second and a drift of -80.8 parts per million.
- Feature 1 confirms that Waveshare's LVGL demo builds with ESP-IDF v6.1 and that the screen and the touch work on the board.
- Feature 2 adds reference/requirements.txt, which pins ParaDigMa 1.1.2, scikit-learn 1.6.0, pytest, and every other package in the Python 3.13 toolbox venv to an exact version.
- Feature 2 adds reference/pads_counts.py, which runs the toolbox on all 10,318 PADS 1.0.0 recordings and counts how often it fires on each task, group, and wrist.
- Feature 2 adds pads_windows.csv, pads_counts.csv, and pads_counts.md in reference/results/, and they hold the 26,264 windows and 99 count rows that the C port must reproduce.
- Feature 2 adds nine unit tests for pads_counts.py in tests/reference/test_pads_counts.py, and they run with pytest in the reference venv.
- Feature 2 adds reference/README.md, which gives the commands to make the venv, download and check PADS, and run each script, and which gives the PADS and ParaDigMa credit lines.
- Feature 2 confirms that compare.py still shows the plain rebuild matches the toolbox, and the tremor label agrees on 200 of 200 windows in both float64 and float32.
- Feature 3 adds tools/gen_tables.py, which takes the model numbers from the ParaDigMa 1.1.2 model file and the tables from reference/plain_detector.py and writes them into core/detector_tables.h.
- Feature 3 adds core/detector_tables.h, which holds the 37 model numbers and the cut-off as 64-bit values, the two Hann windows, the filter table, and the cosine table as 32-bit values, and the model file's SHA-256 hash.
- Feature 3 makes tools/gen_tables.py stop and write no file when the model file's hash, its feature names, or its classifier differ from the ParaDigMa 1.1.2 model.
- Feature 3 adds 16 tests in tests/tools/test_gen_tables.py, which compile the header with tests/tools/dump_tables.c, compare every value with the toolbox and plain_detector.py, and run with pytest in the reference venv.
- Feature 3 confirms that the header gives plain_detector.py the same answers as its own tables, and that the tremor answer agrees with the toolbox on 200 of 200 windows in float32.
- Feature 4 adds the C detector in core/detector.h and core/detector.c, which follows detect() in reference/plain_detector.py step for step in 32-bit floats and scores each window in 64-bit doubles.
- Feature 4 adds unchanged copies of KISS FFT release 131.2.0 in core/kissfft/ and Unity v2.6.1 in tests/unity/.
- Feature 4 adds a CMake build that makes the library tremor_core, the replay program, and the C unit tests on the laptop, and the command `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure` runs it.
- Feature 4 adds core/replay.c, which runs as `build/core/replay --pads FILE` and prints the C detector's numbers and answers for every window of one PADS recording.
- Feature 4 adds tests/detector/make_windows.py, which writes 322 saved windows with the toolbox's answers to tests/detector/windows.csv and tests/detector/answers.csv, and 120 of these windows sit close to a cut-off or test the ends of the peak band.
- Feature 4 adds tests/detector/test_detector.c, which checks the C detector on the saved windows, and its largest difference from the toolbox is 3.6e-06 in the 12 numbers and 2.71e-07 in the probability.
- Feature 4 adds tests/pads/pads_match.py and its committed report tests/pads/pads_match.md, which show that the C detector agrees with the toolbox on all 26,264 windows of the 10,318 PADS recordings and on all 99 count rows, with a largest difference of 5.63e-07 in the probability.
- Feature 4 adds pytest tests for make_windows.py and pads_match.py, and three cases in tests/tools/test_gen_tables.py that check that tools/gen_tables.py stops and writes no file when the feature names or the classifier are wrong.
- Feature 5 adds the time rule in core/reading_time.h and core/reading_time.c, which gives each reading a time from one fixed rate per stretch, takes every rate from at least 10 seconds of burst stamps, and starts a new stretch after a gap or a buffer overflow.
- Feature 5 adds the converter in core/converter.h and core/converter.c, which converts each stretch to 100 samples a second one block at a time with a natural cubic spline and 16 extra readings on each side.
- Feature 5 adds tests/converter/make_cases.py, which saves eight 30-second converter cases with the toolbox's own conversion at 100 Hz to stretches.csv, readings.csv, and expected.csv in tests/converter/.
- Feature 5 adds tests/converter/test_converter.c, which shows that the C converter agrees with the saved toolbox cases within 0.00016 degrees per second from sample 100 on, and the limit is 0.001.
- Feature 5 adds tests/reading_time/test_reading_time.c, which checks the time rule on made-up burst streams and on the twenty one-minute rates from feature 1, where the rule made 6 stretches in twenty minutes.
- Feature 5 adds the two C tests to the CMake build and five pytest cases for make_cases.py in tests/converter/test_make_cases.py.

### Changed

- The tech stack now names ESP-IDF v6.1, LVGL 9.5.0, the Waveshare repo commit 30f3b23, board support package 2.0.0, and QMI8658 driver 2.0.2.
- The .gitignore file now leaves out the ESP-IDF build folders, the downloaded components, and the sdkconfig.old files under firmware/.
- The .gitignore file now leaves out the .vscode/ folder, and git no longer tracks .vscode/settings.json.
- The tech stack now says that the board's measured rate is 114.33 readings a second, which is 2 percent above the datasheet's 112.1.
- The roadmap entry for feature 5 now says that no code or test may assume 112.1 readings a second, because feature 1 measured 114.33 on this board.
- Feature 2 moves the six toolbox scripts from context/ to reference/, and five of them change only their import line to `from plain_detector import build_tables, detect`.
- The .gitignore file now leaves out data/, reference/.venv/, __pycache__/, and .pytest_cache/.
- The tech stack now records the import line change, pads_counts.py and its results, and that PADS 1.0.0 lives in data/pads/ and is never committed.
- Validation check 5 for feature 2 now uses the measured output of spline_test.py and demo_test.py, as the user agreed on 21 October 2026.
- The tech stack now names core/detector_tables.h, the command that makes it, the types of its values, and the command that runs the tests for gen_tables.py.
- The roadmap entry for feature 4 now says that feature 4 decides whether the C scoring step runs in 64-bit or 32-bit floats, and that it adds the two stop case tests for tools/gen_tables.py that feature 3 left out.
- The roadmap entries for features 7 and 9 now say that the hash check and the boot line's table hash use DET_MODEL_SHA256 from core/detector_tables.h.
- The .gitignore file now leaves out the build/ folder.
- The tech stack now names the KISS FFT and Unity commits, says that the detector scores in 64-bit doubles, and gives the commands for the CMake build, replay, the saved windows, and the PADS match.
- The tech stack now says that the detector adds its sums in numpy's order, that KISS FFT never touches the heap, and that only the pipeline task may call the detector.
- The roadmap entry for feature 7 now says that the ESP-IDF component for core/ must keep the -ffp-contract=off flag and the KISS FFT heap options from core/CMakeLists.txt.
- The roadmap entry for feature 8 now says that feature 8 runs the saved windows on the chip, because feature 4 checked the numpy-order sums and the 64-bit scoring step on the laptop only.
- The tech stack now names the time rule and converter files, says that a rate is a whole number of millionths of a reading per second, and gives the converter's block, ring, and rate range and the command that makes the saved converter cases.
- The tech stack and the roadmap entry for feature 5 now point to requirements 21, 22, and 24 of feature 5, which go beyond the build spec's words and wait for the user's review.
- The roadmap entry for feature 7 now says that feature 7 counts how often stretches end on the watch and how long they last, on the wrist and on a table, because the time rule with the measured drift started a new stretch every 2.5 to 5 minutes.
- The roadmap entries for features 7 to 10 now say how the sensor task, the pipeline task, the S line, and replay use the time rule and the converter.
