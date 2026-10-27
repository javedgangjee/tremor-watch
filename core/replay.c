/*
 * replay runs the C detector on a PADS recording or on a recording from the
 * watch, and prints one CSV row for every window.
 *
 *     build/core/replay --pads FILE
 *     build/core/replay --recording FILE [--samples OUT]
 *
 * A PADS line holds seven values: the time, three accelerometer axes, and
 * three gyroscope axes in radians per second. replay converts the gyroscope to
 * degrees per second as numpy's degrees function does, rounds to 32-bit
 * floats, and cuts the first 50 rows, which hold the watch's start vibration.
 * PADS is already at 100 Hz, so there is no rate conversion. Window n holds
 * rows 100n to 100n + 399 after the cut. Columns use the toolbox's names.
 *
 * A recording is the text the watch writes over USB, as described in
 * core/recording_format.md. FILE may be - for standard input. replay times the
 * readings with core/reading_time.h and feeds each whole burst to
 * core/pipeline.h as one part, as the pipeline task does. It makes no sensor
 * fault answers, because those come from the watch's timer.
 *
 * The T line holds no overflow flag, so replay finds stretch starts from the S
 * lines. A burst whose first reading equals the first reading of an earlier S
 * line in the same boot, with a stretch number above every earlier one in that
 * boot, goes to rt_burst() with the overflow flag set. The time rule still
 * runs on every burst, so it finds a drift end by itself.
 *
 * replay skips every line before the first B line and every line that is not
 * a record line. A record line that breaks its pattern counts as bad and is
 * skipped, as does a line of more than 1022 characters or a T line with more
 * than 256 readings. W, F, D and A lines are checked and ignored. A B line
 * with a new boot ID restarts the time rule and the pipeline.
 *
 * With --samples, replay also writes its 100 Hz samples to OUT as CSV, each
 * sample once.
 *
 * At the end replay writes one line of counts to standard error. It exits
 * with code 1 when it cannot read a file or the recording holds no B line.
 */

#include <errno.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "detector.h"
#include "imu_units.h"
#include "pipeline.h"
#include "reading_time.h"
#include "window.h"

/* Every PADS file holds 1024 or 2048 rows, so 4096 rows leave room. */
#define MAX_ROWS 4096
#define PADS_VALUES 7
#define GYRO_FIRST 4
#define CUT_ROWS 50
#define WINDOW_STEP 100
#define LINE_MAX_CHARS 1024

/* numpy's degrees function multiplies by 180 / pi in 64-bit floats. */
#define RAD_TO_DEG (180.0 / 3.141592653589793)

static float rows[MAX_ROWS][DET_AXES];

/* Reads the seven values of one line. Returns false if the line holds fewer
 * than seven numbers. */
static bool read_line_values(const char *line, double values[PADS_VALUES])
{
    const char *p = line;
    for (int v = 0; v < PADS_VALUES; v++) {
        char *end = NULL;
        errno = 0;
        values[v] = strtod(p, &end);
        if (end == p || errno == ERANGE) {
            return false;
        }
        p = end;
        while (*p == ' ' || *p == '\t') {
            p++;
        }
        if (v < PADS_VALUES - 1) {
            if (*p != ',') {
                return false;
            }
            p++;
        }
    }
    return true;
}

/* Reads the gyroscope of one file into rows. Returns the number of rows, or -1
 * after it prints an error. */
