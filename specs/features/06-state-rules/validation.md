# Feature 6 validation: Windows, share, and state rules

Every command runs from the repo root. Every check is automated, and every check runs on the laptop. Checks 1 and 2 need no toolbox. Check 3 needs the reference venv. Work that needs the watch or the screen belongs to feature 7 or later.

The response limits in test_response come from the plan's Response time section, with one more second allowed as requirement 35 says. A planning model on 22 October 2026 ran the same eight cases in Python at 114.3302 readings a second, with 40 runs each. It used scipy's cubic curve over the whole session, plain_detector.py in 32-bit floats, the two-in-a-row rule, and the answer times of test_response. In the five resting cases, the median delay to Tremor was 2.27 to 3.23 seconds and the worst was 5.26 seconds, at 4 Hz and in the hard case. Once Tremor showed, it held until the shake stopped in every run. The median delay back to No tremor was 4.21 to 5.27 seconds, and the worst was 5.27 seconds. In 3 of 40 runs at 4 Hz the face showed Arm moving on the way back, so the test does not forbid it. With the forearm lifted, every run showed Arm moving during the shake. The slow case showed Arm moving in every run and never showed Tremor, and the fast case never showed Tremor. These numbers are for information and are not limits.

## Automated checks

1. The state rules build and pass their C tests.
   - The command is `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure`.
   - test_detector, test_reading_time, and test_converter run unchanged.
   - The cases in tests/window/test_window.c are below. In every block that the cases build, sample k on axis a holds the float k + 0.25a.
     1. The codes are RES_TREMOR 0, RES_NO_TREMOR 1, RES_ARM_MOVING 2, RES_WARMING_UP 3, and RES_SENSOR_FAULT 4, and RES_COUNT is 5. res_name() gives "tremor", "no tremor", "arm moving", "warming up", and "sensor fault" for them, and "unknown" for 5.
     2. A detector result with tremor and at_rest both true gives warming up for window 0, and tremor for windows 1 and 4. A result with tremor false and at_rest true gives warming up for window 0 and no tremor for window 1. A result with both false gives warming up for window 0 and arm moving for window 1.
     3. After win_start(), blocks 0, 1, and 2 give no window. Block 3 gives window 0, and its row r holds sample r. Blocks 4 to 20 each give one window, numbered 1 to 17, and row r of window n holds sample 100n + r on every axis, with every value equal.
     4. After blocks 0 to 5, a block with first sample 700 is refused, and so is a second block with first sample 500. Each refusal writes nothing. The next block, with first sample 600, gives window 3 with the right samples.
     5. After blocks 0 to 5 and then win_start(), a block with first sample 600 is refused. Blocks 0 to 3 then give window 0 again.
   - The cases in tests/share/test_share.c are below. The session starts at 1,000,000 microseconds. Unless a case says otherwise, window n has the time 1,000,000 + 1,000,000n microseconds.
     1. After share_start(), share_percent() returns false, the counts are 0, and share_block_count() gives 0.
     2. Windows 0 to 40 arrive with code no tremor, except that window 4 has tremor, window 8 has warming up, and window 12 has sensor fault. share_add() returns true for windows 4, 16, 20, 24, 28, 32, 36, and 40 and false for every other window. The share is 12.5, from 1 tremor window in 8 still windows. Window 4 is a single odd answer that the face would not show, and it still counts.
     3. Five streams each start with share_start() and use windows 4, 8, 12, and up, with the codes mixed in order. The counts of tremor, no tremor, and arm moving windows and the expected share are (3, 5, 2) for 37.5, (2, 4, 1) for 33.33333333333333, (2, 7, 0) for 22.22222222222222, (4, 0, 3) for 100.0, and (0, 6, 2) for 0.0. Each share equals its value exactly. The counts (3, 5, 2) in a second order give the same 37.5.
     4. A stream of 5 arm moving windows gives no share.
     5. Windows at the times below arrive with window numbers 4, 8, 12, and up. Block 0 gets 30 no tremor windows with times from session start + 0 to session start + 599,999,999. Block 1 gets 29 no tremor windows and 10 arm moving windows, with its first at session start + 600,000,000. Block 2 gets none. Block 3 gets 1 tremor window and 3 no tremor windows. share_block_count() gives 4, and the blocks have numbers 0 to 3. Block 0 has still 30 and is not hollow. Block 1 has still 29 and moving 10 and is hollow. Block 2 is empty, is hollow, and has no share. Block 3 has still 4, a share of 25.0, and is hollow.
     6. One no tremor window lands in each of blocks 0 to 13. share_block_count() gives 12, the oldest kept block has number 2, and the newest has number 13. The session share counts all 14 windows.
     7. A window with a time before the session start goes in block 0.
   - The cases in tests/face/test_face.c are below. Unless a case says otherwise, answer i has the time 1,000,000i microseconds.
     1. The states are FACE_TREMOR 0, FACE_NO_TREMOR 1, FACE_ARM_MOVING 2, FACE_WAITING 3, and FACE_DOSE_DUE 4. face_name() gives "Tremor", "No tremor", "Arm moving", "Waiting", and "Dose due" for them, and "unknown" for 5. face_from_code() maps tremor, no tremor, and arm moving to the state of the same name, and warming up and sensor fault to Waiting.
     2. After face_init(), the shown state and the detector state are Waiting, and face_last_tremor() returns false.
     3. Twenty cases cover each start state S of Waiting, Tremor, No tremor, and Arm moving with each of the five codes c. A new face reaches S with no answer for Waiting, and with two answers of S's code for the others. One answer c then returns false and leaves the state at S. A second answer c then sets the state to face_from_code(c), and it returns true exactly when that state differs from S.
     4. From No tremor, the answers tremor, no tremor, no tremor, tremor, no tremor never change the state, and every call returns false. From Tremor, the answers arm moving, tremor, no tremor, tremor never change the state.
     5. From Tremor, a warming up answer and then a sensor fault answer set Waiting on the second. From Waiting, sensor fault, tremor, tremor set Tremor on the last.
     6. From No tremor, face_set_dose_due(true) returns true and the shown state is Dose due. A second call with true returns false. Two tremor answers then set the detector state to Tremor, the shown state stays Dose due, and both calls return false. face_set_dose_due(false) returns true, and the shown state is Tremor. From Waiting, face_set_dose_due(true) and then false each return true.
     7. From a new face, a tremor answer at 5 s sets no last tremor time. Tremor answers at 6 s and 7 s set it to 6 s and then 7 s. A no tremor answer at 8 s keeps Tremor and keeps 7 s. A tremor answer at 9 s sets 9 s. No tremor answers at 10 s and 11 s set No tremor and keep 9 s. A single tremor answer at 12 s keeps 9 s.
     8. From a new face, tremor answers at 0 s and 1 s show Tremor and set the last tremor time to 1 s. face_gap() then returns true, the shown state and the detector state are Waiting, and the last tremor time stays 1 s. A second face_gap() returns false. A warming up answer at 2 s and a tremor answer at 3 s each return false, Waiting stays, and the last tremor time stays 1 s. A tremor answer at 4 s returns true, shows Tremor, and sets the last tremor time to 4 s. In a separate run from Tremor, face_gap() and then one tremor answer leave Waiting showing, because the tremor answer before the gap does not pair with it. A second tremor answer returns true and shows Tremor. On a new face, face_gap() returns false, the state stays Waiting, and face_last_tremor() returns false.
     9. From No tremor, face_set_dose_due(true) shows Dose due. face_gap() returns false, the shown state stays Dose due, and the detector state is Waiting. A warming up answer and then a no tremor answer each return false, Dose due stays, and the detector state stays Waiting. face_set_dose_due(false) returns true, and the shown state is Waiting. A second no tremor answer returns true and shows No tremor.
   - The cases in tests/dose/test_dose.c are below. The clock offset is 20748 × 86,400,000,000 microseconds, so the timer counts microseconds from local midnight at the start of 22 October 2026, and 08:00:00 means the timer value 28,800,000,000. Unless a case says otherwise, the schedule is "Levodopa" at 08:00, 12:00, and 16:00, the clock is set at 06:00:00, the schedule is set at 06:00:00, and a run of ticks calls dose_tick() at every whole second.
     1. dose_set_schedule() accepts 0 times, 6 different times, a name of 20 bytes, and the times 0 and 1439. It refuses 7 times, the time 1440, a time given twice, and a name of 21 bytes. After a refusal, the old schedule stays. The times 16:00, 08:00, and 12:00 are stored as 480, 720, and 960.
     2. With no clock set, ticks from 07:59:00 to 08:16:00 never return a flag, no dose is due, and dose_next() returns false.
     3. Ticks from 06:00:00 to 07:59:59 return no flag. The tick at 08:00:00 returns DOSE_BECAME_DUE, and dose_due_time() gives 08:00 on 22 October in local microseconds. Ticks to 08:14:59 return no flag and the dose stays due. The tick at 08:15:00 returns DOSE_DUE_ENDED, and no dose is due. Ticks to 11:59:59 return no flag, and the tick at 12:00:00 returns DOSE_BECAME_DUE.
     4. With ticks from 06:00:00, a tap at 08:05:00 is accepted and ends the due dose. dose_last() gives the time 08:05:00 and the answered time 08:00. Ticks to 11:59:59 return no flag.
     5. Four runs each tick from 06:50:00 to 08:01:00 with one tap. A tap at 07:00:00 after that second's tick leaves 08:00 not due. A tap at 06:59:59.999999 lets 08:00 become due. A tap at 07:30:00 leaves 08:00 not due. A tap at 08:00:00 before that second's tick leaves 08:00 not due.
     6. A tick at 07:59:58 and then a tick at 08:00:05 make 08:00 due on the second tick, and a tick at 08:15:00 ends it. In a separate run, a tick at 07:50:00 and then a tick at 08:16:00 make nothing due.
     7. With the clock first set at 08:05:00 and ticks from there, 08:00 never becomes due, and 12:00 does. In a separate run with ticks from 06:00:00, setting the clock at 07:00:00 to an offset 2 hours later moves the local time to 09:00. Ticks then run to 07:30:00 on the timer, which is 09:30 local. 08:00 never becomes due, and dose_next() gives 12:00.
     8. With the schedule 08:00 and 08:10, the tick at 08:00:00 returns DOSE_BECAME_DUE. The tick at 08:10:00 returns DOSE_BECAME_DUE again, and the due time is 08:10. The dose stays due to 08:24:59, and the tick at 08:25:00 returns DOSE_DUE_ENDED. In a separate run, a tap at 08:05:00 leaves 08:10 not due.
     9. With the schedule 00:00 and 23:30, ticks run from 23:00:00 on 22 October to 00:20:00 on 23 October. 23:30 is due from 23:30:00 to 23:44:59. 00:00 on 23 October becomes due at 00:00:00 on 23 October and ends at 00:15:00.
     10. A tap at 09:00:00 is accepted, a tap at 09:00:02.999999 is refused, and a tap at 09:00:03 is accepted. dose_count() gives 2.
     11. With no dose due, a tap at 09:00:00 answers 08:00, a tap at 10:30:00 answers 12:00, and a tap at 10:00:00, which is 2 hours from each, answers 08:00. Each tap is in its own run. With no clock set, a tap answers -1. With an empty schedule, a tap answers -1.
     12. dose_next() gives 08:00 at 07:00:00. While 08:00 is due at 08:05:00, it gives 08:00. At 08:20:00, after the due dose ended, it gives 12:00. After a tap at 11:30:00, it gives 16:00. At 17:00:00 it gives 08:00 on 23 October.
     13. While 08:00 is due at 08:05:00, dose_new_session() leaves no dose due and dose_count() at 0, and dose_last() returns false. The schedule stays, and the tick at 12:00:00 returns DOSE_BECAME_DUE.
     14. Ten taps 3 seconds apart from 07:58:00 are all accepted. dose_count() gives 10, dose_last() gives 07:58:27, and 08:00 does not become due.
     15. With an empty schedule and the clock set, ticks over a whole day return no flag, and dose_next() returns false.
     16. Ticks come at 0.6 s past each second. A tap at 08:00:00.4 answers 08:00, the tick at 08:00:00.6 and the ticks to 08:16:00.6 return no flag, and dose_count() gives 1. With the schedule 07:55 and 08:00 and 07:55 due, a tap at 08:00:00.4 answers 08:00, and nothing becomes due to 08:16:00.6. In a third run the tick at 08:00:00.6 makes 08:00 due, and a tap with the time 08:00:00.4 taken after it answers 08:00 and ends the due dose. Ticks to 08:16:00.6 return no flag. The user asked for this case on 27 October 2026.
     17. While 08:00 is due, a schedule of 12:00 and 16:00 set at 08:01:00 ends the due dose at the tick at 08:01:01, which returns DOSE_DUE_ENDED, and dose_next() then gives 12:00. An empty schedule set at 08:01:00 does the same, and dose_next() returns false. A schedule of 08:00 and 20:00 set at 08:01:00 keeps 08:00 due to 08:14:59, and the tick at 08:15:00 returns DOSE_DUE_ENDED. The user asked for this case on 27 October 2026.
   - The cases in tests/response/test_response.c are below. Each session lasts 80 seconds at 114330200 millionths of a reading per second, with rest to 30 s, a 20 second shake to 50 s, and rest to the end. Reading n has the time n × 1e6 / 114330200 seconds. Each value follows make_session() in reference/demo_test.py, with the size amp, the base frequency f0, the frequency wander w, and the sway sway. The defaults are amp 150, f0 5, w 0.4, and sway 3. The eight cases are 5 Hz with the defaults, 4 Hz with f0 4, 6 Hz with f0 6, gentle with amp 60, hard with amp 600, lifted with sway 15, slow with f0 2.5, amp 200, and w 0, and fast with f0 8, amp 200, and w 0. Each case has ten runs. An answer's time is the time of the last reading of the burst that completes its window, plus 50,000 microseconds for the run and the redraw, as in reference/demo_test.py. The show delay is the time of the first change to Tremor after 30 s, minus 30 s. The back delay is the time of the first change to No tremor after 50 s, minus 50 s. A median over ten runs is the mean of the fifth and sixth values in order.
     1. In every run of every case, the face's first change is from Waiting to No tremor, it comes before 30 s, and the face makes no other change before 30 s.
     2. In every run of the 5 Hz, 4 Hz, 6 Hz, gentle, and hard cases, the face changes to Tremor after 30 s and before 50 s, and it makes no change after that until 50 s. Each of these cases has a median show delay from 2.0 to 3.5 seconds and a worst show delay of at most 6.5 seconds.
     3. In every run of the same five cases, the face changes to No tremor after 50 s. Each case has a median back delay from 4.0 to 5.5 seconds and a worst back delay of at most 6.5 seconds.
     4. In every run of the lifted case, the face shows Arm moving at some time from 30 s to 51 s.
     5. In every run of the slow case, the face never shows Tremor, and it shows Arm moving at some time from 30 s to 51 s.
     6. In every run of the fast case, the face never shows Tremor, and it makes no change after its first change to No tremor.
     7. The test prints, for each case, the number of runs that showed Tremor, the median and worst show delay, the median and worst back delay, and the number of single odd answers that the rule kept off the face.
   - The expected result is that the build prints no warning, and CTest reports 100% tests passed out of 8.

