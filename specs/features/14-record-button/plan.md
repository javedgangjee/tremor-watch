# Feature 14 plan: Record button

The steps run in this order. Every command runs from the repo root with Node v22.22.1 and npm 11.20.0 from nvm. The code is plain JavaScript in CommonJS with `'use strict'` and JSDoc types on each exported function, as in feature 12.

No step changes a file in firmware/, core/, reference/, tools/, tests/, or context/. The files that change outside viewer/ are .gitignore, README.md, and specs/tech-stack.md. Never change a case or a limit in validation.md to make it pass. If a case can pass only that way, stop and report it.

1. Add `class RecordError extends Error` to viewer/src/lib/errors.js beside RecordingError and ArgsError. Its message is the plain sentence the page shows.

2. Write viewer/src/lib/recorder.js as in requirements 10 to 17. It requires only `node:child_process`, `node:events`, `node:fs`, `node:os`, `node:path`, and `./errors`.
   - `DEFAULT_PYTHON` is `~/.espressif/tools/python/v6.1/venv/bin/python` under os.homedir(), with a comment that names specs/tech-stack.md. `KILL_AFTER_MS = 10000`.
   - `recorderSettings({ env, home, cwd, repo })` returns `{ python, script, folder }`. python is env.TREMOR_PYTHON or the default under home. script is `<repo>/tools/watch_cli.py`. folder is env.TREMOR_RECORDINGS resolved against cwd, or `<repo>/recordings`. repo defaults to three folders above recorder.js.
   - `recordingName(date)` gives `tremor-YYYY-MM-DD-HHMMSS.txt.gz` from the local time of date. `freeRecordingPath(folder, date)` makes the folder with `{ recursive: true }` and returns the first name of the series `NAME.txt.gz`, `NAME-2.txt.gz`, `NAME-3.txt.gz` that does not exist.
   - `errorLine(lines)` returns LINE as requirement 16 says, or null for no lines.
   - `class Recorder extends EventEmitter` takes `{ python, script, folder, env = process.env, now = () => new Date(), killAfterMs = KILL_AFTER_MS }`.
     - `state` is `'idle'`, `'recording'`, or `'stopping'`.
     - `start()` throws a RecordError when a recording runs, when the Python is missing or cannot run (fs.accessSync with X_OK), when watch_cli.py is missing, or when the folder cannot be made. Otherwise it picks the file, spawns the child as requirement 12 says, and returns `{ file, startedAt }`. A spawn `error` event, such as EACCES, ends the recording with the message "Could not start PYTHON (CODE).".
     - It reads standard error line by line, keeps the last 50 lines, and emits `status` with `{ state, startedAt, file, text, ok }` for each new line and each change of state. It reads standard output and drops it.
     - `stop()` returns a promise of the outcome. In the recording state it sends SIGINT once, moves to stopping, and starts the kill timer. In the stopping state it returns the same promise. In the idle state it resolves with null.
     - The recording ends once, on the child's `close` event or on a spawn error. The outcome is `{ file, code, signal, killed, fileExists, open, ok, text }`, built as requirement 16 says. The recorder clears the kill timer, moves to idle, emits a last `status` with the outcome's ok and text, emits `done` with the outcome, and resolves every stop promise.

3. Change viewer/src/lib/args.js as in requirement 20. parseArgs() reads `--record-for SECONDS` and returns `{ file, capture, bootId, recordFor }`. It throws an ArgsError when SECONDS is not a whole number from 1 to 86400, when `--record-for` comes without `--capture`, and when it comes with a FILE. `--capture` with no FILE stays an error unless `--record-for` is given. USAGE becomes `npm --prefix viewer start -- [FILE] [--boot ID] [--capture OUT.png] [--record-for SECONDS]`.

4. Change viewer/src/main.js as in requirements 11 to 19.
   - Make one Recorder from `recorderSettings({ env: process.env, home: os.homedir(), cwd: process.env.INIT_CWD || process.cwd() })` when the app starts.
   - `startRecording(win)` calls recorder.start(), sends its status, and turns a RecordError into a status with ok false and its message. `stopRecording()` calls recorder.stop(). The button's IPC and capture mode both use these two functions.
   - Handle `viewer:record-start` and `viewer:record-stop` with ipcMain.on, and answer each only when isOwnPage(win, event) is true. Send every recorder status on `viewer:record-status`, only while the window exists.
   - On the recorder's `done`, open the file with openRecording() when outcome.open is true, the app is not quitting, and the app is not in capture mode, where capture.js opens the file itself.
   - Add a `before-quit` handler. When the recorder is not idle, it calls event.preventDefault(), sets quitting, awaits recorder.stop(), and calls app.quit() again.

