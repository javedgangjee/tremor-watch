# Feature 12 validation: Recording viewer

Every command runs from the repo root with Node v22.22.1 and npm 11.20.0 from nvm. Checks 1 and 3 need no network, no node_modules, no toolbox, and no watch. Check 4 needs the network and runs `npm --prefix viewer ci`, so it runs before check 2. Check 2 needs the installed packages and a logged-in screen on the Mac. Check 5 needs the watch on USB at /dev/cu.usbmodem101. Checks 6 and 7 are manual and wait for the user. SCRATCH means the session's scratch folder, IDFPY means `~/.espressif/tools/python/v6.1/venv/bin/python`, and NAVY means #1B2E42.

The limits come from these sources. The 10 second load and draw limit comes from requirement 24. The colour tolerance of 8 in each channel allows for colour handling in the capture, and NAVY is far from every other colour on the page. The rate tolerance of 115 millionths of a reading per second is 1 part per million, and a stamp rounded to the microsecond over a span of 7 seconds moves the estimate by less than 0.15 parts per million.

## The made-up recording

viewer/test/helpers/synthetic.js builds this recording, and viewer/test/fixtures/synthetic.txt.gz holds it. HASH is DET_MODEL_SHA256 from core/detector_tables.h. Each line has a laptop time with three decimals and a tab in front, and the times never fall. A burst holds 11 readings. The stamp of the burst whose first reading is f in a stretch with first reading f0, start t0, and rate r is t0 + floor((f - f0) × 1e12 / r + 0.5). Each R line has gyroscope counts of round(32 × d) for a shake of d degrees per second plus round(10 × sin(0.37 × f + a)) for axis a of 0, 1, and 2, and accelerometer counts of 0, 0, and 4096. A shake's time is the reading's time since its stretch's t0 in seconds. The W line of window n is written right after the T and R lines of the first burst whose first reading lies at or after n + 4 seconds, with the numbers 0.5, 10, and 5.

1. The file starts with `ESP-ROM:esp32s3-20210327`, `T,500,11,123`, and `R,500,1,2,3,4,5,6`.
2. Boot A starts with `B,305419896,11,12,HASH`, `START uptime_us=1`, and `S,0,0,250000,0,1024`.
3. Stretch 0 has t0 250000 and rate 114330200, and it holds the 1248 bursts whose first reading lies before 120 seconds, which are readings 0 to 13727. `S,0,0,250000,114330200,1024` comes after the first burst at or after 10 seconds. The x axis shakes at 100 × sin(2π × 5 × t) from 30 to 60 seconds, and the y axis at 60 × sin(2π × 0.5 × t) from 80 to 95 seconds.
4. After the first burst at or after 20 seconds come `> TONE,0`, `A,4,0`, `F,0,1`, `W,0,,4,,,`, `D,20000000,`, and `TOUCH x=1 y=2`.
5. In burst 728, which starts at reading 8008 and is the first at or after 70 seconds, the third R line is `R,1234,5`.
6. Bursts 1040 to 1042, which start from 100 to 100.3 seconds, are left out with their W lines, as lost lines are. `B,305419896,11,12,HASH` and `S,0,0,250000,114330200,1024` come again before burst 1043, which starts at reading 11473.
7. Stretch 0 has windows 0 to 115. Window 0 has code 3. Windows 30 to 56 lie inside the shake and have code 0. Windows 77 to 94 touch the sway and have code 2. The other windows have code 1. Window 96 has no W line, because its burst was lost.
8. Stretch 1 starts with `S,1,13728,T1,114331000,1024`, where T1 is the stamp of burst 1247 plus floor(11 × 1e12 / 114330200 + 0.5) plus 6000. It holds 416 bursts, which are 40 seconds of readings. The x axis shakes at 150 × sin(2π × 5.5 × t) from 10 to 25 seconds. Window 0 has code 3, windows 10 to 21 have code 0, and windows 1 to 9 and 22 to 35 have code 1.
9. Then come `> RESET` and `ESP-ROM:esp32s3-20210327`. Boot B starts with `B,4294967295,1,12,HASH` and `S,0,0,300000,0,1024` and never gets a rate line. It holds 84 bursts at the rate 114330200, which are the bursts whose first reading lies before 8 seconds. `W,0,,4,,,` comes after burst 10. The T line of burst 83 is followed by only 5 of its R lines, and the file ends there.