static int read_pads(const char *path)
{
    FILE *file = fopen(path, "r");
    if (file == NULL) {
        fprintf(stderr, "replay: cannot read %s\n", path);
        return -1;
    }
    char line[LINE_MAX_CHARS];
    int n = 0;
    int line_no = 0;
    while (fgets(line, sizeof line, file) != NULL) {
        line_no++;
        size_t len = strlen(line);
        if (len == sizeof line - 1 && line[len - 1] != '\n') {
            fprintf(stderr, "replay: line %d of %s is too long\n", line_no, path);
            fclose(file);
            return -1;
        }
        if (strspn(line, " \t\r\n") == len) {
            continue;
        }
        double values[PADS_VALUES];
        if (!read_line_values(line, values)) {
            fprintf(stderr, "replay: line %d of %s has fewer than %d values\n", line_no, path, PADS_VALUES);
            fclose(file);
            return -1;
        }
        if (n == MAX_ROWS) {
            fprintf(stderr, "replay: %s has more than %d rows\n", path, MAX_ROWS);
            fclose(file);
            return -1;
        }
        for (int axis = 0; axis < DET_AXES; axis++) {
            rows[n][axis] = (float)(values[GYRO_FIRST + axis] * RAD_TO_DEG);
        }
        n++;
    }
    bool failed = ferror(file) != 0;
    fclose(file);
    if (failed) {
        fprintf(stderr, "replay: cannot read %s\n", path);
        return -1;
    }
    return n;
}

static void print_header(void)
{
    printf("window");
    for (int i = 1; i <= DET_MFCC_COUNT; i++) {
        printf(",mfcc_%d", i);
    }
    printf(",pred_tremor_proba,below_tremor_power,freq_peak,pred_arm_at_rest,pred_tremor_checked\n");
}

static void print_window(int index, const det_result_t *r)
{
    printf("%d", index);
    for (int i = 0; i < DET_MFCC_COUNT; i++) {
        printf(",%.9g", (double)r->mfcc[i]);
    }
    printf(",%.17g,%.17g,%.9g,%d,%d\n", r->prob, r->below, (double)r->peak_hz, r->at_rest ? 1 : 0,
           r->tremor ? 1 : 0);
}

#define BURST_MAX 256
/* Window 0 gives all of its samples, and each later window gives its last
 * 100, which no earlier window held. */
#define NEW_SAMPLES_FIRST (DET_WINDOW_LEN - WINDOW_STEP)

/* The record letters of core/recording_format.md. */
#define RECORD_LETTERS "BSTRWFDA"

typedef struct {
    bool has_boot;
    uint32_t boot_id;
    /* top_stretch is the highest stretch number of the boot's S lines. */
    bool has_stretch;
    uint32_t top_stretch;
    /* pending_first is an S line's first reading, waiting for its burst. */
    bool has_pending;
    uint64_t pending_first;
    /* The burst that replay holds until its R lines are in. */
    bool held;
    bool broken;
    uint64_t held_first;
    uint32_t held_count;
    int64_t held_stamp;
    uint32_t held_got;
    /* The counts for the summary line. */
    uint64_t lines;
    uint64_t bad;
    uint64_t dropped;
    uint64_t boots;
    uint64_t stretches;
    uint64_t windows;
} rec_t;

static rt_state_t s_rt;
static pipe_t s_pipe;
static float s_window[DET_WINDOW_LEN][DET_AXES];
static float s_burst[BURST_MAX][CONV_AXES];
static rec_t s_rec;

/* Reads a run of digits that fits in max and moves *p past them. Returns false
 * when there is no digit or the value is too big. */
static bool read_uint(const char **p, uint64_t max, uint64_t *out)
{
    const char *q = *p;
    uint64_t value = 0;
    if (*q < '0' || *q > '9') {
        return false;
    }
    for (; *q >= '0' && *q <= '9'; q++) {
        uint64_t digit = (uint64_t)(*q - '0');
        if (value > (max - digit) / 10u) {
            return false;
        }
        value = value * 10u + digit;
    }
    *p = q;
    *out = value;
    return true;
}

/* Reads digits with an optional leading minus sign. The value must lie from
 * min to max. */
