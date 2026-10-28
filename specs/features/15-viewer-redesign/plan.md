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

## Changes during implement

1. The window of 1400 by 860 pixels cuts the page off above the Summary card, which check 2 says the PNG files show. capture.js now makes the window as tall as the page before it saves the PNG, and then waits two frames in the page. Only the height changes, so the report's cells keep their places. This is a change to capture.js that step 6 did not name.
2. uPlot drew the vertical grid with an x axis of size 0, so no draw hook draws it.
3. The zero line is drawn in uPlot's drawAxes hook, so it lies over the grid and under the readings, as in the design. The selection lines are drawn in the draw hook, over the readings.
4. uPlot's own y steps include 2.5, 25, and 250, which decimalsFor() cannot label so that each tick reads its own value. plot.js gives the y axis steps of 1, 2, and 5 times a power of ten, still at least 48 px apart.
5. Each chart has 8 px above and below its plotting area, and the Answer row has 4 px above and below its blocks for the ring. So the chart body's top padding is 12 px, the Answer row moves up 12 px, the time labels move up 4 px, and each stacked chart after the first moves up 4 px. The gaps the eye sees are then the design's 20 px and 12 px.
6. The boot list uses `appearance: none` and the chevron icon from the bundle's ICONS, because the Mac's own select ignores the `.md-input` look. This is one more icon than requirement 25 lists.
7. uPlot's rule for the hover line is `.u-hz .u-cursor-x`, so viewer.css names the same classes to make the line solid in `--ink-secondary`.
8. The report's selection is `{ stretch, window, code }` of the selected window, or null. Its rowAlignPx is null for a boot with no readings, and the report for a file that cannot be shown also gives theme.
9. With no selection and no window that meets requirement 20's rule, the right arrow selects the last window and the left arrow the first. answerName() gives null for a code other than 0 to 3, and answerText() then gives "No answer yet". chart.js also exports MINUS, TIME_STEPS, JOIN_BELOW_PX, GAP_PX, and AXES.
10. timeTicks() adds 0 to each tick value, because Math.ceil() of a small negative number gives -0, which case 3's deepEqual tells apart from 0.
11. Case 11 writes its B line with DET_MODEL_SHA256 for H, as case 18 does. startText() needs only a line that starts with `B,`.
12. TremorPlot.create() also gives bounds(), and TremorAnswers.create() gives draw(), setPalette(), selection(), and edges() beside tremorBlocks(). Cases 33 and 17 make the two hour file through one helper, and case 33 still makes it new on each run.
13. Feature 12's case 27 sometimes saved the page before the plot was drawn. The resize and the two frames of change 1 give the page a new frame before the capture, and the smoke suite then passed 13 of 13 cases in eleven runs in a row. Before, about one run in five failed, so this is strong but not certain evidence that the race is gone. specs/tech-stack.md says so.

## Second implement round

The user found on 2026-10-28 that the first plan read one decision wrong and dropped all tremor marking from the plots. Requirements 8, 11, 16, 21, and 32 to 35 now give the tremor start and end lines, the dashed grey selection lines, and the shared y range of the stacked plots. The steps above and the changes during implement stay as they were. These steps run in this order, with the same rules as the steps above.

1. Change viewer/src/lib/chart.js as in requirements 16, 21, and 34.
   - `edgesInView(spans, view)` takes `[startS, endS]` pairs as tremorSpans() gives them and returns, in time order, every start and end t with `view.min <= t <= view.max`.
   - `paddedRange(min, max)` gives `[-1, 1]` when either is null, and otherwise adds `(max - min) * 0.05`, or 1 when that is 0, below min and above max. This is plot.js's yRange() moved here unchanged.
   - `sharedRange(columns, i0, i1)` gives paddedRange() of the lowest and highest value from index i0 to i1 of every array in columns, and `[-1, 1]` when columns is empty, either index is null, or i1 is less than i0.
   - `LINES = { tremor: { token: 'ink', widthPx: 2, dashPx: [] }, selection: { token: 'borderControl', widthPx: 1, dashPx: [4, 4] } }`, where each token is a key of TremorTheme.palette().

2. Change viewer/src/lib/pixels.js as in requirement 32. Add `BORDER_CONTROL = { light: '#7F8693', dark: '#727A89' }` with a comment that names colors.css. `samplePoints(bitmap, imageWidth, imageHeight, scale, points, colour, tolerance = 8)` checks the image pixel at `floor(x * scale)` and `floor(y * scale)` for each `{ x, y }` in page pixels and gives `{ checked, matched, misses }`, with a point outside the image as a miss whose found is null. `countColumn(bitmap, imageWidth, imageHeight, scale, line, colours, tolerance = 8)` samples the image column `floor((line.x + line.width / 2) * scale)` at the image rows `floor((line.top + k + 0.5) * scale)` for each whole k from 0 while k is less than line.height, and gives `{ sampled, matches }`, where matches holds the count for each colour. sampleCells() keeps its behaviour.