2. The new C code uses no heap, no ESP-IDF header, no changing static data, and no 112.1.
   - The commands are below, and each one runs after check 1.
     1. `nm -u build/core/libtremor_core.a | grep -E '^_?(malloc|calloc|realloc|free|aligned_alloc|posix_memalign)$'` prints nothing.
     2. `grep -rnE '#include *[<"](esp_|freertos/|driver/|sdkconfig)' core/` prints nothing.
     3. `nm build/core/CMakeFiles/tremor_core.dir/window.c.o build/core/CMakeFiles/tremor_core.dir/share.c.o build/core/CMakeFiles/tremor_core.dir/face.c.o build/core/CMakeFiles/tremor_core.dir/dose.c.o | grep -E ' [bBdD] '` prints nothing.
     4. `grep -rnE '112\.1|\b1121\b|112100' core/*.c core/*.h tests/window tests/share tests/face tests/dose tests/response` prints nothing.
     5. `cmake --build build --clean-first 2>&1 | grep -i warning` prints nothing.

3. The Python tests pass.
   - The command is `reference/.venv/bin/python -m pytest tests -q`.
   - The 47 cases from features 2 to 5 run unchanged.
   - The cases in tests/share/test_share_toolbox.py are below. Each builds a table for aggregate_tremor() with one row per window, times 4 seconds apart from 22 October 2026, and the tremor power 1, 2, 3, and up.
     1. The five count sets of test_share case 3 give perc_windows_tremor equal to 37.5, 33.33333333333333, 22.22222222222222, 100.0, and 0.0 exactly. Tremor windows have pred_arm_at_rest 1 and pred_tremor_checked 1, no tremor windows have 1 and 0, and arm moving windows have 0 and 0.
     2. A table of 5 arm moving windows makes aggregate_tremor() raise Warning.
     3. Every function in the file has a type hint on each argument and on its return. The file contains no `print(`, no `os.path`, and no `except Exception`.
   - The expected result is 50 passed.

