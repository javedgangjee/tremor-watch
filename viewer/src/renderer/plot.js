'use strict';

// Draws one boot of a recording with uPlot: the gyroscope's three axes, the
// tremor spans shaded behind them, and a lane of answer cells along the
// bottom. The page loads this as a classic script, so it adds one global,
// TremorPlot.

(function () {
  // The Okabe and Ito colours, which people with weak colour vision can tell apart.
  const SERIES = [
    { key: 'gx', name: 'gyroscope x', colour: '#D55E00' },
    { key: 'gy', name: 'gyroscope y', colour: '#009E73' },
    { key: 'gz', name: 'gyroscope z', colour: '#CC79A7' },
  ];

  // The names of res_name() in core/window.c. Tremor is the face's Tremor navy,
  // LOOK_TREMOR in core/look.h, and arm moving is a pale tint of LOOK_ARM.
  const ANSWERS = [
    { code: 0, name: 'tremor', colour: '#1B2E42' },
    { code: 1, name: 'no tremor', colour: '#DDD9D2' },
    { code: 2, name: 'arm moving', colour: '#A8C9B3' },
    { code: 3, name: 'warming up', colour: '#EFECE6' },
  ];
  const ANSWER_COLOURS = new Map(ANSWERS.map((a) => [a.code, a.colour]));
  const TREMOR = 0;
  const SHADE = 'rgba(27, 46, 66, 0.18)';

  const LANE_HEIGHT = 16;
  // Space between the lowest reading and the lane, in page pixels.
  const LANE_GAP = 6;
  const AXIS_COLOUR = '#5C6265';
  const GRID_COLOUR = '#ECE8E1';

  // Steps for the time axis in seconds, so its ticks fall on whole times.
  const TIME_STEPS = [0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200];

  /** Give seconds as h:mm:ss, with decimals when the axis steps by less than a second. */
  function formatTime(seconds, step) {
    const decimals = step < 0.1 ? 2 : step < 1 ? 1 : 0;
    const unit = 10 ** decimals;
    const units = Math.round(Math.abs(seconds) * unit);
    const whole = Math.floor(units / unit);
    const h = Math.floor(whole / 3600);
    const m = Math.floor((whole % 3600) / 60);
    const s = String(whole % 60).padStart(2, '0');
    const part = decimals > 0 ? `.${String(units % unit).padStart(decimals, '0')}` : '';
    return `${seconds < 0 ? '-' : ''}${h}:${String(m).padStart(2, '0')}:${s}${part}`;
  }

  /**
   * Make the plot of one boot in target. onFirstDraw runs once, after the
   * first draw.
   */
  function create(target, boot, onFirstDraw) {
    let drawn = false;

    function canvasX(u, seconds) {
      return Math.round(u.valToPos(seconds, 'x', true));
    }

    // Leave room under the readings for the answer lane.
    function yRange(u, min, max) {
      if (min === null || max === null) {
        return [-1, 1];
      }
      // A flat signal still gets a range of 2 degrees per second.
      const pad = (max - min) * 0.05 || 1;
      const low = min - pad;
      const high = max + pad;
      const heightCss = u.bbox && u.bbox.height > 0 ? u.bbox.height / uPlot.pxRatio : 400;
      const room = LANE_HEIGHT + LANE_GAP;
      return [low - ((high - low) * room) / Math.max(heightCss - room, 1), high];
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

    function shadeTremor(u) {
      const { ctx, bbox } = u;
      const { min, max } = u.scales.x;
      ctx.save();
      ctx.fillStyle = SHADE;
      for (const [start, end] of boot.tremorSpans) {
        if (end > min && start < max) {
          const left = canvasX(u, Math.max(start, min));
          ctx.fillRect(left, bbox.top, canvasX(u, Math.min(end, max)) - left, bbox.height);
        }
      }
      ctx.restore();
    }

    // Tremor cells go last, so they always show where cells overlap.
    function drawLane(u) {
      const { ctx, bbox } = u;
      const { min, max } = u.scales.x;
      const height = LANE_HEIGHT * uPlot.pxRatio;
      const top = bbox.top + bbox.height - height;
      ctx.save();
      for (const tremorPass of [false, true]) {
        for (const w of boot.windows) {
          const colour = ANSWER_COLOURS.get(w.code);
          const cellEnd = w.cellStartS + 1;
          if ((w.code === TREMOR) !== tremorPass || colour === undefined || cellEnd <= min || w.cellStartS >= max) {
            continue;
          }
          const left = canvasX(u, Math.max(w.cellStartS, min));
          ctx.fillStyle = colour;
          ctx.fillRect(left, top, Math.max(1, canvasX(u, Math.min(cellEnd, max)) - left), height);
        }
      }
      ctx.restore();
    }

    function firstDraw() {
      if (!drawn) {
        drawn = true;
        onFirstDraw();
      }
    }

    const axis = { stroke: AXIS_COLOUR, grid: { stroke: GRID_COLOUR, width: 1 }, ticks: { stroke: GRID_COLOUR, width: 1 } };
    const options = {
      width: target.clientWidth,
      height: target.clientHeight,
      legend: { show: false },
      cursor: { drag: { x: true, y: false } },
      scales: { x: { time: false }, y: { range: yRange } },
      axes: [
        {
          ...axis,
          label: 'Time since boot (h:mm:ss)',
          incrs: TIME_STEPS,
          space: 90,
          values: (u, splits, _axisIdx, _space, step) => splits.map((v) => formatTime(v, step)),
        },
        { ...axis, label: 'Gyroscope (degrees per second)', size: 60 },
      ],
      series: [{}, ...SERIES.map((s) => ({ label: s.name, stroke: s.colour, width: 1, gaps: breakGaps }))],
      hooks: { drawClear: [shadeTremor], draw: [drawLane, firstDraw] },
    };
    const u = new uPlot(options, [boot.timeS, boot.gx, boot.gy, boot.gz], target);

    // Move the view by half its width, and stop at the ends of the boot.
    function pan(direction) {
      const xs = u.data[0];
      const first = xs[0];
      const last = xs[xs.length - 1];
      const { min, max } = u.scales.x;
      const width = max - min;
      if (width >= last - first) {
        return;
      }
      const start = Math.min(Math.max(min + (direction * width) / 2, first), last - width);
      u.setScale('x', { min: start, max: start + width });
    }

    function onKey(event) {
      if (event.target instanceof HTMLSelectElement) {
        return;
      }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault();
        pan(event.key === 'ArrowLeft' ? -1 : 1);
      }
    }

    function onResize() {
      u.setSize({ width: target.clientWidth, height: target.clientHeight });
    }

    window.addEventListener('keydown', onKey);
    window.addEventListener('resize', onResize);

    return {
      /** The tremor answer cells in view, in page pixels. */
      tremorCells() {
        const box = u.over.getBoundingClientRect();
        const { min, max } = u.scales.x;
        return boot.windows
          .filter((w) => w.code === TREMOR && w.cellStartS + 1 > min && w.cellStartS < max)
          .map((w) => {
            const left = u.valToPos(Math.max(w.cellStartS, min), 'x');
            const right = u.valToPos(Math.min(w.cellStartS + 1, max), 'x');
            return { x: box.left + left, y: box.bottom - LANE_HEIGHT, width: right - left, height: LANE_HEIGHT };
          });
      },
      destroy() {
        window.removeEventListener('keydown', onKey);
        window.removeEventListener('resize', onResize);
        u.destroy();
      },
    };
  }

  window.TremorPlot = { create, SERIES, ANSWERS, SHADE };
})();
