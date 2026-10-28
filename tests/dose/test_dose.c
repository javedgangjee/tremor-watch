/*
 * Unit tests for the dose schedule and the due rule in core/dose.c.
 *
 * The clock offset is 20748 days, so the timer counts microseconds from local
 * midnight at the start of 22 October 2026, and 08:00:00 is the timer value
 * 28,800,000,000. Unless a case says otherwise, the schedule is "Levodopa" at
 * 08:00, 12:00, and 16:00, the clock is set at 06:00:00, the schedule is set
 * at 06:00:00, and a run of ticks calls dose_tick() at every whole second.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "dose.h"
#include "unity.h"

#define SECOND_US INT64_C(1000000)
#define DAY_US (INT64_C(86400) * SECOND_US)
#define OFFSET_US (INT64_C(20748) * DAY_US)
/* AT() gives the timer value of a clock time on 22 October. */
#define AT(h, m, s) (((INT64_C(h) * 60 + (m)) * 60 + (s)) * SECOND_US)
/* LOCAL() gives the local time of a clock time on 22 October plus `day` days. */
#define LOCAL(day, h, m) (OFFSET_US + (day) * DAY_US + AT(h, m, 0))
/* The most events that a run checks. */
#define MAX_EVENTS 8

typedef struct {
    /* The timer value of the tick. */
    int64_t at;
    /* The flags that the tick must return. */
    unsigned flags;
    /* The due dose's local time after a DOSE_BECAME_DUE tick. */
    int64_t due_local;
} event_t;

static dose_t dose;

void setUp(void) {}

void tearDown(void) {}

static dose_schedule_t schedule(const char *name, uint8_t count, const uint16_t *minutes)
{
    dose_schedule_t s;
    memset(&s, 0, sizeof(s));
    strncpy(s.name, name, sizeof(s.name) - 1);
    s.count = count;
    for (uint8_t i = 0; i < count && i < DOSE_MAX_TIMES; i++) {
        s.minutes[i] = minutes[i];
    }
    return s;
}

/* set_times() sets the schedule "Levodopa" with the given times at 06:00:00. */
static void set_times(uint8_t count, const uint16_t *minutes)
{
    dose_schedule_t s = schedule("Levodopa", count, minutes);
    TEST_ASSERT_TRUE(dose_set_schedule(&dose, &s, AT(6, 0, 0)));
}

/* start_default() sets the clock and the schedule at 06:00:00. */
static void start_default(void)
{
    const uint16_t minutes[] = {8 * 60, 12 * 60, 16 * 60};
    dose_init(&dose);
    dose_set_clock(&dose, OFFSET_US, AT(6, 0, 0));
    set_times(3, minutes);
}

/* run() ticks at every whole second from `from` to `to`, both included. Each
 * tick at an event's time must return the event's flags, and every other tick
 * must return no flag. */
static void run(int64_t from, int64_t to, const event_t *events, int n_events)
{
    for (int64_t t = from; t <= to; t += SECOND_US) {
        unsigned want = 0;
        int64_t want_due = 0;
        for (int i = 0; i < n_events; i++) {
            if (events[i].at == t) {
                want = events[i].flags;
                want_due = events[i].due_local;
            }
        }
        unsigned got = dose_tick(&dose, t);
        if (got != want) {
            char msg[64];
            snprintf(msg, sizeof(msg), "tick at %lld s", (long long)(t / SECOND_US));
            TEST_FAIL_MESSAGE(msg);
        }
        if (want == DOSE_BECAME_DUE) {
            int64_t due;
            TEST_ASSERT_TRUE(dose_due_time(&dose, &due));
            TEST_ASSERT_EQUAL_INT64(want_due, due);
        }
    }
}

static void quiet(int64_t from, int64_t to)
{
    run(from, to, NULL, 0);
}