## Automated checks

1. The unit tests pass.
   - The command is `make viewer`, which runs `node --test viewer/test/*.test.js`.
   - "Load" means loadRecording() from viewer/src/lib/load.js. "Readings" means the length of a boot's timeline. A made-up line list uses H for the hash and the patterns of readRecordPatterns().
     1. readRecordPatterns() gives exactly the keys A, B, D, F, R, S, T, and W. Its B pattern matches the first B line of tests/firmware/record_log.txt.gz without its laptop time, and its W pattern matches `W,3,,4,,,` and `W,0,7,0,0.5,10,5`. A copy of core/recording_format.md without its W row throws a RecordingError whose message holds "W".
     2. readRecordingLines() on tests/firmware/record_log.txt.gz gives cutShort false and as many lines as the gunzipped file holds, and each line equals the text after the tab of its raw line. A temporary `.gz` file that holds the first half of that file's bytes gives cutShort true and at least one line, and its lines are the first lines of the whole file.
     3. A temporary `x.txt` that holds `0.001\tB,1,11,12,H\r\nR,0,1,2,3,4,5,6\n` gives the lines `B,1,11,12,H` and `R,0,1,2,3,4,5,6`. A temporary `bad.gz` that holds `hello` throws a RecordingError with "not a gzip file". A path that does not exist throws a RecordingError that names the path. tests/firmware/record_log.txt.gz with maxBytes 1000 throws a RecordingError that names the limit.
     4. The lines `ESP-ROM:esp32s3-20210327`, `T,500,11,123`, `R,500,1,2,3,4,5,6`, `B,1,11,12,H`, `S,0,0,1000,0,1024`, `T,0,2,1000`, `R,0,32,-32,64,0,0,4096`, `R,1,0,0,0,0,0,4096`, `START uptime_us=1`, `> TONE,0`, `A,4,0`, `F,0,1`, and `D,5,` parse to one boot with ID 1, firmware 12, and one burst of 2 readings whose gyro counts are 32, -32, 64, 0, 0, and 0. bad is 0 and droppedBursts is 0.
     5. `T,0,3,1000` with the R lines of readings 0, 2, and 1 gives droppedBursts 1 and no burst. `T,0,3,1000` with the R lines of readings 0 and 1, then `T,3,1,2000` and the R line of reading 3, gives droppedBursts 1 and one burst at reading 3. `T,0,3,1000` with the R lines of readings 0 and 1 at the end of the lines gives droppedBursts 0 and no burst.
     6. After a B line, each of `R,1234,5`, `T,0,0,1000`, `T,0,257,1000`, `R,0,32768,0,0,0,0,0`, `W,0,5,0,1.2.3,1,1`, and `S,0,99999999999999999999,0,0,1024` counts once, so bad is 6, and none of them adds a burst, a stretch, or a window.
     7. Two B lines with ID 1 give one boot, and a third with ID 2 gives a second boot. `S,0,0,1000,0,1024` then `S,0,0,1000,114330200,1024` leave stretch 0 with rate 114330200. `W,0,,4,,,` adds one fault and no window. `W,0,5,0,0.5,10,5` then `W,0,5,1,0.5,10,5` leave window 5 of stretch 0 with code 1.
     8. A stretch `S,0,0,250000,114330200,1024` with 10 bursts from reading 0 gives timeS[i] === (250000 + i × 1e12 / 114330200) / 1e6 for every i, gx[i] === count / 32 for every i, and no break.
     9. A stretch with t0 0 and rate 114330200 gives reading 823178 the time 823178 × 1e12 / 114330200 / 1e6, about 7200.0049 seconds, within 1e-9 seconds. Readings 823178 and 823179 differ by 1 / 114.3302 seconds within 1e-9 seconds. This is the build spec's two hour example, where 32-bit seconds would step in 0.49 millisecond jumps.
     10. Bursts at readings 0 and 22 of one stretch, with readings 11 to 21 missing, give one break before reading 22, and reading 22 keeps the time t0 + 22 × 1e12 / r. Stretches `S,0,0,250000,114330200,1024` and `S,1,11,500000,114330200,1024` with bursts at readings 0 and 11 give one break before reading 11, which has the time 0.5 seconds.
     11. A stretch with rate 0 and bursts 0 to 83 stamped at 300000 + floor(11b × 1e12 / 114330200 + 0.5) is estimated with a rate within 115 of 114330200. A rate 0 stretch with one burst is estimated with 114330200 in a boot with no other rate, and with 114331000 in a boot whose other stretch has that rate.
     12. A burst at reading 0 in a boot whose only S line starts at reading 11 gives noStretchReadings 11, and those readings are left out.
     13. Stretch 0 with t0 250000 and the W lines of window 0 with code 3 and window 5 with code 0 gives window 5 a startS of 5.25, an endS of 9.25, and a cellStartS of 8.25. A W line of stretch 3 with no S line gives notPlaced 1. `W,0,,4,,,` gives faults 1.
     14. tremorSpans() of code 0 windows 5, 6, and 7 of that stretch gives [[5.25, 11.25]]. Windows 5 and 9 touch and give [[5.25, 13.25]]. Windows 5 and 10 give [[5.25, 9.25], [10.25, 14.25]]. Code 1 windows give [].
     15. Load of tests/firmware/record_log.txt.gz gives cutShort false, bad 0, droppedBursts 0, and one boot 2274443476 with firmware 9 and reset cause 11. It has one stretch with first reading 0, t0 234273, and rate 114347777, not estimated, 206041 readings, and no break. Its last reading's time is (234273 + 206040 × 1e12 / 114347777) / 1e6. It has 1798 placed windows, 1797 with code 1 and 1 with code 3, and no tremor span.
     16. Load of tests/firmware/command_log.txt.gz gives boot 3162426297 with 1166 readings and 7 windows, 6 with code 1 and 1 with code 3. Boot 505078862 has 144078 readings, stretch 0 with t0 234313 and rate 114348497, stretch 1 with first reading 108185, t0 946328952, and rate 114349025, one break before reading 108185, and 1252 placed windows, 1250 with code 1 and 2 with code 3.
     17. Load of tests/firmware/drop_log.txt.gz gives droppedBursts 2 and one boot 3492590314 with 25256 readings, two breaks before readings 8052 and 14883, and 216 placed windows, all in stretch 0. The highest is window 276, with a startS of (234278 + 276 × 1e6) / 1e6.
     18. Load of tests/firmware/face_log.txt.gz gives one boot 2694533211 with firmware 11, 130526 readings, and 1138 placed windows, 1137 with code 1 and 1 with code 3.
     19. For each of the four committed logs and the made-up recording, the placed code 0 windows, as "boot,stretch,window", are exactly the keys that a separate scan gives. The scan drops each line's laptop time and takes every line after the first B line that matches `^W,(\d+),(\d+),0,`, keyed by the boot ID of the last B line before it. The set is empty for the four logs and holds 39 keys for the made-up recording.
     20. buildSyntheticText() equals the gunzipped viewer/test/fixtures/synthetic.txt.gz byte for byte.
     21. Load of the made-up recording gives cutShort false, bad 1, droppedBursts 1, and the boots 305419896 and 4294967295. Boot A has 18260 readings. Its stretch 0 has first reading 0, t0 250000, and rate 114330200, and its stretch 1 has first reading 13728, t0 T1, and rate 114331000, both not estimated. It has three breaks, before readings 8019, 11473, and 13728. It has 151 placed windows, 39 with code 0, 92 with code 1, 18 with code 2, and 2 with code 3, 1 fault, and none not placed. Window 96 of stretch 0 is not among them. Its tremor spans are [[30.25, 60.25], [T1 / 1e6 + 10, T1 / 1e6 + 25]]. Boot B has 913 readings, one stretch that is estimated with a rate within 115 of 114330200, 1 fault, and no window.
     22. A temporary copy of the made-up recording cut to its first 60 percent of bytes loads with cutShort true and fewer than 18260 readings in boot A.
     23. parseArgs(['a.gz'], '/x') gives file /x/a.gz with no capture and no boot. parseArgs(['--capture', 'o.png', '--boot', '5', '/abs/a.gz'], '/x') gives capture /x/o.png, boot 5, and file /abs/a.gz. parseArgs([], '/x') gives no file. ['--frob'], ['--capture'], ['a', 'b'], and ['--boot', 'x'] each throw an ArgsError.
     24. sampleCells() on a white BGRA bitmap of 20 by 10 at scale 2 with a block of NAVY from image x 4 to 11 and y 2 to 7 gives checked 1 and matched 1 for the cell at page x 2, y 1, width 4, and height 3. A cell at page x 7 gives matched 0 and one miss. The block with one channel off by 9 gives no match, and off by 8 it matches.
     25. viewer/package.json lists exactly `"uplot": "1.6.32"` under dependencies and `"electron": "44.7.1"` under devDependencies. viewer/package-lock.json has lockfileVersion 3 and gives those versions for node_modules/uplot and node_modules/electron.
     26. Every file in viewer/src/lib/ requires only `node:` modules and files that start with `./`. No file in viewer/src/ or viewer/scripts/ holds `serialport`, `/dev/cu`, or `/dev/tty`. No file in viewer/src/renderer/ holds `http:` or `https:`. The CSP meta tag in viewer/src/renderer/index.html holds exactly the policy of requirement 22. viewer/src/main.js sets contextIsolation true, nodeIntegration false, sandbox true, and webSecurity true. No committed file in viewer/ holds an em dash or an en dash.
   - The expected result is that node reports 0 failed, and every case above is a passing test.

