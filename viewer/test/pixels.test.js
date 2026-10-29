'use strict';

const assert = require('node:assert/strict');
const test = require('node:test');
const { sampleCells, samplePoints, countColumn, INK, INK_SECONDARY } = require('../src/lib/pixels');

// Feature 15 checks the tremor blocks against the light theme's --ink.
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
const cellAt = (x) => ({ x, y: 1, width: 4, height: 3 });

test('case 24: the colour at the centre of each cell', () => {
  const ink = bitmapWithBlock(INK_RGB);
  assert.deepEqual(sampleCells(ink, WIDTH, HEIGHT, 2, [cellAt(2)], INK_LIGHT), { checked: 1, matched: 1, misses: [] });

  const outside = sampleCells(ink, WIDTH, HEIGHT, 2, [cellAt(7)], INK_LIGHT);
  assert.equal(outside.matched, 0);
  assert.equal(outside.misses.length, 1);

  const offBy = (d) => bitmapWithBlock([INK_RGB[0], INK_RGB[1], INK_RGB[2] + d]);
  assert.equal(sampleCells(offBy(9), WIDTH, HEIGHT, 2, [cellAt(2)], INK_LIGHT).matched, 0);
  assert.equal(sampleCells(offBy(8), WIDTH, HEIGHT, 2, [cellAt(2)], INK_LIGHT).matched, 1);
});

test('case 22 of feature 15: samplePoints() and countColumn()', () => {
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

  const grey = new Uint8Array(WIDTH * HEIGHT * 4).fill(255);
  const [r, g, b] = [0x3a, 0x41, 0x50];
  for (const y of [0, 1, 2, 3, 8, 9]) {
    for (const x of [4, 5]) {
      grey.set([b, g, r, 255], (y * WIDTH + x) * 4);
    }
  }
  const colours = [INK_SECONDARY.light, INK_LIGHT];
  const line = (x) => ({ x, width: 1, top: 0, height: 5 });
  assert.deepEqual(countColumn(grey, WIDTH, HEIGHT, 2, line(2), colours), { sampled: 5, matches: [3, 0] });
  assert.deepEqual(countColumn(grey, WIDTH, HEIGHT, 2, line(6), colours), { sampled: 5, matches: [0, 0] });
});
