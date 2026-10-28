# Feature 15 plan: Viewer redesign

The steps run in this order. Every command runs from the repo root with Node v22.22.1 and npm 11.20.0 from nvm. Step 1 needs the network, and npm commands that reach the registry may need the sandbox turned off. The code is plain JavaScript in CommonJS with `'use strict'` and JSDoc types on each exported function, as in features 12 and 14.

No step changes a file in firmware/, core/, reference/, tools/, tests/, or context/, and no step adds a package to viewer/package.json. The files that change outside viewer/ are README.md, THIRD_PARTY.md, and specs/tech-stack.md. Never change a case or a limit in validation.md to make it pass. If a case can pass only that way, stop and report it.

1. Fetch the fonts as in requirement 26.
   - In a new folder in the session's scratch folder, run `npm pack @fontsource-variable/red-hat-display@5.3.0 @fontsource-variable/libre-franklin@5.3.0 @fontsource/ibm-plex-mono@5.3.0` and unpack each tarball into its own new folder with tar. Run no script from the packages.
   - Copy the six files of requirement 26's table into viewer/src/renderer/fonts/ under their committed names, and each package's `package/LICENSE` as OFL-RedHatDisplay.txt, OFL-LibreFranklin.txt, and OFL-IBMPlexMono.txt. Check every SHA-256 with `shasum -a 256` against requirement 26, and stop if one differs.

2. Copy context/viewer-design/colors.css, typography-spacing-fonts.css, and components.css unchanged into viewer/src/renderer/design/. Their `../fonts/` paths then reach the files of step 1.

3. Write viewer/src/lib/chart.js as in requirements 16 to 23 and 34. It wraps its code in a function that sets module.exports when `module` exists and otherwise sets `TremorChart` on the global object, and it requires nothing.
   - `formatValue(value, decimals = 0)` and `decimalsFor(step)` as in requirement 23. `formatClock(seconds, decimals)` gives h:mm:ss with the given decimals and carries a rounded 60 into the next minute. `timeLabel(seconds, step)` is formatClock() with decimalsFor(step).
   - `TIME_STEPS` and `timeTicks(min, max, widthPx)`, which returns `{ step, ticks }`, where each tick is `{ value, label }`. Tick values are whole multiples of the step from the first at or after min to the last at or before max, found with a tolerance of 1e-9 of the step.
   - `xAt(t, view, widthPx)` and `timeAt(x, view, widthPx)`, where view is `{ min, max }`. `blockLayout(window, view, widthPx)` returns `{ x, width, joined }` as in requirement 19, or null when the cell lies outside the view. `JOIN_BELOW_PX = 4` and `GAP_PX = 2`.
   - `answerAt(windows, t)` finds, by binary search on cellStartS, the placed window whose cell `[cellStartS, cellStartS + 1)` holds t, or null. `answerName(code)` gives Tremor, No tremor, Arm moving, or Warming up. `answerText(windows, t)` gives the name or "No answer yet". `windowText(window)` gives the live text of requirement 20.
   - `stepSelection(windows, index, key, view)` gives the new index, or null, for ArrowLeft, ArrowRight, Home, End, and Escape as in requirement 20, and the same index for any other key. `keepInView(view, bounds, start, end)` and `panView(view, bounds, direction)` give a new view, as requirement 20 and feature 12's requirement 20 say. `toggleAxis(shown, axis)` gives the shown axes in the order x, y, z, and keeps the last one.

4. Write viewer/src/lib/title.js as in requirement 28. `dateFromFileName(name)` and `dateFromClockLines(lines)` return `{ year, month, day, hour, minute }` or null, `formatStart(fields)` gives the text, and `startText(fileName, lines)` joins them. The CLOCK ranges are constants with a comment that names the commands table in core/recording_format.md. Change viewer/src/lib/load.js so loadRecording() returns startText beside fileName.

5. Change viewer/src/lib/args.js as in requirement 33. parseArgs() returns `{ file, capture, bootId, recordFor, theme, layout }` and throws an ArgsError for any other theme or layout value. Update USAGE.

6. Change viewer/src/lib/pixels.js and viewer/src/capture.js as in requirement 32. pixels.js exports `INK = { light: '#16181D', dark: '#F4F7FA' }` with a comment that names colors.css. capture.js drops NAVY, checks the tremor blocks against `INK[report.theme]`, and writes theme and tremorColour to OUT.json.

7. Change viewer/src/main.js as in requirements 24 and 33. After app.whenReady() it sets nativeTheme.themeSource to args.theme, and createWindow() takes backgroundColor #16181D when nativeTheme.shouldUseDarkColors is true and #F6F7F9 otherwise. The first openRecording() call for the file named on the command line adds `layout: args.layout` to its message, in capture mode and out of it. The rest of main.js, the preload, and the six calls do not change.

8. Rewrite viewer/src/renderer/index.html as in requirements 3 to 8, 25, 27, 29, and 30.
   - The head holds the policy of requirement 27, the stylesheets design/colors.css, design/typography-spacing-fonts.css, design/components.css, `../../node_modules/uplot/dist/uPlot.min.css`, and viewer.css in that order, and then theme.js.
   - The body holds the sticky header, the record status, the empty card, the error notice, the title block with the boot picker, the cut-short notice, the chart card with its head, body, answer row, time labels, readout, and legend row, and the summary card. It has no style attribute. The icons are inline SVG.
   - At the end it loads `../../node_modules/uplot/dist/uPlot.iife.min.js`, `../lib/chart.js`, plot.js, answer_row.js, and viewer.js as classic scripts.

