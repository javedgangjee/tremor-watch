'use strict';

// Draws the gyroscope readings of one boot with uPlot. Overlaid is one chart
// with the three axes, and Stacked is one chart for each shown axis. All
// charts share one view, the time range on the x axis, and one cursor. In
// Stacked they also share one y range. Every chart shades each tremor
// episode, marks its start and end with vertical lines, and marks the span
// of the selected window with dashed lines. The page loads this as a classic script, so it adds one
// global, TremorPlot.

(function () {
  const C = window.TremorChart;

  const READINGS = { x: 'gx', y: 'gy', z: 'gz' };
  const HEIGHT = { overlaid: 340, stacked: 120 };
  // Room above and below the plotting area, so the top and bottom tick labels show whole.
  const PADDING = [8, 0, 8, 0];
  const Y_AXIS_PX = 64;
  const Y_LABEL_GAP_PX = 12;
  // The least room between two y ticks, so each 120 px stacked plot shows at least two.
  const Y_TICK_SPACE_PX = { overlaid: 48, stacked: 24 };
  const TIME_TICK_SPACE_PX = 90;
  const SYNC_KEY = 'tremor-x';
  // The readout moves to the left of the pointer past this share of the width.
  const FLIP_AT = 0.6;

  // Steps of 1, 2, and 5 for the y axis, so formatValue() with decimalsFor()
  // gives each tick its own text.
  const Y_STEPS = [];
  for (let power = -2; power <= 5; power++) {
    for (const m of [1, 2, 5]) {
      Y_STEPS.push(Number((m * 10 ** power).toPrecision(1)));
    }
  }

  function axisColour(palette, axis) {
    return { x: palette.warning, y: palette.link, z: palette.success }[axis];
  }

  function listText(axes) {
    if (axes.length < 2) {
      return axes.join('');
    }
    return `${axes.slice(0, -1).join(', ')} and ${axes[axes.length - 1]}`;
  }

  /**
   * Make the charts of one boot in body, the chart card's body. onView runs
   * after each change of the view and of the width, and onFirstDraw runs once,
   * after every chart has drawn for the first time.
   */
  function create(body, boot, { layout, shown, palette, onView, onFirstDraw }) {
    const plotsEl = body.querySelector('.plots');
    const readout = {
      box: body.querySelector('.readout'),
      time: body.querySelector('#readout-time'),
      x: body.querySelector('#readout-x'),
      y: body.querySelector('#readout-y'),
      z: body.querySelector('#readout-z'),
      answer: body.querySelector('#readout-answer'),
      axes: [...body.querySelectorAll('.readout-values [data-axis]')],
    };
    const last = boot.timeS.length - 1;
    const bounds = { min: boot.timeS[0], max: boot.timeS[last] };
    const state = { layout, shown: [...shown], palette, view: { ...bounds }, selection: null };
    let charts = [];
    let boxes = [];
    let syncing = false;
    let reported = false;
    let width = plotsEl.clientWidth;
    // The last shared range of the stacked plots, kept for its first and last
    // reading and its axes, so the plots scan the readings once for each view.
    let shared = { key: null, range: null };

    const plotWidth = (u) => u.bbox.width / uPlot.pxRatio;
    const canvasX = (u, seconds) => Math.round(u.valToPos(seconds, 'x', true));

    // Overlaid fits the shown readings in view. Stacked gives every plot the
    // range of the readings of every shown axis in view. uPlot sets the
    // indexes of the readings in view before it ranges y.
    function yRange(u, min, max) {
      if (state.layout !== 'stacked') {
        return C.paddedRange(min, max);
      }
      const [i0, i1] = u.series[0].idxs;
      const key = `${i0},${i1},${state.shown.join('')}`;
      if (shared.key !== key) {
        shared = { key, range: C.sharedRange(state.shown.map((a) => boot[READINGS[a]]), i0, i1) };
      }
      return [...shared.range];
    }

    // Break the lines at each break in view, so no line joins two stretches
    // or crosses a gap in the readings.
    function breakGaps(u, _seriesIdx, idx0, idx1, nullGaps) {
      const xs = u.data[0];
      const gaps = nullGaps.slice();
      for (const i of boot.breaks) {
        if (i - 1 >= idx0 && i <= idx1) {
          const from = canvasX(u, xs[i - 1]);
          const to = canvasX(u, xs[i]);
          if (to > from) {
            gaps.push([from, to]);
          }
        }
      }
      return gaps.sort((a, b) => a[0] - b[0]);
    }

    function lineWidth() {
      return Math.max(1, Math.round(uPlot.pxRatio));
    }

    // The zero line lies over the grid and under the readings.
    function drawZero(u) {
      const { min, max } = u.scales.y;
      if (!(min <= 0 && max >= 0)) {
        return;
      }
      const { ctx, bbox } = u;
      const w = lineWidth();
      ctx.save();
      ctx.fillStyle = state.palette.borderStrong;
      ctx.fillRect(bbox.left, Math.round(u.valToPos(0, 'y', true) - w / 2), bbox.width, w);
      ctx.restore();
    }

    // Draw one vertical line at each time in view, the full height of the
    // plotting area, with a style of C.LINES. Each line and each dash covers
    // whole device pixels, so its colour is exact. Gives the lines drawn, in
    // canvas pixels.
    function drawLines(u, times, style) {
      const { ctx, bbox } = u;
      const { min, max } = u.scales.x;
      const ratio = uPlot.pxRatio;
      const lw = Math.max(1, Math.round(style.widthPx * ratio));
      const dash = style.dashPx.map((d) => Math.max(1, Math.round(d * ratio)));
      const drawn = [];
      ctx.save();
      ctx.beginPath();
      ctx.rect(bbox.left, bbox.top, bbox.width, bbox.height);
      ctx.clip();
      ctx.fillStyle = state.palette[style.token];
      for (const t of times) {
        if (!(t >= min && t <= max)) {
          continue;
        }
        const left = canvasX(u, t) - Math.floor(lw / 2);
        if (dash.length === 0) {
          ctx.fillRect(left, bbox.top, lw, bbox.height);
        } else {
          for (let y = bbox.top; y < bbox.top + bbox.height; y += dash[0] + dash[1]) {
            ctx.fillRect(left, y, lw, Math.min(dash[0], bbox.top + bbox.height - y));
          }
        }
        const from = Math.max(left, bbox.left);
        const to = Math.min(left + lw, bbox.left + bbox.width);
        drawn.push({ t, left: from, width: to - from, top: bbox.top, height: bbox.height });
      }
      ctx.restore();
      return drawn;
    }

    // The shade of each tremor episode lies under the grid and the readings.
    // uPlot calls this hook after it clears the canvas and before it draws
    // the axes. Gives the shades drawn, in canvas pixels.
    function drawBands(u) {
      const { ctx, bbox } = u;
      const { min, max } = u.scales.x;
      const drawn = [];
      if (min === null || max === null) {
        u.tremorBands = drawn;
        return;
      }
      ctx.save();
      ctx.fillStyle = state.palette.surfaceSunken;
      for (const [start, end] of boot.tremorSpans) {
        if (end <= min || start >= max) {
          continue;
        }
        const left = Math.max(canvasX(u, Math.max(start, min)), bbox.left);
        const right = Math.min(canvasX(u, Math.min(end, max)), bbox.left + bbox.width);
        if (right > left) {
          ctx.fillRect(left, bbox.top, right - left, bbox.height);
          drawn.push({ startS: start, endS: end, left, width: right - left, top: bbox.top, height: bbox.height });
        }
      }
      ctx.restore();
      u.tremorBands = drawn;
    }

    // The tremor lines and then the selection lines lie over the readings.
    function drawMarks(u) {
      const { min, max } = u.scales.x;
      const w = state.selection;
      u.tremorLines = drawLines(u, C.edgesInView(boot.tremorSpans, { min, max }), C.LINES.tremor);
      u.selectionLines = w === null ? [] : drawLines(u, [w.startS, w.endS], C.LINES.selection);
    }

    // The lines a chart drew last, in page pixels.
    function pageLines(u, lines) {
      const rect = u.ctx.canvas.getBoundingClientRect();
      const ratio = uPlot.pxRatio;
      return (lines || []).map((l) => ({
        t: l.t,
        x: rect.left + l.left / ratio,
        width: l.width / ratio,
        top: rect.top + l.top / ratio,
        height: l.height / ratio,
      }));
    }

    function plotEdges(u) {
      const box = u.over.getBoundingClientRect();
      return {
        left: box.left + u.valToPos(state.view.min, 'x'),
        right: box.left + u.valToPos(state.view.max, 'x'),
      };
    }

    function sameView(a, b) {
      return Math.abs(a.min - b.min) < 1e-9 && Math.abs(a.max - b.max) < 1e-9;
    }

    function ariaText(axes) {
      const { min, max } = state.view;
      return `Gyroscope ${listText(axes)} in degrees per second from ${C.formatClock(min)} to ${C.formatClock(max)}`;
    }

    function updateAria() {
      for (const box of boxes) {
        box.setAttribute('aria-label', ariaText(box.axes));
      }
    }

    // Set the view on every chart but one, and tell the page.
    function setViewAll(view, except) {
      state.view = { min: view.min, max: view.max };
      syncing = true;
      for (const u of charts) {
        if (u !== except && !sameView(u.scales.x, state.view)) {
          u.setScale('x', { min: state.view.min, max: state.view.max });
        }
      }
      syncing = false;
      updateAria();
      onView(state.view);
    }

    function onScale(u, key) {
      if (key !== 'x' || syncing) {
        return;
      }
      const view = { min: u.scales.x.min, max: u.scales.x.max };
      if (view.min === null || view.max === null || sameView(view, state.view)) {
        return;
      }
      setViewAll(view, u);
    }

    function hideReadout() {
      readout.box.hidden = true;
    }

    // The readout gives the reading nearest the pointer and the answer at its time.
    function onCursor(u) {
      const { idx, left } = u.cursor;
      if (idx === null || idx === undefined || left === undefined || left < 0) {
        hideReadout();
        return;
      }
      const t = boot.timeS[idx];
      readout.time.textContent = C.formatClock(t, 1);
      readout.x.textContent = C.formatValue(boot.gx[idx]);
      readout.y.textContent = C.formatValue(boot.gy[idx]);
      readout.z.textContent = C.formatValue(boot.gz[idx]);
      for (const el of readout.axes) {
        el.hidden = !state.shown.includes(el.dataset.axis);
      }
      readout.answer.textContent = C.answerText(boot.windows, t);
      const over = u.over.getBoundingClientRect();
      const offset = over.left - body.getBoundingClientRect().left;
      readout.box.style.left = `${offset + left}px`;
      readout.box.classList.toggle('readout-flip', left / over.width > FLIP_AT);
      readout.box.hidden = false;
    }

    function onDrawn(u) {
      u.tremorDrawn = true;
      if (!reported && charts.length > 0 && charts.every((c) => c.tremorDrawn)) {
        reported = true;
        onFirstDraw();
      }
    }

    function options(axes, height) {
      const p = state.palette;
      const space = Y_TICK_SPACE_PX[state.layout === 'stacked' ? 'stacked' : 'overlaid'];
      const font = `12px ${p.fontSans}`;
      return {
        width,
        height,
        padding: PADDING,
        legend: { show: false },
        cursor: {
          sync: { key: SYNC_KEY },
          y: false,
          points: { show: false },
          drag: { x: true, y: false },
        },
        scales: { x: { time: false }, y: { range: yRange } },
        axes: [
          {
            size: 0,
            space: TIME_TICK_SPACE_PX,
            incrs: C.TIME_STEPS,
            splits: (u, _i, min, max) => C.timeTicks(min, max, plotWidth(u)).ticks.map((t) => t.value),
            values: (_u, splits) => splits.map(() => ''),
            ticks: { show: false },
            grid: { stroke: p.border, width: 1 },
            border: { show: false },
          },
          {
            size: Y_AXIS_PX,
            gap: Y_LABEL_GAP_PX,
            space,
            incrs: Y_STEPS,
            font,
            stroke: p.inkMuted,
            values: (u, splits, _i, _space, step) => {
              u.tremorTicks = splits.map((v) => C.formatValue(v, C.decimalsFor(step)));
              return u.tremorTicks;
            },
            ticks: { show: false },
            grid: { stroke: p.border, width: 1 },
            border: { show: false },
          },
        ],
        series: [
          {},
          ...axes.map((a) => ({
            label: a,
            stroke: axisColour(p, a),
            width: 1,
            show: state.shown.includes(a),
            gaps: breakGaps,
            points: { show: false },
          })),
        ],
        hooks: {
          drawClear: [drawBands],
          drawAxes: [drawZero],
          draw: [drawMarks, onDrawn],
          setScale: [onScale],
          setCursor: [onCursor],
        },
      };
    }

    function destroyCharts() {
      for (const u of charts) {
        u.destroy();
      }
      charts = [];
      boxes = [];
      plotsEl.replaceChildren();
      hideReadout();
    }

    function build() {
      destroyCharts();
      shared = { key: null, range: null };
      const stacked = state.layout === 'stacked';
      const groups = stacked ? state.shown.map((a) => [a]) : [C.AXES];
      const made = [];
      for (const axes of groups) {
        const box = document.createElement('div');
        box.className = 'plot';
        box.setAttribute('role', 'img');
        box.axes = stacked ? axes : state.shown;
        if (stacked) {
          const name = document.createElement('span');
          name.className = 'plot-name';
          name.setAttribute('aria-hidden', 'true');
          const line = document.createElement('span');
          line.className = `axis-line axis-line-${axes[0]}`;
          name.append(line, axes[0]);
          box.append(name);
        }
        plotsEl.append(box);
        const data = [boot.timeS, ...axes.map((a) => boot[READINGS[a]])];
        const u = new uPlot(options(axes, stacked ? HEIGHT.stacked : HEIGHT.overlaid), data, box);
        if (!sameView(state.view, bounds)) {
          u.setScale('x', { min: state.view.min, max: state.view.max });
        }
        boxes.push(box);
        made.push(u);
      }
      charts = made;
      updateAria();
    }

    function onKey(event) {
      if (event.key !== 'ArrowLeft' && event.key !== 'ArrowRight') {
        return;
      }
      if (event.defaultPrevented || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      const target = event.target;
      if (target instanceof HTMLSelectElement || (target instanceof Element && target.closest('.md-seg, .answer-row'))) {
        return;
      }
      event.preventDefault();
      setViewAll(C.panView(state.view, bounds, event.key === 'ArrowLeft' ? -1 : 1), null);
    }

    const observer = new ResizeObserver(() => {
      const next = plotsEl.clientWidth;
      if (next === width || next <= 0) {
        return;
      }
      width = next;
      for (const u of charts) {
        u.setSize({ width, height: u.height });
      }
      onView(state.view);
    });

    build();
    window.addEventListener('keydown', onKey);
    observer.observe(body);

    return {
      setLayout(next) {
        if (next !== state.layout) {
          state.layout = next;
          build();
        }
      },
      setShown(next) {
        state.shown = [...next];
        if (state.layout === 'stacked') {
          build();
          return;
        }
        const u = charts[0];
        C.AXES.forEach((a, i) => {
          const show = state.shown.includes(a);
          if (u.series[i + 1].show !== show) {
            u.setSeries(i + 1, { show });
          }
        });
        boxes[0].axes = state.shown;
        updateAria();
      },
      setSelection(w) {
        state.selection = w;
        for (const u of charts) {
          u.redraw(false);
        }
      },
      setView(view) {
        setViewAll(view, null);
      },
      view: () => ({ ...state.view }),
      bounds: () => ({ ...bounds }),
      rebuild(next) {
        state.palette = next;
        build();
      },
      plotHeights: () => charts.map((u) => u.height),
      /** Where the first chart puts the view's start and end, in page pixels. */
      firstPlotEdges: () => plotEdges(charts[0]),
      /** Where each chart puts the view's start and end, in page pixels. */
      plotEdges: () => charts.map(plotEdges),
      /** The tremor and selection lines each chart drew last, in page pixels. */
      lines: () =>
        charts.map((u) => ({ tremor: pageLines(u, u.tremorLines), selection: pageLines(u, u.selectionLines) })),
      /** The tremor shades each chart drew last, in page pixels. */
      bands: () =>
        charts.map((u) => {
          const rect = u.ctx.canvas.getBoundingClientRect();
          const ratio = uPlot.pxRatio;
          return (u.tremorBands || []).map((b) => ({
            startS: b.startS,
            endS: b.endS,
            x: rect.left + b.left / ratio,
            width: b.width / ratio,
            top: rect.top + b.top / ratio,
            height: b.height / ratio,
          }));
        }),
      yRanges: () => charts.map((u) => [u.scales.y.min, u.scales.y.max]),
      yTicks: () => charts.map((u) => [...(u.tremorTicks || [])]),
      destroy() {
        window.removeEventListener('keydown', onKey);
        observer.disconnect();
        destroyCharts();
      },
    };
  }

  window.TremorPlot = { create, HEIGHT };
})();
