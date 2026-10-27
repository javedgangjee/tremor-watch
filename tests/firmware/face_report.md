# Face run

## Pass checks

- PASS: one B line and the format. B,2694533211,11,11,4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e
- PASS: screen start. SCREEN_START at_us=581951 display=ok touch=ok audio=ok button=ok face=ok internal_free=162959 internal_largest=90112
- PASS: dashes before the clock. 2 SCREEN_VIEW lines
- PASS: the face of each F line. 6 F lines
- PASS: time after the clock. 29 SCREEN_VIEW lines
- PASS: next dose after each schedule. 2 schedules
- PASS: first dose due. 489889 us after the dose time
- PASS: first dose ends. 489849 us after the dose time plus 900 s
- PASS: second dose and session. 0 problems
- PASS: blocks and share. last SCREEN_VIEW gives (2, '00', 0)
- PASS: minute lines. 19 SCREEN_MINUTE lines
- PASS: nobody touched the watch. 0 lines
- PASS: settings put back. tone=1 times=none name=None

## Measurements

- SCREEN_START gives internal_free=162959 and internal_largest=90112.
- SCREEN_MINUTE gives stack_free from 2312 to 2312 bytes.
- SCREEN_MINUTE gives internal_min from 47972 to 47972 bytes.
- STATE_MINUTE gives stack_free from 2188 to 2204 bytes.
- USB_MINUTE gives stack_free from 2636 to 2700 bytes.
- Dose 1 became due 0.490 seconds after its time.
- Dose 2 became due 0.490 seconds after its time.
- The log holds 31 SCREEN_VIEW lines.
