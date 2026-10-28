'use strict';

// The --ink colour of the page's light and dark themes, from
// viewer/src/renderer/design/colors.css, which fills the tremor blocks.
const INK = { light: '#16181D', dark: '#F4F7FA' };
// The --border-control colour of the light and dark themes, from the same
// file, which draws the dashes of the selection lines.
const BORDER_CONTROL = { light: '#7F8693', dark: '#727A89' };

// A cell narrower than this has no centre pixel that is safely inside it.
const MIN_CELL_WIDTH = 3;

function rgbFromHex(colour) {
  const value = parseInt(colour.replace('#', ''), 16);
  return [(value >> 16) & 0xff, (value >> 8) & 0xff, value & 0xff];
}

function hexFromRgb(rgb) {
  return `#${rgb.map((c) => c.toString(16).padStart(2, '0')).join('').toUpperCase()}`;
}

/**
 * Check the colour at the centre of each cell of a captured page.
 *
 * The bitmap is the BGRA data that nativeImage.toBitmap() gives. Cells are in
 * page pixels, and scale is image pixels per page pixel. Cells narrower than
 * MIN_CELL_WIDTH page pixels are not checked.
 *
 * @param {Uint8Array} bitmap
 * @param {number} imageWidth
 * @param {number} imageHeight
 * @param {number} scale
 * @param {{x: number, y: number, width: number, height: number}[]} cells
 * @param {string} colour The expected colour as #RRGGBB.
 * @param {number} [tolerance] The largest difference allowed in each channel.
 * @returns {{checked: number, matched: number, misses: {cell: object, found: string | null}[]}}
 */
function sampleCells(bitmap, imageWidth, imageHeight, scale, cells, colour, tolerance = 8) {
  const want = rgbFromHex(colour);
  let checked = 0;
  let matched = 0;
  const misses = [];
  for (const cell of cells) {
    if (cell.width < MIN_CELL_WIDTH) {
      continue;
    }
    checked++;
    const x = Math.floor((cell.x + cell.width / 2) * scale);
    const y = Math.floor((cell.y + cell.height / 2) * scale);
    if (x < 0 || y < 0 || x >= imageWidth || y >= imageHeight) {
      misses.push({ cell, found: null });
      continue;
    }
    const at = (y * imageWidth + x) * 4;
    const found = [bitmap[at + 2], bitmap[at + 1], bitmap[at]];
    if (found.every((c, i) => Math.abs(c - want[i]) <= tolerance)) {
      matched++;
    } else {
      misses.push({ cell, found: hexFromRgb(found) });
    }
  }
  return { checked, matched, misses };
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

/**
 * Count the pixels down the middle of a vertical line that match each colour.
 * The line is in page pixels, and it is sampled once for each page pixel of
 * its height, at the middle of that pixel. Rows outside the image are not
 * sampled.
 *
 * @param {Uint8Array} bitmap The BGRA data that nativeImage.toBitmap() gives.
 * @param {number} imageWidth
 * @param {number} imageHeight
 * @param {number} scale Image pixels per page pixel.
 * @param {{x: number, width: number, top: number, height: number}} line
 * @param {string[]} colours The colours to count, each as #RRGGBB.
 * @param {number} [tolerance] The largest difference allowed in each channel.
 * @returns {{sampled: number, matches: number[]}}
 */
function countColumn(bitmap, imageWidth, imageHeight, scale, line, colours, tolerance = 8) {
  const wants = colours.map(rgbFromHex);
  const matches = wants.map(() => 0);
  const x = Math.floor((line.x + line.width / 2) * scale);
  let sampled = 0;
  for (let k = 0; k < line.height; k++) {
    const found = pixelAt(bitmap, imageWidth, imageHeight, x, Math.floor((line.top + k + 0.5) * scale));
    if (found === null) {
      continue;
    }
    sampled++;
    wants.forEach((want, i) => {
      if (near(found, want, tolerance)) {
        matches[i]++;
      }
    });
  }
  return { sampled, matches };
}

module.exports = { sampleCells, samplePoints, countColumn, MIN_CELL_WIDTH, INK, BORDER_CONTROL };
