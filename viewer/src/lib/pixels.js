'use strict';

// The --ink colour of the page's light and dark themes, from
// viewer/src/renderer/design/colors.css, which draws the tremor lines.
const INK = { light: '#16181D', dark: '#F4F7FA' };

function rgbFromHex(colour) {
  const value = parseInt(colour.replace('#', ''), 16);
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff];
}

function hexFromRgb(rgb) {
  return `#${rgb.map((c) => c.toString(16).padStart(2, '0')).join('').toUpperCase()}`;
}

/** The colour of the image pixel at x and y as [r, g, b], or null outside the image. */
function pixelAt(bitmap, imageWidth, imageHeight, x, y) {
  if (x < 0 || y < 0 || x >= imageWidth || y >= imageHeight) {
    return null;
  }
  const at = (y * imageWidth + x) * 4;
  return [bitmap[at + 2], bitmap[at + 1], bitmap[at]];
}

const near = (found, want, tolerance) => found.every((c, i) => Math.abs(c - want[i]) <= tolerance);

/**
 * Check the colour at each point of a captured page. The points are in page
 * pixels, and a point outside the image is a miss whose found is null.
 *
 * @param {Uint8Array} bitmap The BGRA data that nativeImage.toBitmap() gives.
 * @param {number} imageWidth
 * @param {number} imageHeight
 * @param {number} scale Image pixels per page pixel.
 * @param {{x: number, y: number}[]} points
 * @param {string} colour The expected colour as #RRGGBB.
 * @param {number} [tolerance] The largest difference allowed in each channel.
 * @returns {{checked: number, matched: number, misses: {point: object, found: string | null}[]}}
 */
function samplePoints(bitmap, imageWidth, imageHeight, scale, points, colour, tolerance = 8) {
  const want = rgbFromHex(colour);
  let matched = 0;
  const misses = [];
  for (const point of points) {
    const found = pixelAt(bitmap, imageWidth, imageHeight, Math.floor(point.x * scale), Math.floor(point.y * scale));
    if (found !== null && near(found, want, tolerance)) {
      matched++;
    } else {
      misses.push({ point, found: found === null ? null : hexFromRgb(found) });
    }
  }
  return { checked: points.length, matched, misses };
}

module.exports = { samplePoints, INK };
