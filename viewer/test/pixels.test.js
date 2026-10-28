'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { sampleCells } = require('../src/lib/pixels');

const NAVY = '#1B2E42';
const WIDTH = 20;
const HEIGHT = 10;

/** A white BGRA bitmap with a block of one colour from image x 4 to 11 and y 2 to 7. */
function bitmapWithBlock([r, g, b]) {
  const bitmap = new Uint8Array(WIDTH * HEIGHT * 4).fill(255);
  for (let y = 2; y <= 7; y++) {
    for (let x = 4; x <= 11; x++) {
      bitmap.set([b, g, r, 255], (y * WIDTH + x) * 4);
    }
  }
  return bitmap;
}

const NAVY_RGB = [0x1b, 0x2e, 0x42];
const cellAt = (x) => ({ x, y: 1, width: 4, height: 3 });

test('case 24: the colour at the centre of each cell', () => {
  const navy = bitmapWithBlock(NAVY_RGB);
  assert.deepEqual(sampleCells(navy, WIDTH, HEIGHT, 2, [cellAt(2)], NAVY), { checked: 1, matched: 1, misses: [] });

  const outside = sampleCells(navy, WIDTH, HEIGHT, 2, [cellAt(7)], NAVY);
  assert.equal(outside.matched, 0);
  assert.equal(outside.misses.length, 1);

  const offBy = (d) => bitmapWithBlock([NAVY_RGB[0], NAVY_RGB[1], NAVY_RGB[2] + d]);
  assert.equal(sampleCells(offBy(9), WIDTH, HEIGHT, 2, [cellAt(2)], NAVY).matched, 0);
  assert.equal(sampleCells(offBy(8), WIDTH, HEIGHT, 2, [cellAt(2)], NAVY).matched, 1);
});
