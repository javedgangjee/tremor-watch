# Feature 6 plan: Windows, share, and state rules

The steps run in this order. Every command runs from the repo root. No step changes a file in reference/, context/, core/kissfft/, tests/unity/, or tools/. No step changes core/detector.h, core/detector.c, core/detector_tables.h, core/reading_time.h, core/reading_time.c, core/converter.h, core/converter.c, core/replay.c, or a file in tests/detector/, tests/reading_time/, tests/converter/, tests/pads/, tests/reference/, or tests/tools/. No new file may hold the rate 112.1 in any form. Never change a limit or a case in validation.md to make a case pass. If a case can pass only that way, stop and report it.

1. Write core/window.h and core/window.c as in requirements 23 to 25.
   - The header includes detector.h and converter.h for the sizes. It defines `res_code_t` with RES_TREMOR (0), RES_NO_TREMOR (1), RES_ARM_MOVING (2), RES_WARMING_UP (3), and RES_SENSOR_FAULT (4), and RES_COUNT (5).
   - It defines `win_t`, which holds the last four blocks of the stretch and the number of blocks so far.
   - It defines the functions below.
     - `const char *res_name(res_code_t code)` gives "tremor", "no tremor", "arm moving", "warming up", or "sensor fault", and "unknown" for any other value.
     - `res_code_t res_from_answer(uint32_t window, const det_result_t *r)` gives the code as in requirement 24.
     - `void win_start(win_t *w)` starts a new stretch.
     - `bool win_push_block(win_t *w, const float block[CONV_BLOCK_SAMPLES][CONV_AXES], uint64_t first_sample, float window[DET_WINDOW_LEN][DET_AXES], uint32_t *number)` takes the next block. It returns true and writes the window and its number when a window is complete. It returns false otherwise, and it writes nothing.

2. Write core/share.h and core/share.c as in requirements 26 and 27.
   - The header defines SHARE_EVERY (4), SHARE_BLOCKS (12), SHARE_BLOCK_US (600000000), SHARE_WINDOW_STILL_US (4000000), and SHARE_HOLLOW_BELOW_US (120000000).
   - It defines `share_block_t` with `uint32_t number`, `tremor`, `still`, and `moving`, where still counts the tremor and no tremor windows. It defines `share_t`, which holds the session start, the session counts, and a ring of 12 blocks.
   - It defines the functions below.
     - `void share_start(share_t *s, int64_t start_us)` clears the share and sets the session start.
     - `bool share_add(share_t *s, uint32_t window, res_code_t code, int64_t time_us)` returns true when it counts the answer.
     - `bool share_percent(const share_t *s, double *percent)` returns false when no still window has been counted.
     - `uint32_t share_block_count(const share_t *s)` gives the number of blocks kept, from 0 to 12.
     - `const share_block_t *share_block(const share_t *s, uint32_t i)` gives kept block i, where 0 is the oldest. It returns NULL when i is not less than the count.
     - `bool share_block_percent(const share_block_t *b, double *percent)` and `bool share_block_hollow(const share_block_t *b)` give a block's share and whether it is hollow.

3. Write core/face.h and core/face.c as in requirements 28 and 29.
   - The header includes window.h. It defines `face_state_t` with FACE_TREMOR (0), FACE_NO_TREMOR (1), FACE_ARM_MOVING (2), FACE_WAITING (3), and FACE_DOSE_DUE (4). It defines `face_t`, which holds the detector state, the answer before, the dose due flag, and the last tremor time.
   - It defines the functions below.
     - `void face_init(face_t *f)` sets Waiting with no answer before, no dose due, and no last tremor time.
     - `face_state_t face_from_code(res_code_t code)` maps a code to its face state.
     - `bool face_answer(face_t *f, res_code_t code, int64_t time_us)` applies the two-in-a-row rule.
     - `bool face_set_dose_due(face_t *f, bool due)` sets the dose due flag.
     - `face_state_t face_shown(const face_t *f)` and `face_state_t face_detector(const face_t *f)` give the shown state and the detector state.
     - `bool face_last_tremor(const face_t *f, int64_t *time_us)` returns false when there is no last tremor time.
     - `const char *face_name(face_state_t s)` gives "Tremor", "No tremor", "Arm moving", "Waiting", or "Dose due", and "unknown" for any other value.