2. The real app draws each case and exits.
   - The command is `npm --prefix viewer run smoke -- --out SCRATCH/smoke`.
   - Each case runs `electron . FILE [--boot ID] --capture SCRATCH/smoke/<case>.png` and reads `<case>.json`. "Report" means the page's report in the JSON.
     27. The made-up recording exits with code 0. The report gives boot 305419896, 18260 readings, and windows 39 with code 0, 92 with code 1, 18 with code 2, and 2 with code 3. It names 39 tremor cells, and the pixel check gives checked 39 and matched 39 against NAVY. The web preferences give contextIsolation true, nodeIntegration false, sandbox true, and webSecurity true, and the page has no `require` and no `process`.
     28. The made-up recording with `--boot 4294967295` exits with code 0. The report gives 913 readings, one stretch marked as estimated, and no tremor cell.
     29. tests/firmware/record_log.txt.gz exits with code 0. The report gives 206041 readings, windows 1797 with code 1 and 1 with code 3, and no tremor cell.
     30. tests/firmware/command_log.txt.gz with `--boot 505078862` exits with code 0. The report gives 144078 readings and two stretches.
     31. A file `bad.gz` that holds `hello` exits with code 1, the JSON's message holds "not a gzip file", and the PNG exists. A path that does not exist exits with code 1.
     32. `--frob` exits with code 2.
     33. A two hour recording from `node viewer/scripts/make_synthetic.js --long SCRATCH/smoke/long.txt.gz --minutes 120` exits with code 0. It holds one boot with one stretch at the rate 114330200, made of the bursts whose first reading lies before 7200 seconds. A 5 Hz shake of 100 degrees per second on the x axis lasts 20 seconds and starts every 10 minutes from 300 seconds. Window 0 has code 3, the windows that lie inside a shake have code 0, and windows 1 to 7195 otherwise have code 1. The report gives 823185 readings and 204 windows with code 0, and the load time plus the draw time is under 10000 milliseconds.
   - The expected result is that the script prints a pass for all 7 cases and exits with code 0.
   - The validate agent then opens SCRATCH/smoke/synthetic.png with its image reader and checks it by eye. Three coloured lines run across the plot. A NAVY shade covers the x axis shake from about 30 to 60 seconds and the shake from about 130 to 145 seconds. The lane below holds NAVY cells under the shakes and pale green cells under the sway from about 80 to 95 seconds. The lines break near 70, 100, and 120 seconds. The boot list names both boots, and the summary gives 1 bad line and 1 dropped burst.

