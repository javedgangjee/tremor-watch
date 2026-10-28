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
- The mock shades the span of the selected answer block. The user chose to mark the selected window with two vertical lines, one at its start and one at its end, in place of the shading.
- The mock's span runs 7 seconds back from the window's end. A window covers 4 seconds, as feature 12's requirement 18 says, so the lines mark that 4-second span.
- The work runs as spec-driven feature 15, and the wrist tests move to feature 16.