static void test_1_schedule_limits(void)
{
    const uint16_t six[] = {0, 300, 600, 900, 1200, 1439};
    const uint16_t seven[] = {0, 1, 2, 3, 4, 5};
    const uint16_t bad_time[] = {480, 1440};
    const uint16_t twice[] = {480, 720, 480};
    const uint16_t shuffled[] = {960, 480, 720};
    dose_schedule_t s;
    dose_init(&dose);

    s = schedule("Levodopa", 0, NULL);
    TEST_ASSERT_TRUE(dose_set_schedule(&dose, &s, 0));
    TEST_ASSERT_EQUAL_UINT8(0, dose.schedule.count);
    s = schedule("Levodopa", 6, six);
    TEST_ASSERT_TRUE(dose_set_schedule(&dose, &s, 0));
    TEST_ASSERT_EQUAL_UINT8(6, dose.schedule.count);
    TEST_ASSERT_EQUAL_UINT16(0, dose.schedule.minutes[0]);
    TEST_ASSERT_EQUAL_UINT16(1439, dose.schedule.minutes[5]);
    s = schedule("ABCDEFGHIJKLMNOPQRST", 3, shuffled);
    TEST_ASSERT_EQUAL_size_t(20, strlen(s.name));
    TEST_ASSERT_TRUE(dose_set_schedule(&dose, &s, 0));
    TEST_ASSERT_EQUAL_STRING("ABCDEFGHIJKLMNOPQRST", dose.schedule.name);
    TEST_ASSERT_EQUAL_UINT8(3, dose.schedule.count);
    TEST_ASSERT_EQUAL_UINT16(480, dose.schedule.minutes[0]);
    TEST_ASSERT_EQUAL_UINT16(720, dose.schedule.minutes[1]);
    TEST_ASSERT_EQUAL_UINT16(960, dose.schedule.minutes[2]);

    /* Each refusal leaves the schedule above in place. */
    s = schedule("Levodopa", 6, seven);
    s.count = 7;
    TEST_ASSERT_FALSE(dose_set_schedule(&dose, &s, 0));
    s = schedule("Levodopa", 2, bad_time);
    TEST_ASSERT_FALSE(dose_set_schedule(&dose, &s, 0));
    s = schedule("Levodopa", 3, twice);
    TEST_ASSERT_FALSE(dose_set_schedule(&dose, &s, 0));
    s = schedule("Levodopa", 3, shuffled);
    memset(s.name, 'A', sizeof(s.name));
    TEST_ASSERT_FALSE(dose_set_schedule(&dose, &s, 0));
    TEST_ASSERT_EQUAL_STRING("ABCDEFGHIJKLMNOPQRST", dose.schedule.name);
    TEST_ASSERT_EQUAL_UINT8(3, dose.schedule.count);
    TEST_ASSERT_EQUAL_UINT16(480, dose.schedule.minutes[0]);
    TEST_ASSERT_EQUAL_UINT16(720, dose.schedule.minutes[1]);
    TEST_ASSERT_EQUAL_UINT16(960, dose.schedule.minutes[2]);
}

static void test_2_no_clock_no_dose(void)
{
    const uint16_t minutes[] = {8 * 60, 12 * 60, 16 * 60};
    int64_t next;
    dose_init(&dose);
    set_times(3, minutes);
    quiet(AT(7, 59, 0), AT(8, 16, 0));
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_FALSE(dose_next(&dose, AT(8, 16, 0), &next));
}

static void test_3_due_and_ended(void)
{
    start_default();
    quiet(AT(6, 0, 0), AT(7, 59, 59));
    const event_t became = {AT(8, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 8, 0)};
    run(AT(8, 0, 0), AT(8, 0, 0), &became, 1);
    quiet(AT(8, 0, 1), AT(8, 14, 59));
    TEST_ASSERT_TRUE(dose_is_due(&dose));
    const event_t ended = {AT(8, 15, 0), DOSE_DUE_ENDED, 0};
    run(AT(8, 15, 0), AT(8, 15, 0), &ended, 1);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    quiet(AT(8, 15, 1), AT(11, 59, 59));
    const event_t noon = {AT(12, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 12, 0)};
    run(AT(12, 0, 0), AT(12, 0, 0), &noon, 1);
}

