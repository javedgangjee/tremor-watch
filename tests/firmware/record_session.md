# Session comparison of record_log.txt.gz

- The recording is tests/firmware/record_log.txt.gz.
- The toolbox is ParaDigMa 1.1.2.
- The boots are 2274443476.
- replay wrote: replay: lines=228639 bad=0 dropped_bursts=0 boots=1 stretches=1 windows=1798
- The result is pass.

## Stretches

| Boot | Stretch | First reading | t0 (us) | Watch rate (uHz) | Replay rate (uHz) | Checked |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| 2274443476 | 0 | 0 | 234273 | 114347777 | 114347777 | yes, readings 0 to 206040 |

## Replay and the watch

- The run compared 1797 windows, from window 1 to window 1797. Window 0 of each stretch is left out.
- 0 windows differ in the code, the peak, or the probability.
- The largest difference in the probability is 2.51e-10, and the limit is 0.0001.
- The probability's text differs from replay's shortest text on 1790 windows.
- 0 windows were not checked because they lie after a checked part that ended at a gap.
- 0 windows were not checked because they lie in a stretch that started before the recording.
- 0 replay windows at the end of a boot have no W line, which is allowed.
- replay gave 0 windows in stretches that it starts after a gap with no S line, and they are not compared.
- 0 checks failed.

No window differs.

## The toolbox and the watch

- The toolbox's window k was compared with the watch's window 4k from k = 1 on. The toolbox's codes agree on 449 of 449 windows, which is 100.0 percent.
- The largest difference in the probability is 1.02e-09.
- The toolbox's agreement has no pass limit.

No window differs.

## Share

- Over the 449 windows that the toolbox compares, the share of still time with tremor is 0.0 percent from the watch's codes and 0.0 percent from the toolbox's codes.
- The share has no pass limit.
