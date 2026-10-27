/*
 * record.c holds the recording line format and the command parser. See
 * record.h. The parser reads the line in place and keeps no copy of it.
 *
 * The W line writes the probability and the low-frequency sum as the shortest
 * text that reads back as the same double, laid out as %.17g lays it out.
 * picolibc on the watch prints %.17g that way, so the W line matches the
 * ANSWER line. The laptop's C library prints all 17 digits, so this file finds
 * the shortest text itself and both sides agree.
 */

#include "record.h"

#include <inttypes.h>
#include <math.h>
#include <stdlib.h>
#include <stdio.h>
#include <string.h>

/* A whole number has at most this many digits. */
#define WHOLE_DIGITS_MAX 19
/* A double reads back from at most this many significant digits. */
#define DOUBLE_DIGITS_MAX 17
/* The text of one number holds at most this many bytes with its zero byte. */
#define NUMBER_MAX 40
/* A minute of the local day lies from 0 to 1439. */
#define MINUTE_MAX (DOSE_DAY_MINUTES - 1)
#define MINUTE_US INT64_C(60000000)

/* One comma-separated field of a command line. */
typedef struct {
    const char *p;
    size_t n;
} field_t;

/* Walks the fields of a command line. */
typedef struct {
    const char *p;
    const char *end;
    bool done;
} cursor_t;

/* Gives the length that snprintf() wrote, or 0 when the line and its zero
 * byte did not fit. */
static size_t finish(int n, size_t size)
{
    if (n < 0 || (size_t)n >= size) {
        return 0;
    }
    return (size_t)n;
}

size_t rec_boot(char *buf, size_t size, uint32_t boot_id, uint32_t reset_cause, uint32_t version, const char *hash)
{
    return finish(snprintf(buf, size, "B,%" PRIu32 ",%" PRIu32 ",%" PRIu32 ",%s", boot_id, reset_cause, version, hash),
        size);
}

size_t rec_stretch(char *buf, size_t size, uint32_t stretch, uint64_t first, int64_t t0_us, uint32_t rate_uhz,
    uint32_t range_dps)
{
    return finish(snprintf(buf, size, "S,%" PRIu32 ",%" PRIu64 ",%" PRId64 ",%" PRIu32 ",%" PRIu32, stretch, first,
                      t0_us, rate_uhz, range_dps),
        size);
}

size_t rec_burst(char *buf, size_t size, uint64_t first, uint32_t count, int64_t stamp_us)
{
    return finish(snprintf(buf, size, "T,%" PRIu64 ",%" PRIu32 ",%" PRId64, first, count, stamp_us), size);
}

size_t rec_reading(char *buf, size_t size, uint64_t number, const int16_t gyro[3], const int16_t accel[3])
{
    return finish(snprintf(buf, size, "R,%" PRIu64 ",%d,%d,%d,%d,%d,%d", number, (int)gyro[0], (int)gyro[1],
                      (int)gyro[2], (int)accel[0], (int)accel[1], (int)accel[2]),
        size);
}

/* Writes the shortest text that reads back as v, laid out as %.17g lays it
 * out. It finds the fewest significant digits from 1 to 17 that read back as
 * v. It writes them in fixed form when the exponent lies from -4 to 16 and in
 * exponent form otherwise, with no trailing zeros. */
static void shortest_double(char out[NUMBER_MAX], double v)
{
    if (!isfinite(v)) {
        snprintf(out, NUMBER_MAX, "%.17g", v);
        return;
    }
    char e[NUMBER_MAX];
    for (int p = 1; p <= DOUBLE_DIGITS_MAX; p++) {
        snprintf(e, sizeof e, "%.*e", p - 1, v);
        if (strtod(e, NULL) == v) {
            break;
        }
    }
    /* e holds an optional minus sign, the digits with a point after the
     * first, the letter e, and the exponent. */
    const char *s = e;
    bool negative = *s == '-';
    if (negative) {
        s++;
    }
    char digits[DOUBLE_DIGITS_MAX + 1];
    int n = 0;
    for (; *s != 'e' && *s != '\0'; s++) {
        if (*s >= '0' && *s <= '9' && n < DOUBLE_DIGITS_MAX) {
            digits[n++] = *s;
        }
    }
    int exponent = *s == 'e' ? atoi(s + 1) : 0;
    while (n > 1 && digits[n - 1] == '0') {
        n--;
    }
    digits[n] = '\0';

    char *o = out;
    if (negative) {
        *o++ = '-';
    }
    if (exponent < -4 || exponent >= DOUBLE_DIGITS_MAX) {
        *o++ = digits[0];
        if (n > 1) {
            *o++ = '.';
            memcpy(o, digits + 1, (size_t)(n - 1));
            o += n - 1;
        }
        snprintf(o, (size_t)(out + NUMBER_MAX - o), "e%c%02d", exponent < 0 ? '-' : '+', abs(exponent));
        return;
    }
    if (exponent < 0) {
        *o++ = '0';
        *o++ = '.';
        for (int i = -1; i > exponent; i--) {
            *o++ = '0';
        }
        memcpy(o, digits, (size_t)n);
        o += n;
    } else {
        for (int i = 0; i <= exponent; i++) {
            *o++ = i < n ? digits[i] : '0';
        }
        if (n > exponent + 1) {
            *o++ = '.';
            memcpy(o, digits + exponent + 1, (size_t)(n - exponent - 1));
            o += n - exponent - 1;
        }
    }
    *o = '\0';
}