3. `make check` runs the unit tests and needs no network.
   - The commands are `git worktree add SCRATCH/clean HEAD`, `make -C SCRATCH/clean viewer`, `git worktree remove --force SCRATCH/clean`, then `make -n check`, then `make check`.
   - The expected result is that `make viewer` passes in the clean worktree, which has no viewer/node_modules. `make -n check` lists the laptop, hash, viewer, and firmware steps in that order, and `make check` exits with code 0. .github/workflows/check.yml has a viewer job that uses actions/setup-node@v4 with node-version "22.22.1" and runs `make viewer`. Nothing is pushed, so CI does not run in this feature.

4. The packages install from the lock file.
   - The commands are `npm --prefix viewer ci`, `npm --prefix viewer ls --depth=0`, and `viewer/node_modules/.bin/electron --version`.
   - The expected result is that the install exits with code 0, the list shows electron@44.7.1 and uplot@1.6.32 and nothing else, and Electron prints v44.7.1.

5. A fresh recording from the watch opens.
   - The commands are `IDFPY tools/watch_cli.py record --out SCRATCH/table.txt.gz --minutes 3`, which resets the watch, then `viewer/node_modules/.bin/electron viewer SCRATCH/table.txt.gz --capture SCRATCH/table.png`, and last `gunzip -c SCRATCH/table.txt.gz | cut -f2- | grep -c '^W,[0-9]*,[0-9]*,0,'`.
   - The expected result is that the recording exits with code 0, the capture exits with code 0, its report gives at least 19000 readings and at least 170 windows, and its number of windows with code 0 equals the grep count. The watch lies on the table, so the count is most likely 0. When the watch is not on USB, this check is recorded as not run, and the validate stage says so.

