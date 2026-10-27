/*
 * dose.h holds the dose schedule and the due rule.
 *
 * The schedule has one medicine name and up to six local clock times a day.
 * A dose time becomes due at that clock time unless a dose was logged in the
 * hour before it. The due state ends when "Took it" is tapped or fifteen
 * minutes pass, and the watch does not remind again. Until the clock is set,
 * the schedule stays off.
 *
 * Time counts in the watch's 64-bit microsecond timer. The local clock in
 * microseconds since 1970 is the timer plus an offset, which
 * dose_set_clock() sets. A dose time is a local time in microseconds since
 * 1970. A schedule time is a minute of the local day.
 *
 * The caller owns the state. The file has no static data that changes. On the
 * watch the state task owns the doses.
 */

#ifndef DOSE_H
#define DOSE_H

#include <stdbool.h>
#include <stdint.h>

/* A schedule holds at most 6 times a day. */
#define DOSE_MAX_TIMES 6
/* A medicine name holds at most 20 bytes, without its zero byte. */
#define DOSE_NAME_MAX 20
/* The rules keep the latest 8 doses. */
#define DOSE_LOG_LEN 8
#define DOSE_DAY_MINUTES 1440
/* A due dose ends 15 minutes after its time. */
#define DOSE_DUE_US 900000000
/* A dose logged in the hour before a dose time stops it becoming due. */
#define DOSE_BEFORE_US 3600000000
/* After a dose is logged, taps are refused for 3 seconds. */
#define DOSE_LOCK_US 3000000
/* The answered time of a dose that answers no scheduled time. */
#define DOSE_NONE (-1)

/* dose_tick() sets this flag when a dose time becomes due, so the tone plays. */
#define DOSE_BECAME_DUE 1u
/* dose_tick() sets this flag when a due dose ends after 15 minutes. */
#define DOSE_DUE_ENDED 2u

typedef struct {
    /* The medicine name, ended by a zero byte. */
    char name[DOSE_NAME_MAX + 1];
    /* The number of times, from 0 to 6. A schedule with no times is off. */
    uint8_t count;
    /* The times as minutes of the local day, from 0 to 1439. */
    uint16_t minutes[DOSE_MAX_TIMES];
} dose_schedule_t;

typedef struct {
    /* The timer value of the tap. */
    int64_t time_us;
    /* The local time of the scheduled dose that the tap answers, or DOSE_NONE. */
    int64_t answers_local_us;
} dose_entry_t;

typedef struct {
    /* The schedule, with its times in rising order. */
    dose_schedule_t schedule;
    /* The local clock is the timer plus offset_us once clock_set is true. */
    bool clock_set;
    int64_t offset_us;
    /* The timer value of the last tick, once ticked is true. Setting the
     * clock, setting the schedule, and starting a session count as ticks. */
    bool ticked;
    int64_t last_tick_us;
    /* The local time of the due dose, while due is true. */
    bool due;
    int64_t due_local_us;
    /* The latest doses in a ring. The oldest kept dose sits at log_head. */
    dose_entry_t log[DOSE_LOG_LEN];
    uint32_t log_head;
    uint32_t log_kept;
    /* The number of doses in the session. */
    uint32_t count;
} dose_t;

/* dose_init() clears everything. The first tick after it only records its time. */
void dose_init(dose_t *d);

/* dose_set_schedule() checks and stores the schedule, and it counts as a tick
 * that makes nothing due. It refuses a name of more than 20 bytes, more than 6
 * times, a time above 1439, or a time given twice. A refused schedule leaves
 * the old one in place, and the call returns false. */
bool dose_set_schedule(dose_t *d, const dose_schedule_t *s, int64_t now_us);

/* dose_set_clock() sets the clock, so the local time is the timer plus
 * offset_us. It counts as a tick that makes nothing due. */
void dose_set_clock(dose_t *d, int64_t offset_us, int64_t now_us);

/* dose_new_session() drops the doses and any due dose. It keeps the schedule
 * and the clock, and it counts as a tick that makes nothing due. */
void dose_new_session(dose_t *d, int64_t now_us);

/* dose_tick() applies the due rule and returns the flags. The state task calls
 * it at least once a second. */
unsigned dose_tick(dose_t *d, int64_t now_us);

/* dose_took_it() logs a dose at now_us and ends a due dose. It refuses a tap
 * less than 3 seconds after the last accepted dose and returns false. */
bool dose_took_it(dose_t *d, int64_t now_us);

bool dose_is_due(const dose_t *d);

/* dose_due_time() gives the due dose's local time. It returns false when no
 * dose is due. */
bool dose_due_time(const dose_t *d, int64_t *local_us);

/* dose_last() gives the latest dose. It returns false when the session has none. */
bool dose_last(const dose_t *d, dose_entry_t *out);

/* dose_count() gives the number of doses in the session. */
uint32_t dose_count(const dose_t *d);

/* dose_next() gives the dose time that the Medication screen shows. It is the
 * due dose's time while a dose is due. Otherwise it is the first scheduled
 * time after now that no logged dose covers by the hour rule. It returns false
 * when the clock is not set or the schedule is off. */
bool dose_next(const dose_t *d, int64_t now_us, int64_t *local_us);

#endif /* DOSE_H */