4. The reference, the detector, the time rule, the converter, and the tables have not changed.
   - The command is `git diff 32c51a9 --stat -- reference/ context/ core/kissfft/ core/detector.h core/detector.c core/detector_tables.h core/reading_time.h core/reading_time.c core/converter.h core/converter.c core/replay.c tools/ tests/unity/ tests/detector/ tests/reading_time/ tests/converter/ tests/pads/ tests/reference/ tests/tools/`.
   - The command prints nothing.

5. The repo holds the right files.
   - The command is `git diff 32c51a9 --stat` on the feature branch after the implement commit.
   - The expected result lists core/CMakeLists.txt, core/window.h, core/window.c, core/share.h, core/share.c, core/face.h, core/face.c, core/dose.h, core/dose.c, tests/CMakeLists.txt, tests/window/test_window.c, tests/share/test_share.c, tests/share/test_share_toolbox.py, tests/face/test_face.c, tests/dose/test_dose.c, tests/response/test_response.c, specs/tech-stack.md, specs/roadmap.md, and the three files in specs/features/06-state-rules/. It lists no other file.

## Requirement coverage

Requirement 1 is covered by test_window cases 3 to 5 and test_response, which runs a window for every block. Requirement 2 is covered by test_window case 3 and test_response. Requirement 3 is covered by test_share cases 2 and 3 and check 3 case 1. Requirement 4 is covered by test_window case 2 and test_share case 2. Requirement 5 is covered by test_window cases 1 and 2 and test_share cases 2 and 4. Requirement 6 is covered by test_share cases 3 and 4 and check 3 cases 1 and 2. Requirement 7 is covered by test_face cases 3 to 5 and test_share case 2. Requirement 8 is covered by test_response cases 1 to 6. Requirement 9 is covered by test_face cases 1, 5, 6, 8, and 9. Requirement 10 is covered by check 1, which builds the rules into tremor_core and runs their tests. Requirement 11 is covered by test_dose case 1. Requirement 12 is covered by test_dose cases 3, 5, and 8. Requirement 13 is covered by test_dose cases 3 and 8 and test_face case 6. Requirement 14 is covered by test_dose cases 3, 4, and 8. Requirement 15 is covered by test_dose cases 10 and 14, where every accepted tap stays in the count. Requirement 16 is covered by test_dose cases 2 and 7. Requirement 17 is covered by test_dose case 13 and test_share case 1. Requirement 18 is covered by test_dose case 10. Requirement 19 is covered by test_share cases 5 to 7, test_face case 7, and test_dose cases 4 and 12. Requirement 20 is covered by check 2 and by check 1, which builds on the laptop. Requirement 21 is covered by check 1. Requirement 22 is covered by checks 2 and 4. Requirements 23 to 25 are covered by check 2 item 3 and test_window cases 1 to 5. Requirement 26 is covered by test_share cases 2 to 4 and check 3. Requirement 27 is covered by test_share cases 5 to 7. Requirements 28 and 29 are covered by test_face cases 1 to 9. Requirements 30 to 34 are covered by test_dose cases 1 to 17. Requirement 35 is covered by test_response cases 1 to 7. Requirement 36 is covered by check 3. Requirement 37 is covered by check 5.