static bool read_int(const char **p, int64_t min, int64_t max, int64_t *out)
{
    const char *q = *p;
    bool negative = *q == '-';
    if (negative) {
        q++;
    }
    uint64_t magnitude;
    uint64_t limit = negative ? (uint64_t)(-(min + 1)) + 1u : (uint64_t)max;
    if (!read_uint(&q, limit, &magnitude)) {
        return false;
    }
    if (negative) {
        *out = magnitude == 0 ? 0 : -(int64_t)(magnitude - 1u) - 1;
    } else {
        *out = (int64_t)magnitude;
    }
    *p = q;
    return true;
}

static bool read_comma(const char **p)
{
    if (**p != ',') {
        return false;
    }
    (*p)++;
    return true;
}

/* Moves *p past a run of characters from `allowed`. The run may be empty. */
static void read_chars(const char **p, const char *allowed)
{
    while (**p != '\0' && strchr(allowed, **p) != NULL) {
        (*p)++;
    }
}

typedef struct {
    uint32_t boot_id;
} b_line_t;

typedef struct {
    uint32_t number;
    uint64_t first;
} s_line_t;

typedef struct {
    uint64_t first;
    uint32_t count;
    int64_t stamp;
} t_line_t;

typedef struct {
    uint64_t number;
    int16_t gyro[CONV_AXES];
} r_line_t;

/* Reads ^B,(\d+),(\d+),(\d+),([0-9a-f]{64})$. */
static bool parse_b(const char *line, b_line_t *out)
{
    const char *p = line + 2;
    uint64_t id;
    uint64_t cause;
    uint64_t version;
    if (!read_uint(&p, UINT32_MAX, &id) || !read_comma(&p) || !read_uint(&p, UINT32_MAX, &cause) ||
        !read_comma(&p) || !read_uint(&p, UINT32_MAX, &version) || !read_comma(&p)) {
        return false;
    }
    const char *hash = p;
    read_chars(&p, "0123456789abcdef");
    if (p - hash != 64 || *p != '\0') {
        return false;
    }
    out->boot_id = (uint32_t)id;
    return true;
}

/* Reads ^S,(\d+),(\d+),(-?\d+),(\d+),(\d+)$. */
static bool parse_s(const char *line, s_line_t *out)
{
    const char *p = line + 2;
    uint64_t number;
    uint64_t first;
    int64_t t0;
    uint64_t rate;
    uint64_t range;
    if (!read_uint(&p, UINT32_MAX, &number) || !read_comma(&p) || !read_uint(&p, UINT64_MAX, &first) ||
        !read_comma(&p) || !read_int(&p, INT64_MIN, INT64_MAX, &t0) || !read_comma(&p) ||
        !read_uint(&p, UINT32_MAX, &rate) || !read_comma(&p) || !read_uint(&p, UINT32_MAX, &range) || *p != '\0') {
        return false;
    }
    out->number = (uint32_t)number;
    out->first = first;
    return true;
}

/* Reads ^T,(\d+),(\d+),(-?\d+)$ with at most BURST_MAX readings. */
static bool parse_t(const char *line, t_line_t *out)
{
    const char *p = line + 2;
    uint64_t first;
    uint64_t count;
    int64_t stamp;
    if (!read_uint(&p, UINT64_MAX, &first) || !read_comma(&p) || !read_uint(&p, BURST_MAX, &count) ||
        !read_comma(&p) || !read_int(&p, INT64_MIN, INT64_MAX, &stamp) || *p != '\0') {
        return false;
    }
    out->first = first;
    out->count = (uint32_t)count;
    out->stamp = stamp;
    return true;
}

/* Reads ^R,(\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+),(-?\d+)$,
 * where each count fits in 16 bits. */
static bool parse_r(const char *line, r_line_t *out)
{
    const char *p = line + 2;
    if (!read_uint(&p, UINT64_MAX, &out->number)) {
        return false;
    }
    for (int i = 0; i < 6; i++) {
        int64_t value;
        if (!read_comma(&p) || !read_int(&p, INT16_MIN, INT16_MAX, &value)) {
            return false;
        }
        if (i < CONV_AXES) {
            out->gyro[i] = (int16_t)value;
        }
    }
    return *p == '\0';
}