5. Change viewer/src/capture.js as in requirement 20.
   - runCapture() awaits `open()`, so open may be async. With recordFor, main.js passes an open that starts the recording, waits recordFor seconds, stops it, and awaits the outcome. It then opens the file when outcome.open is true. Otherwise, and when start() throws a RecordError, it sends the page a `viewer:recording` message with ok false and the status text, so the page shows the message and reports.
   - OUT.json gains `recording` with file, exitCode, signal, and text, or null without recordFor. The exit code is 1 when the recording's exit code was not 0.
   - Every path that exits stops a running recording first.

6. Change viewer/src/preload.js as in requirement 18. Add startRecording() and stopRecording(), which send `viewer:record-start` and `viewer:record-stop` with no argument, and onRecordStatus(callback), which passes only the status object on.

7. Change the page as in requirements 14 and 19.
   - viewer/src/renderer/index.html gains `<button id="record" type="button">Record</button>` after the Open button and `<p id="record-status" class="record-status" role="status" hidden></p>` under the bar. The CSP does not change.
   - viewer/src/renderer/viewer.js sends startRecording() or stopRecording() from the button by state, sets the button text and its disabled state from each status, runs a one-second timer for h:mm:ss while recording, and shows the status text. bootReport() and the failure report gain `recordStatus`, which is the status line's text.
   - viewer/src/renderer/viewer.css gains `.recording` for the button, with background #1B2E42 from the `--tremor` token and white text, and `.record-status` with a `.failed` look in `--text`.

8. Write viewer/test/helpers/fake_watch_cli.js as in requirement 21. It finds `--out FILE` anywhere in its arguments, so it works both as `node fake_watch_cli.js record --out FILE` and behind a shell script that passes the watch_cli.py path first. When it has set its SIGINT handler, it writes `Saving the recording to FILE. Press Ctrl-C to stop.` to standard error, as watch_cli.py does, so a test stops it only after that line and never before the handler is in place. It reads one environment variable, FAKE_WATCH_CLI, as JSON with these fields.
   - `argsOut`: a file where it writes its arguments and PYTHONUNBUFFERED as JSON.
   - `startLines`: lines it writes to standard error after the first line.
   - `dieWith`: an exit code. With it, the fake writes only startLines, makes no file, and exits at once, as watch_cli.py does when it cannot open the port.
   - `ignoreInt`: true makes it ignore SIGINT.
   - `closeDelayMs`: a wait between SIGINT and the exit.
   - `copy`: a gzip file whose bytes it writes to FILE at SIGINT. Without it, it writes three fixed lines as gzip.
   - `stopLines`: lines it writes at SIGINT, after "The recording was stopped." and before "Saved N lines to FILE.".
   - `exitCode`: the code at SIGINT, 0 by default.
   - `sigintOut`: a file where it adds one line for each SIGINT.
   - Like watch_cli.py, it exits with code 1 and "FILE exists already." when FILE exists at its start.

9. Write viewer/test/recorder.test.js with cases 1 to 12 of check 1 in validation.md, and add cases 13 and 14 to viewer/test/args.test.js and viewer/test/package.test.js. Each test uses a folder from tempFolder(), runs the fake with process.execPath as the Python and fake_watch_cli.js as the script, and gives each wait a limit of 10 seconds so a hung child fails the test and does not hang it. Change case 23 in args.test.js to expect `recordFor: null`.

10. Change viewer/scripts/smoke.js with cases 34 and 35 of check 2. The script writes OUT/fake-python, a shell script with mode 755 that runs `exec "<node>" "<fake_watch_cli.js>" "$@"`, where node is process.execPath. runApp() takes an optional env. The case count line then says 9 cases.

11. Change the docs as in requirement 22.
    - .gitignore gains `/recordings/`.
    - specs/tech-stack.md: the Recording viewer section replaces "It reads saved files only and never opens the watch's port." with the Record button, the child process, TREMOR_PYTHON, TREMOR_RECORDINGS, the recordings folder, and the fact that the viewer still never opens the port. It names recorder.js among the modules, gives the preload's six calls, and adds `--record-for SECONDS` to the start command. The smoke line gains the two record cases.
    - README.md: the View a recording section replaces "It reads saved files only and never opens the watch's port." and gains a short paragraph on Record and Stop, where the files go, the two environment variables, and what happens on a failure. The Repo layout row for viewer/ says it can also record through watch_cli.py.

12. Run `make viewer`, `npm --prefix viewer run smoke -- --out SCRATCH/smoke`, and `make check`, and fix the failures. When the watch is on USB with the Tremor log firmware, run the command of check 4 once with `--record-for 20` and look at the PNG. Do not commit anything in recordings/.
