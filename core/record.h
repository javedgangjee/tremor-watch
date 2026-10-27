/*
 * record.h holds the recording line format and the command parser.
 *
 * core/recording_format.md describes every field. Each line function writes
 * one line with no newline into the caller's buffer and returns its length.
 * It returns 0 when the line and its zero byte do not fit in size bytes.
 *
 * The laptop sends four commands over the same port. rec_parse_command()
 * checks one command line, and the watch answers it with one A line from
 * rec_reply().
 *
 * The file has no static data that changes, and it allocates no memory.
 */

#ifndef RECORD_H
#define RECORD_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "dose.h"
#include "face.h"
#include "window.h"

/* A buffer of this many bytes holds the longest line and its zero byte. */
#define REC_LINE_MAX 128
/* A command line holds at most this many characters before its newline. */
#define REC_COMMAND_MAX 127

/* The CLOCK command accepts a UTC time from 1 January 2020 to before
 * 1 January 2100, in microseconds since 1970. */
#define REC_CLOCK_MIN_US INT64_C(1577836800000000)
#define REC_CLOCK_END_US INT64_C(4102444800000000)
/* The CLOCK command accepts a local offset from -720 to 840 minutes. */
#define REC_OFFSET_MIN (-720)
#define REC_OFFSET_MAX 840

/* The command numbers of the A line. REC_CMD_EMPTY marks an empty line,
 * which gets no answer. */
typedef enum {
    REC_CMD_UNKNOWN = 0,
    REC_CMD_CLOCK = 1,
    REC_CMD_SCHEDULE = 2,
    REC_CMD_SESSION = 3,
    REC_CMD_TONE = 4,
    REC_CMD_EMPTY = 5
} rec_cmd_t;

/* The result numbers of the A line. */
typedef enum {
    REC_DONE = 0,
    REC_UNKNOWN = 1,
    REC_BAD_FORMAT = 2,
    REC_REFUSED = 3,
    REC_NOT_STORED = 4,
    REC_BUSY = 5
} rec_result_t;

/* rec_command_t holds one parsed command. Each kind uses only its own fields. */
typedef struct {
    rec_cmd_t kind;
    /* CLOCK gives the UTC time in microseconds since 1970 and the local
     * offset in minutes. */
    int64_t utc_us;
    int32_t offset_min;
    /* SCHEDULE gives the name and the times in the order of the line. */
    dose_schedule_t schedule;
    /* TONE gives the tone setting. */
    bool tone_on;
} rec_command_t;

/* rec_boot() writes "B,<boot_id>,<reset_cause>,<version>,<hash>". */
size_t rec_boot(char *buf, size_t size, uint32_t boot_id, uint32_t reset_cause, uint32_t version, const char *hash);

/* rec_stretch() writes "S,<stretch>,<first>,<t0_us>,<rate_uhz>,<range_dps>".
 * The rate is 0 while the time rule has no rate for the stretch. */
size_t rec_stretch(char *buf, size_t size, uint32_t stretch, uint64_t first, int64_t t0_us, uint32_t rate_uhz,
    uint32_t range_dps);

/* rec_burst() writes "T,<first>,<count>,<stamp_us>". */
size_t rec_burst(char *buf, size_t size, uint64_t first, uint32_t count, int64_t stamp_us);

/* rec_reading() writes "R,<n>,<gx>,<gy>,<gz>,<ax>,<ay>,<az>" with the raw
 * counts. */
size_t rec_reading(char *buf, size_t size, uint64_t number, const int16_t gyro[3], const int16_t accel[3]);

/* rec_window() writes "W,<stretch>,<window>,<code>,<prob>,<below>,<peak>".
 * The probability and the low-frequency sum use the shortest text that reads
 * back as the same double, which is what %.17g gives on the watch. The peak
 * uses %.9g, so it reads back as the same float. An answer with no
 * window leaves the window and the three numbers empty. */
size_t rec_window(char *buf, size_t size, uint32_t stretch, bool has_window, uint32_t window, res_code_t code,
    double prob, double below, float peak_hz);

/* rec_face() writes "F,<time_us>,<state>". */
size_t rec_face(char *buf, size_t size, int64_t time_us, face_state_t state);

/* rec_dose() writes "D,<time_us>,<answers_local_us>". The second value is
 * empty when the dose answers no scheduled time. */
size_t rec_dose(char *buf, size_t size, const dose_entry_t *dose);

/* rec_reply() writes "A,<command>,<result>". */
size_t rec_reply(char *buf, size_t size, rec_cmd_t command, rec_result_t result);

/* rec_parse_command() reads one command line without its newline. It drops
 * one carriage return at the end of the line. It fills *out and sets
 * out->kind even when it refuses the line, so the answer can name the
 * command. It returns REC_DONE for a good command and for an empty line,
 * REC_UNKNOWN for an unknown command, REC_BAD_FORMAT for a line that breaks
 * the format, and REC_REFUSED for a value out of its range. A time given
 * twice in a schedule is left to dose_set_schedule(). */
rec_result_t rec_parse_command(const char *line, rec_command_t *out);

/* rec_clock_offset_us() gives the dose clock's offset for a CLOCK command
 * whose newline arrived at the timer value stamp_us. It is
 * utc_us + offset_min * 60000000 - stamp_us. */
int64_t rec_clock_offset_us(int64_t utc_us, int32_t offset_min, int64_t stamp_us);

#endif /* RECORD_H */
