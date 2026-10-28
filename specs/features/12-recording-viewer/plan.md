# Feature 12 plan: Recording viewer

The steps run in this order. Every command runs from the repo root with Node v22.22.1 and npm 11.20.0 from nvm. npm commands that reach the registry may need the sandbox turned off. The code is plain JavaScript in CommonJS with `'use strict'` and JSDoc types on each exported function.

No step changes a file in firmware/, core/, reference/, tools/, tests/, or context/. The files that change outside viewer/ are the Makefile, .github/workflows/check.yml, .gitignore, README.md, and specs/tech-stack.md. Never change a case or a limit in validation.md to make it pass. If a case can pass only that way, stop and report it.

1. Make the package.
   - Write viewer/package.json with the name tremor-log-viewer, `"private": true`, `"main": "src/main.js"`, and the scripts `start` (`electron .`), `test` (`node --test test/*.test.js`), `smoke` (`node scripts/smoke.js`), and `fixture` (`node scripts/make_synthetic.js`). Write viewer/.npmrc with `save-exact=true`.
   - Run `npm --prefix viewer install --save-dev electron@44.7.1` and `npm --prefix viewer install uplot@1.6.32`, and commit viewer/package-lock.json. package.json must list exactly these two packages with no `^` or `~`.
   - Add `viewer/node_modules/` to .gitignore.

2. Write viewer/src/lib/errors.js. It holds `class RecordingError extends Error`, whose message is the plain sentence the page shows.

3. Write viewer/src/lib/format.js as in requirement 15.
   - `readRecordPatterns(docPath = <repo>/core/recording_format.md)` returns an object of eight RegExp keyed by letter. It reads the table rows with the row pattern of record_patterns() in tools/compare_session.py and throws a RecordingError that names the missing letters.

4. Write viewer/src/lib/read_text.js as in requirements 2, 8, 13, and 21.
   - `readRecordingLines(filePath, { maxBytes = 400 * 1024 * 1024 } = {})` returns `{ lines, cutShort }`. It reads the file with node:fs. For a `.gz` name it calls zlib.gunzipSync() with maxOutputLength. When that fails with Z_BUF_ERROR or "unexpected end of file", it calls gunzipSync() again with `finishFlush: zlib.constants.Z_SYNC_FLUSH`, sets cutShort, and drops a last line that has no newline. Any other gzip error becomes "FILE is not a gzip file". A text over maxBytes becomes a RecordingError that gives the limit.
   - Each line loses a leading laptop time and tab when the part before the tab reads as a number, as read_recording() in tools/compare_session.py does. A carriage return at the end is dropped.

5. Write viewer/src/lib/parse.js as in requirements 6 and 16.
   - `parseLines(lines, patterns)` returns `{ boots, counts }`. counts holds lines, bad, droppedBursts, and noB. Each boot holds id, resetCause, firmware, tableHash, `sLines` (a Map from stretch number to `{ first, t0Us, rateUhz }`), `bursts` (an array of `{ first, count, stampUs, gyro }`, where gyro is an Int16Array of count × 3 counts), `windows` (a Map keyed `"s,n"` to `{ stretch, window, code }`), and faults.
   - A held burst closes at the next T line, the next B line, and the end of the lines. The end of the lines leaves out a burst that is in order but short without a count.
   - The parser does no time maths.

6. Write viewer/src/lib/timeline.js as in requirements 3, 7, and 17.
   - `GYRO_COUNTS_PER_DPS = 32`, with a comment that names core/imu_units.h. `FALLBACK_RATE_UHZ = 114330200`, with a comment that names feature 1's measured rate in specs/tech-stack.md.
   - `stretchTable(boot)` returns the stretches in order of first reading, each with number, first, t0Us, rateUhz, and estimated. `buildTimeline(boot)` returns `{ stretches, timeS, gx, gy, gz, breaks, noStretchReadings }`. timeS is a Float64Array of seconds since boot, computed as `(t0Us + (n - first) * 1e12 / rateUhz) / 1e6`. gx, gy, and gz are Float32Array in degrees per second. breaks is an array of indexes i where a line must not join reading i - 1 to reading i.

7. Write viewer/src/lib/windows.js as in requirement 18.
   - `placeWindows(boot, stretches)` returns `{ placed, notPlaced, faults }`. Each placed window holds stretch, window, code, startS, endS, and cellStartS, in order of startS.
   - `tremorSpans(placed)` returns the union of the spans of the code 0 windows as sorted `[startS, endS]` pairs, joining spans that overlap or touch.

