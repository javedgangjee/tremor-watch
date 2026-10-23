# Table run of 30 minutes

## Pass checks

- PASS: one start, no reset or error. 0 bad lines
- PASS: sensor settings. ctrl1=0x6C ctrl2=0x26 ctrl3=0x66 ctrl7=0x03 fifo_ctrl=0x0D fifo_wtm=11 gyro_range_dps=1024 int1_level=0
- PASS: power chip. [{'pmu': 'ok', 'vbus': '1', 'battery': '0', 'battery_mv': '0', 'battery_percent': '-1'}]
- PASS: five tasks. sensor:core1/p12 pipeline:core1/p8 state:core0/p6 screen:core0/p5 usb:core0/p3
- PASS: every minute line. all present
- PASS: no losses. kind1_ends=0 overflow=0 full=0 read_error=0 stall=0 late=0 msg_drops=0 breaks=0 line_drops=0 kind1_lines=0
- PASS: reading counts agree. difference 11
- PASS: burst sizes and delay. bursts=18711 at_wtm=18711 largest=11 delay_us=5566
- PASS: rates near feature 1's rate. 2 rates, limits 114215870 to 114444530, rates [114351161, 114350493]
- PASS: stretch numbers. numbers [0, 1]
- PASS: drift ends beyond half a period. all beyond
- PASS: still on the table. 30 minutes
- PASS: screen updates. updates=1799, need 1620

## Stretches

| Stretch | Start (s) | Length (s) | Rate (uHz) | Ended by | Stamp error (us) |
|---|---|---|---|---|---|
| 0 | 0.000 | 746.958 | 114351161 | kind 2 time | 4382.5 |
| 1 | 747.054 | open | 114350493 | open |  |

## Counts

- Stretches: 2
- Ends of the first kind: 0
- Ends of the second kind: 1
- Closed stretch lengths in seconds: shortest 746.958, median 746.958, longest 746.958
- Rate changes in parts per million: -5.8
