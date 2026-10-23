# Drop run

## Pass checks

- PASS: one boot. 1 START lines, 1 different B lines
- PASS: every line is whole. 0 bad lines
- PASS: T lines on both sides. 730 before CLOSE, 1569 after OPEN
- PASS: no task waited. line_drops=0 msg_drops=0 record_drops=0 answer_drops=0 faults=0 screen_drops=0
- PASS: answers went on. widest pair 62 windows, 0 problems
- PASS: gap and repeated lines. port_drops=7488 restarts=1 gap at the close=1 other gaps=1

## Measurements

- The last USB_MINUTE line gives port_drops=7488 and restarts=1.
- The watch dropped 7488 lines while nobody read the port.
- The laptop lost the lines from the `> CLOSE` line to the first text after the `> OPEN` line, which is `> PARTIAL 9,-854`.
- The gap at the close runs from the T line at reading 8019 to the T line at reading 8052. It spans 22 readings in the T numbers, and the R lines of 28 readings are missing.
- The watch's own gap runs from the T line at reading 8129 to the T line at reading 14883, and it spans 6743 readings.
- 95 lines from before the close arrived after the OPEN line.