8. Write viewer/src/lib/load.js. `loadRecording(filePath, { docPath, maxBytes } = {})` reads, parses, and places, and returns a plain object that structured clone can copy: file name, cutShort, counts, and for each boot its id, firmware, reset cause, stretches, timeline arrays, breaks, placed windows, tremor spans, and counts. It throws a RecordingError for no B line and for boots with no reading.

9. Write viewer/src/lib/args.js and viewer/src/lib/pixels.js.
   - `parseArgs(argv, cwd)` returns `{ file, capture, bootId }` and throws an ArgsError for an unknown option, a missing value, a second FILE, or a boot ID that is not a whole number. Relative paths resolve against cwd. main.js passes `process.env.INIT_CWD || process.cwd()` and the arguments after Electron's own, which are `process.argv.slice(2)` for `electron .`.
   - `sampleCells(bitmap, imageWidth, imageHeight, scale, cells, colour, tolerance = 8)` reads the BGRA bitmap that nativeImage.toBitmap() gives at the centre of each cell, where cells are in page pixels and scale is image pixels per page pixel. It returns `{ checked, matched, misses }`.

10. Write viewer/src/main.js and viewer/src/capture.js as in requirements 13, 21, 22, and 23.
    - main.js makes one BrowserWindow of 1400 by 860 with the web preferences of requirement 22 and the preload script, and loads src/renderer/index.html with loadFile(). It sets a menu with the standard app and edit menus and File > Open (Cmd+O). It denies window.open, will-navigate, and every permission request. It handles `viewer:open` with dialog.showOpenDialog() filtered to `.gz` and `.txt`, and it sends each result on `viewer:recording` as `{ ok: true, recording }` or `{ ok: false, file, message }`. It checks that each message comes from its own page before it answers.
    - With `--capture`, capture.js waits for `viewer:drawn`, calls webContents.capturePage(), writes the PNG and the JSON of requirement 23, and exits with its code. Try a hidden window with `paintWhenInitiallyHidden` first. If capturePage() gives an empty image on macOS, show the window instead and say so in the implement report.
    - A bad argument prints the usage line `npm --prefix viewer start -- [FILE] [--boot ID] [--capture OUT.png]` and exits with code 2.

11. Write viewer/src/preload.js. It exposes `window.viewer` with openFile(), onRecording(callback), and reportDrawn(report) through contextBridge and nothing else.

12. Write viewer/src/renderer/index.html, viewer.css, plot.js, and viewer.js as in requirements 19 and 20.
    - index.html holds the CSP meta tag of requirement 22 and loads `../../node_modules/uplot/dist/uPlot.min.css`, `../../node_modules/uplot/dist/uPlot.iife.min.js`, plot.js, and viewer.js as classic scripts.
    - plot.js makes the uPlot chart with x as seconds since boot, shown as h:mm:ss, and the three series. It passes the typed arrays as they are. A series `gaps` hook adds a gap at each break in view, so no null values are needed. If the hook cannot do this, build plain arrays with one null at each break instead and say so in the implement report. A `drawClear` hook shades the tremor spans, and a `draw` hook draws the answer lane. It also handles the arrow keys and the double click.
    - viewer.js shows the summary, the legend, the boot list, the Open button, and the message for a bad file. After the first draw it calls reportDrawn() with the boot, the number of readings, the windows of each code, the tremor cells in page pixels, and the draw time.

13. Write viewer/test/helpers/synthetic.js and viewer/scripts/make_synthetic.js as in requirement 25 and the recording that check 1 of validation.md describes, and commit viewer/test/fixtures/synthetic.txt.gz. The generator takes no clock time and no random seed from outside, so it gives the same text each run. make_synthetic.js writes gzip with mtime 0.

14. Write the unit tests in viewer/test/ with the cases of check 1 in validation.md: format.test.js, read_text.test.js, parse.test.js, timeline.test.js, windows.test.js, args.test.js, pixels.test.js, recordings.test.js, synthetic.test.js, and package.test.js. A test that needs a made-up file writes it to a folder from fs.mkdtempSync() under os.tmpdir().