size_t rec_window(char *buf, size_t size, uint32_t stretch, bool has_window, uint32_t window, res_code_t code,
    double prob, double below, float peak_hz)
{
    if (!has_window) {
        return finish(snprintf(buf, size, "W,%" PRIu32 ",,%d,,,", stretch, (int)code), size);
    }
    char prob_text[NUMBER_MAX];
    char below_text[NUMBER_MAX];
    shortest_double(prob_text, prob);
    shortest_double(below_text, below);
    return finish(snprintf(buf, size, "W,%" PRIu32 ",%" PRIu32 ",%d,%s,%s,%.9g", stretch, window, (int)code, prob_text,
                      below_text, (double)peak_hz),
        size);
}

size_t rec_face(char *buf, size_t size, int64_t time_us, face_state_t state)
{
    return finish(snprintf(buf, size, "F,%" PRId64 ",%d", time_us, (int)state), size);
}

size_t rec_dose(char *buf, size_t size, const dose_entry_t *dose)
{
    if (dose->answers_local_us == DOSE_NONE) {
        return finish(snprintf(buf, size, "D,%" PRId64 ",", dose->time_us), size);
    }
    return finish(snprintf(buf, size, "D,%" PRId64 ",%" PRId64, dose->time_us, dose->answers_local_us), size);
}

size_t rec_reply(char *buf, size_t size, rec_cmd_t command, rec_result_t result)
{
    return finish(snprintf(buf, size, "A,%d,%d", (int)command, (int)result), size);
}

/* Gives the next field, or returns false when no field is left. A line with n
 * commas has n + 1 fields, and a field may be empty. */
static bool next_field(cursor_t *c, field_t *f)
{
    if (c->done) {
        return false;
    }
    const char *q = c->p;
    while (q < c->end && *q != ',') {
        q++;
    }
    f->p = c->p;
    f->n = (size_t)(q - c->p);
    if (q < c->end) {
        c->p = q + 1;
    } else {
        c->done = true;
    }
    return true;
}

static bool same(const field_t *f, const char *word)
{
    size_t n = strlen(word);
    return f->n == n && memcmp(f->p, word, n) == 0;
}

/* Reads an optional minus sign and 1 to 19 digits. A value beyond the 64-bit
 * range becomes the nearest 64-bit value, which lies outside every range that
 * a command accepts. */
static bool parse_whole(const field_t *f, int64_t *out)
{
    size_t i = 0;
    bool negative = false;
    if (f->n > 0 && f->p[0] == '-') {
        negative = true;
        i = 1;
    }
    size_t digits = f->n - i;
    if (digits < 1 || digits > WHOLE_DIGITS_MAX) {
        return false;
    }
    uint64_t value = 0;
    for (; i < f->n; i++) {
        char ch = f->p[i];
        if (ch < '0' || ch > '9') {
            return false;
        }
        value = value * 10u + (uint64_t)(ch - '0');
    }
    if (value > (uint64_t)INT64_MAX) {
        *out = negative ? INT64_MIN : INT64_MAX;
    } else {
        *out = negative ? -(int64_t)value : (int64_t)value;
    }
    return true;
}

/* True for a letter, a digit, or one of - . / + */
static bool name_char(char ch)
{
    return (ch >= 'A' && ch <= 'Z') || (ch >= 'a' && ch <= 'z') || (ch >= '0' && ch <= '9') || ch == '-' ||
        ch == '.' || ch == '/' || ch == '+';
}

