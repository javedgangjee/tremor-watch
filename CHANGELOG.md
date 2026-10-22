# Changelog

This file records each change to Tremor log that a person who reads or runs the project needs to know.

## Unreleased

### Added

- The project documents are in context/, and they include the build spec, the watch face design, and the Python toolbox scripts.
- The constitution in specs/ gives the mission, the tech stack, and a roadmap of twelve features, and CLAUDE.md tells agents to follow it.
- Feature 1 adds a rate program in firmware/bringup/ that turns on the screen, sets the QMI8658 to rate code 0x06 with a gyroscope range of ±1024 degrees per second, and prints the measured reading rate each minute for twenty minutes.
- Feature 1 adds firmware/bringup/rate_log.txt, which shows a 20-minute rate of 114.33 readings a second and a drift of -80.8 parts per million.
- Feature 1 confirms that Waveshare's LVGL demo builds with ESP-IDF v6.1 and that the screen and the touch work on the board.

### Changed

- The tech stack now names ESP-IDF v6.1, LVGL 9.5.0, the Waveshare repo commit 30f3b23, board support package 2.0.0, and QMI8658 driver 2.0.2.
- The .gitignore file now leaves out the ESP-IDF build folders, the downloaded components, and the sdkconfig.old files under firmware/.
- The .gitignore file now leaves out the .vscode/ folder, and git no longer tracks .vscode/settings.json.
- The tech stack now says that the board's measured rate is 114.33 readings a second, which is 2 percent above the datasheet's 112.1.
