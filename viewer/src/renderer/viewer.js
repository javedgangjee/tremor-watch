'use strict';

// The page: the Open and Record buttons, the record status, the boot list,
// the summary, the legend, and the message for a file that cannot be shown.
// TremorPlot in plot.js draws.

(function () {
  const $ = (id) => document.getElementById(id);
  const els = {
    open: $('open'),
    record: $('record'),
    recordStatus: $('record-status'),
    bootPicker: $('boot-picker'),
    boot: $('boot'),
    fileName: $('file-name'),
    cutShort: $('cut-short'),
    summary: $('summary'),
    legend: $('legend'),
    plot: $('plot'),
    empty: $('empty'),
    message: $('message'),
    messageText: $('message-text'),
  };

  let recording = null;
  let plot = null;
  let startedAt = 0;
  // The last status from the recorder, and the timer that counts its time.
  let recordStatus = { state: 'idle', startedAt: null, text: null, ok: null };
  let recordTimer = null;

  const count = (n) => n.toLocaleString('en-GB');

  function clearPlot() {
    if (plot !== null) {
      plot.destroy();
      plot = null;
    }
    els.plot.replaceChildren();
  }

  function showMessage(text) {
    recording = null;
    clearPlot();
    for (const el of [els.bootPicker, els.cutShort, els.summary, els.legend, els.empty]) {
      el.hidden = true;
    }
    els.fileName.textContent = '';
    els.messageText.textContent = text;
    els.message.hidden = false;
  }

  function fact(label, value) {
    const row = document.createElement('div');
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = label;
    dd.textContent = value;
    row.append(dt, dd);
    return row;
  }

  function stretchText(s) {
    const rate = (s.rateUhz / 1e6).toFixed(6);
    return `${s.number} from reading ${count(s.first)} at ${rate}/s${s.estimated ? ' (estimated)' : ''}`;
  }

  function showSummary(boot) {
    const answers = TremorPlot.ANSWERS.map((a) => `${count(boot.counts.windowsByCode[a.code])} ${a.name}`);
    els.summary.replaceChildren(
      fact('Boot', String(boot.id)),
      fact('Firmware', String(boot.firmware)),
      fact('Reset cause', String(boot.resetCause)),
      fact(boot.stretches.length === 1 ? 'Stretch' : 'Stretches', boot.stretches.map(stretchText).join('; ') || 'none'),
      fact('Readings', count(boot.counts.readings)),
      fact('Windows', answers.join(', ')),
      fact('Sensor faults', count(boot.counts.faults)),
      fact('Bad lines', count(recording.counts.bad)),
      fact('Dropped bursts', count(recording.counts.droppedBursts)),
      fact('Readings with no stretch', count(boot.counts.noStretchReadings)),
      fact('Windows not placed', count(boot.counts.notPlaced)),
    );
    els.summary.hidden = false;
  }

  function swatch(colour, isLine) {
    const el = document.createElement('span');
    el.className = isLine ? 'swatch line' : 'swatch';
    el.style.background = colour;
    return el;
  }

  function legendItem(colour, isLine, text) {
    const li = document.createElement('li');
    li.append(swatch(colour, isLine), text);
    return li;
  }

  function showLegend() {
    els.legend.replaceChildren(
      ...TremorPlot.SERIES.map((s) => legendItem(s.colour, true, s.name)),
      legendItem(TremorPlot.SHADE, false, 'tremor window span'),
      ...TremorPlot.ANSWERS.map((a) => legendItem(a.colour, false, `answer: ${a.name}`)),
    );
    els.legend.hidden = false;
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
    els.bootPicker.hidden = boots.length < 2;
  }

  // Two frames make sure the drawing has reached the screen before the report,
  // which a capture waits for. The fields are made then, so drawMs counts the
  // time to the screen.
  function report(makeFields) {
    requestAnimationFrame(() => requestAnimationFrame(() => window.viewer.reportDrawn(makeFields())));
  }

  function bootReport(boot) {
    return {
      ok: true,
      bootId: boot.id,
      readings: boot.counts.readings,
      stretches: boot.stretches.map(({ number, first, rateUhz, estimated }) => ({ number, first, rateUhz, estimated })),
      windowsByCode: boot.counts.windowsByCode,
      tremorCells: plot === null ? [] : plot.tremorCells(),
      drawMs: performance.now() - startedAt,
      recordStatus: els.recordStatus.textContent,
    };
  }

  function showBoot(boot) {
    clearPlot();
    els.message.hidden = true;
    showSummary(boot);
    showLegend();
    if (boot.counts.readings === 0) {
      els.empty.textContent = 'This boot holds no readings.';
      els.empty.hidden = false;
      report(() => bootReport(boot));
      return;
    }
    els.empty.hidden = true;
    plot = TremorPlot.create(els.plot, boot, () => report(() => bootReport(boot)));
  }

  function showRecording(next, bootId) {
    recording = next;
    const boot =
      recording.boots.find((b) => b.id === bootId) ||
      recording.boots.find((b) => b.counts.readings > 0);
    els.fileName.textContent = recording.fileName;
    els.cutShort.hidden = !recording.cutShort;
    fillBootList(recording.boots, boot);
    showBoot(boot);
  }

  window.viewer.onRecording((message) => {
    startedAt = performance.now();
    if (message.ok) {
      showRecording(message.recording, message.bootId);
    } else {
      showMessage(message.message);
      report(() => ({ ok: false, message: message.message, recordStatus: els.recordStatus.textContent }));
    }
  });

  /** Give a time in milliseconds as h:mm:ss. */
  function clock(ms) {
    const s = Math.max(0, Math.floor(ms / 1000));
    const two = (n) => String(n).padStart(2, '0');
    return `${Math.floor(s / 3600)}:${two(Math.floor(s / 60) % 60)}:${two(s % 60)}`;
  }

  function showRecordStatus() {
    const { state, startedAt: since, text, ok } = recordStatus;
    let line = text ?? '';
    if (state !== 'idle') {
      const label = state === 'recording' ? 'Recording' : 'Stopping';
      line = `${label} ${since === null ? '' : clock(Date.now() - since)}.${text ? ` ${text}` : ''}`;
    }
    els.recordStatus.textContent = line;
    els.recordStatus.hidden = line === '';
    els.recordStatus.classList.toggle('failed', ok === false);
  }

  const BUTTON_TEXT = { idle: 'Record', recording: 'Stop', stopping: 'Stopping' };

  window.viewer.onRecordStatus((status) => {
    recordStatus = status;
    els.record.textContent = BUTTON_TEXT[status.state];
    els.record.disabled = status.state === 'stopping';
    els.record.classList.toggle('recording', status.state !== 'idle');
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