/* Checks the patterns of the W, F, D and A lines, which replay does not use. */
static bool follows_ignored(const char *line)
{
    const char *p = line + 2;
    uint64_t u;
    int64_t i;
    switch (line[0]) {
    case 'W':
        if (!read_uint(&p, UINT64_MAX, &u) || !read_comma(&p)) {
            return false;
        }
        read_chars(&p, "0123456789");
        if (!read_comma(&p) || *p < '0' || *p > '4' || p[1] != ',') {
            return false;
        }
        p += 2;
        for (int n = 0; n < 3; n++) {
            read_chars(&p, "-+.0123456789e");
            if (n < 2 && !read_comma(&p)) {
                return false;
            }
        }
        return *p == '\0';
    case 'F':
        return read_int(&p, INT64_MIN, INT64_MAX, &i) && read_comma(&p) && *p >= '0' && *p <= '4' && p[1] == '\0';
    case 'D':
        if (!read_int(&p, INT64_MIN, INT64_MAX, &i) || !read_comma(&p)) {
            return false;
        }
        return *p == '\0' || (read_int(&p, INT64_MIN, INT64_MAX, &i) && *p == '\0');
    case 'A':
        return *p >= '0' && *p <= '4' && p[1] == ',' && p[2] >= '0' && p[2] <= '5' && p[3] == '\0';
    default:
        return false;
    }
}

static void print_recording_header(void)
{
    printf("boot,stretch,first,t0_us,rate_uhz,window,time_us,code");
    for (int i = 1; i <= DET_MFCC_COUNT; i++) {
        printf(",mfcc_%d", i);
    }
    printf(",pred_tremor_proba,below_tremor_power,freq_peak,pred_arm_at_rest,pred_tremor_checked\n");
}

/* Runs the detector on every complete window and prints the rows. */
static void run_windows(FILE *samples)
{
    uint32_t number;
    int64_t time_us;
    while (pipe_window(&s_pipe, s_window, &number, &time_us)) {
        det_result_t r;
        det_run(s_window, &r);
        const rt_stretch_t *st = pipe_stretch(&s_pipe);
        printf("%" PRIu32 ",%" PRIu32 ",%" PRIu64 ",%" PRId64 ",%" PRIu32 ",%" PRIu32 ",%" PRId64 ",%d",
               s_rec.boot_id, st->number, st->first_reading, st->t0_us, st->rate_uhz, number, time_us,
               (int)res_from_answer(number, &r));
        for (int i = 0; i < DET_MFCC_COUNT; i++) {
            printf(",%.9g", (double)r.mfcc[i]);
        }
        printf(",%.17g,%.17g,%.9g,%d,%d\n", r.prob, r.below, (double)r.peak_hz, r.at_rest ? 1 : 0,
               r.tremor ? 1 : 0);
        s_rec.windows++;
        if (samples != NULL) {
            int start = number == 0 ? 0 : NEW_SAMPLES_FIRST;
            for (int k = start; k < DET_WINDOW_LEN; k++) {
                uint64_t sample = (uint64_t)number * WINDOW_STEP + (uint64_t)k;
                fprintf(samples, "%" PRIu32 ",%" PRIu32 ",%" PRIu64 ",%.9g,%.9g,%.9g\n", s_rec.boot_id, st->number,
                        sample, (double)s_window[k][0], (double)s_window[k][1], (double)s_window[k][2]);
            }
        }
    }
}

/* Passes the held burst on when it holds exactly its count of R lines in
 * order. Otherwise drops it and counts it. */
