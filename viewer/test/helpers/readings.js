'use strict';

/**
 * Give the reading number at timeline index i of a loaded boot, from the
 * stretch that holds it. The tests use it to name breaks by reading number.
 */
function readingAt(boot, i) {
  const us = boot.timeS[i] * 1e6;
  const s = boot.stretches.filter((st) => st.t0Us <= us + 1).pop();
  return s.first + Math.round(((us - s.t0Us) * s.rateUhz) / 1e12);
}

module.exports = { readingAt };