## Results

The checks ran on 23 October 2026 on branch feature/06-state-rules at commit 00f9f68, which holds the gap fix. The build folder was removed before check 1. Every check passed.

1. Check 1 passed. The clean build printed no warning, and CTest reported 100% tests passed out of 8. test_detector, test_reading_time, and test_converter passed unchanged. test_window ran 5 cases, test_share ran 7, test_face ran 9, test_dose ran 15, and test_response ran 7, each with 0 failures. A reading of test_face cases 8 and 9 found that they match their text here. test_response printed the table below, where each delay is in seconds. It is the same table as on 22 October, because the fix does not touch any code that test_response runs.

   | Case | Runs with Tremor | Show median | Show worst | Back median | Back worst | Single odd answers |
   |---|---|---|---|---|---|---|
   | 5 Hz | 10 of 10 | 2.27 | 3.23 | 4.74 | 5.27 | 0 |
   | 4 Hz | 10 of 10 | 3.23 | 5.26 | 4.21 | 4.21 | 4 |
   | 6 Hz | 10 of 10 | 3.23 | 3.23 | 5.27 | 5.27 | 0 |
   | gentle | 10 of 10 | 3.23 | 3.23 | 4.21 | 5.27 | 0 |
   | hard | 10 of 10 | 2.27 | 5.26 | 5.27 | 5.27 | 4 |
   | lifted | 2 of 10 | none | 2.27 | 4.21 | 5.27 | 11 |
   | slow | 0 of 10 | none | none | 5.27 | 5.27 | 0 |
   | fast | 0 of 10 | none | none | none | none | 0 |

   The lifted row has no show median because only 2 runs showed Tremor, and 2.27 s is the worst of those two.
