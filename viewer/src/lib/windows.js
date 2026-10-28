'use strict';

// Window n of a stretch holds the 100 Hz samples 100n to 100n + 399, so it
// spans 4 seconds from t0 + n seconds, as core/window.h gives it.
const WINDOW_S = 4;
const TREMOR = 0;

/**
 * Place each W line of a boot on the time axis with the t0 of its stretch.
 *
 * Each placed window spans startS to endS, and its answer cell starts at
 * cellStartS, which is the last second of the span, the second the window
 * added. A W line whose stretch has no S line in the boot is not placed.
 *
 * @param {{windows: Map<string, {stretch: number, window: number, code: number}>, faults: number}} boot
 * @param {{number: number, t0Us: number}[]} stretches
 * @returns {{placed: object[], notPlaced: number, faults: number}}
 */
function placeWindows(boot, stretches) {
  const t0ByStretch = new Map(stretches.map((s) => [s.number, s.t0Us]));
  const placed = [];
  let notPlaced = 0;
  for (const { stretch, window, code } of boot.windows.values()) {
    const t0Us = t0ByStretch.get(stretch);
    if (t0Us === undefined) {
      notPlaced++;
      continue;
    }
    placed.push({
      stretch,
      window,
      code,
      startS: (t0Us + window * 1e6) / 1e6,
      endS: (t0Us + (window + WINDOW_S) * 1e6) / 1e6,
      cellStartS: (t0Us + (window + WINDOW_S - 1) * 1e6) / 1e6,
    });
  }
  placed.sort((a, b) => a.startS - b.startS);
  return { placed, notPlaced, faults: boot.faults };
}

/**
 * Give the union of the spans of the tremor windows as sorted [startS, endS]
 * pairs. Spans that overlap or touch join into one.
 *
 * @param {{code: number, startS: number, endS: number}[]} placed
 * @returns {[number, number][]}
 */
function tremorSpans(placed) {
  const spans = placed
    .filter((w) => w.code === TREMOR)
    .map((w) => [w.startS, w.endS])
    .sort((a, b) => a[0] - b[0]);
  const joined = [];
  for (const span of spans) {
    const last = joined[joined.length - 1];
    if (last && span[0] <= last[1]) {
      last[1] = Math.max(last[1], span[1]);
    } else {
      joined.push(span);
    }
  }
  return joined;
}

module.exports = { placeWindows, tremorSpans };
