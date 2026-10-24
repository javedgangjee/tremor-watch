/*
 * view.c builds the texts and values that the face draws. view.h describes
 * them, and feature 11's requirements 48 to 53 and 62 give the details.
 *
 * Day and minute sums use 64-bit whole numbers with division that rounds down.
 */

#include "view.h"

#include <inttypes.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#define MINUTE_US INT64_C(60000000)
#define DAY_US (INT64_C(1440) * MINUTE_US)
#define NO_TIME "--:--"

static const char *const STATUS_LABELS[LOOK_STATUS_ROWS] = {
    "Battery", "Voltage", "Uptime", "Rate", "Stretch", "Detector", "Recording", "Firmware", "Tables",
};

static const char *const WEEKDAYS[7] = {"Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"};
static const char *const MONTHS[12] = {
    "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
};

const char *view_status_label(unsigned row)
{
    return row < LOOK_STATUS_ROWS ? STATUS_LABELS[row] : "";
}

/* floor_div() divides by a positive number and rounds down. */
static int64_t floor_div(int64_t a, int64_t b)
{
    int64_t q = a / b;
    if (a % b != 0 && a < 0) {
        q--;
    }
    return q;
}

/* clock_text() writes "HH:MM" for a local time in microseconds since 1970. */
static void clock_text(char *out, size_t size, int64_t local_us)
{
    int64_t day = floor_div(local_us, DAY_US);
    int64_t minutes = (local_us - day * DAY_US) / MINUTE_US;
    snprintf(out, size, "%02d:%02d", (int)(minutes / 60), (int)(minutes % 60));
}

/* date_text() writes the short weekday, the day, and the short month, as in
 * "Fri 23 Oct". The day and month come from the days since 1970 by the civil
 * calendar rule, and 1 January 1970 was a Thursday. */
static void date_text(char *out, size_t size, int64_t local_us)
{
    int64_t days = floor_div(local_us, DAY_US);
    int64_t z = days + 719468;
    int64_t era = floor_div(z, 146097);
    int64_t doe = z - era * 146097;
    int64_t yoe = (doe - doe / 1460 + doe / 36524 - doe / 146096) / 365;
    int64_t doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    int64_t mp = (5 * doy + 2) / 153;
    int day = (int)(doy - (153 * mp + 2) / 5 + 1);
    int month = (int)(mp < 10 ? mp + 3 : mp - 9);
    int64_t weekday = days + 4 - floor_div(days + 4, 7) * 7;
    snprintf(out, size, "%s %d %s", WEEKDAYS[weekday], day, MONTHS[month - 1]);
}

/* round_half_up() rounds a percent to a whole number with halves going up. */
static int round_half_up(double percent)
{
    return (int)floor(percent + 0.5);
}

/* dose_value() writes a Medication value: the name, a comma, a space, and
 * the time, or the time alone when the schedule has no name. */
static void dose_value(view_cut_t *out, const char *name, const char *time)
{
    size_t name_len = strlen(name);
    if (name_len == 0) {
        snprintf(out->text, sizeof out->text, "%s", time);
        out->cut_at = 0;
        out->cut_len = 0;
        return;
    }
    snprintf(out->text, sizeof out->text, "%s, %s", name, time);
    out->cut_at = 0;
    out->cut_len = (uint8_t)name_len;
}

/* plain_value() writes a value that holds no name. */
static void plain_value(view_cut_t *out, const char *text)
{
    snprintf(out->text, sizeof out->text, "%s", text);
    out->cut_at = 0;
    out->cut_len = 0;
}

/* local_or_dashes() writes "HH:MM" for a timer value when the clock is set,
 * and dashes when it is not. */
static void local_or_dashes(char *out, size_t size, const dose_t *d, int64_t timer_us)
{
    if (d->clock_set) {
        clock_text(out, size, timer_us + d->offset_us);
    } else {
        snprintf(out, size, "%s", NO_TIME);
    }
}

static void build_doses(view_t *v, const sess_t *s, int64_t now_us)
{
    const dose_t *d = &s->dose;
    const char *name = d->schedule.name;
    char time[8];

    view_cut_t last;
    dose_entry_t entry;
    if (dose_last(d, &entry)) {
        local_or_dashes(time, sizeof time, d, entry.time_us);
        dose_value(&last, name, time);
    } else {
        plain_value(&last, "None yet");
    }

    view_cut_t next;
    int64_t next_local;
    if (d->schedule.count == 0) {
        plain_value(&next, "No schedule");
        snprintf(v->next_short, sizeof v->next_short, "none");
    } else if (!d->clock_set) {
        dose_value(&next, name, NO_TIME);
        snprintf(v->next_short, sizeof v->next_short, "%s", NO_TIME);
    } else if (dose_next(d, now_us, &next_local)) {
        clock_text(time, sizeof time, next_local);
        dose_value(&next, name, time);
        snprintf(v->next_short, sizeof v->next_short, "%s", time);
    } else {
        plain_value(&next, "No schedule");
        snprintf(v->next_short, sizeof v->next_short, "none");
    }

    int64_t due_local;
    v->due = dose_due_time(d, &due_local);
    if (v->due) {
        clock_text(time, sizeof time, due_local);
        snprintf(v->label_1, sizeof v->label_1, "Dose due");
        dose_value(&v->value_1, name, time);
        snprintf(v->label_2, sizeof v->label_2, "Last dose");
        v->value_2 = last;
    } else {
        snprintf(v->label_1, sizeof v->label_1, "Last dose");
        v->value_1 = last;
        snprintf(v->label_2, sizeof v->label_2, "Next dose");
        v->value_2 = next;
    }

    static const char NEXT_WORDS[] = "Next dose ";
    size_t words = strlen(NEXT_WORDS);
    size_t rest = strnlen(next.text, sizeof v->logged_next.text - words - 1);
    memcpy(v->logged_next.text, NEXT_WORDS, words);
    memcpy(v->logged_next.text + words, next.text, rest);
    v->logged_next.text[words + rest] = '\0';
    v->logged_next.cut_at = (uint8_t)(strlen(NEXT_WORDS) + next.cut_at);
    v->logged_next.cut_len = next.cut_len;
}