static void test_4_tap_ends_due_dose(void)
{
    const event_t became = {AT(8, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 8, 0)};
    dose_entry_t last;
    start_default();
    run(AT(6, 0, 0), AT(8, 5, 0), &became, 1);
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(8, 5, 0)));
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_TRUE(dose_last(&dose, &last));
    TEST_ASSERT_EQUAL_INT64(AT(8, 5, 0), last.time_us);
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 8, 0), last.answers_local_us);
    quiet(AT(8, 5, 1), AT(11, 59, 59));
}

/* hour_run() ticks from 06:50:00 to 08:01:00 with one tap. The tap comes just
 * before the tick at tick_after, and it has the time tap_us. */
static void hour_run(int64_t tap_us, int64_t tick_after, bool want_due)
{
    const event_t became = {AT(8, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 8, 0)};
    start_default();
    quiet(AT(6, 50, 0), tick_after - SECOND_US);
    TEST_ASSERT_TRUE(dose_took_it(&dose, tap_us));
    run(tick_after, AT(8, 1, 0), &became, want_due ? 1 : 0);
}

static void test_5_hour_before_rule(void)
{
    /* A tap at 07:00:00 after that second's tick. */
    hour_run(AT(7, 0, 0), AT(7, 0, 1), false);
    /* A tap at 06:59:59.999999. */
    hour_run(AT(7, 0, 0) - 1, AT(7, 0, 0), true);
    /* A tap at 07:30:00. */
    hour_run(AT(7, 30, 0), AT(7, 30, 1), false);
    /* A tap at 08:00:00 before that second's tick. */
    hour_run(AT(8, 0, 0), AT(8, 0, 0), false);
}

static void test_6_gap_between_ticks(void)
{
    start_default();
    TEST_ASSERT_EQUAL_UINT(0, dose_tick(&dose, AT(7, 59, 58)));
    TEST_ASSERT_EQUAL_UINT(DOSE_BECAME_DUE, dose_tick(&dose, AT(8, 0, 5)));
    TEST_ASSERT_EQUAL_UINT(DOSE_DUE_ENDED, dose_tick(&dose, AT(8, 15, 0)));

    start_default();
    TEST_ASSERT_EQUAL_UINT(0, dose_tick(&dose, AT(7, 50, 0)));
    TEST_ASSERT_EQUAL_UINT(0, dose_tick(&dose, AT(8, 16, 0)));
    TEST_ASSERT_FALSE(dose_is_due(&dose));
}

static void test_7_setting_the_clock(void)
{
    const uint16_t minutes[] = {8 * 60, 12 * 60, 16 * 60};
    const event_t noon = {AT(12, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 12, 0)};
    int64_t next;
    dose_init(&dose);
    set_times(3, minutes);
    dose_set_clock(&dose, OFFSET_US, AT(8, 5, 0));
    run(AT(8, 5, 0), AT(12, 0, 0), &noon, 1);

    start_default();
    quiet(AT(6, 0, 0), AT(6, 59, 59));
    dose_set_clock(&dose, OFFSET_US + AT(2, 0, 0), AT(7, 0, 0));
    quiet(AT(7, 0, 0), AT(7, 30, 0));
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_TRUE(dose_next(&dose, AT(7, 30, 0), &next));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 12, 0), next);
}

static void test_8_later_time_takes_the_place(void)
{
    const uint16_t minutes[] = {8 * 60, 8 * 60 + 10};
    const event_t events[] = {
        {AT(8, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 8, 0)},
        {AT(8, 10, 0), DOSE_BECAME_DUE, LOCAL(0, 8, 10)},
        {AT(8, 25, 0), DOSE_DUE_ENDED, 0},
    };
    dose_init(&dose);
    dose_set_clock(&dose, OFFSET_US, AT(6, 0, 0));
    set_times(2, minutes);
    run(AT(6, 0, 0), AT(8, 24, 59), events, 2);
    TEST_ASSERT_TRUE(dose_is_due(&dose));
    run(AT(8, 25, 0), AT(8, 25, 0), &events[2], 1);
    TEST_ASSERT_FALSE(dose_is_due(&dose));

    dose_init(&dose);
    dose_set_clock(&dose, OFFSET_US, AT(6, 0, 0));
    set_times(2, minutes);
    run(AT(6, 0, 0), AT(8, 5, 0), events, 1);
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(8, 5, 0)));
    quiet(AT(8, 5, 1), AT(8, 30, 0));
    TEST_ASSERT_FALSE(dose_is_due(&dose));
}

