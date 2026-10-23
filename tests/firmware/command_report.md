# Command run

## Pass checks

- PASS: boot 1. B,317511800,11,9,4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e
- PASS: nine bad commands. 0 problems
- PASS: tone off. answer A,4,0, SETTINGS [{'source': 'command', 'store': 'ok', 'tone': '0', 'times': 'none'}]
- PASS: schedule. SCHEDULE,TestDose,303 gets A,2,0, SETTINGS [{'source': 'command', 'store': 'ok', 'tone': '0', 'times': '303', 'name': 'TestDose'}]
- PASS: restart keeps the settings. B,3421497796,11,9,4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e
- PASS: clock. difference 0 us
- PASS: dose becomes due. 876355 us after T
- PASS: due dose ends. 876332 us after T + 900 s
- PASS: new session. 0 problems
- PASS: tone on. answer A,4,0, SETTINGS [{'source': 'command', 'store': 'ok', 'tone': '1', 'times': '303', 'name': 'TestDose'}]
- PASS: settings put back. commands and answers [('SCHEDULE', 'A,2,0'), ('TONE,1', 'A,4,0')], want ['SCHEDULE', 'TONE,1']
- PASS: format in both boots. 0 problems

## Measurements

- The due F line came 0.876 seconds after T.
- The F line that ended the due state came 0.876 seconds after T + 900 seconds.
- The clock difference was 0 microseconds.
- Boot 2's reset cause was 11.
- The time from a command to its answer on the laptop was median 0.011 and maximum 0.021 seconds over 16 commands.
- STATE_MINUTE gives the free stack in bytes as 2268, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252, 2252.
- USB_MINUTE gives the free stack in bytes as 2700, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636, 2636.