static void pass_on(FILE *samples)
{
    if (!s_rec.held) {
        return;
    }
    s_rec.held = false;
    if (s_rec.broken || s_rec.held_got != s_rec.held_count) {
        s_rec.dropped++;
        return;
    }
    if (s_rec.held_count == 0) {
        return;
    }
    bool overflow = s_rec.has_pending && s_rec.held_first == s_rec.pending_first;
    if (overflow) {
        s_rec.has_pending = false;
    }
    unsigned rt_flags = rt_burst(&s_rt, s_rec.held_first, s_rec.held_count, s_rec.held_stamp, overflow);
    if ((rt_flags & RT_NEW_STRETCH) != 0) {
        s_rec.stretches++;
    }
    const rt_stretch_t *st = rt_current(&s_rt);
    pipe_part_t part = {
        .stretch = st->number,
        .flags = rt_flags,
        .rate_uhz = st->rate_uhz,
        .stamp_us = s_rec.held_stamp,
        .first_reading = s_rec.held_first,
        .count = s_rec.held_count,
    };
    unsigned flags = pipe_part(&s_pipe, &part, s_rec.held_stamp);
    if ((flags & PIPE_DROP) == 0) {
        for (uint32_t i = 0; i < s_rec.held_count; i++) {
            pipe_push(&s_pipe, s_burst[i]);
        }
    }
    run_windows(samples);
}

/* Applies one line of the recording, without its line end. A B line first
 * passes on the held burst. */
static void take_line(const char *line, FILE *samples)
{
    /* Only a record letter and a comma make a record line. Every other line,
     * such as a diagnostic line or a "> " line, is skipped. */
    if (line[0] == '\0' || strchr(RECORD_LETTERS, line[0]) == NULL || line[1] != ',') {
        return;
    }
    /* Before the first B line every line is skipped. */
    if (!s_rec.has_boot && line[0] != 'B') {
        return;
    }
    switch (line[0]) {
    case 'B': {
        b_line_t b;
        if (!parse_b(line, &b)) {
            if (s_rec.has_boot) {
                s_rec.bad++;
            }
            return;
        }
        pass_on(samples);
        if (!s_rec.has_boot || b.boot_id != s_rec.boot_id) {
            s_rec.has_boot = true;
            s_rec.boot_id = b.boot_id;
            s_rec.has_stretch = false;
            s_rec.has_pending = false;
            s_rec.boots++;
            rt_init(&s_rt);
            pipe_init(&s_pipe, 0);
        }
        return;
    }
    case 'S': {
        s_line_t s;
        if (!parse_s(line, &s)) {
            s_rec.bad++;
            return;
        }
        if (!s_rec.has_stretch || s.number > s_rec.top_stretch) {
            s_rec.has_stretch = true;
            s_rec.top_stretch = s.number;
            s_rec.has_pending = true;
            s_rec.pending_first = s.first;
        }
        return;
    }
    case 'T': {
        t_line_t t;
        if (!parse_t(line, &t)) {
            s_rec.bad++;
            return;
        }
        pass_on(samples);
        s_rec.held = true;
        s_rec.broken = false;
        s_rec.held_first = t.first;
        s_rec.held_count = t.count;
        s_rec.held_stamp = t.stamp;
        s_rec.held_got = 0;
        return;
    }
    case 'R': {
        r_line_t r;
        if (!parse_r(line, &r)) {
            s_rec.bad++;
            return;
        }
        if (!s_rec.held || s_rec.broken) {
            return;
        }
        if (s_rec.held_got >= s_rec.held_count || r.number != s_rec.held_first + s_rec.held_got) {
            s_rec.broken = true;
            return;
        }
        for (int axis = 0; axis < CONV_AXES; axis++) {
            s_burst[s_rec.held_got][axis] = imu_gyro_dps(r.gyro[axis]);
        }
        s_rec.held_got++;
        return;
    }
    default:
        if (!follows_ignored(line)) {
            s_rec.bad++;
        }
        return;
    }
}