## Manual checks

6. The app works by hand.
   - Run `npm --prefix viewer start -- tests/firmware/command_log.txt.gz`.
   - The window opens on boot 3162426297. Pick boot 505078862 in the boot list, and the plot shows about 21 minutes with a line break at the start of stretch 1. Drag across a few seconds, and the plot zooms in to show single readings. Press the right arrow key, and the view moves by half its width. Double click, and the whole boot shows again. Press Cmd+O, pick tests/firmware/record_log.txt.gz, and the plot and the summary change to that file. Open a file that is not a recording, and the page shows one plain message and no plot.

7. A real wrist shake shows as tremor.
   - Run `IDFPY tools/watch_cli.py record --out ~/shake.txt.gz --minutes 3` with the watch on the wrist. Rest the forearm on a table and shake the hand from the wrist 4 to 6 times a second for 20 seconds, twice, with a minute of rest between, as the build spec's section on making the Tremor screen appear says.
   - Run `npm --prefix viewer start -- ~/shake.txt.gz`.
   - The expected result is that NAVY shades cover the two shakes, the shaken axes swing widely there, and the summary's number of tremor windows equals `gunzip -c ~/shake.txt.gz | cut -f2- | grep -c '^W,[0-9]*,[0-9]*,0,'`.

## Requirement coverage

- Requirements 1 and 22 are covered by checks 1 case 26 and 2 case 27.
- Requirements 2, 6, 15, and 16 are covered by check 1 cases 1 to 7 and 15 to 21.
- Requirements 3, 7, and 17 are covered by check 1 cases 8 to 12, 15 to 18, and 21, and by check 2 case 28.
- Requirements 4, 9, and 18 are covered by check 1 cases 13, 14, 19, and 21, by check 2 case 27, and by manual check 7.
- Requirement 5 is covered by check 1 case 26.
- Requirement 8 is covered by check 1 cases 2 and 22.
- Requirements 10 and 24 are covered by check 2 case 33.
- Requirement 11 is covered by `git diff --stat main` in the validate stage, which must list no file in firmware/, core/, reference/, tools/, or tests/.
- Requirement 12 is covered by check 1 case 25 and check 4.
- Requirements 13, 19, and 20 are covered by check 2 cases 27 to 30, its look at the PNG, and manual check 6.
- Requirement 14 is covered by check 1 case 26 and check 3.
- Requirement 21 is covered by check 1 case 3 and check 2 case 31.
- Requirement 23 is covered by check 1 cases 23 and 24 and check 2.
- Requirement 25 is covered by check 1 cases 19 to 22.
- Requirement 26 is covered by check 3.
- Requirement 27 is covered by reading specs/tech-stack.md, README.md, and .gitignore in the validate stage.

## Results, 2026-10-27

The validate stage ran on branch feature/12-recording-viewer at commit 2bb5556 with a clean tree, Node v22.22.1, and npm 11.20.0. SCRATCH was a new folder in the session's scratch folder.

Checks 1, 2, 3, and 4 passed. Check 5 did not run, because the watch holds another project's firmware and this stage was told not to flash it. Checks 6 and 7 wait for the user. The stage drove the real window for most of check 6, as the section on check 6 says, but it could not press Cmd+O or use the system's open dialog, and it did not mark check 6 as passed. So the feature is not ready for review until the user runs check 5 on the Tremor log firmware and checks 6 and 7 by hand.

### Automated checks

