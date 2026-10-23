# Recording run of 30 minutes

## Pass checks of table_run.py

- PASS: one start, no reset or error. 0 bad lines
- PASS: sensor settings. ctrl1=0x6C ctrl2=0x26 ctrl3=0x66 ctrl7=0x03 fifo_ctrl=0x0D fifo_wtm=11 gyro_range_dps=1024 int1_level=0
- PASS: power chip. [{'pmu': 'ok', 'vbus': '1', 'battery': '0', 'battery_mv': '0', 'battery_percent': '-1'}]
- PASS: five tasks. sensor:core1/p12 pipeline:core1/p8 state:core0/p6 screen:core0/p5 usb:core0/p3
- PASS: every minute line. all present
- PASS: no losses. kind1_ends=0 overflow=0 full=0 read_error=0 stall=0 late=0 msg_drops=0 breaks=0 line_drops=0 kind1_lines=0
- PASS: reading counts agree. difference 11
- PASS: burst sizes and delay. bursts=18710 at_wtm=18710 largest=11 delay_us=5561
- PASS: rates near feature 1's rate. 1 rates, limits 114215870 to 114444530, rates [114347777]
- PASS: stretch numbers. numbers [0]
- PASS: drift ends beyond half a period. all beyond
- PASS: still on the table. 30 minutes
- PASS: screen updates. updates=1800, need 1620

## Pass checks of pipeline_run.py

- PASS: detector ready, no end request. DETECTOR_INIT lines [{'ok': '1'}], 0 error or end request lines
- PASS: window numbers and codes. 0 problems
- PASS: an answer each second. 0 problems
- PASS: a GAP line for each later stretch. 0 problems
- PASS: face follows the model. 0 problems
- PASS: share counts match the answers. 0 problems
- PASS: no faults or drops. faults=0 end_requests=0 answer_drops=0 screen_drops=0 pipeline=0
- PASS: screen shows the face. face=1 face_changes=1, want face 1 and 1 changes

## Pass checks of the record lines

- PASS: one B line before START. B,2274443476,11,9,4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e
- PASS: every line follows the format. 0 bad lines
- PASS: S lines. 1 stretches, 0 problems
- PASS: T and R lines. 18732 T lines, 206041 readings, 0 problems
- PASS: a W line for each answer. 1798 W lines, 0 problems
- PASS: an F line for each face change. 1 FACE lines and 1 F lines
- PASS: no D or A line. 0 lines
- PASS: no drops and no commands. record_drops=0 line_drops=0 port_drops=0 restarts=0 commands=0

## Measurements

- The log holds 103 lines before the B line.
- USB_MINUTE gives 4439 bytes a second over 30 minutes.
- The log gives 4439 bytes a second and 127 lines a second.
- The largest gap between two line arrivals after the first minute is 0.103 seconds.
- PIPELINE_MINUTE gives the free stack in bytes at each minute as 2528, 2368, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240, 2240.
- STATE_MINUTE gives the free stack in bytes at each minute as 2268, 2268, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252.
- USB_MINUTE gives the free stack in bytes at each minute as 2700, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636.
- The detector run time in microseconds is minimum 6787, median 6868, maximum 8857.
- The delay from the burst's stamp to the end of the run in microseconds has a median of 12697 and a maximum of 60076.
- Stretch 0 gave its window 0 answer 10.020 seconds after its t0.
- The answers by code are tremor 0, no tremor 1797, arm moving 0, warming up 1, sensor fault 0.
- 0 tremor answers came on a still table, and each one is a false alarm.
- The share at minute 30 is 0.000000.
- The log holds 1 FACE lines.
- The pipeline task's free stack in bytes was 2240, 2368, 2528.
- The state task's free stack in bytes was 2252, 2268.
- The gap path did not run on the watch, because no stretch ended.

## Stretches

| Stretch | t0 (us) | Rate (uHz) | Ended by |
|---|---|---|---|
| 0 | 234273 | 114347777 | open |
