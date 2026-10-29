# Feature 14 validation: Record button

Every command runs from the repo root with Node v22.22.1 and npm 11.20.0 from nvm. Checks 1 and 3 need no network, no node_modules, no toolbox, and no watch. Check 2 needs the installed packages and a logged-in screen on the Mac. Check 4 needs the watch on USB at /dev/cu.usbmodem101 with the Tremor log firmware. Check 6 is manual and waits for the user. SCRATCH means a new folder in the session's scratch folder.

The limits come from these sources. The 10 second kill limit comes from requirement 15. The 10 second limit on each wait in the tests stops a hung child from hanging the run. In check 4 a 60 second recording loses up to about 10 seconds to the reset and the boot, so it holds at least 50 seconds of readings at about 114.35 a second, which is more than 5700. Each new stretch gives no window for its first 4 seconds, and feature 12's check 5 saw two stretch ends in 3 minutes, so 50 seconds give at least 30 windows.

## Terms

- "The fake" is viewer/test/helpers/fake_watch_cli.js. "A recorder" is a Recorder from viewer/src/lib/recorder.js with process.execPath as the Python, the fake as the script, a new folder from tempFolder() as the folder, and FAKE_WATCH_CLI in its env.
- "Run to the end" means start(), then stop() when the case says so, then await the outcome or the `done` event.
- NOW is `new Date(2026, 9, 28, 14, 30, 5)`, which is 14:30:05 local time on 2026-10-28.

## Automated checks

1. The unit tests pass.
   - The command is `make viewer`, which runs `node --test viewer/test/*.test.js`.
     1. recordingName(NOW) is `tremor-2026-10-28-143005.txt.gz`. freeRecordingPath() on a folder that does not exist makes it and gives that name. With that name taken it gives `tremor-2026-10-28-143005-2.txt.gz`, and with both taken it gives `-3`. Each path it gives does not exist.
     2. recorderSettings({ env: {}, home: '/h', cwd: '/c', repo: '/r' }) gives python `/h/.espressif/tools/python/v6.1/venv/bin/python`, script `/r/tools/watch_cli.py`, and folder `/r/recordings`. With TREMOR_PYTHON `/p/python` and TREMOR_RECORDINGS `rec` it gives python `/p/python` and folder `/c/rec`.
     3. A recorder with now NOW and a folder whose path holds a space and a `$` runs to the end with a stop after the status whose text is the fake's first line, `Saving the recording to <file>. Press Ctrl-C to stop.`. The fake's argsOut gives the arguments `[<fake>, 'record', '--out', '<folder>/tremor-2026-10-28-143005.txt.gz']` exactly, with the space and the `$` unchanged, and PYTHONUNBUFFERED `1`. The states in the status events are recording, then stopping, then idle. sigintOut holds one line. The outcome has code 0, signal null, open true, and ok true, and its text is `Saved 3 lines to <file>.`. The file gunzips with no error to the fake's three lines.
     4. With startLines `["The watch set its clock."]`, a status event in the recording state has the text `The watch set its clock.` before stop() is called.
     5. With stopLines `["The clock command got result 4. The watch applied the setting but could not store it, so a restart loses it."]` and exitCode 1, a run to the end gives code 1, open true, and ok false. The file exists, and the text is `watch_cli.py stopped with code 1: The clock command got result 4. ...` with the whole line.
     6. With startLines `["Traceback (most recent call last):", "serial.serialutil.SerialException: [Errno 2] could not open port /x: [Errno 2] No such file or directory: '/x'"]` and dieWith 1, `done` comes with no call to stop(). The outcome has code 1, fileExists false, open false, and ok false, its text ends with the SerialException line, and the state is idle. With startLines `["ModuleNotFoundError: No module named 'serial'"]` and dieWith 1, the text also names pyserial and TREMOR_PYTHON.
     7. stop() called twice while recording gives the same promise, sigintOut holds one line, and the outcome is the one of case 3. A start() while recording throws a RecordError, and the first recording goes on. stop() on an idle recorder resolves with null.
     8. With closeDelayMs 500, stop() resolves no sooner than 450 ms after it was called, and the file then gunzips whole. This is the wait that `before-quit` relies on.
     9. With ignoreInt true and killAfterMs 300, the outcome has signal SIGKILL, killed true, and open false, and its text says watch_cli.py did not stop and the file may be cut short.
     10. A recorder whose python is `<folder>/no-such-python` throws a RecordError from start() whose message names that path and TREMOR_PYTHON. A python that is a file with mode 644 throws a RecordError too. A script that does not exist throws a RecordError that names it. In each case no file is made in the folder and the state stays idle.
     11. A folder that already holds `tremor-2026-10-28-143005.txt.gz` with the bytes `keep` gives a recording in `tremor-2026-10-28-143005-2.txt.gz`, and the first file still holds `keep` after the run.
     12. errorLine() of `["a", "The clock command got no answer.", "The recording was stopped by SIGTERM.", "Saved 10 lines to F."]` is `The clock command got no answer.`. errorLine() of `["a", "b"]` is `b`, of `["Saved 1 lines to F."]` is `Saved 1 lines to F.`, and of `[]` is null.
     13. parseArgs(['--record-for', '60', '--capture', 'o.png'], '/x') gives file null, capture /x/o.png, bootId null, and recordFor 60. ['--record-for', '60'], ['--record-for', '60', '--capture', 'o.png', 'a.gz'], ['--record-for', '0', '--capture', 'o.png'], ['--record-for', '1.5', '--capture', 'o.png'], and ['--record-for', '86401', '--capture', 'o.png'] each throw an ArgsError. Feature 12's case 23 passes with `recordFor: null` in its expected objects.
     14. viewer/src/preload.js exposes exactly the keys openFile, onRecording, reportDrawn, startRecording, stopRecording, and onRecordStatus. startRecording and stopRecording send their channel with no other argument. In viewer/src/main.js each `ipcMain.on` handler for `viewer:open`, `viewer:record-start`, and `viewer:record-stop` calls isOwnPage(). No file in viewer/src/ holds `shell: true`, `exec(`, or `execSync(`. viewer/src/lib/recorder.js requires only `node:` modules and `./errors`. Feature 12's case 26 still passes.
   - The expected result is that node reports 0 failed, and every case above and every case of feature 12's check 1 is a passing test.

