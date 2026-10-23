# Drop run

## Pass checks

- PASS: one boot. 1 START lines, 1 different B lines
- PASS: every line is whole. 0 bad lines
- PASS: T lines on both sides. 730 before CLOSE, 1569 after OPEN
- PASS: no task waited. line_drops=0 msg_drops=0 record_drops=0 answer_drops=0 faults=0 screen_drops=0
- PASS: answers went on. widest pair 62 windows, 0 problems
- FAIL: gap and repeated lines. port_drops=7482 restarts=1 gaps=2, first: 2 gaps in the T numbers

## Measurements

- The last USB_MINUTE line gives port_drops=7482 and restarts=1.
- The watch dropped 7482 lines while nobody read the port.
- The gap in the T numbers spans 22 readings.
- 97 lines from before the close arrived after the OPEN line.
