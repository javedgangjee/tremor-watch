'use strict';

// The page: the Open and Record buttons, the record status, the title block,
// the boot list, the chips and the layout control, the legend, the summary,
// and the notices. TremorPlot in plot.js draws the charts, and TremorAnswers
// in answer_row.js draws the Answer row.

(function () {
  const C = window.TremorChart;
  const $ = (id) => document.getElementById(id);
  const els = {
    open: $('open'),
    record: $('record'),
    recordLabel: $('record-label'),
    recordIcons: { play: $('record-icon-play'), stop: $('record-icon-stop'), loader: $('record-icon-loader') },
    recordStatus: $('record-status'),
    recordStatusIcon: $('record-status-icon'),
    recordText: $('record-text'),
    message: $('message'),
    messageText: $('message-text'),
    empty: $('empty'),
    titleBlock: $('title-block'),
    startText: $('start-text'),
    fileName: $('file-name'),
    bootPicker: $('boot-picker'),
    boot: $('boot'),
    cutShort: $('cut-short'),
    chartCard: $('chart-card'),
    chips: [...document.querySelectorAll('#chips .md-chip')],
    layout: $('layout'),
    layoutOptions: [...document.querySelectorAll('#layout .md-seg-opt')],
    chartBody: $('chart-body'),
    plots: $('plots'),
    answerLine: $('answer-line'),
    answerRow: $('answer-row'),
    answerCanvas: $('answer-canvas'),
    timeLine: $('time-line'),
    timeLabels: $('time-labels'),
    noReadings: $('no-readings'),
    readout: $('readout'),
    counts: [0, 1, 2, 3].map((code) => $(`count-${code}`)),
    selectionText: $('selection-text'),
    summary: $('summary'),
    facts: $('facts'),
  };

  // The faces the canvases draw with, loaded before the first draw so that
  // canvas text never shows in a fallback font.
  const fontsReady = Promise.all(
    ['700 20px "Red Hat Display"', '400 12px "Libre Franklin"', '500 12px "Libre Franklin"', '400 13px "IBM Plex Mono"'].map(
      (font) => document.fonts.load(font),
    ),
  ).catch(() => null);

  let recording = null;
  let boot = null;
  let plot = null;
  let row = null;
  let layout = 'overlaid';
  let shown = [...C.AXES];
  let palette = TremorTheme.palette();
  let startedAt = 0;
  // The window that capture mode selects in the first file's shown boot
  // before it reports, as { stretch, window }, or null.
  let pendingSelect = null;
  // Counts the boots shown, so a boot that waits for the fonts is dropped
  // when another one came after it.
  let showCount = 0;
  // The last status from the recorder, and the timer that counts its time.
  let recordStatus = { state: 'idle', startedAt: null, text: null, ok: null };
  let recordTimer = null;

  const count = (n) => n.toLocaleString('en-GB');
  const show = (el, on) => {
    el.hidden = !on;
  };

  function clearCharts() {
    if (plot !== null) {
      plot.destroy();
      plot = null;
    }
    if (row !== null) {
      row.destroy();
      row = null;
    }
    els.timeLabels.replaceChildren();
    els.selectionText.textContent = '';
    els.readout.hidden = true;
  }

  function showMessage(text) {
    recording = null;
    boot = null;
    showCount++;
    clearCharts();
    for (const el of [els.titleBlock, els.cutShort, els.chartCard, els.summary, els.empty]) {
      show(el, false);
    }
    els.messageText.textContent = text;
    show(els.message, true);
  }

  function fact(label, value, mono = false) {
    const item = document.createElement('div');
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.className = 'field-label';
    dt.textContent = label;
    dd.textContent = value;
    if (mono) {
      dd.classList.add('fact-mono');
    }
    item.append(dt, dd);
    return item;
  }

  function stretchText(s) {
    const rate = (s.rateUhz / 1e6).toFixed(6);
    return `${s.number} from reading ${count(s.first)} at ${rate}/s${s.estimated ? ' (estimated)' : ''}`;
  }

  function showSummary(b) {
    const answers = [0, 1, 2, 3].map((code) => `${count(b.counts.windowsByCode[code])} ${C.answerName(code).toLowerCase()}`);
    els.facts.replaceChildren(
      fact('Boot', String(b.id), true),
      fact('Firmware', String(b.firmware)),
      fact('Reset cause', String(b.resetCause)),
      fact(b.stretches.length === 1 ? 'Stretch' : 'Stretches', b.stretches.map(stretchText).join('; ') || 'none'),
      fact('Readings', count(b.counts.readings)),
      fact('Windows', answers.join(', ')),
      fact('Sensor faults', count(b.counts.faults)),
      fact('Bad lines in the file', count(recording.counts.bad)),
      fact('Dropped bursts in the file', count(recording.counts.droppedBursts)),
      fact('Readings with no stretch', count(b.counts.noStretchReadings)),
      fact('Windows not placed', count(b.counts.notPlaced)),
    );
    show(els.summary, true);
  }

  function showLegend(b) {
    els.counts.forEach((el, code) => {
      el.textContent = count(b.counts.windowsByCode[code]);
    });
  }

  function fillBootList(boots, selected) {
    els.boot.replaceChildren(
      ...boots.map((b, i) => {
        const option = document.createElement('option');
        option.value = String(i);
        option.textContent = `${b.id} (${count(b.counts.readings)} readings)`;
        return option;
      }),
    );
    els.boot.value = String(boots.indexOf(selected));
    show(els.bootPicker, boots.length > 1);
  }

  function showChips() {
    for (const chip of els.chips) {
      const on = shown.includes(chip.dataset.axis);
      chip.classList.toggle('md-chip-on', on);
      chip.setAttribute('aria-pressed', on ? 'true' : 'false');
      chip.querySelector('.chip-check').toggleAttribute('hidden', !on);
    }
  }

  function showLayout() {
    for (const option of els.layoutOptions) {
      const on = option.dataset.layout === layout;
      option.classList.toggle('md-seg-on', on);
      option.setAttribute('aria-checked', on ? 'true' : 'false');
      option.tabIndex = on ? 0 : -1;
    }
  }

  function enableControls(on) {
    for (const el of [...els.chips, ...els.layoutOptions]) {
      el.disabled = !on;
    }
  }

  function drawTimeLabels() {
    if (plot === null) {
      return;
    }
    const view = plot.view();
    const width = els.timeLabels.clientWidth;
    const { ticks } = C.timeTicks(view.min, view.max, width);
    els.timeLabels.replaceChildren(
      ...ticks.map((tick) => {
        const label = document.createElement('span');
        label.className = 'time-label';
        label.textContent = tick.label;
        label.style.left = `${C.xAt(tick.value, view, width)}px`;
        return label;
      }),
    );
  }

  function onView() {
    if (row !== null) {
      row.draw();
    }
    drawTimeLabels();
  }

  // Two frames make sure the drawing has reached the screen before the report,
  // which a capture waits for. The fields are made then, so drawMs counts the
  // time to the screen.
  function report(makeFields) {
    requestAnimationFrame(() => requestAnimationFrame(() => window.viewer.reportDrawn(makeFields())));
  }

  function fontsLoaded() {
    const families = new Set();
    for (const face of document.fonts) {
      if (face.status === 'loaded') {
        families.add(face.family.replace(/["']/g, ''));
      }
    }
    return [...families];
  }

  function rowAlignPx() {
    if (plot === null || row === null) {
      return null;
    }
    const a = plot.firstPlotEdges();
    const b = row.edges();
    return Math.max(Math.abs(a.left - b.left), Math.abs(a.right - b.right));
  }

  function selectionReport() {
    const w = row === null ? null : row.selection();
    return w === null ? null : { stretch: w.stretch, window: w.window, code: w.code };
  }

  function bootReport(b) {
    return {
      ok: true,
      bootId: b.id,
      readings: b.counts.readings,
      stretches: b.stretches.map(({ number, first, rateUhz, estimated }) => ({ number, first, rateUhz, estimated })),
      windowsByCode: b.counts.windowsByCode,
      tremorCells: row === null ? [] : row.tremorBlocks(),
      drawMs: performance.now() - startedAt,
      recordStatus: els.recordText.textContent,
      theme: document.documentElement.dataset.theme,
      layout,
      shownAxes: [...shown],
      plotHeights: plot === null ? [] : plot.plotHeights(),
      fontsLoaded: fontsLoaded(),
      startText: recording.startText,
      selection: selectionReport(),
      rowAlignPx: rowAlignPx(),
      ...lineReport(),
    };
  }

  // Where the charts put the view and the lines they drew, in page pixels.
  function lineReport() {
    if (plot === null) {
      return { view: null, plotEdges: null, tremorLines: [], selectionLines: [], yRanges: null, yTicks: null };
    }
    const lines = plot.lines();
    return {
      view: plot.view(),
      plotEdges: plot.plotEdges(),
      tremorLines: lines.map((l) => l.tremor),
      selectionLines: lines.map((l) => l.selection),
      yRanges: plot.yRanges(),
      yTicks: plot.yTicks(),
    };
  }

  // Select the window that capture mode asked for, when this boot holds it.
  function selectWanted(b, wanted) {
    if (wanted === null || row === null) {
      return;
    }
    const w = b.windows.find((x) => x.stretch === wanted.stretch && x.window === wanted.window);
    if (w !== undefined) {
      row.select(w);
    }
  }

  async function showBoot(b) {
    const mine = ++showCount;
    // Only the first boot shown of the first file takes the capture's selection.
    const wanted = pendingSelect;
    pendingSelect = null;
    clearCharts();
    boot = b;
    show(els.message, false);
    show(els.empty, false);
    show(els.chartCard, true);
    showSummary(b);
    showLegend(b);
    showChips();
    showLayout();
    const hasReadings = b.counts.readings > 0;
    enableControls(hasReadings);
    for (const el of [els.plots, els.answerLine, els.timeLine]) {
      show(el, hasReadings);
    }
    show(els.noReadings, !hasReadings);
    await fontsReady;
    if (mine !== showCount) {
      return;
    }
    if (!hasReadings) {
      report(() => bootReport(b));
      return;
    }
    plot = TremorPlot.create(els.chartBody, b, {
      layout,
      shown,
      palette,
      onView,
      onFirstDraw: () => {
        onView();
        // uPlot calls this from inside its draw, where a redraw would be
        // dropped, so the selection waits for the draw to end. The report
        // waits two frames, so the charts have drawn the selection by then.
        queueMicrotask(() => selectWanted(b, wanted));
        report(() => bootReport(b));
      },
    });
    row = TremorAnswers.create(els.answerRow, els.answerCanvas, els.selectionText, b, {
      palette,
      getView: () => plot.view(),
      onSelect: (w) => plot.setSelection(w),
      onShowSpan: (view) => plot.setView(view),
    });
    onView();
  }

  function showRecording(next, bootId) {
    recording = next;
    const b =
      recording.boots.find((x) => x.id === bootId) || recording.boots.find((x) => x.counts.readings > 0);
    show(els.titleBlock, true);
    els.startText.textContent = recording.startText ?? '';
    show(els.startText, recording.startText !== null);
    els.fileName.textContent = recording.fileName;
    show(els.cutShort, recording.cutShort);
    fillBootList(recording.boots, b);
    showBoot(b);
  }

  window.viewer.onRecording((message) => {
    startedAt = performance.now();
    if (message.ok) {
      if (message.layout === 'overlaid' || message.layout === 'stacked') {
        layout = message.layout;
      }
      pendingSelect = message.select ?? null;
      showRecording(message.recording, message.bootId);
    } else {
      showMessage(message.message);
      report(() => ({
        ok: false,
        message: message.message,
        recordStatus: els.recordText.textContent,
        theme: document.documentElement.dataset.theme,
      }));
    }
  });

  TremorTheme.onChange(() => {
    palette = TremorTheme.palette();
    if (plot !== null) {
      plot.rebuild(palette);
      row.setPalette(palette);
      drawTimeLabels();
    }
  });

  for (const chip of els.chips) {
    chip.addEventListener('click', () => {
      shown = C.toggleAxis(shown, chip.dataset.axis);
      showChips();
      if (plot !== null) {
        plot.setShown(shown);
      }
    });
  }

  function setLayout(next) {
    if (next === layout) {
      return;
    }
    layout = next;
    showLayout();
    if (plot !== null) {
      plot.setLayout(layout);
      onView();
    }
  }

  for (const option of els.layoutOptions) {
    option.addEventListener('click', () => setLayout(option.dataset.layout));
  }

  // The keys of the design system's SegmentedControl.
  els.layout.addEventListener('keydown', (event) => {
    const options = els.layoutOptions;
    const current = Math.max(0, options.findIndex((o) => o.dataset.layout === layout));
    const key = event.key;
    let next = null;
    if (key === 'ArrowRight' || key === 'ArrowDown') {
      next = (current + 1) % options.length;
    } else if (key === 'ArrowLeft' || key === 'ArrowUp') {
      next = (current - 1 + options.length) % options.length;
    } else if (key === 'Home') {
      next = 0;
    } else if (key === 'End') {
      next = options.length - 1;
    }
    if (next === null || options[next].disabled) {
      return;
    }
    event.preventDefault();
    setLayout(options[next].dataset.layout);
    options[next].focus();
  });

  /** Give a time in milliseconds as h:mm:ss. */
  function clock(ms) {
    return C.formatClock(Math.max(0, Math.floor(ms / 1000)));
  }

  function showRecordStatus() {
    const { state, startedAt: since, text, ok } = recordStatus;
    let line = text ?? '';
    if (state !== 'idle') {
      const label = state === 'recording' ? 'Recording' : 'Stopping';
      line = `${label} ${since === null ? '' : clock(Date.now() - since)}.${text ? ` ${text}` : ''}`;
    }
    const failed = ok === false;
    els.recordText.textContent = line;
    els.recordStatus.className = failed ? 'md-notice md-notice-danger' : 'record-status';
    els.recordStatus.setAttribute('role', failed ? 'alert' : 'status');
    els.recordStatusIcon.toggleAttribute('hidden', !failed);
    show(els.recordStatus, line !== '');
  }

  const BUTTON = {
    idle: { text: 'Record', icon: 'play' },
    recording: { text: 'Stop', icon: 'stop' },
    stopping: { text: 'Stopping', icon: 'loader' },
  };

  window.viewer.onRecordStatus((status) => {
    recordStatus = status;
    const look = BUTTON[status.state];
    els.recordLabel.textContent = look.text;
    for (const [name, icon] of Object.entries(els.recordIcons)) {
      icon.toggleAttribute('hidden', name !== look.icon);
    }
    els.record.disabled = status.state === 'stopping';
    if (status.state === 'idle') {
      clearInterval(recordTimer);
      recordTimer = null;
    } else if (recordTimer === null) {
      recordTimer = setInterval(showRecordStatus, 1000);
    }
    showRecordStatus();
  });

  els.open.addEventListener('click', () => window.viewer.openFile());
  els.record.addEventListener('click', () => {
    if (recordStatus.state === 'recording') {
      window.viewer.stopRecording();
    } else if (recordStatus.state === 'idle') {
      // A failure message stays until the next press of Record.
      recordStatus = { state: 'idle', startedAt: null, text: null, ok: null };
      showRecordStatus();
      window.viewer.startRecording();
    }
  });
  els.boot.addEventListener('change', () => {
    startedAt = performance.now();
    showBoot(recording.boots[Number(els.boot.value)]);
  });
})();