2. Check 2 passed. Items 1 to 5 each printed nothing.
3. Check 3 passed. pytest reported 50 passed.
4. Check 4 passed. The command printed nothing.
5. Check 5 passed. The stat lists the 21 files that the check names, and it lists no other file.

Every item in requirements.md has at least one passing check. Requirement 9 now has a passing check for its words "after a gap", which are test_face cases 8 and 9.

### The gap fix

The gap finding of 22 October is fixed. Commit 00f9f68 changes six files. These are core/face.h, core/face.c, tests/face/test_face.c, and the three files in this folder. `git diff f7d9e94 00f9f68` shows that face.c gains only `face_gap()`, and face.h gains its declaration and comment and a reworded header comment. No other code line changed, and test_face cases 1 to 7 are unchanged. Requirement 28 drops the old sentence that answers on each side of a stretch break count as in a row, and it states the gap rule in its place.

`face_gap()` sets the detector state to Waiting, clears the answer before, and leaves the dose due flag and the last tremor time alone. It returns true only when the shown state changes. This matches requirement 28 word for word. The function touches only the face_t, so it changes nothing in the share or the recording, and requirement 7 still holds.

Case 8 of test_face checks that a gap from Tremor shows Waiting at once, that the last tremor time stays, that a second call returns false, and that one warming up answer and one tremor answer after the gap leave Waiting. It then checks that two tremor answers in the new stretch show Tremor and set a new last tremor time. Its second run shows that a tremor answer before the gap does not pair with one after it. Its third run shows that a call on a new face changes nothing. Case 9 checks that a gap while a dose is due keeps Dose due on the face, sets the detector state underneath to Waiting, and that the face shows Waiting when the dose ends. Together these cover every sentence of requirement 28 about the gap.

