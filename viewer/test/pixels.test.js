'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { samplePoints, INK } = require('../src/lib/pixels');

// Feature 15 checks the tremor lines against the light theme's --ink.
const INK_LIGHT = INK.light;
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

const INK_RGB = [0x16, 0x18, 0x1d];

test('case 22 of feature 15: samplePoints()', () => {
  const ink = bitmapWithBlock(INK_RGB);
  const points = [
    { x: 4, y: 2 },
    { x: 7, y: 2 },
    { x: 20, y: 2 },
  ];
  const sampled = samplePoints(ink, WIDTH, HEIGHT, 2, points, INK_LIGHT);
  assert.equal(sampled.checked, 3);
  assert.equal(sampled.matched, 1);
  assert.deepEqual(
    sampled.misses.map((m) => m.found),
    ['#FFFFFF', null],
  );

  const offBy = (d) => bitmapWithBlock([INK_RGB[0], INK_RGB[1], INK_RGB[2] + d]);
  assert.equal(samplePoints(offBy(9), WIDTH, HEIGHT, 2, [points[0]], INK_LIGHT).matched, 0);
  assert.equal(samplePoints(offBy(8), WIDTH, HEIGHT, 2, [points[0]], INK_LIGHT).matched, 1);
});