/* Reads one recording and prints its rows. Returns the exit code. */
static int run_recording(const char *path, const char *samples_path)
{
    bool from_stdin = strcmp(path, "-") == 0;
    FILE *file = from_stdin ? stdin : fopen(path, "r");
    if (file == NULL) {
        fprintf(stderr, "replay: cannot read %s\n", path);
        return 1;
    }
    FILE *samples = NULL;
    if (samples_path != NULL) {
        samples = fopen(samples_path, "w");
        if (samples == NULL) {
            fprintf(stderr, "replay: cannot write %s\n", samples_path);
            if (!from_stdin) {
                fclose(file);
            }
            return 1;
        }
        fprintf(samples, "boot,stretch,sample,gyroscope_x,gyroscope_y,gyroscope_z\n");
    }
    print_recording_header();

    char line[LINE_MAX_CHARS];
    bool too_long = false;
    while (fgets(line, sizeof line, file) != NULL) {
        size_t len = strlen(line);
        bool whole = len > 0 && line[len - 1] == '\n';
        if (too_long) {
            /* The rest of a long line ends when its newline arrives. */
            too_long = !whole;
            continue;
        }
        s_rec.lines++;
        if (!whole && len == sizeof line - 1) {
            too_long = true;
            if (s_rec.has_boot) {
                s_rec.bad++;
            }
            continue;
        }
        if (whole) {
            line[--len] = '\0';
        }
        if (len > 0 && line[len - 1] == '\r') {
            line[--len] = '\0';
        }
        take_line(line, samples);
    }
    bool failed = ferror(file) != 0;
    if (!from_stdin) {
        fclose(file);
    }
    /* A capture can stop in the middle of the last burst. That burst is left
     * out, and it counts as dropped only when its R lines break their order. */
    if (s_rec.held && !s_rec.broken && s_rec.held_got < s_rec.held_count) {
        s_rec.held = false;
    }
    if (!failed) {
        pass_on(samples);
    }
    if (samples != NULL && fclose(samples) != 0) {
        fprintf(stderr, "replay: cannot write %s\n", samples_path);
        failed = true;
    }
    fprintf(stderr,
            "replay: lines=%" PRIu64 " bad=%" PRIu64 " dropped_bursts=%" PRIu64 " boots=%" PRIu64
            " stretches=%" PRIu64 " windows=%" PRIu64 "\n",
            s_rec.lines, s_rec.bad, s_rec.dropped, s_rec.boots, s_rec.stretches, s_rec.windows);
    if (failed) {
        fprintf(stderr, "replay: cannot read %s\n", path);
        return 1;
    }
    if (!s_rec.has_boot) {
        fprintf(stderr, "replay: %s holds no B line\n", path);
        return 1;
    }
    return 0;
}

static void print_usage(void)
{
    fprintf(stderr, "usage: replay --pads FILE\n");
    fprintf(stderr, "       replay --recording FILE [--samples OUT]\n");
}

static int run_pads(const char *path)
{
    if (!det_init()) {
        fprintf(stderr, "replay: det_init failed\n");
        return 1;
    }
    int n = read_pads(path);
    if (n < 0) {
        return 1;
    }

    print_header();
    int kept = n > CUT_ROWS ? n - CUT_ROWS : 0;
    for (int w = 0; w * WINDOW_STEP + DET_WINDOW_LEN <= kept; w++) {
        det_result_t r;
        const float(*window)[DET_AXES] = &rows[CUT_ROWS + w * WINDOW_STEP];
        det_run(window, &r);
        print_window(w, &r);
    }
    return 0;
}

int main(int argc, char **argv)
{
    if (argc == 3 && strcmp(argv[1], "--pads") == 0) {
        return run_pads(argv[2]);
    }
    bool recording = (argc == 3 || argc == 5) && strcmp(argv[1], "--recording") == 0;
    if (!recording || (argc == 5 && strcmp(argv[3], "--samples") != 0)) {
        print_usage();
        return 1;
    }
    if (!det_init()) {
        fprintf(stderr, "replay: det_init failed\n");
        return 1;
    }
    return run_recording(argv[2], argc == 5 ? argv[4] : NULL);
}
