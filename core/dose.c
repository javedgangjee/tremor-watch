/*
 * dose.c holds the dose schedule and the due rule. See dose.h.
 *
 * Day and minute sums use 64-bit whole numbers with division that rounds down.
 */

#include "dose.h"

#include <string.h>

#define MINUTE_US INT64_C(60000000)
#define DAY_US (DOSE_DAY_MINUTES * MINUTE_US)

/* Divides by a positive number and rounds down. */
static int64_t floor_div(int64_t a, int64_t b)
{
    int64_t q = a / b;
    if (a % b != 0 && a < 0) {
        q--;
    }
    return q;
}

/* Gives the local time of schedule time i on local day `day`. */
static int64_t dose_at(const dose_t *d, int64_t day, uint8_t i)
{
    return day * DAY_US + (int64_t)d->schedule.minutes[i] * MINUTE_US;
}

/* True when a kept dose has a local time from D minus 1 hour to D, with both
 * ends included. */
static bool covered(const dose_t *d, int64_t dose_local_us)
{
    for (uint32_t i = 0; i < d->log_kept; i++) {
        const dose_entry_t *e = &d->log[(d->log_head + i) % DOSE_LOG_LEN];
        int64_t local = e->time_us + d->offset_us;
        if (local >= dose_local_us - DOSE_BEFORE_US && local <= dose_local_us) {
            return true;
        }
    }
    return false;
}

/* True when the schedule holds the minute of the day of a local time. */
static bool in_schedule(const dose_t *d, int64_t local_us)
{
    int64_t minute = (local_us - floor_div(local_us, DAY_US) * DAY_US) / MINUTE_US;
    for (uint8_t i = 0; i < d->schedule.count; i++) {
        if (d->schedule.minutes[i] == minute) {
            return true;
        }
    }
    return false;
}

static bool is_on(const dose_t *d)
{
    return d->clock_set && d->schedule.count > 0;
}

/* Records a tick that makes nothing due. */
static void mark_tick(dose_t *d, int64_t now_us)
{
    d->ticked = true;
    d->last_tick_us = now_us;
}

void dose_init(dose_t *d)
{
    memset(d, 0, sizeof(*d));
}

bool dose_set_schedule(dose_t *d, const dose_schedule_t *s, int64_t now_us)
{
    if (memchr(s->name, '\0', sizeof(s->name)) == NULL || s->count > DOSE_MAX_TIMES) {
        return false;
    }
    dose_schedule_t sorted;
    memset(&sorted, 0, sizeof(sorted));
    memcpy(sorted.name, s->name, sizeof(sorted.name));
    sorted.count = s->count;
    /* Insertion sort keeps the times in rising order and finds a time given
     * twice. */
    for (uint8_t i = 0; i < s->count; i++) {
        uint16_t m = s->minutes[i];
        if (m >= DOSE_DAY_MINUTES) {
            return false;
        }
        uint8_t j = i;
        while (j > 0 && sorted.minutes[j - 1] > m) {
            sorted.minutes[j] = sorted.minutes[j - 1];
            j--;
        }
        if (j > 0 && sorted.minutes[j - 1] == m) {
            return false;
        }
        sorted.minutes[j] = m;
    }
    d->schedule = sorted;
    mark_tick(d, now_us);
    return true;
}

void dose_set_clock(dose_t *d, int64_t offset_us, int64_t now_us)
{
    d->clock_set = true;
    d->offset_us = offset_us;
    mark_tick(d, now_us);
}

void dose_new_session(dose_t *d, int64_t now_us)
{
    d->due = false;
    d->due_local_us = 0;
    d->log_head = 0;
    d->log_kept = 0;
    d->count = 0;
    mark_tick(d, now_us);
}