4. Write core/dose.h and core/dose.c as in requirements 30 to 34.
   - The header defines DOSE_MAX_TIMES (6), DOSE_NAME_MAX (20), DOSE_LOG_LEN (8), DOSE_DAY_MINUTES (1440), DOSE_DUE_US (900000000), DOSE_BEFORE_US (3600000000), DOSE_LOCK_US (3000000), DOSE_NONE (-1), and the flags DOSE_BECAME_DUE (1) and DOSE_DUE_ENDED (2).
   - It defines `dose_schedule_t` with `char name[DOSE_NAME_MAX + 1]`, `uint8_t count`, and `uint16_t minutes[DOSE_MAX_TIMES]`. It defines `dose_entry_t` with `int64_t time_us` and `int64_t answers_local_us`. It defines `dose_t`, which holds the schedule, the clock offset and whether it is set, the last tick, the due dose, the latest 8 doses, and the dose count.
   - It defines the functions below.
     - `void dose_init(dose_t *d)` clears everything. The first tick after it only records its time.
     - `bool dose_set_schedule(dose_t *d, const dose_schedule_t *s, int64_t now_us)` checks and stores the schedule.
     - `void dose_set_clock(dose_t *d, int64_t offset_us, int64_t now_us)` sets the clock, where the local time in microseconds since 1970 is the timer plus the offset.
     - `void dose_new_session(dose_t *d, int64_t now_us)` drops the doses and any due dose.
     - `unsigned dose_tick(dose_t *d, int64_t now_us)` applies the due rule and returns the flags.
     - `bool dose_took_it(dose_t *d, int64_t now_us)` logs a dose or refuses the tap.
     - `bool dose_is_due(const dose_t *d)` and `bool dose_due_time(const dose_t *d, int64_t *local_us)` give the due state and the due dose's local time.
     - `bool dose_last(const dose_t *d, dose_entry_t *out)` and `uint32_t dose_count(const dose_t *d)` give the latest dose and the count.
     - `bool dose_next(const dose_t *d, int64_t now_us, int64_t *local_us)` gives the next dose time as in requirement 33.
   - Day and minute sums use 64-bit whole numbers with division that rounds down.

5. Add window.c, share.c, face.c, and dose.c to tremor_core in core/CMakeLists.txt, with the TREMOR_WARNINGS flags that detector.c has. res_name() and face_name() use switch statements, so that no file has a static table.

6. Write tests/window/test_window.c, tests/share/test_share.c, tests/face/test_face.c, and tests/dose/test_dose.c with the cases in validation.md check 1.

7. Write tests/response/test_response.c with the cases in validation.md check 1, as in requirement 35.
   - It uses a seeded splitmix64 generator for uniform numbers and the Box-Muller method for normal numbers. Run r of case c uses seed 1000 × (c + 1) + r.
   - It builds the session in 64-bit floats, clips each value to -1024 and 1023.96875, rounds it to the nearest 1/32, and passes it to the converter as a 32-bit float.
   - It sets the converter's rate before the first reading, pushes bursts of 11 readings, and calls conv_block() after each burst until it returns false.

8. Add test_window, test_share, test_face, test_dose, and test_response to tests/CMakeLists.txt in the way test_reading_time is added.

9. Write tests/share/test_share_toolbox.py with the cases in validation.md check 3, as in requirement 36. It follows the user's Python rules, and it uses three test functions with no parametrize.

10. Build and run every check.
    - Run `cmake -S . -B build && cmake --build build && ctest --test-dir build --output-on-failure`.
    - Run `reference/.venv/bin/python -m pytest tests -q`.
    - Run checks 2, 4, and 5 in validation.md.
    - If a case fails, fix the C code or the test code, and run the checks again.

11. Update specs/tech-stack.md as in requirement 37. Under Shared C library, add that core/window.h holds the result codes and the window rule, core/share.h holds the session share and the Session screen's blocks, core/face.h holds the face state and the two-in-a-row rule, and core/dose.h holds the dose schedule and the due rule, and that the caller owns the state of each.

12. Set the status of feature 6 to in progress in specs/roadmap.md. This step is done in plan mode.

## Changes during implement

- The plan does not say what dose_tick() returns when a due dose reaches its 15 minutes on the same tick that a later time becomes due. The tick returns DOSE_BECAME_DUE only, because a dose is still due and the tone must play.
- The plan does not say where share_add() puts a window whose block has already dropped out of the 12 kept blocks. Such a window counts in the session share only.
- dose_set_schedule() counts as a tick only when it accepts the schedule, because a refused schedule changes nothing.
- tests/response/test_response.c runs the sessions before the Unity tests. A failed converter or detector call there is recorded, and case 1 checks it first, because Unity cannot check a value outside a test.
- tests/response/test_response.c counts a single odd answer as an answer whose state differs from the state the face shows after it, when the next answer does not agree with it. The plan does not define the count, and the count is for information only.
- tests/share/test_share_toolbox.py checks its own text for the banned words in case 3, so it builds those words from two parts and does not hold them whole.
- Validate found that the face never showed Waiting after a gap, because each new stretch gives only one warming up answer. core/face.h and core/face.c now have `face_gap()`, as requirement 28 says. The state task calls it when a new stretch starts after a gap, and it sets Waiting at once, clears the answer before, and keeps the last tremor time. The first stretch after face_init() needs no call. tests/face/test_face.c has cases 8 and 9 for it. The user chose this rule on 23 October 2026.

The agent decided this on 22 October 2026, and the user accepted it on 27 October 2026.
