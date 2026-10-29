'use strict';

const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const { REPO, VIEWER } = require('./helpers/paths');
const { INK } = require('../src/lib/pixels');

const RENDERER = path.join(VIEWER, 'src', 'renderer');
const DESIGN = path.join(REPO, 'context', 'viewer-design');
const read = (file) => fs.readFileSync(file, 'utf8');
const sha256 = (file) => crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex');

// The files and sums of requirement 26 in specs/features/15-viewer-redesign/requirements.md.
const FONT_SUMS = {
  'RedHatDisplay-Variable-latin.woff2': 'f7a7830b81e351f89b91f0201de71c8d937e25df5a3e31ecca9b4ee877abedb7',
  'LibreFranklin-Variable-latin.woff2': '52e605852c72cc2df1473df1fb7f26a3a0be58e31835bc8f33f29b1918c82cbd',
  'LibreFranklin-Variable-Italic-latin.woff2': 'c9fb9170f00060c83306219df8357a81a56c5ad142e25b3e3d9c21d2d47e2009',
  'IBMPlexMono-Regular-latin.woff2': '08949f728dc52d528e69b1667d15c89a5686a4ee9a296ff90983985f99c380f7',
  'IBMPlexMono-Medium-latin.woff2': '01d285447409c8a588692162439a038b8cbd7871309ee20267b0d2d91c6e8e22',
  'IBMPlexMono-SemiBold-latin.woff2': '0d1f0b8d0722224e32e9f28261bdc86c79115be73444ae5eceb73976a1bcdf83',
};
const LICENCE_SUMS = {
  'OFL-RedHatDisplay.txt': 'b0f9871d4d4b7b9919b5b8858ba47352284c982c3699c7b15d784846d4494140',
  'OFL-LibreFranklin.txt': '7e982e27dc99e50b47daf19c27bb32419bee58ddc371f073520dc823e7882940',
  'OFL-IBMPlexMono.txt': '23b0a9d0c6d3f140a0b77e483c5cfa6bba574325ef5cb189ed9f2fec4884533f',
};
const DESIGN_FILES = ['colors.css', 'typography-spacing-fonts.css', 'components.css'];

const POLICY =
  "default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; base-uri 'none'; form-action 'none'";