2. The real app passes the smoke cases.
   - The command is `npm --prefix viewer run smoke -- --out SCRATCH/smoke`.
   - Feature 12's cases 27 to 33 run as before. Case 27 has failed once in five runs on 2026-10-28, with a PNG of the empty start page, because the capture took a frame before the drawn plot reached it. When case 27 alone fails, run the command once more and judge the second run, and report both runs.
     34. With TREMOR_PYTHON set to SCRATCH/smoke/fake-python, TREMOR_RECORDINGS set to a new folder SCRATCH/smoke/recordings, and FAKE_WATCH_CLI giving copy as viewer/test/fixtures/synthetic.txt.gz, the app runs with `--record-for 2 --capture SCRATCH/smoke/record_fake.png`. It exits with code 0. OUT.json's recording has exitCode 0 and a file in SCRATCH/smoke/recordings whose name matches `^tremor-\d{4}-\d{2}-\d{2}-\d{6}\.txt\.gz$`, and that folder holds only that file. OUT.json's recording.text starts with `Saved `. The report gives boot 305419896 and 18260 readings, and its recordStatus is empty.
     35. With TREMOR_PYTHON set to SCRATCH/smoke/no-such-python and TREMOR_RECORDINGS set to a new folder SCRATCH/smoke/recordings_none, `--record-for 2 --capture SCRATCH/smoke/record_missing.png` exits with code 1. OUT.json's message names TREMOR_PYTHON, the PNG exists, and no file is in the folder.
   - The expected result is that the script prints a pass for all 9 cases and exits with code 0.
   - The validate agent opens SCRATCH/smoke/record_fake.png and checks by eye that the bar shows Open recording and Record, that the status line says the recording was saved, and that the made-up recording is drawn as in feature 12's check 2.