static void test_9_midnight(void)
{
    const uint16_t minutes[] = {0, 23 * 60 + 30};
    const event_t events[] = {
        {AT(23, 30, 0), DOSE_BECAME_DUE, LOCAL(0, 23, 30)},
        {AT(23, 45, 0), DOSE_DUE_ENDED, 0},
        {DAY_US + AT(0, 0, 0), DOSE_BECAME_DUE, LOCAL(1, 0, 0)},
        {DAY_US + AT(0, 15, 0), DOSE_DUE_ENDED, 0},
    };
    dose_schedule_t s = schedule("Levodopa", 2, minutes);
    dose_init(&dose);
    dose_set_clock(&dose, OFFSET_US, AT(23, 0, 0));
    TEST_ASSERT_TRUE(dose_set_schedule(&dose, &s, AT(23, 0, 0)));
    run(AT(23, 0, 0), AT(23, 44, 59), events, 4);
    TEST_ASSERT_TRUE(dose_is_due(&dose));
    run(AT(23, 45, 0), DAY_US + AT(0, 20, 0), events, 4);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
}

static void test_10_three_second_lock(void)
{
    start_default();
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(9, 0, 0)));
    TEST_ASSERT_FALSE(dose_took_it(&dose, AT(9, 0, 3) - 1));
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(9, 0, 3)));
    TEST_ASSERT_EQUAL_UINT32(2, dose_count(&dose));
}

/* answered() gives the answered time of one tap at tap_us in a new run. */
static int64_t answered(int64_t tap_us)
{
    dose_entry_t last;
    start_default();
    TEST_ASSERT_TRUE(dose_took_it(&dose, tap_us));
    TEST_ASSERT_TRUE(dose_last(&dose, &last));
    return last.answers_local_us;
}

static void test_11_answered_time(void)
{
    const uint16_t minutes[] = {8 * 60, 12 * 60, 16 * 60};
    dose_entry_t last;
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 8, 0), answered(AT(9, 0, 0)));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 12, 0), answered(AT(10, 30, 0)));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 8, 0), answered(AT(10, 0, 0)));

    dose_init(&dose);
    set_times(3, minutes);
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(9, 0, 0)));
    TEST_ASSERT_TRUE(dose_last(&dose, &last));
    TEST_ASSERT_EQUAL_INT64(DOSE_NONE, last.answers_local_us);

    dose_init(&dose);
    dose_set_clock(&dose, OFFSET_US, AT(6, 0, 0));
    set_times(0, NULL);
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(9, 0, 0)));
    TEST_ASSERT_TRUE(dose_last(&dose, &last));
    TEST_ASSERT_EQUAL_INT64(DOSE_NONE, last.answers_local_us);
}

static void test_12_next_dose(void)
{
    const event_t events[] = {
        {AT(8, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 8, 0)},
        {AT(8, 15, 0), DOSE_DUE_ENDED, 0},
        {AT(16, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 16, 0)},
        {AT(16, 15, 0), DOSE_DUE_ENDED, 0},
    };
    int64_t next;
    start_default();
    run(AT(6, 0, 0), AT(7, 0, 0), events, 4);
    TEST_ASSERT_TRUE(dose_next(&dose, AT(7, 0, 0), &next));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 8, 0), next);
    run(AT(7, 0, 1), AT(8, 5, 0), events, 4);
    TEST_ASSERT_TRUE(dose_next(&dose, AT(8, 5, 0), &next));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 8, 0), next);
    run(AT(8, 5, 1), AT(8, 20, 0), events, 4);
    TEST_ASSERT_TRUE(dose_next(&dose, AT(8, 20, 0), &next));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 12, 0), next);
    run(AT(8, 20, 1), AT(11, 30, 0), events, 4);
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(11, 30, 0)));
    TEST_ASSERT_TRUE(dose_next(&dose, AT(11, 30, 0), &next));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 16, 0), next);
    run(AT(11, 30, 1), AT(17, 0, 0), events, 4);
    TEST_ASSERT_TRUE(dose_next(&dose, AT(17, 0, 0), &next));
    TEST_ASSERT_EQUAL_INT64(LOCAL(1, 8, 0), next);
}

