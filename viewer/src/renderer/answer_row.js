'use strict';

// The Answer row under the charts: one block for each window answer on the
// shared time axis, the selected window, its keys, and the line that reads
// the selection out. The page loads this as a classic script, so it adds one
// global, TremorAnswers.

(function () {
  const C = window.TremorChart;

  const BLOCK_PX = 28;
  // Room above and below the blocks for the selection ring.
  const RING_ROOM_PX = 4;
  const ROW_PX = BLOCK_PX + 2 * RING_ROOM_PX;
  const RADIUS_PX = 2;
  const TREMOR = 0;
  // The dashes of a 1 px dashed border.
  const DASH = [3, 3];
  const KEYS = ['ArrowLeft', 'ArrowRight', 'Home', 'End', 'Escape'];

  /** How each answer code is drawn, from the tokens of the palette. */
  function looks(p) {
    return {
      0: { fill: p.ink },
      1: { fill: p.surfaceCard, border: p.borderControl },
      2: { fill: p.borderStrong },
      3: { fill: p.surfaceSunken, border: p.borderControl, dash: DASH },
    };
  }

  /**
   * Make the row. getView gives the shared view, onSelect gets each new
   * selection or null, and onShowSpan gets a view that shows the selected cell.
   */
  function create(rowEl, canvas, liveEl, boot, { palette, getView, onSelect, onShowSpan }) {
    let look = looks(palette);
    let selected = null;
    let widthPx = 0;
    const windows = boot.windows;
    const bounds = { min: boot.timeS[0], max: boot.timeS[boot.timeS.length - 1] };

    function edgeLine(ctx, x, y, w, dash) {
      ctx.setLineDash(dash || []);
      ctx.beginPath();
      ctx.moveTo(x, y + 0.5);
      ctx.lineTo(x + w, y + 0.5);
      ctx.moveTo(x, y + BLOCK_PX - 0.5);
      ctx.lineTo(x + w, y + BLOCK_PX - 0.5);
      ctx.stroke();
    }

    function drawBlock(ctx, w, box) {
      const style = look[w.code];
      if (style === undefined) {
        return;
      }
      const y = RING_ROOM_PX;
      ctx.fillStyle = style.fill;
      if (box.joined) {
        ctx.fillRect(box.x, y, box.width, BLOCK_PX);
        if (style.border) {
          ctx.strokeStyle = style.border;
          ctx.lineWidth = 1;
          edgeLine(ctx, box.x, y, box.width, style.dash);
        }
        return;
      }
      ctx.beginPath();
      ctx.roundRect(box.x, y, box.width, BLOCK_PX, RADIUS_PX);
      ctx.fill();
      if (style.border) {
        ctx.strokeStyle = style.border;
        ctx.lineWidth = 1;
        ctx.setLineDash(style.dash || []);
        ctx.beginPath();
        ctx.roundRect(box.x + 0.5, y + 0.5, Math.max(0, box.width - 1), BLOCK_PX - 1, RADIUS_PX - 0.5);
        ctx.stroke();
      }
    }

    // The ring is 2 px of the card's colour and then 2 px of --link.
    function drawRing(ctx, box) {
      const y = RING_ROOM_PX;
      ctx.setLineDash([]);
      ctx.fillStyle = palette.link;
      ctx.beginPath();
      ctx.roundRect(box.x - 4, y - 4, box.width + 8, BLOCK_PX + 8, RADIUS_PX + 4);
      ctx.fill();
      ctx.fillStyle = palette.surfaceCard;
      ctx.beginPath();
      ctx.roundRect(box.x - 2, y - 2, box.width + 4, BLOCK_PX + 4, RADIUS_PX + 2);
      ctx.fill();
    }

    function draw() {
      const view = getView();
      const ratio = window.devicePixelRatio || 1;
      widthPx = rowEl.clientWidth;
      const wantW = Math.round(widthPx * ratio);
      const wantH = Math.round(ROW_PX * ratio);
      if (canvas.width !== wantW || canvas.height !== wantH) {
        canvas.width = wantW;
        canvas.height = wantH;
      }
      canvas.style.width = `${widthPx}px`;
      canvas.style.height = `${ROW_PX}px`;
      const ctx = canvas.getContext('2d');
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.clearRect(0, 0, widthPx, ROW_PX);
      ctx.save();
      ctx.beginPath();
      ctx.rect(0, 0, widthPx, ROW_PX);
      ctx.clip();
      // Tremor blocks go last, so they show where cells share a pixel.
      for (const tremorPass of [false, true]) {
        for (const w of windows) {
          if ((w.code === TREMOR) !== tremorPass) {
            continue;
          }
          const box = C.blockLayout(w, view, widthPx);
          if (box !== null) {
            drawBlock(ctx, w, box);
          }
        }
      }
      if (selected !== null) {
        const box = C.blockLayout(windows[selected], view, widthPx);
        if (box !== null) {
          drawRing(ctx, box);
          drawBlock(ctx, windows[selected], box);
        }
      }
      ctx.restore();
    }

    function select(index, moveView) {
      selected = index;
      const w = index === null ? null : windows[index];
      liveEl.textContent = w === null ? '' : C.windowText(w);
      onSelect(w);
      if (w !== null && moveView) {
        const view = getView();
        const next = C.keepInView(view, bounds, w.cellStartS, w.cellStartS + 1);
        if (next.min !== view.min || next.max !== view.max) {
          onShowSpan(next);
          return;
        }
      }
      draw();
    }

    function onClick(event) {
      const rect = canvas.getBoundingClientRect();
      const t = C.timeAt(event.clientX - rect.left, getView(), rect.width);
      const w = C.answerAt(windows, t);
      const index = w === null ? -1 : windows.indexOf(w);
      select(index < 0 || index === selected ? null : index, false);
    }

    function onKey(event) {
      if (!KEYS.includes(event.key) || event.metaKey || event.ctrlKey || event.altKey) {
        return;
      }
      event.preventDefault();
      const next = C.stepSelection(windows, selected, event.key, getView());
      if (next !== selected) {
        select(next, true);
      }
    }

    rowEl.addEventListener('click', onClick);
    rowEl.addEventListener('keydown', onKey);
    liveEl.textContent = '';

    return {
      draw,
      setPalette(next) {
        palette = next;
        look = looks(next);
        draw();
      },
      /** The selected window, or null. */
      selection: () => (selected === null ? null : windows[selected]),
      /** The tremor blocks drawn in view, in page pixels, without the gap. */
      tremorBlocks() {
        const rect = canvas.getBoundingClientRect();
        const view = getView();
        const blocks = [];
        for (const w of windows) {
          const box = w.code === TREMOR ? C.blockLayout(w, view, widthPx) : null;
          if (box !== null) {
            blocks.push({ x: rect.left + box.x, y: rect.top + RING_ROOM_PX, width: box.width, height: BLOCK_PX });
          }
        }
        return blocks;
      },
      /** Where the row puts the view's start and end, in page pixels. */
      edges() {
        const rect = canvas.getBoundingClientRect();
        return { left: rect.left, right: rect.left + widthPx };
      },
      destroy() {
        rowEl.removeEventListener('click', onClick);
        rowEl.removeEventListener('keydown', onKey);
        liveEl.textContent = '';
      },
    };
  }

  window.TremorAnswers = { create };
})();