3. Change viewer/src/lib/args.js and viewer/src/main.js as in requirement 33. args.js exports `captureSelect(env)`, which reads env.TREMOR_CAPTURE_SELECT. readArgs() in main.js calls it after parseArgs() when args.capture is set, inside the same try, so an ArgsError exits with code 2 as now. The first openRecording() call for the command line's file adds `select` to its message when it is not null.

4. Change viewer/src/renderer/plot.js as in requirements 16 and 21.
   - Overlaid keeps uPlot's own data range and passes it to C.paddedRange(). In Stacked each chart's y range function returns C.sharedRange() of the readings of every shown axis, from `u.series[0].idxs`, which uPlot 1.6.32 sets for the new x range before it ranges y. The result is kept for the last i0, i1, and shown axes, so the three charts scan the readings once for each view. setShown() in Stacked already makes the charts again, so the range follows the chips.
   - The y tick space is 48 px in Overlaid and 24 px in Stacked. The y values function keeps the labels it gave last on the chart, for yTicks.
   - The draw hook draws the tremor lines at C.edgesInView(boot.tremorSpans, the chart's x range) and then the selection lines, each with its C.LINES style and colour from the palette. A line is `max(1, round(widthPx * uPlot.pxRatio))` device pixels wide, its left edge is the rounded canvas x less half that width, and the dashes of a selection line are filled rectangles of `round(4 * uPlot.pxRatio)` device pixels from bbox.top, so no edge is blurred. drawSelection() no longer uses `--link`.
   - Each chart keeps the lines it drew last in page pixels. The returned object adds `lines()`, which gives one `{ tremor, selection }` for each chart, `plotEdges()`, which gives firstPlotEdges() for every chart, `yRanges()`, and `yTicks()`.

5. Change viewer/src/renderer/index.html and viewer/src/renderer/viewer.css as in requirements 8 and 21. The legend gains `<li><span class="swatch swatch-edge"></span><span>Tremor start and end</span></li>` before the Window span item. `.swatch-edge` has no fill, no radius, and a 2px solid `--ink` border at its left and right, and `.swatch-span` changes to a 1px dashed `--border-control` border at its left and right.

6. Change viewer/src/renderer/answer_row.js and viewer/src/renderer/viewer.js as in requirements 32 and 33.
   - answer_row.js gives `select(window)`, which selects a placed window as a click on its block does, with the live text, onSelect(), and keepInView().
   - When the first file's message holds select, viewer.js looks up that stretch and window among the shown boot's placed windows and calls select() once the row exists. It sends the report only after the charts have drawn with that selection, such as on the next animation frame. A boot opened later starts with no selection, as before.
   - bootReport() adds view, plotEdges, tremorLines and selectionLines from lines(), yRanges, and yTicks. Each is null for a boot with no readings, except tremorLines and selectionLines, which are empty arrays.

7. Change viewer/src/capture.js as in requirement 32. When message.ok is true, OUT.json adds tremorLinePixels from samplePoints() at a quarter, a half, and three quarters of the height of each tremor line of every chart, at `x + width / 2`, against INK of the theme. It adds selectionLinePixels as `{ lines, sampled, lineColour, tremorColour }`, the sums of countColumn() over every selection line of every chart with the colours BORDER_CONTROL and INK of the theme. Both are null when message.ok is false.

8. Change the tests as in check 1 of validation.md. viewer/test/chart.test.js gains cases 19 to 21, viewer/test/pixels.test.js gains case 22, and viewer/test/args.test.js gains case 23. Case 14 in viewer/test/design.test.js also checks BORDER_CONTROL against colors.css and the new legend item in index.html.

9. Change viewer/scripts/smoke.js as in check 2 of validation.md. It requires ../src/lib/load.js and ../src/lib/chart.js to find the episodes and the shared range of boot A. Cases 27, 15, 16, 17, and 18 gain their new checks, and case 24 is new, named "case 24 of feature 15". The script then prints 14 cases.

10. Change the docs as in requirement 36. In README.md, View a recording says that black vertical lines mark where each tremor episode starts and ends in every plot, that the selected window's 4 seconds are marked by two dashed grey lines, and that the stacked plots share one scale. specs/tech-stack.md names TREMOR_CAPTURE_SELECT as a capture test hook and adds the selection lines to the smoke cases.

11. Run `make viewer`, `npm --prefix viewer run smoke -- --out SCRATCH/smoke`, and `make check`, fix the failures, and look at the PNG files of check 2.
