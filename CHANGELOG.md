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
