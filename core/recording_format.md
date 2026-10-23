# Recording format

The watch writes the recording as text over its built-in USB port, which the laptop sees as /dev/cu.usbmodem101. The port is the chip's USB Serial/JTAG port, and the baud rate setting does not matter. Each line ends with a newline. core/record.h writes the record lines and parses the commands, and the feature 9 requirements in specs/features/09-usb-recording/requirements.md give the reasons.

## Where the recording starts

The chip's ROM writes its own boot text to the port before the firmware starts. A reader skips every line before the first B line. ESP-IDF's log and its crash text go to UART0 only, so they never reach the port. A crash shows in the recording as a new B line with its reset cause.

## Record lines

A record line starts with one upper-case letter and a comma. Its fields are separated by commas and hold no spaces. Every value is a whole number in decimal, apart from the table hash and the three detector numbers of the W line. Times are microseconds of the watch's 64-bit timer, which starts at 0 at boot, unless a field says otherwise.

| Line | Fields | Pattern |
|---|---|---|
| B | boot ID, reset cause, firmware version, table hash | `^B,(\d+),(\d+),(\d+),([0-9a-f]{64})$` |
| S | stretch, first reading, t0 in microseconds, rate in millionths of a reading per second, gyroscope range in degrees per second | `^S,(\d+),(\d+),(-?\d+),(\d+),(\d+)$` |
| T | first reading, number of readings, burst stamp in microseconds | `^T,(\d+),(\d+),(-?\d+)$` |
| R | reading number, gyroscope x, y, and z, accelerometer x, y, and z | `^R,(\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+)$` |
| W | stretch, window, result code, probability, low-frequency sum, peak frequency in Hz | `^W,(\d+),(\d*),([0-4]),([-+.0-9e]*),([-+.0-9e]*),([-+.0-9e]*)$` |
| F | time in microseconds, new face state | `^F,(-?\d+),([0-4])$` |
| D | time in microseconds, local time of the scheduled dose it answers | `^D,(-?\d+),(-?\d*)$` |
| A | command number, result number | `^A,([0-4]),([0-5])$` |

- The B line marks a boot. The boot ID is a random 32-bit number. The reset cause is the number that esp_reset_reason() gives. The firmware version is FIRMWARE_VERSION in firmware/main/tasks.h. The table hash is the 64 lower-case hexadecimal digits of DET_MODEL_SHA256 in core/detector_tables.h, which is the SHA-256 hash of the detector's model file.
- The S line starts a stretch. The first reading's number counts from power-on, and t0 is the stamp of the stretch's first burst. The rate is the whole number of millionths of a reading per second that the time rule holds, so 114.3302 readings a second is 114330200. The range is 1024.
- The T line records a burst. Its R lines follow it, one for each reading, numbered in order.
- The R line holds the raw counts of one reading. A gyroscope count divided by 32 gives degrees per second. An accelerometer count divided by 4096 gives g.
- The W line records one answer. The result codes are 0 for tremor, 1 for no tremor, 2 for arm moving, 3 for warming up, and 4 for sensor fault, as in core/window.h. The probability and the low-frequency sum are the shortest decimal text that reads back as the same 64-bit double. The peak is a 32-bit float with up to 9 significant digits. A number may use an exponent, as in 7.817677252158094e-05.
- A sensor fault answer has no window. Its W line leaves the window and the three numbers empty, as in `W,3,,4,,,`, and its stretch is the pipeline task's current stretch.
- The F line records a change of the shown face state. The states are 0 for Tremor, 1 for No tremor, 2 for Arm moving, 3 for Waiting, and 4 for Dose due, as in core/face.h. The time is the moment the state task changed the state.
- The D line records a dose taken. The second value is local time in microseconds since 1970, and it is empty when the dose answers no scheduled time.
- The A line answers one command, as the Commands section says.

## Stretches and the S line

The S line of a stretch comes before the stretch's first T line, and that T line's stamp equals t0. When the time rule has no rate for the stretch yet, as in the first stretch after power-on, the S line gives rate 0. When the time rule sets the rate, the watch writes the S line again with the same stretch number, first reading, and t0, and with the rate. A reader takes the last S line of each stretch number.

## Lines that do not fit

The watch puts each line into its USB send buffer with no wait. When the buffer has no room, because no program reads the port, the watch drops the whole line and counts it. No task ever waits on the port.

After a drop, the next line that fits first brings the B line and the latest S line again, in that order. So a recording that starts or restarts in the middle of a session still names its boot and its stretch. A reader sees a gap in the T numbers there, and it takes the repeated B line as the same boot when its boot ID is the same. Lines that sat in the send buffer while nobody read come out first.

## Commands

The laptop sends commands over the same port. A command is one line of at most 127 characters that ends with a newline, and a carriage return before the newline is allowed. The commands are in upper case, and their fields are separated by commas with no spaces. A whole number is an optional minus sign and 1 to 19 digits.