3. `make check` runs the unit tests and needs no network.
   - The commands are `git worktree add SCRATCH/clean HEAD`, `make -C SCRATCH/clean viewer`, `git worktree remove --force SCRATCH/clean`, and then `make check`.
   - The expected result is that `make viewer` passes in the clean worktree, which has no viewer/node_modules, and `make check` exits with code 0.

4. A recording made through the app from the real watch opens and draws.
   - The command is `TREMOR_RECORDINGS=SCRATCH/rec viewer/node_modules/.bin/electron viewer --record-for 60 --capture SCRATCH/rec.png`. It uses the default Python, which must hold pyserial, and watch_cli.py's default port. The recording resets the watch.
   - Let F be OUT.json's recording.file. Count the W lines of F with `gunzip -c F | cut -f2- | awk -F, '/^B,/{b=1} b && /^W,[0-9]+,[0-9]+,[0-4],/{n[$4]++} END{for(c=0;c<5;c++) print c, n[c]+0}'`.
   - The expected result is this.
     - The app exits with code 0, and OUT.json's recording has exitCode 0 and signal null. F lies in SCRATCH/rec with a name of the form of requirement 13, and `gzip -t F` exits with code 0.
     - F holds a `> CLOCK,` line and the answer `A,1,0` after its first B line, and only one boot ID.
     - The report gives at least 5700 readings and at least 30 windows, and windowsByCode for each code 0 to 4 equals the count of the awk command for that code.
     - OUT.json's recording.text starts with `Saved `, the page's recordStatus is empty, and the PNG shows the plot of F.
   - When the watch is not on USB or runs other firmware, this check is recorded as not run, and the validate stage says so. When the watch restarts during the minute, so that F holds two boot IDs, run the check once more.
   - If the validate agent can drive the window with Playwright's Electron support, as feature 12's check 6 did, it also presses the real Record button, waits about 20 seconds, presses Stop, and records what the page showed. This part is for information and does not decide the check.

5. The feature changes only the files it should.
   - The command is `git diff --stat feature/13-edf-export`.
   - The expected result is that it lists no file in firmware/, core/, reference/, tools/, tests/, or context/, and no file in recordings/.

## Manual checks

6. The button works by hand.
   - With the watch on USB, run `npm --prefix viewer start`. Press Record. The button turns navy and reads Stop, the time counts up each second, and within a few seconds the status line says "The watch set its clock.". After about a minute press Stop. The button reads Stopping for about a second, then Record, the status line goes, and the plot of the new file shows with its name in the Summary.
   - Press Record again, and after about 20 seconds press Cmd+Q. The app stays open for about a second and then quits. Run `gzip -t` on the newest file in recordings/, and it exits with code 0.
   - Unplug the watch, start the app, and press Record. Within a few seconds the status line gives "watch_cli.py stopped with code 1:" and a line that says the port could not be opened, the button reads Record again, and the plot does not change.
   - Run `TREMOR_PYTHON=/nope npm --prefix viewer start` and press Record. The status line gives one plain message that names /nope and TREMOR_PYTHON.

## Requirement coverage