A scratch program fed face_answer() the same codes as on 22 October, with a call to face_gap() before the second warming up answer. The codes were warming up, no tremor, no tremor, no tremor, then the gap, then warming up, no tremor, tremor, tremor, tremor. The face showed Waiting, Waiting, No tremor, No tremor, then Waiting at the gap, then Waiting, Waiting, Waiting, Tremor, and Tremor. So Waiting shows from the gap through the warm-up window, and it ends only when two answers in the new stretch agree.

The fix follows the build spec. The Watch face section says Waiting shows while the watch warms up after a start or a gap, and now it does. The Response time section says the face changes only when two answers in a row agree. Every change that an answer causes still needs two agreeing answers. The change to Waiting at a gap comes from an event and not from an answer, so it does not break that rule. This reading of the two sections is the user's choice of 23 October 2026, and requirement 28 records it. The sensor task finds a gap only when the next burst arrives, as the plan's time rule says, so the call at the start of the new stretch is the first moment the watch knows of the gap. The face keeps its last state during the gap itself, when no answers come.

Nothing calls `face_gap()` yet. The state task comes in feature 8, and the roadmap entry for feature 8 does not yet say that the state task calls it at each new stretch after a gap. Replan should add this.

### Against the build spec

A reading of core/window.c, core/share.c, core/face.c, and core/dose.c beside the plan's Windows, Response time, Firmware design, Dose schedule, and Watch face sections finds that the code follows these rules.

