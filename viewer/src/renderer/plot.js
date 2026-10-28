'use strict';

// Draws the gyroscope readings of one boot with uPlot. Overlaid is one chart
// with the three axes, and Stacked is one chart for each shown axis. All
// charts share one view, the time range on the x axis, and one cursor. The
// page loads this as a classic script, so it adds one global, TremorPlot.

(function () {
  const C = window.TremorChart;

  const READINGS = { x: 'gx', y: 'gy', z: 'gz' };
  const HEIGHT = { overlaid: 420, stacked: 150 };
  // Room above and below the plotting area, so the top and bottom tick labels show whole.
  const PADDING = [8, 0, 8, 0];
  const Y_AXIS_PX = 64;
  const Y_LABEL_GAP_PX = 12;
  const Y_TICK_SPACE_PX = 48;
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
    };
    const last = boot.timeS.length - 1;
    const bounds = { min: boot.timeS[0], max: boot.timeS[last] };
    const state = { layout, shown: [...shown], palette, view: { ...bounds }, selection: null };
    let charts = [];
    let boxes = [];
    let syncing = false;
    let reported = false;
    let width = plotsEl.clientWidth;

    const plotWidth = (u) => u.bbox.width / uPlot.pxRatio;
    const canvasX = (u, seconds) => Math.round(u.valToPos(seconds, 'x', true));

    // A flat signal still gets a range of 2 degrees per second.
    function yRange(_u, min, max) {
      if (min === null || max === null) {
        return [-1, 1];
      }
      const pad = (max - min) * 0.05 || 1;
      return [min - pad, max + pad];
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

    // The two lines of the selected window lie over the readings.
    function drawSelection(u) {
      const w = state.selection;
      if (w === null) {
        return;
      }
      const { ctx, bbox } = u;
      const { min, max } = u.scales.x;
      const lw = lineWidth();
      ctx.save();
      ctx.fillStyle = state.palette.link;
      for (const t of [w.startS, w.endS]) {
        if (t >= min && t <= max) {
          ctx.fillRect(canvasX(u, t) - Math.floor(lw / 2), bbox.top, lw, bbox.height);
        }
      }
      ctx.restore();
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
            space: Y_TICK_SPACE_PX,
            incrs: Y_STEPS,
            font,
            stroke: p.inkMuted,
            values: (_u, splits, _i, _space, step) => splits.map((v) => C.formatValue(v, C.decimalsFor(step))),
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
          drawAxes: [drawZero],
          draw: [drawSelection, onDrawn],
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
          name.textContent = axes[0];
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
      firstPlotEdges() {
        const u = charts[0];
        const box = u.over.getBoundingClientRect();
        return {
          left: box.left + u.valToPos(state.view.min, 'x'),
          right: box.left + u.valToPos(state.view.max, 'x'),
        };
      },
      destroy() {
        window.removeEventListener('keydown', onKey);
        observer.disconnect();
        destroyCharts();
      },
    };
  }

  window.TremorPlot = { create, HEIGHT };
})();
