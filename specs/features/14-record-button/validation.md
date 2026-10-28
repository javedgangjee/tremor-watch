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
     34. With TREMOR_PYTHON set to SCRATCH/smoke/fake-python, TREMOR_RECORDINGS set to a new folder SCRATCH/smoke/recordings, and FAKE_WATCH_CLI giving copy as viewer/test/fixtures/synthetic.txt.gz, the app runs with `--record-for 2 --capture SCRATCH/smoke/record_fake.png`. It exits with code 0. OUT.json's recording has exitCode 0 and a file in SCRATCH/smoke/recordings whose name matches `^tremor-\d{4}-\d{2}-\d{2}-\d{6}\.txt\.gz$`, and that folder holds only that file. The report gives boot 305419896 and 18260 readings, and its recordStatus starts with `Saved `.
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
     - The page's recordStatus starts with `Saved `, and the PNG shows the plot of F.
   - When the watch is not on USB or runs other firmware, this check is recorded as not run, and the validate stage says so. When the watch restarts during the minute, so that F holds two boot IDs, run the check once more.
   - If the validate agent can drive the window with Playwright's Electron support, as feature 12's check 6 did, it also presses the real Record button, waits about 20 seconds, presses Stop, and records what the page showed. This part is for information and does not decide the check.

5. The feature changes only the files it should.
   - The command is `git diff --stat feature/13-edf-export`.
   - The expected result is that it lists no file in firmware/, core/, reference/, tools/, tests/, or context/, and no file in recordings/.

## Manual checks

6. The button works by hand.
   - With the watch on USB, run `npm --prefix viewer start`. Press Record. The button turns navy and reads Stop, the time counts up each second, and within a few seconds the status line says "The watch set its clock.". After about a minute press Stop. The button reads Stopping for about a second, then Record, the status line gives "Saved N lines to ..." with a path in recordings/, and the plot of the new file shows.
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