15. Write viewer/scripts/smoke.js with the cases of check 2 in validation.md. It finds the Electron binary with `require('electron')`, runs the app in capture mode on each case with a 90 second limit, reads each JSON, prints one line per case, and exits with code 1 when a case fails. It keeps the PNG and JSON files in the folder given by `--out DIR`, or in a new temporary folder that it names.

16. Change the Makefile, the CI workflow, and the docs as in requirements 26 and 27.
    - The Makefile gains `viewer:` with `node --test viewer/test/*.test.js`, `check` becomes `laptop hash viewer firmware`, and the comment at the top describes the new target.
    - .github/workflows/check.yml gains a viewer job on ubuntu-24.04 with actions/checkout@v4, actions/setup-node@v4 with node-version "22.22.1", and `make viewer`.
    - specs/tech-stack.md gains a Recording viewer section with the versions, the folder, the modules, and the commands, adds the viewer to `make check` under Tests and checks, and adds Electron and uPlot with their MIT licences under Licences and credits.
    - README.md gains a short section on viewing a recording with the install and start commands.

17. Run `make viewer`, `npm --prefix viewer run smoke -- --out SCRATCH/smoke`, and `make check`, fix the failures, and look at the PNG files.

## Changes during implement

1. Check 1 case 9 gave the expected time as 823178 × 1e6 / 114330200 / 1e6, which is 0.0072 seconds, while the same case says about 7200.0049 seconds. The case now reads 823178 × 1e12 / 114330200 / 1e6, which is the time in microseconds over 1e6. The code did not change.
2. Check 2 case 33 expected 823174 readings. The bursts whose first reading lies before 7200 seconds are bursts 0 to 74834, because burst 74834 starts at reading 823174, which is 7199.97 seconds. That gives 74835 bursts and 823185 readings, so the case now says 823185. The 204 tremor windows and windows 1 to 7195 were right.
3. The hidden window gave a full image with capturePage() on this Mac, so the fallback that shows the window did not run. OUT.json says so in shownWindow. The fallback stays in capture.js for a Mac that gives an empty image.
4. uPlot took the typed arrays as they are, and its series gaps hook breaks the lines, so no plain arrays with nulls were needed. uPlot loads from viewer/node_modules with loadFile() under the page's policy.
5. The parser's counts hold lines, bad, and droppedBursts, and no noB. load.js finds a file with no B line from its empty boot list, and its message gives the number of lines read.
6. The viewer:recording message for a good file also carries bootId, the boot that `--boot` names, so the page can start on it. A `--boot` ID that the file does not hold gives the page's message and exit code 1 in capture mode, and the message lists the file's boots.
7. ArgsError lives in viewer/src/lib/errors.js beside RecordingError. `--capture` with no FILE is an ArgsError, because nothing could be drawn. A failure of the app outside these paths exits with code 2, because the page was never drawn.
8. A boot with no readings shows "This boot holds no readings" in place of the plot. load.js throws only when no boot of the file has a reading.
9. sampleCells() checks only cells at least 3 page pixels wide, as requirement 23 says, so its checked count leaves narrower cells out. The two hour recording's cells are under 1 pixel wide, so its pixel check has 0 cells.
10. The page measures drawMs from the moment the recording arrives to two animation frames after the first draw, so the time counts the frame that reaches the screen. OUT.json also gives totalMs, which runs from the start of the load in the main process to the page's report.
11. The tests use three small helpers that the plan did not name: viewer/test/helpers/paths.js for the repo paths, temp.js for the temporary folder, and readings.js, which turns a timeline index back into its reading number so the tests can name each break by reading.
12. The smoke script runs the bad file and the missing file of case 31 as one case with two captures, so it prints 7 cases as validation.md expects.
13. npm audit reports advisory GHSA-jr5w-w6x2-84p9 for Electron 44.0.0 to 44.9.0, about trusting compromised eMudhra certificates, with a fix in 44.10.0. The viewer loads no remote content, so it does not reach the advisory's case, and the version stays at the 44.7.1 that requirement 12 and case 25 pin. The user decides whether to move to 44.10.0.
14. THIRD_PARTY.md and the Status section of README.md were not changed, because the plan does not name them. The replan stage can add Electron and uPlot to THIRD_PARTY.md and mark feature 12 as built in README.md.
15. viewer/package.json also gives a one-line description and the MIT licence of the project, so npm does not warn about them.
