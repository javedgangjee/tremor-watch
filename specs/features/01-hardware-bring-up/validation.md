# Feature 1 validation: Hardware bring-up

## Automated checks

1. The rate program builds with no errors and no warnings.
   - The command is `idf.py -C firmware/bringup set-target esp32s3 build`, run in a shell where ESP-IDF v6.1 is active.
   - The expected result is exit code 0 and no lines with "warning:" in the output.

2. The tech stack file names the versions.
   - The command is `grep -n "Feature 1 records" specs/tech-stack.md; grep -nE "ESP-IDF v[0-9]+\.[0-9]+\.[0-9]+|LVGL 9\.5\.0" specs/tech-stack.md`.
   - The expected result is that the first grep prints nothing and the second grep prints at least two lines.

## Manual checks

3. The screen and the touch work.
   - Flash examples/esp-idf/02_lvgl_demo_v9 with `idf.py -p <port> flash monitor`.
   - Tap a control near each corner of the screen and one in the middle.
   - The expected result is that the demo draws with no lines or blocks of wrong colour, and each of the five taps changes the control under the finger.

4. The sensor settings are right.
   - Flash the rate program and read the start lines in the serial output.
   - The expected result is that the gyroscope and the accelerometer are both on, the output rate code is 0x06 for both, and the gyroscope range is ±1024 degrees per second.

5. The rate is measured over twenty minutes.
   - Put the watch still on a table with the screen on and USB power in. Run `idf.py -p <port> monitor | tee firmware/bringup/rate_log.txt` for 21 minutes.
   - The expected result is twenty one-minute lines and one summary line in the log.
   - The expected result is a 20-minute rate within 2 percent of 112.1 readings a second, which is 109.86 to 114.34.
   - The drift in parts per million and the lowest and highest one-minute rates are recorded in the Results section. No limit applies to the drift.

6. The screen shows the rate.
   - Look at the watch during check 5.
   - The expected result is that the screen shows a rate that matches the last one-minute line in the log.

## Requirement coverage

Requirement 1 is covered by check 3. Requirement 2 is covered by check 3. Requirements 3 and 4 are covered by check 4. Requirements 5, 6, 13, and 14 are covered by check 5. Requirements 7 and 16 are covered by check 2. Requirement 8 needs no check. Requirements 9 and 10 are covered by checks 1 and 3. Requirements 11, 12, and 15 are covered by checks 1 and 5.