static void test_13_new_session(void)
{
    const event_t became = {AT(8, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 8, 0)};
    const event_t noon = {AT(12, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 12, 0)};
    dose_entry_t last;
    start_default();
    run(AT(6, 0, 0), AT(8, 5, 0), &became, 1);
    dose_new_session(&dose, AT(8, 5, 0));
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_EQUAL_UINT32(0, dose_count(&dose));
    TEST_ASSERT_FALSE(dose_last(&dose, &last));
    TEST_ASSERT_EQUAL_UINT8(3, dose.schedule.count);
    TEST_ASSERT_EQUAL_STRING("Levodopa", dose.schedule.name);
    run(AT(8, 5, 1), AT(12, 0, 0), &noon, 1);
}

static void test_14_ten_taps(void)
{
    dose_entry_t last;
    start_default();
    quiet(AT(6, 0, 0), AT(7, 57, 59));
    for (int i = 0; i < 10; i++) {
        int64_t t = AT(7, 58, 0) + 3 * SECOND_US * i;
        quiet(t, t);
        TEST_ASSERT_TRUE(dose_took_it(&dose, t));
        quiet(t + SECOND_US, t + 2 * SECOND_US);
    }
    quiet(AT(7, 58, 30), AT(8, 16, 0));
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_EQUAL_UINT32(10, dose_count(&dose));
    TEST_ASSERT_TRUE(dose_last(&dose, &last));
    TEST_ASSERT_EQUAL_INT64(AT(7, 58, 27), last.time_us);
}

static void test_15_empty_schedule(void)
{
    int64_t next;
    dose_init(&dose);
    dose_set_clock(&dose, OFFSET_US, AT(0, 0, 0));
    set_times(0, NULL);
    quiet(AT(0, 0, 0), DAY_US);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_FALSE(dose_next(&dose, AT(12, 0, 0), &next));
}

/* A tick comes at 0.6 s past each second, as on the watch, where the ticks do
 * not line up with the minute. */
#define PHASE_US 600000

static void test_16_tap_before_the_tick(void)
{
    const uint16_t two[] = {7 * 60 + 55, 8 * 60};
    dose_entry_t last;

    /* A tap at 08:00:00.4 answers 08:00, so the tick at 08:00:00.6 makes
     * nothing due. */
    start_default();
    quiet(AT(7, 0, 0) + PHASE_US, AT(7, 59, 59) + PHASE_US);
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(8, 0, 0) + 400000));
    TEST_ASSERT_TRUE(dose_last(&dose, &last));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 8, 0), last.answers_local_us);
    quiet(AT(8, 0, 0) + PHASE_US, AT(8, 16, 0) + PHASE_US);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_EQUAL_UINT32(1, dose_count(&dose));

    /* With 07:55 due, a tap at 08:00:00.4 answers 08:00, as it would if a
     * tick had come at the tap. Nothing becomes due after it. */
    dose_init(&dose);
    dose_set_clock(&dose, OFFSET_US, AT(6, 0, 0));
    set_times(2, two);
    const event_t became = {AT(7, 55, 0) + PHASE_US, DOSE_BECAME_DUE, LOCAL(0, 7, 55)};
    run(AT(7, 0, 0) + PHASE_US, AT(7, 59, 59) + PHASE_US, &became, 1);
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(8, 0, 0) + 400000));
    TEST_ASSERT_TRUE(dose_last(&dose, &last));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 8, 0), last.answers_local_us);
    quiet(AT(8, 0, 0) + PHASE_US, AT(8, 16, 0) + PHASE_US);
    TEST_ASSERT_FALSE(dose_is_due(&dose));

    /* The state task may take a tap after a tick that came later than the
     * tap. The tick at 08:00:00.6 makes 08:00 due, and the tap at 08:00:00.4
     * then answers it. Nothing becomes due after it. */
    start_default();
    const event_t eight = {AT(8, 0, 0) + PHASE_US, DOSE_BECAME_DUE, LOCAL(0, 8, 0)};
    run(AT(7, 0, 0) + PHASE_US, AT(8, 0, 0) + PHASE_US, &eight, 1);
    TEST_ASSERT_TRUE(dose_took_it(&dose, AT(8, 0, 0) + 400000));
    TEST_ASSERT_TRUE(dose_last(&dose, &last));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 8, 0), last.answers_local_us);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    quiet(AT(8, 0, 1) + PHASE_US, AT(8, 16, 0) + PHASE_US);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
}

