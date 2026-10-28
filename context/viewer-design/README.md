# Viewer design

The user made the new viewer design in Claude Design on 2026-10-28, in the project `aba1db46-1f1c-41c7-be5d-5d191e20ca9a`. These files are local copies, saved on 2026-10-28.

- `Tremor Log Viewer.dc.html` is the design page. It is a Claude Design component file. The markup is HTML with `{{ }}` holes, `sc-for` loops and `sc-if` blocks, and the script at the end fills the holes. The `x-import` tags stand for design system components (Button, Chip, SegmentedControl), and `_ds_bundle.js` holds their source. The page shows one made-up 30-second recording drawn as SVG paths.
- `colors.css`, `typography-spacing-fonts.css`, and `components.css` are the design system's tokens and component classes. The design system is called "My Default". The colours have a light and a dark set.
- `_ds_bundle.js` is the design system's compiled component code. It shows the markup each component makes, such as the `md-btn` classes and the icon paths for `folder` and `play`.
- The design system uses three fonts, which are under the SIL Open Font Licence 1.1. They are Red Hat Display (variable), Libre Franklin (variable, roman and italic), and IBM Plex Mono (400, 500, and 600), as latin subsets in woff2. The font files are not copied here.

## The design's rules

These come from the design system's readme.

- Text is in sentence case. There are no emoji and no exclamation marks.
- Libre Franklin is used for all text except the wordmark, which uses Red Hat Display 700, and identifiers such as file names, which use IBM Plex Mono. Counts use tabular figures.
- Dates read as words, such as `Oct 28, 2026 at 14:28`, in 24-hour time.
- Cards are white with a 1 px ring and no drop shadow. Only floating layers, such as the tooltip and the sticky header, get a shadow.
- Blue is used only for primary actions, links, focus, and selection.
- Every control shows the focus ring `--shadow-focus`.
- Every text colour holds at least 4.5:1 contrast on every surface in both themes.

## The user's decisions on 2026-10-28

- The mock leaves out the boot picker, the summary facts, the cut-short note, the record status line, and the error message. The user chose to keep each of them, restyled with the design system.
- The mock shades the span of the selected answer block, and the viewer before feature 15 shaded the span of every tremor window. In place of shading, the user wants vertical lines in the signal area where tremor starts and where it ends. An earlier note here read this as two lines for the selected window only. The user corrected that on 2026-10-28.
- The tremor lines follow the signal span. Consecutive and overlapping tremor windows join into one episode, as tremorSpans() joins them. One line marks the start of the first tremor window's 4 seconds of signal, and one marks the end of the last one's. The lines have no text on the plot, and a legend entry names them.
- The two lines for the selected answer block stay, but dashed and grey, so they never look like the tremor lines or the blue y trace. A window covers 4 seconds, as feature 12's requirement 18 says, so they mark that 4-second span and not the mock's 7 seconds.
- In stacked mode the plots share one y range, so each plot has readable labels and the same scale.
- The work runs as spec-driven feature 15, and the wrist tests move to feature 16.
