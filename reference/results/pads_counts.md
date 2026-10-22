# PADS tremor counts

- The run date is 2026-10-22.
- The toolbox is ParaDigMa 1.1.2 with scikit-learn 1.6.0.
- The model file's SHA-256 hash is 4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e.
- The data is PADS 1.0.0.
- The run read 10318 files, and 0 files were missing or unreadable.
- Each recording ran on its own with the default TremorConfig, after the first 50 rows were cut.
- A window fired when the toolbox's pred_tremor_checked is 1.

The share is the part of windows in which the toolbox fired. It is not a hit rate in the Parkinson's or other movement disorder columns, because PADS does not say when tremor was present. A patient window that did not fire may hold no tremor.

| Task | Group | Wrist | Windows | Fired | Share |
| --- | --- | --- | ---: | ---: | ---: |
| Relaxed | healthy | left | 316 | 16 | 0.0506 |
| Relaxed | healthy | right | 316 | 11 | 0.0348 |
| Relaxed | healthy | both | 632 | 27 | 0.0427 |
| Relaxed | Parkinson's | left | 1104 | 266 | 0.2409 |
| Relaxed | Parkinson's | right | 1104 | 245 | 0.2219 |
| Relaxed | Parkinson's | both | 2208 | 511 | 0.2314 |
| Relaxed | other movement disorder | left | 456 | 137 | 0.3004 |
| Relaxed | other movement disorder | right | 456 | 137 | 0.3004 |
| Relaxed | other movement disorder | both | 912 | 274 | 0.3004 |
| RelaxedTask | healthy | left | 316 | 19 | 0.0601 |
| RelaxedTask | healthy | right | 316 | 11 | 0.0348 |
| RelaxedTask | healthy | both | 632 | 30 | 0.0475 |
| RelaxedTask | Parkinson's | left | 1104 | 299 | 0.2708 |
| RelaxedTask | Parkinson's | right | 1104 | 265 | 0.2400 |
| RelaxedTask | Parkinson's | both | 2208 | 564 | 0.2554 |
| RelaxedTask | other movement disorder | left | 456 | 124 | 0.2719 |
| RelaxedTask | other movement disorder | right | 456 | 124 | 0.2719 |
| RelaxedTask | other movement disorder | both | 912 | 248 | 0.2719 |
| StretchHold | healthy | left | 158 | 0 | 0.0000 |
| StretchHold | healthy | right | 158 | 0 | 0.0000 |
| StretchHold | healthy | both | 316 | 0 | 0.0000 |
| StretchHold | Parkinson's | left | 552 | 63 | 0.1141 |
| StretchHold | Parkinson's | right | 552 | 51 | 0.0924 |
| StretchHold | Parkinson's | both | 1104 | 114 | 0.1033 |
| StretchHold | other movement disorder | left | 228 | 36 | 0.1579 |
| StretchHold | other movement disorder | right | 228 | 39 | 0.1711 |
| StretchHold | other movement disorder | both | 456 | 75 | 0.1645 |
| LiftHold | healthy | left | 158 | 0 | 0.0000 |
| LiftHold | healthy | right | 158 | 0 | 0.0000 |
| LiftHold | healthy | both | 316 | 0 | 0.0000 |
| LiftHold | Parkinson's | left | 552 | 44 | 0.0797 |
| LiftHold | Parkinson's | right | 552 | 36 | 0.0652 |
| LiftHold | Parkinson's | both | 1104 | 80 | 0.0725 |
| LiftHold | other movement disorder | left | 228 | 21 | 0.0921 |
| LiftHold | other movement disorder | right | 228 | 19 | 0.0833 |
| LiftHold | other movement disorder | both | 456 | 40 | 0.0877 |
| HoldWeight | healthy | left | 158 | 5 | 0.0316 |
| HoldWeight | healthy | right | 158 | 2 | 0.0127 |
| HoldWeight | healthy | both | 316 | 7 | 0.0222 |
| HoldWeight | Parkinson's | left | 552 | 153 | 0.2772 |
| HoldWeight | Parkinson's | right | 552 | 126 | 0.2283 |
| HoldWeight | Parkinson's | both | 1104 | 279 | 0.2527 |
| HoldWeight | other movement disorder | left | 228 | 71 | 0.3114 |
| HoldWeight | other movement disorder | right | 228 | 67 | 0.2939 |
| HoldWeight | other movement disorder | both | 456 | 138 | 0.3026 |
| PointFinger | healthy | left | 158 | 0 | 0.0000 |
| PointFinger | healthy | right | 158 | 0 | 0.0000 |
| PointFinger | healthy | both | 316 | 0 | 0.0000 |
| PointFinger | Parkinson's | left | 552 | 1 | 0.0018 |
| PointFinger | Parkinson's | right | 552 | 2 | 0.0036 |
| PointFinger | Parkinson's | both | 1104 | 3 | 0.0027 |
| PointFinger | other movement disorder | left | 228 | 2 | 0.0088 |
| PointFinger | other movement disorder | right | 228 | 0 | 0.0000 |
| PointFinger | other movement disorder | both | 456 | 2 | 0.0044 |
| DrinkGlas | healthy | left | 158 | 1 | 0.0063 |
| DrinkGlas | healthy | right | 158 | 0 | 0.0000 |
| DrinkGlas | healthy | both | 316 | 1 | 0.0032 |
| DrinkGlas | Parkinson's | left | 552 | 13 | 0.0236 |
| DrinkGlas | Parkinson's | right | 552 | 7 | 0.0127 |
| DrinkGlas | Parkinson's | both | 1104 | 20 | 0.0181 |
| DrinkGlas | other movement disorder | left | 228 | 2 | 0.0088 |
| DrinkGlas | other movement disorder | right | 228 | 3 | 0.0132 |
| DrinkGlas | other movement disorder | both | 456 | 5 | 0.0110 |
| CrossArms | healthy | left | 158 | 0 | 0.0000 |
| CrossArms | healthy | right | 158 | 0 | 0.0000 |
| CrossArms | healthy | both | 316 | 0 | 0.0000 |
| CrossArms | Parkinson's | left | 552 | 35 | 0.0634 |
| CrossArms | Parkinson's | right | 552 | 24 | 0.0435 |
| CrossArms | Parkinson's | both | 1104 | 59 | 0.0534 |
| CrossArms | other movement disorder | left | 228 | 28 | 0.1228 |
| CrossArms | other movement disorder | right | 228 | 21 | 0.0921 |
| CrossArms | other movement disorder | both | 456 | 49 | 0.1075 |
| TouchIndex | healthy | left | 158 | 0 | 0.0000 |
| TouchIndex | healthy | right | 158 | 0 | 0.0000 |
| TouchIndex | healthy | both | 316 | 0 | 0.0000 |
| TouchIndex | Parkinson's | left | 552 | 2 | 0.0036 |
| TouchIndex | Parkinson's | right | 552 | 2 | 0.0036 |
| TouchIndex | Parkinson's | both | 1104 | 4 | 0.0036 |
| TouchIndex | other movement disorder | left | 228 | 1 | 0.0044 |
| TouchIndex | other movement disorder | right | 228 | 0 | 0.0000 |
| TouchIndex | other movement disorder | both | 456 | 1 | 0.0022 |
| TouchNose | healthy | left | 158 | 0 | 0.0000 |
| TouchNose | healthy | right | 158 | 0 | 0.0000 |
| TouchNose | healthy | both | 316 | 0 | 0.0000 |
| TouchNose | Parkinson's | left | 552 | 2 | 0.0036 |
| TouchNose | Parkinson's | right | 552 | 1 | 0.0018 |
| TouchNose | Parkinson's | both | 1104 | 3 | 0.0027 |
| TouchNose | other movement disorder | left | 228 | 0 | 0.0000 |
| TouchNose | other movement disorder | right | 228 | 0 | 0.0000 |
| TouchNose | other movement disorder | both | 456 | 0 | 0.0000 |
| Entrainment | healthy | left | 316 | 7 | 0.0222 |
| Entrainment | healthy | right | 316 | 8 | 0.0253 |
| Entrainment | healthy | both | 632 | 15 | 0.0237 |
| Entrainment | Parkinson's | left | 1104 | 98 | 0.0888 |
| Entrainment | Parkinson's | right | 1104 | 79 | 0.0716 |
| Entrainment | Parkinson's | both | 2208 | 177 | 0.0802 |
| Entrainment | other movement disorder | left | 456 | 32 | 0.0702 |
| Entrainment | other movement disorder | right | 456 | 23 | 0.0504 |
| Entrainment | other movement disorder | both | 912 | 55 | 0.0603 |