/* due_at_eight() runs the default schedule from 06:00:00 to 08:01:00, so
 * 08:00 is due. */
static void due_at_eight(void)
{
    const event_t became = {AT(8, 0, 0), DOSE_BECAME_DUE, LOCAL(0, 8, 0)};
    start_default();
    run(AT(6, 0, 0), AT(8, 1, 0), &became, 1);
    TEST_ASSERT_TRUE(dose_is_due(&dose));
}

static void test_17_schedule_change_while_due(void)
{
    const uint16_t later[] = {12 * 60, 16 * 60};
    const uint16_t keeps[] = {8 * 60, 20 * 60};
    const event_t ended_now = {AT(8, 1, 1), DOSE_DUE_ENDED, 0};
    const event_t ended_late = {AT(8, 15, 0), DOSE_DUE_ENDED, 0};
    dose_schedule_t s;
    int64_t next;

    /* A schedule without 08:00 ends the due dose at the next tick. */
    due_at_eight();
    s = schedule("Levodopa", 2, later);
    TEST_ASSERT_TRUE(dose_set_schedule(&dose, &s, AT(8, 1, 0)));
    run(AT(8, 1, 1), AT(11, 59, 59), &ended_now, 1);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_TRUE(dose_next(&dose, AT(11, 59, 59), &next));
    TEST_ASSERT_EQUAL_INT64(LOCAL(0, 12, 0), next);

    /* An empty schedule ends the due dose at the next tick. */
    due_at_eight();
    s = schedule("Levodopa", 0, NULL);
    TEST_ASSERT_TRUE(dose_set_schedule(&dose, &s, AT(8, 1, 0)));
    run(AT(8, 1, 1), AT(9, 0, 0), &ended_now, 1);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
    TEST_ASSERT_FALSE(dose_next(&dose, AT(9, 0, 0), &next));

    /* A schedule that still holds 08:00 keeps it due until 08:15. */
    due_at_eight();
    s = schedule("Levodopa", 2, keeps);
    TEST_ASSERT_TRUE(dose_set_schedule(&dose, &s, AT(8, 1, 0)));
    run(AT(8, 1, 1), AT(8, 14, 59), NULL, 0);
    TEST_ASSERT_TRUE(dose_is_due(&dose));
    run(AT(8, 15, 0), AT(8, 15, 0), &ended_late, 1);
    TEST_ASSERT_FALSE(dose_is_due(&dose));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_schedule_limits);
    RUN_TEST(test_2_no_clock_no_dose);
    RUN_TEST(test_3_due_and_ended);
    RUN_TEST(test_4_tap_ends_due_dose);
    RUN_TEST(test_5_hour_before_rule);
    RUN_TEST(test_6_gap_between_ticks);
    RUN_TEST(test_7_setting_the_clock);
    RUN_TEST(test_8_later_time_takes_the_place);
    RUN_TEST(test_9_midnight);
    RUN_TEST(test_10_three_second_lock);
    RUN_TEST(test_11_answered_time);
    RUN_TEST(test_12_next_dose);
    RUN_TEST(test_13_new_session);
    RUN_TEST(test_14_ten_taps);
    RUN_TEST(test_15_empty_schedule);
    RUN_TEST(test_16_tap_before_the_tick);
    RUN_TEST(test_17_schedule_change_while_due);
    return UNITY_END();
}
