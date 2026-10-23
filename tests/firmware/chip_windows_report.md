# Saved windows on the chip

## Pass checks

- PASS: CRC rule matches zlib. want 0xcbf43926, lines [{'value': '0xcbf43926'}]
- PASS: embedded windows. want bytes=1545600 crc32=0x841aeb95, lines [{'windows': '322', 'bytes': '1545600', 'crc32': '0x841aeb95'}]
- PASS: every window ran twice. 644 runs
- PASS: pass 1 matches the toolbox. 0 failures
- PASS: pass 2 equals pass 1. every window has the same text

## Pass 1 against the toolbox

- The largest difference in the 12 numbers is 3.66e-06.
- The largest difference in the probability is 2.66e-07.
- The largest relative difference in the low-frequency sum is 1.1e-06.
- 31 windows are near a cut-off, and 11 of them are near a peak tie.
- An answer differs on 0 windows, and the peak differs on 0.

## Detector run time on the chip

| Pass | Runs | Minimum (us) | Median (us) | Maximum (us) |
|---|---|---|---|---|
| 1 | 322 | 6603 | 6612.5 | 6803 |
| 2 | 322 | 6603 | 6619 | 6646 |