| Command | Fields | Ranges |
|---|---|---|
| `CLOCK,<utc_us>,<offset_min>` | the UTC time in microseconds since 1970 and the local offset in minutes | The time lies from 1577836800000000 (1 January 2020) to before 4102444800000000 (1 January 2100). The offset lies from -720 to 840. |
| `SCHEDULE[,<name>[,<minute>...]]` | the medicine name and up to six times as minutes of the local day | The name has 1 to 20 characters, and each is a letter, a digit, or one of `-`, `.`, `/`, and `+`. A minute lies from 0 to 1439, and no minute may come twice. |
| `SESSION` | none | none |
| `TONE,<0\|1>` | 0 turns the tone off and 1 turns it on | 0 or 1 |

- CLOCK sets the dose clock. The watch stamps the command when its newline arrives and sets the local time to the UTC time plus the offset at that stamp, so the time the line takes to arrive does not move the clock. The clock lives in memory only, so a restart leaves it unset until the next CLOCK command. Until the clock is set, the dose schedule stays off.
- SCHEDULE sets the medicine name and the dose times and keeps them in the chip's settings store. `SCHEDULE` with no fields turns the schedule off and clears the name. `SCHEDULE,<name>` keeps the name with no times.
- SESSION starts a new session. The share, the answers, and the doses start again, and the face shows Waiting until two answers agree.
- TONE turns the tone on or off and keeps the setting in the settings store. With nothing stored, the tone is on.
- An empty line gets no answer.

The watch answers each command with one A line. The command numbers are 0 for an unknown command, 1 for CLOCK, 2 for SCHEDULE, 3 for SESSION, and 4 for TONE. The result numbers are below.

| Result | Meaning |
|---|---|
| 0 | The watch applied the command. |
| 1 | The command is unknown. |
| 2 | The line breaks the format, or it is longer than 127 characters. |
| 3 | A value lies outside its range, or a schedule gives a time twice. |
| 4 | The watch applied the setting but could not store it, so a restart loses it. |
| 5 | The watch was busy and dropped the command, so the laptop may send it again. |

## Reset causes

The reset cause of the B line is the number of esp_reset_reason_t in ESP-IDF v6.1's esp_system.h.

| Number | Cause |
|---|---|
| 0 | The cause is unknown. |
| 1 | The chip powered on. |
| 2 | The external pin reset the chip. |
| 3 | The software called esp_restart(). |
| 4 | The software panicked, for example after a crash. |
| 5 | The interrupt watchdog fired. |
| 6 | The task watchdog fired. |
| 7 | Another watchdog fired. |
| 8 | The chip woke from deep sleep. |
| 9 | The supply voltage dropped too low. |
| 10 | The SDIO bus reset the chip. |
| 11 | The USB peripheral reset the chip, as a laptop's reset through the port does. |
| 12 | JTAG reset the chip. |
| 13 | An efuse error reset the chip. |
| 14 | A power glitch reset the chip. |
| 15 | The CPU locked up. |

## Diagnostic lines

The watch also writes diagnostic lines, such as START, TASK, STRETCH, ANSWER, FACE, SETTINGS, and the minute lines. They exist for the checks in tests/firmware/, and a reader of the recording skips them. A diagnostic line starts with an upper-case word of at least three characters, which holds upper-case letters, digits, and underscores and no comma. Its other fields have the form `key=value` with a space between them. The pattern `^[A-Z][A-Z0-9_]{2,}( |$)` tells a diagnostic line apart from a record line, because a record line has a comma after its first letter.

## Saved recordings

tools/watch_cli.py saves a recording as a gzip text file. Each line of the file holds the laptop's time in seconds since the port opened, with three decimals, then a tab, and then the text of one line from the watch. A line whose text starts with `> ` is a command that the laptop sent, or a note from a script, and not a line from the watch. tools/compare_session.py and the scripts in tests/firmware/ read this form. They drop the laptop time and the tab before they read the text.

`build/core/replay --recording FILE` reads the text lines with no laptop time, and FILE may be `-` for the standard input. It skips every line before the first B line, every line that starts with `> `, every diagnostic line, and every other line that does not start with a record letter and a comma. A line that starts with a record letter and a comma but breaks its pattern counts as a bad line and is skipped. A B line with a new boot ID starts the time rule and the pipe again, and a B line with the same boot ID is a repeat after a drop. replay keeps each T line until its R lines are in. It passes a burst on only when the burst holds exactly its count of R lines, numbered in order, and otherwise it drops the burst and counts it. The last burst of the file is left out without a count when its R lines are in order but too few, because the capture stopped in it. replay ignores the W, F, D, and A lines.

The T line holds no overflow flag, so replay finds every stretch start from the S lines. When an S line's stretch number is above every stretch number of the boot before it, replay notes the S line's first reading. When it passes on the burst that starts at that reading, it gives the time rule the overflow flag, so the stretch ends there as it did on the watch. The time rule still runs on every burst, so replay also finds a drift end by itself, and a gap in the T numbers ends replay's stretch where the watch's stretch went on.