- Window n holds samples 100n to 100n + 399, and win_push_block() gives it as soon as the block that holds sample 100n + 399 arrives. No timer is involved.
- Every window gives an answer, so the face gets one each second.
- share_add() counts only windows whose number divides by 4, leaves out window 0, and counts only tremor, no tremor, and arm moving. The share is tremor windows over still windows times 100, as in aggregate_tremor().
- The five result codes come from one list in window.h, and there is no idle code.
- The face changes on answers only when two answers in a row map to the same state. face_answer() changes only the face, so the state task can pass the same raw code to share_add().
- Waiting shows after a start and, with face_gap(), after a gap.
- Dose due takes over the shown state while a dose is due, and the detector state returns when it ends.
- A schedule holds one name and up to six times. A time becomes due unless a dose was logged in the hour before it. The due state ends on a tap or after 15 minutes, and the same time never becomes due again. Nothing becomes due until the clock is set.
- A tap less than 3 seconds after the last dose is refused, and every accepted tap stays in the count.
- The four files hold no ESP-IDF header, no heap call, and no static data that changes.

One part of the Waiting rule still depends on later features. The Watch face section says Waiting shows when the sensor has failed. A single sensor fault answer still never shows, because a single odd answer never shows. The face shows Waiting only after two sensor fault or warming up answers in a row. Feature 7 or 8 decides how often the sensor fault code comes, and so whether the face shows Waiting when the sensor fails.

The code goes beyond the build spec's words in these places. Each comes from a requirement that the user accepted on 27 October 2026, or from the plan's list of changes during implement.

- The result codes and the face states have fixed numbers, as requirements 24 and 28 say.
- A Session block takes each counted still window as 4 seconds of still time. The share keeps the latest 12 blocks and drops older ones, and a window in a dropped block counts in the session share only. A window timed before the session start goes in block 0. These come from requirement 27 and the plan's changes.
- The last tremor time is the latest tremor answer after which the face shows Tremor, as requirement 29 says. A gap keeps it.
- A dose time becomes due at the first tick at or after it, and only when that tick comes within 15 minutes. The hour before includes both ends. A later time that becomes due while another is due takes its place and plays the tone again. A time that passed before the clock, the schedule, or a new session was set never becomes due. When a due dose ends and a later time becomes due on the same tick, the tick returns only DOSE_BECAME_DUE. These come from requirement 31 and the plan's changes.
- The 3 second lock lives in dose_took_it() as well as on the screen. A tap with no clock or no schedule is accepted and answers -1. A tap with no dose due answers the nearest scheduled time. The rules keep the latest 8 doses. These come from requirement 32.
- dose_next() skips a time that a logged dose already covers, as requirement 33 says.
- A new session keeps the schedule and the clock, as requirement 34 says.
- The hour rule turns each logged dose into local time with the clock offset in force when it checks, not the offset in force at the tap. If the laptop sets the clock again with a different offset, earlier doses move in local time. No requirement states this.

