# PADS match of the C detector

- The run date is 2026-10-22.
- The toolbox is ParaDigMa 1.1.2 with scikit-learn 1.6.0.
- The model file's SHA-256 hash is 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e.
- DET_MODEL_SHA256 in core/detector_tables.h is 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e.
- KISS FFT is tag 131.2.0, commit 7bce4153c6bc8aba2db0e889e576f9d00505cbe1.
- The run compared 10318 files and 26264 windows, and 0 files were missing.
- The toolbox run gave the same probability, low-frequency sum, peak, and answers as reference/results/pads_windows.csv on all 26264 windows.
- Replay window 4k was compared with the toolbox's window k. Replay gave 0 windows more or fewer than the toolbox on the 4 s grid.
- The largest difference in the 12 numbers is 2.07e-06, and the limit is 0.0001.
- The largest difference in the probability is 5.63e-07, and the limit is 0.0001.
- The largest relative difference in the low-frequency sum is 5.33e-07. It has no limit.
- 32 windows are near a cut-off under requirement 27 of feature 4.
- An answer differs on 0 windows, and the peak differs on 0 windows.
- 0 windows or files failed the match rule.
- 0 of the 99 count rows differ from reference/results/pads_counts.csv, and 0 of them are not explained by the windows listed below.
- The result is pass.

## Windows where an answer or the peak differs

No window has a different answer or peak.

## Count rows that differ from pads_counts.csv

Every count row equals pads_counts.csv.