test('case 13 of feature 15: the fonts, their licences, and the design files', () => {
  const fonts = path.join(RENDERER, 'fonts');
  for (const [name, sum] of Object.entries({ ...FONT_SUMS, ...LICENCE_SUMS })) {
    assert.equal(sha256(path.join(fonts, name)), sum, name);
  }
  for (const name of DESIGN_FILES) {
    assert.ok(fs.readFileSync(path.join(RENDERER, 'design', name)).equals(fs.readFileSync(path.join(DESIGN, name))), name);
  }
  const typography = read(path.join(RENDERER, 'design', 'typography-spacing-fonts.css'));
  const named = [...typography.matchAll(/url\('([^']+)'\)/g)].map(([, url]) => path.resolve(RENDERER, 'design', url));
  assert.deepEqual(new Set(named), new Set(Object.keys(FONT_SUMS).map((name) => path.join(fonts, name))));
  assert.equal(named.length, 6);

  const thirdParty = read(path.join(REPO, 'THIRD_PARTY.md'));
  for (const word of ['Red Hat Display', 'Libre Franklin', 'IBM Plex Mono', 'viewer/src/renderer/fonts/']) {
    assert.ok(thirdParty.includes(word), `THIRD_PARTY.md names ${word}`);
  }
});

/** The value of a custom property in a block of colors.css, with each var() followed. */
function tokenValue(css, selector, name) {
  const blockOf = (sel) => {
    const at = css.indexOf(`${sel} {`);
    assert.ok(at !== -1, `colors.css has no ${sel} block`);
    return css.slice(at, css.indexOf('}', at));
  };
  const lookup = (n, sel) => {
    const found = new RegExp(`${n}:\\s*([^;]+);`).exec(blockOf(sel));
    if (found === null && sel !== ':root, [data-theme="light"]') {
      return lookup(n, ':root, [data-theme="light"]');
    }
    assert.ok(found, `${sel} gives no ${n}`);
    const value = found[1].trim();
    const ref = /^var\((--[a-z0-9-]+)\)$/.exec(value);
    return ref ? lookup(ref[1], sel) : value;
  };
  return lookup(name, selector);
}

test('case 14 of feature 15: the page, its policy, its icons, and its colours', () => {
  const html = read(path.join(RENDERER, 'index.html'));
  assert.equal(/http-equiv="Content-Security-Policy" content="([^"]*)"/.exec(html)[1], POLICY);

  const head = html.slice(0, html.indexOf('</head>'));
  const links = [...head.matchAll(/<link rel="stylesheet" href="([^"]+)">/g)].map(([, href]) => href);
  assert.deepEqual(links, [
    'design/colors.css',
    'design/typography-spacing-fonts.css',
    'design/components.css',
    '../../node_modules/uplot/dist/uPlot.min.css',
    'viewer.css',
  ]);
  const headScripts = [...head.matchAll(/<script src="([^"]+)">/g)].map(([, src]) => src);
  assert.deepEqual(headScripts, ['theme.js']);
  assert.ok(head.indexOf('theme.js') > head.indexOf('viewer.css'), 'theme.js loads after the stylesheets');

  const body = html.slice(html.indexOf('<body'));
  const bodyScripts = [...body.matchAll(/<script src="([^"]+)">/g)].map(([, src]) => src);
  assert.deepEqual(bodyScripts, [
    '../../node_modules/uplot/dist/uPlot.iife.min.js',
    '../lib/chart.js',
    'plot.js',
    'viewer.js',
  ]);
  assert.ok(!html.includes('style='), 'index.html holds a style attribute');

  const bundle = read(path.join(DESIGN, '_ds_bundle.js'));
  for (const icon of ['folder', 'play', 'chevron']) {
    const paths = new RegExp(`\\n\\s*${icon}: \\[([^\\]]+)\\]`).exec(bundle)[1];
    for (const [, d] of paths.matchAll(/'([^']+)'/g)) {
      assert.ok(html.includes(`d="${d}"`), `index.html holds the ${icon} path ${d}`);
    }
  }

  const colourLiteral = /#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})(?![0-9a-zA-Z])|\b(?:rgba?|hsl)\(/;
  for (const name of ['viewer.css', 'theme.js', 'plot.js', 'viewer.js']) {
    const found = colourLiteral.exec(read(path.join(RENDERER, name)));
    assert.equal(found, null, `${name} holds the colour literal ${found && found[0]}`);
  }

  const chartPath = path.join(VIEWER, 'src', 'lib', 'chart.js');
  const context = {};
  vm.runInNewContext(read(chartPath), context);
  assert.ok(context.TremorChart, 'chart.js sets TremorChart');
  assert.deepEqual(Object.keys(context.TremorChart).sort(), Object.keys(require(chartPath)).sort());

  const colors = read(path.join(RENDERER, 'design', 'colors.css'));
  assert.equal(INK.light, tokenValue(colors, ':root, [data-theme="light"]', '--ink'));
  assert.equal(INK.dark, tokenValue(colors, '[data-theme="dark"]', '--ink'));

  assert.ok(!html.includes('class="legend'), 'index.html holds no legend');
  assert.ok(!html.includes('answer-row'), 'index.html holds no Answer row');
  const span = /<div id="span"[^>]*>([\s\S]*?)<\/div>/.exec(html)[1];
  const options = [...span.matchAll(/data-span="([^"]+)">([^<]+)</g)].map(([, value, text]) => [value, text]);
  assert.deepEqual(options, [['10', '10 s'], ['30', '30 s'], ['60', '1 min'], ['all', 'All']]);
  assert.ok(/<button id="earlier"[^>]*aria-label="Earlier"/.test(html), 'index.html holds the Earlier button');
  for (const title of ['Recording', 'Data quality']) {
    assert.ok(html.includes(`<h3 class="summary-group-title">${title}</h3>`), `the summary has the group ${title}`);
  }
  const fileRule = /\.facts \.fact-file \{([^}]*)\}/.exec(read(path.join(RENDERER, 'viewer.css')))[1];
  for (const line of ['grid-column: 1 / -1;', 'white-space: nowrap;', 'overflow: hidden;', 'text-overflow: ellipsis;']) {
    assert.ok(fileRule.includes(line), `the file name rule holds ${line}`);
  }
});