- Requirements 1 and 3 are covered by check 1 cases 3 to 9, check 2 case 34, check 4, and manual check 6.
- Requirement 2 and requirement 9 are covered by check 1 case 14, feature 12's case 26, and check 4, which shows watch_cli.py's clock line in the file.
- Requirement 4 and requirement 11 are covered by check 1 cases 2, 6, and 10, check 2 case 35, check 4, and manual check 6.
- Requirement 5 is covered by check 2 case 34 and check 4.
- Requirement 6 and requirement 12 are covered by check 1 case 3, which checks the exact arguments with no `--port` and no `--minutes`.
- Requirements 7 and 22 are covered by check 5 and by reading specs/tech-stack.md, README.md, and .gitignore in the validate stage.
- Requirement 8 and requirement 18 are covered by check 1 case 14, feature 12's case 26, and feature 12's case 27 in check 2.
- Requirement 10 is covered by check 1 case 14 and check 3.
- Requirement 13 is covered by check 1 cases 1, 2, and 11 and check 2 case 34.
- Requirements 14 and 15 are covered by check 1 cases 3, 4, 7, and 9 and manual check 6.
- Requirement 16 is covered by check 1 cases 3, 5, 6, 9, and 12 and check 2 cases 34 and 35.
- Requirement 17 is covered by check 1 case 8 and manual check 6.
- Requirement 19 is covered by the look at record_fake.png in check 2 and manual check 6.
- Requirement 20 is covered by check 1 case 13, check 2 cases 34 and 35, and check 4.
- Requirement 21 is covered by checks 1 and 3.

## Results, 2026-10-28

The validate stage ran on branch feature/14-record-button at commit a378d28 with a clean tree, Node v22.22.1, and npm 11.20.0. SCRATCH was a new folder in the session's scratch folder. The watch was on USB at /dev/cu.usbmodem101 with the Tremor log firmware 12, and the default Python held pyserial 3.5.

Checks 1 to 4 passed. Check 5 fails as written, and the check's base is at fault, as the section on check 5 says. Check 6 waits for the user. The stage drove the real window through every step of check 6 except the unplugged watch, as the section on check 6 says, but it did not mark check 6 as passed. So the feature is ready for review once the user runs check 6 and decides on the wording of check 5.

### Automated checks

1. Check 1 passed. `make viewer` exited with code 0, and node reported 40 tests, 40 passed, and 0 failed. These are feature 12's 26 cases, with case 23 expecting `recordFor: null`, and cases 1 to 14 of this feature, each named "case N of feature 14".
   - Case 14 changed during implement, as item 1 of "Changes during implement" in plan.md says. The test looks for `exec(` only in files that hold the text `child_process`, and it looks for `shell: true` and `execSync(` in every file. The stage agrees with the change. format.js and parse.js call RegExp's exec(), which runs no program, so the case as worded fails on feature 12's code. A file that requires child_process in either spelling still holds that text, so the narrowed test still finds `exec(` where it could run a program. The stage read recorder.js, the only file that requires child_process, and it calls spawn() only. The case's wording in this file should be changed to match the test, which is the user's call.
2. Check 2 passed on the second run, as the check allows. The stage ran the smoke command five times, each in a new folder. Four runs printed a pass for all 9 cases and "9 of 9 cases passed" and exited with code 0. One run, the fourth, failed case 27 alone with 0 of 39 tremor cells matched and every sampled cell white, which is the known race of a capture taken before the plot was drawn. The run after it passed all 9 cases. So case 27 failed once in five runs, the same rate the check gives.
   - Case 34 gave exit code 0, a recording with exitCode 0 and signal null, one file `tremor-2026-10-28-134434.txt.gz` in SCRATCH/smoke3b/recordings and nothing else, boot 305419896, 18260 readings, and a recordStatus of "Saved 21106 lines to ...". Case 35 gave exit code 1, a message that names the missing Python and TREMOR_PYTHON, a PNG, and an empty recordings_none folder.
   - The stage looked at record_fake.png. The bar shows Open recording and Record with the same look, the status line under it says "Saved 21106 lines to" and the file path, and the made-up recording is drawn as in feature 12's check 2, with the two navy shakes, the green sway cells, and the gaps.
   - Case 27 in the passing runs gave contextIsolation true, nodeIntegration false, sandbox true, webSecurity true, no `require` and no `process` on the page, and 39 of 39 tremor cells matched.
