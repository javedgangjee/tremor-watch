# Third-party parts

The project's own code is under the MIT licence in LICENSE. These parts come from other projects and keep their own licences.

## Kept in this repo

| Part | Where | Licence | Licence text |
| --- | --- | --- | --- |
| ParaDigMa 1.1.2 tremor model, by the ParaDigMa authors | tests/model/tremor_detection_clf_package.pkl, and the numbers in core/detector_tables.h made from it | Apache-2.0 | tests/model/LICENSE |
| KISS FFT 131.2.0, by Mark Borgerding | core/kissfft/ | BSD-3-Clause | core/kissfft/COPYING, core/kissfft/LICENSES/BSD-3-Clause |
| Unity 2.6.1, by ThrowTheSwitch | tests/unity/ | MIT | tests/unity/LICENSE.txt |
| XPowersLib, by Lewis He | firmware/components/XPowersLib/ | MIT | firmware/components/XPowersLib/LICENSE |
| Red Hat Display font, by The Red Hat Project Authors | firmware/main/assets/RedHatDisplay-Bold.ttf, and face_font_*.c made from it | SIL Open Font Licence 1.1 | firmware/main/assets/OFL.txt |
| Red Hat Display variable font, latin subset from Fontsource 5.3.0, by The Red Hat Project Authors | viewer/src/renderer/fonts/RedHatDisplay-Variable-latin.woff2 | SIL Open Font Licence 1.1 | viewer/src/renderer/fonts/OFL-RedHatDisplay.txt |
| Libre Franklin variable font, roman and italic, latin subset from Fontsource 5.3.0, by The Libre Franklin Project Authors | viewer/src/renderer/fonts/LibreFranklin-Variable-latin.woff2 and LibreFranklin-Variable-Italic-latin.woff2 | SIL Open Font Licence 1.1 | viewer/src/renderer/fonts/OFL-LibreFranklin.txt |
| IBM Plex Mono 400, 500, and 600, latin subset from Fontsource 5.3.0, by IBM Corp. | viewer/src/renderer/fonts/IBMPlexMono-Regular-latin.woff2, IBMPlexMono-Medium-latin.woff2, and IBMPlexMono-SemiBold-latin.woff2 | SIL Open Font Licence 1.1 | viewer/src/renderer/fonts/OFL-IBMPlexMono.txt |
| Lucide 0.469.0 icons, by Lucide Contributors | the path data in tools/gen_face_assets.py, and face_icons.c made from it | ISC | firmware/main/assets/LUCIDE_LICENSE.txt |
| Results made from PADS 1.0.0, by Varghese and colleagues | reference/results/, tests/pads/pads_match.md | CC BY-NC-SA 4.0 | reference/results/LICENSE.md |

The face design file, context/Tremor Watch Light.html, is a saved design page. It holds copies of the Red Hat Display, Barlow, and Barlow Condensed fonts, which are under the SIL Open Font Licence 1.1, and of React and React DOM, which are under the MIT licence.

## Fetched at build time

These are not kept in the repo. ESP-IDF's component manager fetches them into firmware/managed_components/, and each copy carries its own licence file.

| Part | Version | Licence |
| --- | --- | --- |
| ESP-IDF, by Espressif | 6.1 | Apache-2.0 |
| LVGL, by LVGL Kft | 9.5.0 | MIT |
| Waveshare board support package esp32_s3_touch_amoled_2_06 | 2.0.0 | Apache-2.0 |
| Waveshare qmi8658 and esp_lcd_sh8601 drivers | 2.0.2 and the version the package needs | Apache-2.0 |
| Espressif components, such as esp_lvgl_port, esp_lcd_touch, and usb | the versions the package needs | Apache-2.0 |

The Python toolbox in reference/ installs ParaDigMa and its dependencies from PyPI, as reference/requirements.txt pins them. It also pins edfio 0.4.18, which only the tests use and which is under the Apache-2.0 licence.

npm fetches the recording viewer's two packages into viewer/node_modules/, as viewer/package-lock.json pins them. They are Electron 44.7.1 and uPlot 1.6.32, and both are under the MIT licence.