1. Check 1 passed. `make viewer` exited with code 0, and node reported 26 tests, 26 passed, and 0 failed, one test for each of cases 1 to 26.
2. Check 2 passed. The smoke script printed a pass for all 7 cases and "7 of 7 cases passed", and it exited with code 0.
   - Case 27 gave boot 305419896, 18260 readings, windows 39, 92, 18, and 2 for codes 0 to 3, 39 tremor cells, and the pixel check 39 checked and 39 matched. The web preferences gave contextIsolation true, nodeIntegration false, sandbox true, and webSecurity true, and the page had no `require` and no `process`.
   - Case 28 gave 913 readings and one stretch, estimated at 114330201, which lies within 115 of 114330200, and no tremor cell.
   - Case 29 gave 206041 readings, windows 1797 with code 1 and 1 with code 3, and no tremor cell. Case 30 gave 144078 readings and two stretches.
   - In case 31 `bad.gz` exited with code 1 with the message "... bad.gz is not a gzip file." and a PNG that shows the message. The missing file exited with code 1 with the message "Could not read ..., because it does not exist." Case 32 exited with code 2.
   - Case 33 gave one boot with one stretch at 114330200, 823185 readings, and windows 204 with code 0, 6991 with code 1, and 1 with code 3. That is window 0 with code 3 and windows 1 to 7195 otherwise, and 204 is 12 shakes of 17 windows each. The load took 334 ms and the draw 28 ms, so the sum is 362 ms, well under 10000 ms.
   - The hidden window gave a full image every time, so shownWindow was false in each JSON.
   - The stage looked at SCRATCH/smoke/synthetic.png. Three coloured lines run across the plot. A navy shade covers the x axis shake from 30 to 60 seconds and the shake from about 130 to 145 seconds, and it starts where the shaking starts. The lane holds navy cells under both shakes, from about 33 and 133 seconds, which is the last second of the first tremor window, and pale green cells from about 80 to 98 seconds under the sway. The lines break at 100 seconds, where a clear gap shows, and near 70 and 120 seconds, where the gaps are a pixel or two wide at this zoom. The summary gives 1 bad line and 1 dropped burst. The PNG shows the boot list closed, with boot 305419896 picked. The driven run of check 6 read the list's options, which name both boots, 305419896 with 18,260 readings and 4294967295 with 913 readings.
3. Check 3 passed. `make viewer` in a clean worktree of HEAD, which had no viewer/node_modules, gave 26 passed and 0 failed, and the worktree was removed. `make -n check` listed the laptop, hash, viewer, and firmware steps in that order. `make check` exited with code 0, with "100% tests passed out of 16", "model hash matches", 26 viewer tests passed, and "Project build complete". .github/workflows/check.yml has a viewer job on ubuntu-24.04 with actions/setup-node@v4, node-version "22.22.1", and `make viewer`. Nothing was pushed.
4. Check 4 passed. `npm --prefix viewer ci` exited with code 0 and added 14 packages. `npm --prefix viewer ls --depth=0` listed electron@44.7.1 and uplot@1.6.32 and nothing else. `viewer/node_modules/.bin/electron --version` printed v44.7.1. Electron 44 has no install script, so it fetched its binary on this first run and printed "Downloading Electron binary...". So the first start after `npm ci` also needs the network, which README.md line 127 and specs/tech-stack.md line 85 do not say.
5. Check 5 did not run. `IDFPY tools/watch_cli.py record --out SCRATCH/table.txt.gz --minutes 3` exited with code 1 and said "No B line came, so the clock was not set." The 89 saved lines are a boot log of the ESP-IDF project "aac_watch", app version e0cc451-dirty, built on 25 Oct 2026, so the watch no longer runs the Tremor log firmware. Neither the code nor the check is at fault. The viewer opened that file and exited with code 1 with the message "table.txt.gz holds no B line in its 89 lines, so it is not a recording from the watch.", which is the plain message requirement 21 asks for.

### Manual checks

