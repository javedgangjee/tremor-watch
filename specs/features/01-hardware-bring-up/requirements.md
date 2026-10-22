# Feature 1 requirements: Hardware bring-up

## From the project documents

1. The watch runs a Waveshare ESP-IDF demo for this board. This comes from the plan's Build order, in the paragraph before step 1.
2. The screen and the touch work. This comes from the same paragraph.
3. The QMI8658 runs at 112.1 readings a second with the gyroscope and the accelerometer both on. This comes from the same paragraph and from the plan's Sensor and converter section.
4. The gyroscope range is ±1024 degrees per second. This comes from the plan's Sensor and converter section.
5. The real sensor rate is measured against the watch's 64-bit microsecond timer. This comes from the paragraph before step 1.
6. The change in the rate over twenty minutes is measured and noted. This comes from the same paragraph.
7. The exact ESP-IDF version and the exact LVGL version are written into specs/tech-stack.md. This comes from the roadmap entry for feature 1 and from specs/tech-stack.md.
8. The battery check is left out by the user's decision. The roadmap entry for feature 1 records this.

## Not covered by the project documents

The user decided each item below on 21 October 2026.

9. The ESP-IDF version is v6.1, which is already on the laptop. Waveshare tests its examples on v5.5.5 and on v6.0.2 only, so a build problem in a Waveshare example may come from the version.
10. The demo that proves the screen and the touch is examples/esp-idf/02_lvgl_demo_v9 from Waveshare's repo. It is built from source with ESP-IDF v6.1, so it also proves the toolchain.
11. The rate program lives in firmware/bringup/ and is committed. The plan's Repo layout does not list this folder, and feature 7 can delete it.
12. The rate program counts readings with the sensor's own reading counter, which goes up by one for each reading. It does not use the sensor's buffer or its interrupt, because feature 7 sets those up.
13. The drift is the difference between the rate over the first five minutes and the rate over the last five minutes, in parts per million. The program also reports the lowest and the highest one-minute rate.
14. The rate passes when it is within 2 percent of 112.1 readings a second. A rate outside that range goes to the user before feature 5 starts.
15. The twenty-minute log is saved as firmware/bringup/rate_log.txt and is committed.
16. specs/tech-stack.md also records the Waveshare repo commit and the board support package version, because feature 7 starts from the same package.
