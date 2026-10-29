'use strict';

// The pure rules of the viewer's page: number and time text, the time ticks,
// the map from time to x, the answer at a time, the view, the shown axes,
// the tremor lines, and the y ranges. It requires nothing.
// Under Node it sets module.exports, and the page, which loads it as a
// classic script, gets the global TremorChart.

(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module !== null && module.exports) {
    module.exports = api;
  } else {
    root.TremorChart = api;
  }
})(typeof globalThis === 'object' ? globalThis : this, function () {
  // The minus sign U+2212, which reads better than the hyphen in numbers.
  const MINUS = '−';

  // Steps for the time axis in seconds, so its ticks fall on whole times.
  const TIME_STEPS = [
    0.01, 0.02, 0.05, 0.1, 0.2, 0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300, 600, 900, 1800, 3600, 7200, 10800, 21600,
    43200, 86400,
  ];
  // The least room between two time ticks, in CSS pixels.
  const TIME_TICK_SPACE_PX = 90;

  // The answer of each result code, as res_name() in core/window.c names them.
  const ANSWER_NAMES = ['Tremor', 'No tremor', 'Arm moving', 'Warming up'];
  const AXES = ['x', 'y', 'z'];

  /**
   * Give a number with the given decimals, commas between groups of three
   * digits, and the minus sign U+2212 before a negative value. A value that
   * rounds to zero gets no sign.
   *
   * @param {number} value
   * @param {number} [decimals]
   * @returns {string}
   */
  function formatValue(value, decimals = 0) {
    const text = Math.abs(value).toFixed(decimals);
    const [whole, part] = text.split('.');
    const grouped = whole.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
    const sign = value < 0 && Number(text) !== 0 ? MINUS : '';
    return `${sign}${grouped}${part === undefined ? '' : `.${part}`}`;
  }

  /**
   * Give the decimals that tell ticks of the given step apart.
   *
   * @param {number} step
   * @returns {number}
   */
  function decimalsFor(step) {
    if (step >= 1) {
      return 0;
    }
    return step >= 0.1 ? 1 : 2;
  }

  /**
   * Give seconds as h:mm:ss with the given decimals. A second that rounds up
   * to 60 carries into the minute.
   *
   * @param {number} seconds
   * @param {number} [decimals]
   * @returns {string}
   */
  function formatClock(seconds, decimals = 0) {
    const unit = 10 ** decimals;
    const units = Math.round(Math.abs(seconds) * unit);
    const whole = Math.floor(units / unit);
    const h = Math.floor(whole / 3600);
    const m = String(Math.floor((whole % 3600) / 60)).padStart(2, '0');
    const s = String(whole % 60).padStart(2, '0');
    const part = decimals > 0 ? `.${String(units % unit).padStart(decimals, '0')}` : '';
    const sign = seconds < 0 && units > 0 ? MINUS : '';
    return `${sign}${h}:${m}:${s}${part}`;
  }

  /**
   * Give the label of a time tick, with the decimals its step needs.
   *
   * @param {number} seconds
   * @param {number} step
   * @returns {string}
   */
  function timeLabel(seconds, step) {
    return formatClock(seconds, decimalsFor(step));
  }

  /**
   * Give the time ticks from min to max for a width in CSS pixels. The step is
   * the smallest of TIME_STEPS that puts the ticks at least 90 px apart.
   *
   * @param {number} min
   * @param {number} max
   * @param {number} widthPx
   * @returns {{step: number, ticks: {value: number, label: string}[]}}
   */
  function timeTicks(min, max, widthPx) {
    const span = max - min;
    let step = TIME_STEPS[TIME_STEPS.length - 1];
    if (span > 0 && widthPx > 0) {
      const found = TIME_STEPS.find((s) => (s * widthPx) / span >= TIME_TICK_SPACE_PX);
      if (found !== undefined) {
        step = found;
      }
    }
    const ticks = [];
    if (!(span >= 0)) {
      return { step, ticks };
    }
    const first = Math.ceil(min / step - 1e-9);
    const last = Math.floor(max / step + 1e-9);
    for (let k = first; k <= last; k++) {
      // Adding 0 turns the -0 of a first tick at 0 into 0.
      const value = k * step + 0;
      ticks.push({ value, label: timeLabel(value, step) });
    }
    return { step, ticks };
  }

  /**
   * Give the x of a time in a view drawn across widthPx pixels.
   *
   * @param {number} t
   * @param {{min: number, max: number}} view
   * @param {number} widthPx
   * @returns {number}
   */
  function xAt(t, view, widthPx) {
    return ((t - view.min) * widthPx) / (view.max - view.min);
  }

  /**
   * Give the placed window whose cell, from cellStartS for 1 second, holds t,
   * or null. The windows are in order of time.
   *
   * @param {{cellStartS: number}[]} windows
   * @param {number} t
   * @returns {object | null}
   */
  function answerAt(windows, t) {
    let low = 0;
    let high = windows.length - 1;
    let found = -1;
    while (low <= high) {
      const mid = (low + high) >> 1;
      if (windows[mid].cellStartS <= t) {
        found = mid;
        low = mid + 1;
      } else {
        high = mid - 1;
      }
    }
    if (found < 0 || t >= windows[found].cellStartS + 1) {
      return null;
    }
    return windows[found];
  }

  /**
   * Give the name of an answer code, or null for a code with no name.
   *
   * @param {number} code
   * @returns {string | null}
   */
  function answerName(code) {
    return ANSWER_NAMES[code] ?? null;
  }

  /**
   * Give the answer at a time, or "No answer yet" when no cell holds it.
   *
   * @param {{cellStartS: number, code: number}[]} windows
   * @param {number} t
   * @returns {string}
   */
  function answerText(windows, t) {
    const w = answerAt(windows, t);
    return (w === null ? null : answerName(w.code)) ?? 'No answer yet';
  }

  /**
   * Give a view of the given width that starts at min, moved inside the
   * bounds. A width that covers the bounds gives the bounds.
   *
   * @param {number} min
   * @param {number} width
   * @param {{min: number, max: number}} bounds
   * @returns {{min: number, max: number}}
   */
  function clampView(min, width, bounds) {
    if (width >= bounds.max - bounds.min) {
      return { min: bounds.min, max: bounds.max };
    }
    const start = Math.min(Math.max(min, bounds.min), bounds.max - width);
    return { min: start, max: start + width };
  }

  /**
   * Move the view by half its width, left for -1 and right for 1, and stop at
   * the bounds.
   *
   * @param {{min: number, max: number}} view
   * @param {{min: number, max: number}} bounds
   * @param {number} direction
   * @returns {{min: number, max: number}}
   */
  function panView(view, bounds, direction) {
    const width = view.max - view.min;
    if (width >= bounds.max - bounds.min) {
      return { min: view.min, max: view.max };
    }
    return clampView(view.min + (direction * width) / 2, width, bounds);
  }

  /**
   * Show or hide one axis. The result keeps the order x, y, z, and the last
   * shown axis stays.
   *
   * @param {string[]} shown
   * @param {string} axis
   * @returns {string[]}
   */
  function toggleAxis(shown, axis) {
    if (shown.includes(axis)) {
      return shown.length === 1 ? [...shown] : shown.filter((a) => a !== axis);
    }
    return AXES.filter((a) => a === axis || shown.includes(a));
  }

  // How the lines over the plots are drawn. Each token is a key of
  // TremorTheme.palette().
  const LINES = {
    tremor: { token: 'ink', widthPx: 2 },
  };

  /**
   * Give, in order of time, each start and end of the spans that lies in the
   * view, edges included.
   *
   * @param {[number, number][]} spans Sorted [startS, endS] pairs, as tremorSpans() gives them.
   * @param {{min: number, max: number}} view
   * @returns {number[]}
   */
  function edgesInView(spans, view) {
    const edges = [];
    for (const [start, end] of spans) {
      for (const t of [start, end]) {
        if (t >= view.min && t <= view.max) {
          edges.push(t);
        }
      }
    }
    return edges.sort((a, b) => a - b);
  }

  /**
   * Give a y range from the lowest to the highest value with 5 percent of the
   * height added above and below. A flat signal gets 1 above and below, and
   * no values give -1 to 1.
   *
   * @param {number | null} min
   * @param {number | null} max
   * @returns {[number, number]}
   */
  function paddedRange(min, max) {
    if (min === null || max === null) {
      return [-1, 1];
    }
    const pad = (max - min) * 0.05 || 1;
    return [min - pad, max + pad];
  }

  /**
   * Give paddedRange() of the lowest and highest value from index i0 to i1 of
   * every array in columns, so several plots share one scale.
   *
   * @param {ArrayLike<number>[]} columns
   * @param {number | null} i0
   * @param {number | null} i1
   * @returns {[number, number]}
   */
  function sharedRange(columns, i0, i1) {
    if (columns.length === 0 || i0 === null || i1 === null || i1 < i0) {
      return [-1, 1];
    }
    let min = Infinity;
    let max = -Infinity;
    for (const column of columns) {
      for (let i = i0; i <= i1; i++) {
        const v = column[i];
        if (v < min) {
          min = v;
        }
        if (v > max) {
          max = v;
        }
      }
    }
    return min === Infinity ? [-1, 1] : paddedRange(min, max);
  }

  return {
    MINUS,
    TIME_STEPS,
    AXES,
    formatValue,
    decimalsFor,
    formatClock,
    timeLabel,
    timeTicks,
    xAt,
    answerAt,
    answerName,
    answerText,
    clampView,
    panView,
    toggleAxis,
    edgesInView,
    paddedRange,
    sharedRange,
    LINES,
  };
});