### The response time limits

This finding from 22 October still holds, because the table above is the same. The limits here are the build spec's numbers plus one answer step. The build spec's own numbers, read strictly, would fail 6 of the 20 measures in the five resting cases. The show median is 2.27 s in the 5 Hz and hard cases, which is 0.23 s under "about 2½". The worst show delay is 5.26 s in the 4 Hz and hard cases, which is 0.26 s over "at most about 5". The back median is 4.21 s in the 4 Hz and gentle cases, which is 0.29 s under "about 4½". Every other measure lies inside the build spec's numbers, and no back worst is over 5.27 s, which lies inside 5½.

Only the worst show delay is slower than the build spec, and by 0.26 s. The other misses are faster than the build spec says. Answers come once a second, so every delay falls on a grid of whole seconds plus 0.21 to 0.27 s, and a band one second wide such as 2½ to 3½ holds only one point of that grid. On 22 October, reference/demo_test.py, which has no two-in-a-row rule, gave a first Tremor answer after a median of 1.3 to 2.3 s and a first No tremor answer after 3.3 to 4.3 s, with a worst first Tremor of 4.3 s at 4 Hz. With one more answer for the rule, these become about 2.3 to 3.3 s, 4.3 to 5.3 s, and a worst of 5.3 s. So the build spec's own simulation sits outside its words by about the same amounts, and the words read as "about" fit both. Check 4 shows that the reference has not changed since then.

### The lifted case

This finding from 22 October still holds. The lifted row is the same, and the fix does not touch the converter, the window rule, the detector, or face_answer(). The build spec says that with the forearm lifted the face showed Arm moving for most of the shake. It does not say that Tremor never shows. On 22 October, reference/demo_test.py gave a single Tremor answer about 2.3 s after the shake started in 10 of 10 lifted runs, and 3 of 10 runs gave Tremor again after the shake stopped.

In the C test, every tremor answer in the lifted case comes from window 27, 28, or 49. These windows hold the shake's start at 30 s or its end at 50 s, so the sway covers only part of the window. The low-frequency sum stays under 50 while the 5 Hz shake sets the peak. Runs 6 and 9 gave tremor in both windows 27 and 28, so the rule let Tremor show for about 2 seconds before Arm moving. Every lifted run showed Arm moving for about 80 percent of the shake's answers.

On 22 October a scratch program wrote out the readings of the 10 lifted sessions that test_response builds, with the C answer for each window. scipy's cubic interp1d and plain_detector.py in 32-bit floats then ran on the same readings. The Python chain gave the same tremor and arm at rest answers on all 750 windows after window 0, and it found the same 15 tremor windows. The probability differed by at most 2.0e-7, and the low-frequency sum by at most 3.1e-5. So the 2 of 10 runs come from the C test's random numbers, and they do not point to a fault in the C chain. The planning model's 0 of 40 used numpy's random numbers, which give other phases.

### The banned words in test_share_toolbox.py

This finding from 22 October still holds, because the fix does not change the file. The split words only stop the check from matching its own pattern list. A scan of the file's syntax tree found no call to print, no import of os, no try block, and no except clause. The file reads its own text with pathlib. Every function has type hints on its arguments and its return, and the list type is parameterised. So the file breaks none of the Python rules. The check is a plain text search, so it would miss a form such as `from os import path`. That is a gap in the check, and it hides nothing in this file.