static void build_tremor(view_t *v, const sess_t *s)
{
    int64_t last_us;
    if (!face_last_tremor(&s->face, &last_us)) {
        snprintf(v->last_tremor_short, sizeof v->last_tremor_short, "none");
    } else {
        local_or_dashes(v->last_tremor_short, sizeof v->last_tremor_short, &s->dose, last_us);
    }
    /* With no tremor yet the line is empty, so Home hides it. The user chose
     * this on 2026-10-24. last_tremor_short keeps "none" for the record line. */
    if (strcmp(v->last_tremor_short, "none") == 0) {
        v->last_tremor[0] = '\0';
    } else {
        snprintf(v->last_tremor, sizeof v->last_tremor, "Last tremor %s", v->last_tremor_short);
    }
}

static void build_share(view_t *v, const sess_t *s)
{
    const share_t *sh = &s->share;
    double percent;
    if (share_percent(sh, &percent)) {
        v->percent = round_half_up(percent);
        snprintf(v->share, sizeof v->share, "Tremor %d%%", v->percent);
    } else {
        v->percent = -1;
        snprintf(v->share, sizeof v->share, "Tremor --%%");
    }
    snprintf(v->share_line, sizeof v->share_line, "of still time this session");

    v->block_count = share_block_count(sh);
    for (uint32_t i = 0; i < SHARE_BLOCKS; i++) {
        const share_block_t *b = share_block(sh, i);
        double block_percent;
        v->hollow[i] = b != NULL && share_block_hollow(b);
        v->block_percent[i] = b != NULL && share_block_percent(b, &block_percent) ? round_half_up(block_percent) : -1;
    }
    const share_block_t *oldest = share_block(sh, 0);
    if (oldest != NULL) {
        int64_t start_us = sh->start_us + (int64_t)oldest->number * SHARE_BLOCK_US;
        local_or_dashes(v->blocks_left, sizeof v->blocks_left, &s->dose, start_us);
    } else {
        local_or_dashes(v->blocks_left, sizeof v->blocks_left, &s->dose, sh->start_us);
    }
    snprintf(v->blocks_right, sizeof v->blocks_right, "Now");
}

static void build_status(view_t *v, const view_input_t *in)
{
    char(*st)[sizeof v->status[0]] = v->status;
    const size_t n = sizeof v->status[0];
    if (in->battery_known) {
        snprintf(st[0], n, "%d%%", in->battery_percent);
        snprintf(st[1], n, "%u.%u V", (unsigned)((in->battery_mv + 50) / 1000),
                 (unsigned)((in->battery_mv + 50) / 100 % 10));
        snprintf(v->battery, sizeof v->battery, "%d%%", in->battery_percent);
    } else {
        snprintf(st[0], n, "--");
        snprintf(st[1], n, "--");
        snprintf(v->battery, sizeof v->battery, "--%%");
    }
    snprintf(st[2], n, "%" PRIu32 " h %" PRIu32 " m", in->uptime_s / 3600, in->uptime_s / 60 % 60);
    if (in->has_answer && in->rate_uhz > 0) {
        uint32_t thousandths = (uint32_t)(((uint64_t)in->rate_uhz + 500) / 1000);
        snprintf(st[3], n, "%" PRIu32 ".%03" PRIu32 " Hz", thousandths / 1000, thousandths % 1000);
    } else {
        snprintf(st[3], n, "--");
    }
    if (in->has_answer) {
        /* A run time is far below a second, so the tenths of a millisecond
         * are kept under 100000. */
        int64_t run_us = in->run_us < 0 ? 0 : in->run_us > INT64_C(9999999) ? INT64_C(9999999) : in->run_us;
        uint32_t tenths = (uint32_t)((run_us + 50) / 100);
        snprintf(st[4], n, "%" PRIu32, in->stretch);
        snprintf(st[5], n, "%" PRIu32 ".%" PRIu32 " ms", tenths / 10 % 100000, tenths % 10);
    } else {
        snprintf(st[4], n, "--");
        snprintf(st[5], n, "--");
    }
    snprintf(st[6], n, "%s", in->recording ? "On" : "Off");
    snprintf(st[7], n, "%" PRIu32, in->firmware);
    snprintf(st[8], n, "%.*s", VIEW_HASH_DIGITS, in->hash != NULL ? in->hash : "--");
}

void view_build(view_t *v, const sess_t *s, const view_input_t *in, int64_t now_us)
{
    memset(v, 0, sizeof *v);
    v->face = face_shown(&s->face);
    local_or_dashes(v->time, sizeof v->time, &s->dose, now_us);
    if (s->dose.clock_set) {
        date_text(v->date, sizeof v->date, now_us + s->dose.offset_us);
    } else {
        snprintf(v->date, sizeof v->date, "--- -- ---");
    }
    build_tremor(v, s);
    build_doses(v, s, now_us);
    build_share(v, s);
    build_status(v, in);
    v->tone_on = in->tone_on;
    v->dose_tones = in->dose_tones;
    v->doses_accepted = in->doses_accepted;
}