3. Check 3 passed. The check names `git worktree add`, but the user does not use worktrees, so the stage made the clean copy with `git archive HEAD | tar -x -C SCRATCH/clean`. The copy had no viewer/node_modules, and `make -C SCRATCH/clean viewer` gave 40 passed and 0 failed. `make check` in the repo exited with code 0, with "100% tests passed out of 16", "model hash matches", 40 viewer tests passed, and "Project build complete". The tree stayed clean.
4. Check 4 passed. The app exited with code 0. OUT.json's recording had exitCode 0, signal null, and the text "Saved 7612 lines to ...", and F was SCRATCH/rec/tremor-2026-10-28-134554.txt.gz, the only file in SCRATCH/rec. `gzip -t F` exited with code 0.
   - F holds one boot ID, 369707515, with firmware 12. Its B line is line 110, the line `> CLOCK,1793209555689292,-240` follows at line 111, and `A,1,0` comes at line 121.
   - The report gave 6754 readings, which passes the limit of 5700, and 55 windows, which passes the limit of 30. windowsByCode was 0, 54, 0, 1, and 0 for codes 0 to 4, and the awk command gave the same five counts.
   - The page's recordStatus starts with "Saved ", and rec.png shows the plot of F, about 60 seconds of a still watch with no tremor cell and 54 no tremor cells.
   - The optional part ran with Playwright 1.64.0, which was installed in SCRATCH and not in the repo, and a small wrapper in SCRATCH that loads viewer/src/main.js unchanged. The section on check 6 gives what the page showed.
5. Check 5 fails as written, and the check's base is at fault. `git diff --stat feature/13-edf-export` lists context/tremor-log-plan.html, with one paragraph changed so the viewer may have a Record button. That change came from commit 80be0ea, which added feature 14 to the roadmap and the build spec before the plan, and the roadmap says the user asked for it. `git diff --stat 80be0ea HEAD`, which covers the plan and the implement commits, lists no file in firmware/, core/, reference/, tools/, tests/, or context/, and no file in recordings/. The check should name 80be0ea as its base, which is the user's call.

### Manual checks

6. Check 6 waits for the user. The stage drove the real window with Playwright for most of it, with TREMOR_RECORDINGS set to a folder in SCRATCH, so the repo's recordings/ folder was never made. Playwright cannot press Cmd+Q, so the stage called app.quit(), which the Quit menu item calls, and it closed the window with BrowserWindow.close(), which the close button calls. The stage saw these steps work.
   - Record turned the button to Stop with background rgb(27, 46, 66), which is #1B2E42, and white text. The status line read "Recording 0:00:00. Saving the recording to ...", then "Recording 0:00:01. The watch set its clock." within about one second, and the time went up by one each second up to 0:00:20. The status text was rgb(92, 98, 101), which is #5C6265.
   - Stop showed "Stopping" with the button turned off and "Stopping 0:00:20. The recording was stopped.". Less than a second later the button read Record, the status gave "Saved 2556 lines to" a path in the recordings folder, and the plot of the new file showed. A forced second click while the button was off started nothing.
   - While a recording ran, Open with the dialog replaced in the main process showed tests/firmware/command_log.txt.gz, and the button still read Stop. Stop then replaced it with the new file.
   - app.quit() after 20 seconds of recording held the quit. watch_cli.py ended, then Electron exited with code 0 about 0.17 seconds after the quit. Closing the window did the same in about 0.16 seconds. SIGINT to the app's process group, as Ctrl-C in its terminal sends, and SIGTERM or SIGHUP to Electron alone also ended watch_cli.py before Electron exited. In every case no watch_cli.py process was left, `gzip -t` passed on the file, the file ended with a newline, and the viewer opened it and drew it.
   - TREMOR_PYTHON=/nope gave the status "There is no Python at /nope. Set TREMOR_PYTHON to the path of a Python that holds pyserial." in the main text colour, rgb(17, 19, 21), and made no file. TREMOR_PYTHON=/usr/bin/python3, which has no pyserial, gave "watch_cli.py stopped with code 1: ModuleNotFoundError: No module named 'serial' This Python has no pyserial. Set TREMOR_PYTHON to the ESP-IDF Python, which holds it." and made no file.
   - The steps still waiting for the user are these. With the watch on USB, run `npm --prefix viewer start` from the repo root and do each step of check 6 by hand. Press Record, check the navy Stop button, the time, and "The watch set its clock.", and press Stop after about a minute. Press Record again and press Cmd+Q on the keyboard after about 20 seconds, check that the app quits after about a second, and run `gzip -t` on the newest file in recordings/. Then unplug the watch, start the app, press Record, and check for "watch_cli.py stopped with code 1:" with a line that says the port could not be opened and no change to the plot. Last, run `TREMOR_PYTHON=/nope npm --prefix viewer start`, press Record, and check for one message that names /nope and TREMOR_PYTHON. Remove recordings/ afterwards if the files are not wanted.

