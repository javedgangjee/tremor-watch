'use strict';

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

module.exports = { sampleCells, MIN_CELL_WIDTH };
