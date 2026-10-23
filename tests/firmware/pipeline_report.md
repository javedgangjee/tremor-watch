# Pipeline run of 30 minutes

## Pass checks of table_run.py

- PASS: one start, no reset or error. 0 bad lines
- PASS: sensor settings. ctrl1=0x6C ctrl2=0x26 ctrl3=0x66 ctrl7=0x03 fifo_ctrl=0x0D fifo_wtm=11 gyro_range_dps=1024 int1_level=0
- PASS: power chip. [{'pmu': 'ok', 'vbus': '1', 'battery': '0', 'battery_mv': '0', 'battery_percent': '-1'}]
- PASS: five tasks. sensor:core1/p12 pipeline:core1/p8 state:core0/p6 screen:core0/p5 usb:core0/p3
- PASS: every minute line. all present
- PASS: no losses. kind1_ends=0 overflow=0 full=0 read_error=0 stall=0 late=0 msg_drops=0 breaks=0 line_drops=0 kind1_lines=0
- PASS: reading counts agree. difference 11
- PASS: burst sizes and delay. bursts=18711 at_wtm=18711 largest=11 delay_us=5468
- PASS: rates near feature 1's rate. 1 rates, limits 114215870 to 114444530, rates [114351469]
- PASS: stretch numbers. numbers [0]
- PASS: drift ends beyond half a period. all beyond
- PASS: still on the table. 30 minutes
- PASS: screen updates. updates=1800, need 1620

## Pass checks of feature 8

- PASS: detector ready, no end request. DETECTOR_INIT lines [{'ok': '1'}], 0 error or end request lines
- PASS: window numbers and codes. 0 problems
- PASS: an answer each second. 0 problems
- PASS: a GAP line for each later stretch. 0 problems
- PASS: face follows the model. 0 problems
- PASS: share counts match the answers. 0 problems
- PASS: no faults or drops. faults=0 end_requests=0 answer_drops=0 screen_drops=0 pipeline=0
- PASS: screen shows the face. face=1 face_changes=1, want face 1 and 1 changes

## Measurements

- The detector run time in microseconds is minimum 6769, median 6869, maximum 8803.
- The delay from the burst's stamp to the end of the run in microseconds has a median of 12422 and a maximum of 62675.
- Stretch 0 gave its window 0 answer 10.020 seconds after its t0.
- The answers by code are tremor 0, no tremor 1795, arm moving 0, warming up 1, sensor fault 0.
- 0 tremor answers came on a still table, and each one is a false alarm.
- The share at minute 30 is 0.000000.
- The log holds 1 FACE lines.
- The pipeline task's free stack in bytes was 2240, 2368, 2576.
- The state task's free stack in bytes was 2488, 2520, 2536.
- The gap path did not run on the watch, because no stretch ended.

## Stretches

| Stretch | t0 (us) | Rate (uHz) | Ended by |
|---|---|---|---|
| 0 | 238216 | 114351469 | open |