9. Write viewer/src/renderer/theme.js as in requirement 24. It sets data-theme at once and on each change of the media query. It exposes `TremorTheme.palette()`, which reads the tokens the canvases use, and `TremorTheme.onChange(callback)`.

10. Rewrite viewer/src/renderer/plot.js as in requirements 16 to 18, 21, and 22. `TremorPlot.create(body, boot, { layout, shown, palette, onView, onFirstDraw })` makes the charts and returns an object with `setLayout()`, `setShown()`, `setSelection()`, `setView()`, `view()`, `rebuild(palette)`, `plotHeights()`, `firstPlotEdges()`, and `destroy()`.
    - Each chart uses x as seconds since boot, the series of its axes with strokes from the palette, the gaps hook of feature 12, a y axis of size 64 with formatValue() labels, an x axis that draws only its grid at timeTicks() splits, and padding `[8, 0, 8, 0]`. If uPlot cannot draw the grid with an x axis of size 0, draw the vertical grid lines in a draw hook at the same ticks and say so in the implement report.
    - A draw hook draws the zero line in `--border-strong` and the selection lines in `--link`. A setScale hook passes each new x range to the shared view, which sets it on the other charts once, calls onView(), and so draws the answer row and the time labels again.
    - The cursor syncs through `uPlot.sync('tremor-x')`, with no y line and no points. A setCursor hook fills the readout from cursor.idx with formatClock(), formatValue(), and answerText(), and places it as requirement 7 says.
    - The arrow key handler of feature 12 moves to here and calls panView() on the shared view. It skips events from the boot list, the segmented control, and the answer row.
    - A ResizeObserver on the card body sets each chart's width and draws the row again.

11. Write viewer/src/renderer/answer_row.js as in requirements 6, 19, 20, and 21. `TremorAnswers.create(rowEl, canvas, liveEl, boot, { palette, getView, onSelect, onShowSpan })` draws the blocks with blockLayout() in the order of requirement 19, the selected block's ring, and the row's focus look. It handles click with timeAt() and answerAt(), the keys with stepSelection(), and asks the view to move with keepInView(). It sets the live text with windowText(), and its `tremorBlocks()` gives the tremor blocks in page pixels for the report.

12. Rewrite viewer/src/renderer/viewer.js as in requirements 10, 20, 24, 26, and 29 to 32.
    - It builds the chips and the segmented control with the markup of requirement 25 and passes their changes to the chart. toggleAxis() decides the shown axes.
    - It shows the title block with startText and the file name, the boot picker, the cut-short notice, the legend with each answer's count and the Window span item, the summary card, the empty card, the error notice, and the boot with no readings.
    - The record button and the status keep feature 14's logic. The page swaps the icon and the label in a span, and sets the notice classes and role on a failure.
    - Before the first draw it awaits the document.fonts.load() calls of requirement 26. On a theme change it calls the chart's rebuild() and draws the row again.
    - bootReport() adds the fields of requirement 32, with tremorCells from tremorBlocks() and rowAlignPx from the first chart's edges and the row's edges.

13. Rewrite viewer/src/renderer/viewer.css with the page layout of the design: the sticky header, the 32 px and 24 px page padding, the 20 px gaps, the chart card head and body paddings, the 64 px grids, the answer row and time label rows, the readout card, the legend, the summary grid, the notices' placement, `.u-cursor-x` as a 1 px solid `--ink-secondary` line, and `.u-select` as `color-mix(in srgb, var(--link) 12%, transparent)`. Every colour is a token.

14. Change the tests as in requirement 35 and check 1 of validation.md.
    - Write viewer/test/chart.test.js with cases 1 to 9, viewer/test/title.test.js with cases 10 and 11, and viewer/test/design.test.js with cases 13 and 14. Add case 12 to viewer/test/args.test.js.
    - Change feature 12's case 23 and feature 14's case 13 in args.test.js to expect theme and layout, feature 12's case 24 in pixels.test.js to use INK light, and feature 12's case 26 in package.test.js as requirement 35 says.
    - Name the new tests "case N of feature 15".

15. Change viewer/scripts/smoke.js as in check 2 of validation.md. runApp() adds `--theme light` unless the case's arguments name a theme. Case 27 gains its new checks, case 34 gains its startText check, and cases 15 to 18 are new, named "case N of feature 15". The script then prints 13 cases.

16. Change the docs as in requirement 36.
    - specs/tech-stack.md, Recording viewer section: the design files in viewer/src/renderer/design/, the fonts and their Fontsource 5.3.0 source, the theme and `--theme`, `--layout`, chart.js and title.js among the modules, and the smoke cases. Licences and credits: the three fonts under the SIL Open Font Licence 1.1.
    - README.md, View a recording: the new page, the chips, the layout control, the hover readout, the answer row and its selection lines and keys, the dark theme, and `--theme` and `--layout`. It drops the words on shading the tremor windows and the line under the bar.
    - THIRD_PARTY.md, Kept in this repo: one row for each font with its folder and licence text.

17. Run `make viewer`, `npm --prefix viewer run smoke -- --out SCRATCH/smoke`, and `make check`, fix the failures, and look at the PNG files of check 2. If Chromium refuses the fonts from file URLs under `font-src 'self'`, stop and report it, because any other way to load them changes requirement 27.
