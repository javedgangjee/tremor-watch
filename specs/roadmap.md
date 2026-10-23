# Roadmap

The features follow the build order in context/tremor-log-plan.html. "Step" means a numbered step in that page's Build order section, and the other references name its sections.

1. Hardware bring-up
   - The goal is to prove the board works and to learn the real sensor rate before any code is written.
   - It covers the work before step 1. It flashes Waveshare's ESP-IDF demo, confirms the screen and touch, and measures the 112.1 Hz rate and its drift over twenty minutes. It does not check how long the battery runs the screen, by the user's decision, although the plan asks for that check. It also records the ESP-IDF and LVGL versions in specs/tech-stack.md.
   - The status is done.

2. Python reference
   - The goal is to set up the toolbox on the laptop as the reference the C port must match.
   - It covers steps 1 and 2 and the Test data and Repo layout sections. It moves the scripts from context/ into reference/, pins the requirements, confirms that compare.py still matches, and counts how often the toolbox fires on each PADS task in each group.
   - The status is done.

3. Generated tables
   - The goal is to write the detector's fixed numbers into a committed C header.
   - It covers step 3 and the Detector recipe section. tools/gen_tables.py writes the model numbers, both Hann windows, the filter table, the cosine table, and the model file's hash.
   - The status is planned.

4. C detector and the PADS match
   - The goal is to port the detector to C and show that it agrees with the toolbox on saved windows and on every PADS file.
   - It covers steps 4 to 6, the Detector recipe section, and the replay program in the Shared C library section. It uses KISS FFT and 32-bit floats, and it saves a few hundred test windows with the toolbox's answers, including windows close to each cut-off. It produces the match report with the largest difference in the probability.
   - The status is planned.

5. Reading times and converter
   - The goal is to give each reading its time and convert the readings to 100 a second as the toolbox does.
   - It covers steps 7 and 8 and the Sensor and converter section. It saves converter cases, and the C converter must agree within 0.001 degrees per second outside window 0. Feature 1 measured 114.33 readings a second on this board, so no code or test may assume 112.1, and each stretch takes its rate from the reading times as the plan says.
   - The status is planned.

6. Windows, share, and state rules
   - The goal is to build the rules that turn answers into the face state, the session share, and dose due timing.
   - It covers step 9 and the Windows, Response time, Firmware design, and Dose schedule sections. It includes the result codes, the two-in-a-row rule, and unit tests for every state change.
   - The status is planned.

7. Commit checks, firmware base, and sensor task
   - The goal is to run every check that needs no toolbox with one make command, strip Waveshare's example to the five tasks, and read the IMU into timed stretches.
   - It covers steps 10 to 12 and the Firmware design and Sensor and converter sections. The firmware build is one of the make checks.
   - The status is planned.

8. Pipeline and state tasks
   - The goal is to run the converter and the detector on the watch and hold the state for the session.
   - It covers steps 13 and 14 and the Windows and Firmware design sections. It measures how long each detector run takes on the chip.
   - The status is planned.

9. USB recording and commands
   - The goal is to write every reading and answer to the laptop and accept the laptop's commands.
   - It covers step 15 and the USB recording section. It adds the recording format document to core/, the boot line, and the commands for the clock, the dose schedule, a new session, and the tone.
   - The status is planned.

10. Laptop tools
    - The goal is to drive the watch from the laptop and compare each session with replay and the toolbox.
    - It covers steps 16 and 17. It writes tools/watch_cli.py and tools/compare_session.py, and it adds recording input to replay.
    - The status is planned.

11. Watch face
    - The goal is to build the four screens, the state circle, and the dose flow for a wearer with tremor.
    - It covers steps 18 and 19 and the Watch face section. It starts from context/Tremor Watch Light.html and makes the changes that the Watch face section lists. It also picks the No tremor green and the Waiting outline colour, which the design file does not have.
    - The status is planned.

12. Wrist tests, demo, and deliverables
    - The goal is to measure false alarms, response time, and readability with the builder wearing the watch, then record the demo and produce the deliverables.
    - It covers steps 20 to 24 and the Response time and What you deliver sections. It includes the demo video, the session report, the results table, the results page, and the credit lines. It has no write-up, by the user's decision, although the plan asks for one.
    - The status is planned.
