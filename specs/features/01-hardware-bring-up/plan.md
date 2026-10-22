# Feature 1 plan: Hardware bring-up

The steps run in this order. Steps 2 and 4 need the watch on USB and the user's hands.

1. Check that ESP-IDF v6.1 on the laptop activates and that `idf.py --version` reports v6.1. This step changes no repo files.

2. Clone Waveshare's repo github.com/waveshareteam/ESP32-S3-Touch-AMOLED-2.06 outside this repo and note its commit. Build examples/esp-idf/02_lvgl_demo_v9 and flash it. The user taps the screen and checks that the demo reacts. This step changes no repo files.

3. Write the rate program in firmware/bringup/. It creates firmware/bringup/CMakeLists.txt, firmware/bringup/sdkconfig.defaults, firmware/bringup/main/CMakeLists.txt, firmware/bringup/main/idf_component.yml, and firmware/bringup/main/main.c.
   - The component file pins the Waveshare board support package, the Waveshare QMI8658 driver, and LVGL 9.5.0 to exact versions.
   - The program turns on the screen through the board support package and shows the current rate as text, so the board runs warm as it will in a session.
   - The program turns on the gyroscope and the accelerometer and sets both to output rate code 0x06. The driver names this code 125 Hz, but with the gyroscope on the datasheet gives 112.1 Hz for it. The program sets the gyroscope range to ±1024 degrees per second. It reads the settings back and prints them at start.
   - A task checks the sensor's reading counter every millisecond. When the counter changes, the task stamps the change with esp_timer_get_time().
   - The program ignores the first 2 seconds. Each minute after that, it prints one line with the minute number, the rate over that minute, and the rate since the start.
   - After 20 minutes it prints a summary line with the rate over the full 20 minutes, the lowest and the highest one-minute rate, and the drift from the first five minutes to the last five minutes in parts per million.

4. Flash the rate program. The user leaves the watch still on a table on USB power for 21 minutes while the laptop saves the serial output to firmware/bringup/rate_log.txt.

5. Update specs/tech-stack.md. Replace the two "Feature 1 records the exact version here" sentences with ESP-IDF v6.1 and LVGL 9.5.0. Add the Waveshare repo commit and the board support package version.

6. Set the status of feature 1 to in progress in specs/roadmap.md. This step is done in plan mode.
