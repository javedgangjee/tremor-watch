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

## Results

The checks ran on 21 October 2026.

1. Check 1 passes. The build exits with code 0, and the output has no lines with "warning:". The output does have five CMake warnings about private include folders. They come from the esp_wifi and wpa_supplicant components inside ESP-IDF v6.1, and not from the rate program. The set-target step left sdkconfig unchanged.
2. Check 2 passes. The first grep prints nothing. The second grep prints line 12, which names ESP-IDF v6.1.0, and line 14, which names LVGL 9.5.0.
3. Check 3 passes. The widgets demo from examples/esp-idf/02_lvgl_demo_v9 was built with ESP-IDF v6.1 from the clone at commit 30f3b23 and flashed. The local change in that clone only switches the demo from music to widgets. The demo booted with no errors and drew cleanly, and the user reports that all five taps changed the control under the finger.
4. Check 4 passes. The log shows gyro_on=1, accel_on=1, rate code 0x06 for both, and a gyroscope range of ±1024 degrees per second. The raw registers agree, because CTRL2 is 0x26, CTRL3 is 0x66, and CTRL7 is 0x03.
5. Check 5 passes. The log has twenty one-minute lines and one summary line. The 20-minute rate is 114.3302 readings a second. This is 1.99 percent above 112.1, and the 2 percent limit is 114.342, so the rate passes by 0.012 readings a second. The lowest one-minute rate is 114.3257, and the highest is 114.3386. The first five minutes give 114.3355, the last five minutes give 114.3263, and the drift is -80.8 parts per million. The counter line shows no step larger than one and no read errors.
6. Check 6 passes. The user reports that the screen showed a rate that matched the newest one-minute line during the run.

Every item in requirements.md is covered by at least one passing check. Requirement 8 needs no check.

The measured rate of 114.33 readings a second is 0.012 readings a second below the upper limit. The specs give 112.1 in several places, so feature 5 must take the rate from the reading times.
