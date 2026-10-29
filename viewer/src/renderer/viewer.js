'use strict';

// The page: the Open and Record buttons, the record status, the boot list,
// the chips, the layout and time span controls, the Earlier button, the
// summary, and the notices. TremorPlot in plot.js draws the charts.

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
    bootPicker: $('boot-picker'),
    boot: $('boot'),
    cutShort: $('cut-short'),
    bootView: $('boot-view'),
    chartCard: $('chart-card'),
    chips: [...document.querySelectorAll('#chips .md-chip')],
    layout: $('layout'),
    layoutOptions: [...document.querySelectorAll('#layout .md-seg-opt')],
    span: $('span'),
    spanOptions: [...document.querySelectorAll('#span .md-seg-opt')],
    earlier: $('earlier'),
    chartBody: $('chart-body'),
    plots: $('plots'),
    timeLine: $('time-line'),
    timeLabels: $('time-labels'),
    noReadings: $('no-readings'),
    readout: $('readout'),
    summary: $('summary'),
    factsRecording: $('facts-recording'),
    factsQuality: $('facts-quality'),
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
  let layout = 'overlaid';
  let shown = [...C.AXES];
  let palette = TremorTheme.palette();
  let startedAt = 0;
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
    els.timeLabels.replaceChildren();
    els.readout.hidden = true;
  }

  function showMessage(text) {
    recording = null;
    boot = null;
    showCount++;
    clearCharts();
    for (const el of [els.bootPicker, els.cutShort, els.bootView, els.chartCard, els.summary, els.empty]) {
      show(el, false);
    }
    els.messageText.textContent = text;
    show(els.message, true);
  }

  // One fact of the summary, as a dt and a dd. look is 'mono' for an
  // identifier, or 'quiet' for a count of zero.
  function fact(label, value, look = null) {
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = label;
    dd.textContent = value;
    if (look !== null) {
      dd.classList.add(`fact-${look}`);
    }
    return [dt, dd];
  }

  // A count of the data quality group, quiet when it is zero.
  function issue(label, n) {
    return fact(label, count(n), n === 0 ? 'quiet' : null);
  }

  // The file name sits on its own line under its label, and a name too long
  // for the card ends in an ellipsis. The tooltip gives the whole name.
  function fileFact(name) {
    const [dt, dd] = fact('File', name, 'mono');
    dd.classList.add('fact-file');
    dd.title = name;
    return [dt, dd];
  }

  function showSummary(b) {
    els.factsRecording.replaceChildren(
      ...fileFact(recording.fileName),
      ...fact('Boot', String(b.id), 'mono'),
      ...fact('Firmware', String(b.firmware)),
      ...fact('Reset cause', String(b.resetCause)),
      ...fact('Readings', count(b.counts.readings)),
    );
    els.factsQuality.replaceChildren(
      ...issue('Sensor faults', b.counts.faults),
      ...issue('Bad lines in the file', recording.counts.bad),
      ...issue('Dropped bursts in the file', recording.counts.droppedBursts),
      ...issue('Readings with no stretch', b.counts.noStretchReadings),
      ...issue('Windows not placed', b.counts.notPlaced),
    );
    show(els.summary, true);
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
    for (const el of [...els.chips, ...els.layoutOptions, ...els.spanOptions]) {
      el.disabled = !on;
    }
    if (!on) {
      els.earlier.disabled = true;
    }
  }

  // The option of the time span control that the view matches: All when the
  // view shows the whole boot, else the option of the view's width, else
  // none, as after a drag to another width.
  function spanOf(view, bounds) {
    const near = (a, b) => Math.abs(a - b) < 1e-6;
    if (near(view.min, bounds.min) && near(view.max, bounds.max)) {
      return 'all';
    }
    const width = view.max - view.min;
    const option = els.spanOptions.find((o) => o.dataset.span !== 'all' && near(Number(o.dataset.span), width));
    return option === undefined ? null : option.dataset.span;
  }

  // Mark the time span option of the view and turn the Earlier button off at
  // the start of the boot. An option as long as the boot or longer would
  // only show what All shows, so it is off. With no option marked, the first
  // one takes the keyboard focus.
  function showSpan() {
    if (plot === null) {
      return;
    }
    const view = plot.view();
    const bounds = plot.bounds();
    const on = spanOf(view, bounds);
    els.spanOptions.forEach((option, i) => {
      const selected = option.dataset.span === on;
      option.classList.toggle('md-seg-on', selected);
      option.setAttribute('aria-checked', selected ? 'true' : 'false');
      option.tabIndex = selected || (on === null && i === 0) ? 0 : -1;
      option.disabled = option.dataset.span !== 'all' && Number(option.dataset.span) >= bounds.max - bounds.min;
    });
    els.earlier.disabled = view.min <= bounds.min + 1e-6;
  }

  // Show the given span, centred where the view's centre is, inside the boot.
  function setSpan(span) {
    if (plot === null) {
      return;
    }
    const bounds = plot.bounds();
    if (span === 'all') {
      plot.setView(bounds);
      return;
    }
    const view = plot.view();
    const width = Number(span);
    plot.setView(C.clampView((view.min + view.max) / 2 - width / 2, width, bounds));
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
    drawTimeLabels();
    showSpan();
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

  function bootReport(b) {
    return {
      ok: true,
      bootId: b.id,
      readings: b.counts.readings,
      stretches: b.stretches.map(({ number, first, rateUhz, estimated }) => ({ number, first, rateUhz, estimated })),
      windowsByCode: b.counts.windowsByCode,
      drawMs: performance.now() - startedAt,
      recordStatus: els.recordText.textContent,
      theme: document.documentElement.dataset.theme,
      layout,
      shownAxes: [...shown],
      plotHeights: plot === null ? [] : plot.plotHeights(),
      fontsLoaded: fontsLoaded(),
      span: plot === null ? null : spanOf(plot.view(), plot.bounds()),
      spansOff: els.spanOptions.filter((o) => o.disabled).map((o) => o.dataset.span),
      tremorBands: plot === null ? [] : plot.bands(),
      ...lineReport(),
    };
  }

  // Where the charts put the view and the tremor lines they drew, in page pixels.
  function lineReport() {
    if (plot === null) {
      return { view: null, plotEdges: null, tremorLines: [], yRanges: null, yTicks: null };
    }
    return {
      view: plot.view(),
      plotEdges: plot.plotEdges(),
      tremorLines: plot.tremorLines(),
      yRanges: plot.yRanges(),
      yTicks: plot.yTicks(),
    };
  }

  async function showBoot(b) {
    const mine = ++showCount;
    clearCharts();
    boot = b;
    show(els.message, false);
    show(els.empty, false);
    show(els.bootView, true);
    show(els.chartCard, true);
    showSummary(b);
    showChips();
    showLayout();
    const hasReadings = b.counts.readings > 0;
    enableControls(hasReadings);
    for (const el of [els.plots, els.timeLine]) {
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
        report(() => bootReport(b));
      },
    });
    onView();
  }

  function showRecording(next, bootId) {
    recording = next;
    const b =
      recording.boots.find((x) => x.id === bootId) || recording.boots.find((x) => x.counts.readings > 0);
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
  for (const option of els.spanOptions) {
    option.addEventListener('click', () => setSpan(option.dataset.span));
  }
  els.earlier.addEventListener('click', () => {
    if (plot !== null) {
      plot.setView(C.panView(plot.view(), plot.bounds(), -1));
    }
  });

  // The keys of the design system's SegmentedControl. current gives the
  // index of the chosen option, and choose takes the option to choose. The
  // arrow keys pass over an option that is off.
  function segmentKeys(group, options, current, choose) {
    group.addEventListener('keydown', (event) => {
      let next = segmentStep(options, current(), event.key);
      // Home and End go on inwards from an end that is off.
      const onward = { Home: 'ArrowRight', End: 'ArrowLeft' }[event.key] ?? event.key;
      for (let tries = 1; next !== null && options[next].disabled && tries < options.length; tries++) {
        next = segmentStep(options, next, onward);
      }
      if (next === null || options[next].disabled) {
        return;
      }
      event.preventDefault();
      choose(options[next]);
      options[next].focus();
    });
  }

  function segmentStep(options, current, key) {
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
    return next;
  }

  segmentKeys(
    els.layout,
    els.layoutOptions,
    () => Math.max(0, els.layoutOptions.findIndex((o) => o.dataset.layout === layout)),
    (option) => setLayout(option.dataset.layout),
  );
  segmentKeys(
    els.span,
    els.spanOptions,
    () => Math.max(0, els.spanOptions.findIndex((o) => o.classList.contains('md-seg-on'))),
    (option) => setSpan(option.dataset.span),
  );

  /** Give a time in milliseconds as h:mm:ss. */
  function clock(ms) {
    return C.formatClock(Math.max(0, Math.floor(ms / 1000)));
  }

  function showRecordStatus() {
    const { state, startedAt: since, text, ok } = recordStatus;
    // A recording that ended well opens its file, so the line goes. A failure
    // stays until the next press of Record.
    let line = ok === true ? '' : text ?? '';
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