static rec_result_t parse_clock(cursor_t *c, rec_command_t *out)
{
    field_t utc;
    field_t offset;
    field_t extra;
    if (!next_field(c, &utc) || !next_field(c, &offset) || next_field(c, &extra)) {
        return REC_BAD_FORMAT;
    }
    int64_t utc_us = 0;
    int64_t offset_min = 0;
    if (!parse_whole(&utc, &utc_us) || !parse_whole(&offset, &offset_min)) {
        return REC_BAD_FORMAT;
    }
    if (utc_us < REC_CLOCK_MIN_US || utc_us >= REC_CLOCK_END_US || offset_min < REC_OFFSET_MIN ||
        offset_min > REC_OFFSET_MAX) {
        return REC_REFUSED;
    }
    out->utc_us = utc_us;
    out->offset_min = (int32_t)offset_min;
    return REC_DONE;
}

static rec_result_t parse_schedule(cursor_t *c, rec_command_t *out)
{
    field_t name;
    if (!next_field(c, &name)) {
        /* SCHEDULE with no fields turns the schedule off and clears the name. */
        return REC_DONE;
    }
    if (name.n == 0) {
        return REC_BAD_FORMAT;
    }
    for (size_t i = 0; i < name.n; i++) {
        if (!name_char(name.p[i])) {
            return REC_BAD_FORMAT;
        }
    }
    bool refused = name.n > DOSE_NAME_MAX;
    uint32_t count = 0;
    field_t minute;
    while (next_field(c, &minute)) {
        int64_t value = 0;
        if (!parse_whole(&minute, &value)) {
            return REC_BAD_FORMAT;
        }
        if (value < 0 || value > MINUTE_MAX) {
            refused = true;
        } else if (count < DOSE_MAX_TIMES) {
            out->schedule.minutes[count] = (uint16_t)value;
        }
        count++;
    }
    if (refused || count > DOSE_MAX_TIMES) {
        memset(out->schedule.minutes, 0, sizeof out->schedule.minutes);
        return REC_REFUSED;
    }
    memcpy(out->schedule.name, name.p, name.n);
    out->schedule.name[name.n] = '\0';
    out->schedule.count = (uint8_t)count;
    return REC_DONE;
}

static rec_result_t parse_tone(cursor_t *c, rec_command_t *out)
{
    field_t value;
    field_t extra;
    if (!next_field(c, &value) || next_field(c, &extra)) {
        return REC_BAD_FORMAT;
    }
    int64_t on = 0;
    if (!parse_whole(&value, &on)) {
        return REC_BAD_FORMAT;
    }
    if (on != 0 && on != 1) {
        return REC_REFUSED;
    }
    out->tone_on = on == 1;
    return REC_DONE;
}

rec_result_t rec_parse_command(const char *line, rec_command_t *out)
{
    memset(out, 0, sizeof *out);
    out->kind = REC_CMD_UNKNOWN;

    /* The scan stops two characters past the limit, which is enough to tell
     * that a line is too long. */
    size_t len = 0;
    while (len <= REC_COMMAND_MAX + 1 && line[len] != '\0') {
        len++;
    }
    if (len > 0 && line[len] == '\0' && line[len - 1] == '\r') {
        len--;
    }
    if (len > REC_COMMAND_MAX) {
        return REC_BAD_FORMAT;
    }
    if (len == 0) {
        out->kind = REC_CMD_EMPTY;
        return REC_DONE;
    }

    cursor_t c = {line, line + len, false};
    field_t word;
    next_field(&c, &word);
    if (same(&word, "CLOCK")) {
        out->kind = REC_CMD_CLOCK;
        return parse_clock(&c, out);
    }
    if (same(&word, "SCHEDULE")) {
        out->kind = REC_CMD_SCHEDULE;
        return parse_schedule(&c, out);
    }
    if (same(&word, "SESSION")) {
        out->kind = REC_CMD_SESSION;
        field_t extra;
        return next_field(&c, &extra) ? REC_BAD_FORMAT : REC_DONE;
    }
    if (same(&word, "TONE")) {
        out->kind = REC_CMD_TONE;
        return parse_tone(&c, out);
    }
    return REC_UNKNOWN;
}

int64_t rec_clock_offset_us(int64_t utc_us, int32_t offset_min, int64_t stamp_us)
{
    return utc_us + (int64_t)offset_min * MINUTE_US - stamp_us;
}