6. Check 6 waits for the user. The stage did the steps it could with Playwright's Electron support, which it installed in SCRATCH and not in the repo. Playwright adds `--remote-debugging-port=0` before the app path, which the app's strict argument reader refuses, so a small wrapper in SCRATCH passed on only the arguments after the app path and then loaded viewer/src/main.js unchanged. The stage saw these steps work in the real window.
   - The window opened on boot 3162426297, and the boot list named both boots. Picking boot 505078862 showed about 21 minutes and changed the summary to that boot.
   - The break at the start of stretch 1 lies between 946.3246 and 946.3290 seconds, about 4 ms apart, so it cannot show at full view. After three drags to a view of about 20 ms around it, the lines of all three axes stop at the last reading of stretch 0 and start again at the first reading of stretch 1, with no line between.
   - A drag across about 3 seconds showed single readings, and the y axis fitted the readings in view. The right arrow key moved the view from about 12:52.4 to 12:55.8 to about 12:54.1 to 12:57.4, which is half its width. Double click showed the whole boot again.
   - With the open dialog replaced in the main process so that it gave record_log.txt.gz, a click on the File menu's Open item changed the plot and the summary to that file. A Cmd+O key press sent by Playwright did not reach the menu. With the dialog giving a text file that is not a recording, the Open button showed one plain message, "notrec.txt holds no B line in its 47 lines, so it is not a recording from the watch.", and no plot. bad.gz gave the gzip message, and the made-up recording then drew again.
   - A call to window.open() and a change of location.href to a web address left the page where it was and opened no window.
   - The steps still waiting for the user are these. Run `npm --prefix viewer start -- tests/firmware/command_log.txt.gz` from the repo root, and do each step of check 6 by hand. Press Cmd+O on the keyboard, and check that the system's open dialog appears, shows only .gz and .txt files, and opens tests/firmware/record_log.txt.gz. Then use the dialog again to open a file that is not a recording, and check for one plain message and no plot.
7. Check 7 waits for the user. It also needs the watch on the Tremor log firmware, which it no longer runs.

### Requirement coverage

- Requirement 11 holds. `git diff --stat main` lists no file in firmware/, core/, reference/, tools/, or tests/.
- Requirement 27 holds. specs/tech-stack.md has a Recording viewer section with the versions, the folder, the modules, and the commands, adds `make viewer` to `make check` and the smoke command, and gives the MIT licences of Electron and uPlot. README.md has a section on viewing a recording and credits Electron and uPlot. .gitignore holds viewer/node_modules/.
- Requirement 20, the drag zoom, the double click, and the arrow keys, has no passing check, because only check 6 covers it. The driven run saw each part of it work.
- Requirement 13 has passing checks for FILE and `--boot`, and the stage ran `npm --prefix viewer start -- tests/firmware/command_log.txt.gz --boot 505078862 --capture SCRATCH/npmstart.png` from the repo root, which exited with code 0 and resolved the file against the repo root. Its File menu item, Cmd+O, and open dialog wait for check 6.
- Requirements 4, 9, and 18 pass on check 1 cases 13, 14, 19, and 21 and check 2 case 27 with the made-up recording. Their check on a real wrist shake waits for check 7.
- Every other requirement has at least one passing check from checks 1 to 4.

### Other findings

- The summary of each boot shows the bad lines and dropped bursts of the whole file, in viewer/src/renderer/viewer.js lines 72 and 73. Boot B of the made-up recording shows 1 bad line and 1 dropped burst, which both lie in boot A.
- viewer/src/main.js line 21 takes the app's arguments from index 2 of process.argv, so an Electron or Chromium switch before the app path makes the app refuse to start. `npm --prefix viewer start` and the smoke script never do this, so no requirement fails.
- An empty or header-only `.gz` file is read as a gzip file cut short in viewer/src/lib/read_text.js lines 39 to 60, so the page says the file holds no B line in its 0 lines, not that it is not a gzip file. The message is still plain, and the app does not crash.
- The stage loaded a 375 MB text file of 9,878,220 readings, just under the 400 MB limit. Electron's Node loaded it in 3.9 seconds with 1.5 GB of memory, and the real app drew it in about 4 seconds in capture mode.
- The electron settings match requirement 22. The CSP is exact, the four web preferences are set, the preload gives three calls, every IPC message is checked against the page's own frame and URL, and new windows, navigation, and permissions are denied.

### Decision for the user

`npm audit` reports advisory GHSA-jr5w-w6x2-84p9 for Electron 44.0.0 to 44.9.0, fixed in 44.10.0. The advisory is about trusting certificates from compromised eMudhra intermediates, so it matters only for TLS connections. The viewer opens no network connection. Its page loads only local files under a CSP of `default-src 'none'`, and it denies navigation and new windows. So the stage's view is that the advisory does not reach this app. Moving to 44.10.0 is still cheap, but it needs requirement 12 and check 1 case 25 changed, and that is the user's call.