### Requirement coverage

- Every requirement from 1 to 22 has at least one passing check, with the three notes below.
- Requirement 7 holds for the plan and implement commits. The one change in context/ came with the roadmap commit 80be0ea, as check 5 says.
- Requirement 17's hold on quit has no passing check other than check 1 case 8, which tests stop()'s wait and not the `before-quit` handler. The driven run saw the hold work for the quit, the window close, and the signals. Manual check 6 decides it.
- Requirement 19's navy button and the Open button while recording have no passing automated check, because record_fake.png shows the idle bar only. The driven run saw both work. Manual check 6 decides them.
- Requirement 22 holds. The stage read the diff. specs/tech-stack.md names recorder.js, the six calls, both environment variables, the recordings folder, `--record-for`, and the two smoke cases. README.md has a paragraph on Record and Stop and a new viewer/ row, and .gitignore holds `/recordings/`. The Makefile did not change.

### Other findings

- viewer/src/main.js lines 117 and 127 send a failed recording to the page's message area in capture mode. When no file was made, as in case 35, record_missing.png shows the heading "The viewer cannot show this file" from viewer/src/renderer/index.html line 32 over a reason about the Python, and the status line above repeats the same text. There is no file in this case, so the heading misleads. With the button, a failure with no file shows only in the status line, so the heading does not appear there. When watch_cli.py made a file with no B line, the heading is right.
- README.md line 137 says that when watch_cli.py stops with an error, the plot stays as it was. When watch_cli.py exits with another code and made a file, the viewer opens that file, as requirement 16 says, so the plot changes. The driven run saw this when Stop came about 150 ms after Record. watch_cli.py exited with code 1 and "No B line came", the 47 line file stayed in the recordings folder, and the page replaced the plot with feature 12's message that the file holds no B line.
- When Stop comes within about 30 ms of Record, SIGINT reaches watch_cli.py before it sets its handlers, so Python ends by the signal and makes no file. The status then reads "watch_cli.py was ended by SIGINT.", from viewer/src/lib/recorder.js line 119, which reads like a fault after a normal press and does not say that nothing was saved.
- viewer/src/lib/recorder.js line 132 adds the pyserial hint straight after watch_cli.py's line, which has no full stop, so the status reads "No module named 'serial' This Python has no pyserial."
- When Electron is killed with SIGKILL, watch_cli.py goes on recording with no viewer, as requirement 17 says. The stage sent it SIGINT after about 15 seconds, and the file then passed `gzip -t` and opened.
- The stage found no race between Stop and a child that ends by itself. When the child has exited and `close` has not come yet, Node's kill() sends no signal, the kill timer is cleared when `close` comes, and #end() runs once. When `close` came first, stop() resolves with null and the page's press does nothing.
- The settings of feature 12's requirement 22 hold. The CSP did not change, the four web preferences are set, the preload gives six calls, each of the three page messages is checked with isOwnPage(), and new windows, navigation, and permissions are still denied.