unsigned dose_tick(dose_t *d, int64_t now_us)
{
    if (!d->ticked) {
        mark_tick(d, now_us);
        return 0;
    }
    int64_t last_us = d->last_tick_us;
    d->last_tick_us = now_us;
    if (!d->clock_set) {
        return 0;
    }
    int64_t now_local = now_us + d->offset_us;

    /* The latest time D with last tick < D <= now, now < D + 15 minutes, and
     * no dose logged from D - 1 hour to D becomes due. D lies within 15
     * minutes before now, so it lies today or yesterday. */
    if (d->schedule.count > 0) {
        int64_t after = last_us + d->offset_us;
        if (now_local - DOSE_DUE_US > after) {
            after = now_local - DOSE_DUE_US;
        }
        int64_t today = floor_div(now_local, DAY_US);
        bool found = false;
        int64_t best = 0;
        for (int64_t day = today - 1; day <= today; day++) {
            for (uint8_t i = 0; i < d->schedule.count; i++) {
                int64_t t = dose_at(d, day, i);
                if (t > after && t <= now_local && !covered(d, t) && (!found || t > best)) {
                    found = true;
                    best = t;
                }
            }
        }
        /* A new due time takes the place of a due dose, and the tone plays. */
        if (found && !(d->due && d->due_local_us == best)) {
            d->due = true;
            d->due_local_us = best;
            return DOSE_BECAME_DUE;
        }
    }

    /* A due dose ends 15 minutes after its time, or when a new schedule no
     * longer holds its time. */
    if (d->due && (now_local >= d->due_local_us + DOSE_DUE_US || !in_schedule(d, d->due_local_us))) {
        d->due = false;
        return DOSE_DUE_ENDED;
    }
    return 0;
}

/* Gives the scheduled time nearest to now, before or after. A tie goes to the
 * earlier one. */
static int64_t nearest(const dose_t *d, int64_t now_local)
{
    int64_t today = floor_div(now_local, DAY_US);
    int64_t best = 0;
    int64_t best_gap = 0;
    bool found = false;
    /* The days and the times run in rising order, so a strict test keeps the
     * earlier time on a tie. */
    for (int64_t day = today - 1; day <= today + 1; day++) {
        for (uint8_t i = 0; i < d->schedule.count; i++) {
            int64_t t = dose_at(d, day, i);
            int64_t gap = t >= now_local ? t - now_local : now_local - t;
            if (!found || gap < best_gap) {
                found = true;
                best = t;
                best_gap = gap;
            }
        }
    }
    return best;
}

bool dose_took_it(dose_t *d, int64_t now_us)
{
    dose_entry_t last;
    if (dose_last(d, &last) && now_us - last.time_us < DOSE_LOCK_US) {
        return false;
    }
    /* The due rule runs at the tap's time first, as a tick would, so a dose
     * time that passed since the last tick is due when the tap answers it.
     * A tap that the state task takes after a later tick skips this, so the
     * last tick never moves back. */
    if (d->ticked && now_us > d->last_tick_us) {
        (void)dose_tick(d, now_us);
    }
    dose_entry_t entry;
    entry.time_us = now_us;
    if (d->due) {
        entry.answers_local_us = d->due_local_us;
    } else if (is_on(d)) {
        entry.answers_local_us = nearest(d, now_us + d->offset_us);
    } else {
        entry.answers_local_us = DOSE_NONE;
    }

    if (d->log_kept < DOSE_LOG_LEN) {
        d->log[(d->log_head + d->log_kept) % DOSE_LOG_LEN] = entry;
        d->log_kept++;
    } else {
        d->log[d->log_head] = entry;
        d->log_head = (d->log_head + 1) % DOSE_LOG_LEN;
    }
    d->count++;
    d->due = false;
    return true;
}

bool dose_is_due(const dose_t *d)
{
    return d->due;
}

bool dose_due_time(const dose_t *d, int64_t *local_us)
{
    if (!d->due) {
        return false;
    }
    *local_us = d->due_local_us;
    return true;
}

bool dose_last(const dose_t *d, dose_entry_t *out)
{
    if (d->log_kept == 0) {
        return false;
    }
    *out = d->log[(d->log_head + d->log_kept - 1) % DOSE_LOG_LEN];
    return true;
}

uint32_t dose_count(const dose_t *d)
{
    return d->count;
}

bool dose_next(const dose_t *d, int64_t now_us, int64_t *local_us)
{
    if (!is_on(d)) {
        return false;
    }
    if (d->due) {
        *local_us = d->due_local_us;
        return true;
    }
    /* A logged dose covers only times up to 1 hour after it, so a time on the
     * day after tomorrow is never covered. */
    int64_t now_local = now_us + d->offset_us;
    int64_t today = floor_div(now_local, DAY_US);
    for (int64_t day = today; day <= today + 2; day++) {
        for (uint8_t i = 0; i < d->schedule.count; i++) {
            int64_t t = dose_at(d, day, i);
            if (t > now_local && !covered(d, t)) {
                *local_us = t;
                return true;
            }
        }
    }
    return false;
}
