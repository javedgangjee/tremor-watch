'use strict';

// IMU_GYRO_COUNTS_PER_DPS in core/imu_units.h.
const GYRO_COUNTS_PER_DPS = 32;

// Feature 1's measured rate of 114.3302 readings a second, from the Hardware
// section of specs/tech-stack.md. Used only when a boot gives no rate at all.
const FALLBACK_RATE_UHZ = 114330200;

function byFirstReading(bursts) {
  return [...bursts].sort((a, b) => a.first - b.first);
}

/** The rate from the first and last kept bursts of a stretch, or null with fewer than two. */
function estimateRate(bursts) {
  if (bursts.length < 2) {
    return null;
  }
  const first = bursts[0];
  const last = bursts[bursts.length - 1];
  const spanUs = last.stampUs - first.stampUs;
  return spanUs > 0 ? Math.round(((last.first - first.first) * 1e12) / spanUs) : null;
}

/**
 * Give the stretches of a boot in order of first reading, each with the t0 and
 * rate of its last S line. A stretch whose S line gives rate 0 gets a rate
 * estimated from its bursts and is marked as estimated.
 *
 * @param {{sLines: Map<number, {first: number, t0Us: number, rateUhz: number}>, bursts: object[]}} boot
 * @returns {{number: number, first: number, t0Us: number, rateUhz: number, estimated: boolean}[]}
 */
function stretchTable(boot) {
  const stretches = [...boot.sLines]
    .map(([number, s]) => ({ number, first: s.first, t0Us: s.t0Us, rateUhz: s.rateUhz, estimated: false }))
    .sort((a, b) => a.first - b.first);
  const known = stretches.filter((s) => s.rateUhz > 0);
  const bootRate = known.length > 0 ? known[known.length - 1].rateUhz : FALLBACK_RATE_UHZ;
  const bursts = byFirstReading(boot.bursts);
  stretches.forEach((s, i) => {
    if (s.rateUhz > 0) {
      return;
    }
    const end = i + 1 < stretches.length ? stretches[i + 1].first : Infinity;
    const own = bursts.filter((b) => b.first >= s.first && b.first < end);
    s.rateUhz = estimateRate(own) ?? bootRate;
    s.estimated = true;
  });
  return stretches;
}

/**
 * Give each kept reading of a boot its time in seconds since boot and its
 * gyroscope values in degrees per second.
 *
 * Reading n of a stretch with first reading f, start t0Us, and rate rateUhz
 * lies at t0Us + (n - f) * 1e12 / rateUhz microseconds, as rt_reading_time_us()
 * in core/reading_time.h gives it. breaks holds each index i where the plot
 * must not join reading i - 1 to reading i, which is the start of a stretch
 * and each gap in the kept bursts. Readings below the first stretch are left
 * out and counted.
 *
 * @param {object} boot A boot from parseLines().
 * @returns {{stretches: object[], timeS: Float64Array, gx: Float32Array, gy: Float32Array, gz: Float32Array, breaks: number[], noStretchReadings: number}}
 */
function buildTimeline(boot) {
  const stretches = stretchTable(boot);
  const bursts = byFirstReading(boot.bursts);
  const lowest = stretches.length > 0 ? stretches[0].first : Infinity;
  let total = 0;
  let noStretchReadings = 0;
  for (const b of bursts) {
    const below = Math.min(b.count, Math.max(0, lowest - b.first));
    noStretchReadings += below;
    total += b.count - below;
  }

  const timeS = new Float64Array(total);
  const gx = new Float32Array(total);
  const gy = new Float32Array(total);
  const gz = new Float32Array(total);
  const breaks = [];
  let i = 0;
  let k = -1;
  let lastK = -1;
  let lastN = -1;
  for (const b of bursts) {
    for (let j = 0; j < b.count; j++) {
      const n = b.first + j;
      while (k + 1 < stretches.length && stretches[k + 1].first <= n) {
        k++;
      }
      if (k < 0) {
        continue;
      }
      const s = stretches[k];
      if (i > 0 && (k !== lastK || n !== lastN + 1)) {
        breaks.push(i);
      }
      timeS[i] = (s.t0Us + ((n - s.first) * 1e12) / s.rateUhz) / 1e6;
      gx[i] = b.gyro[j * 3] / GYRO_COUNTS_PER_DPS;
      gy[i] = b.gyro[j * 3 + 1] / GYRO_COUNTS_PER_DPS;
      gz[i] = b.gyro[j * 3 + 2] / GYRO_COUNTS_PER_DPS;
      lastK = k;
      lastN = n;
      i++;
    }
  }
  return { stretches, timeS, gx, gy, gz, breaks, noStretchReadings };
}

module.exports = { stretchTable, buildTimeline, GYRO_COUNTS_PER_DPS, FALLBACK_RATE_UHZ };
