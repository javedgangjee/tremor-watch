/*
 * Unit tests for the time rule in core/reading_time.c.
 *
 * Each case feeds the rule a burst stream that a helper builds from a list of
 * rates and stamp shifts. Every burst holds 11 readings, the first burst starts
 * at reading 0, and each burst is stamped at the time of its eleventh reading,
 * rounded to a whole microsecond. The first stamp is 1,000,000 microseconds.
 */

#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "reading_time.h"
#include "unity.h"

#define BURST_LEN 11
#define FIRST_STAMP_US 1000000
#define MAX_BURSTS 13000
#define MAX_SHIFTS 4
/* No overflow in the stream. */
#define NO_OVERFLOW (-1.0)

/* The rate measured over twenty minutes in firmware/bringup/rate_log.txt. */
#define BOARD_RATE_UHZ 114330200u
/* A measured rate must lie within this many millionths of the true rate. */
#define RATE_NEAR 10
/* A stretch takes its rate after 10 seconds of stamps. */
#define RATE_SPAN_US 10000000
/* Every stretch except the last must last at least 60 seconds, because the
 * plan says a stretch "is minutes long". */
#define MIN_STRETCH_US 60000000

/* The twenty one-minute rates in firmware/bringup/rate_log.txt, in millionths
 * of a reading per second. They are copied here because feature 7 may delete
 * that folder. */
static const uint32_t board_minutes[20] = {
    114338600u, 114336300u, 114336000u, 114333300u, 114333300u, 114333300u, 114331400u,
    114329500u, 114330600u, 114328900u, 114329500u, 114327600u, 114328100u, 114327600u,
    114327600u, 114326200u, 114327600u, 114325700u, 114326200u, 114325700u,
};

typedef struct {
    /* Each later stamp moves by shift_us from at_s seconds after the first stamp. */
    double at_s;
    int64_t shift_us;
} shift_t;

typedef struct {
    double seconds;
    const uint32_t *rates;
    int n_rates;
    /* Each rate holds for this many seconds, and the last one holds to the end. */
    double rate_s;
    shift_t shifts[MAX_SHIFTS];
    int n_shifts;
    /* The first burst at or after this many seconds has the overflow flag set. */
    double overflow_at_s;
} stream_t;

typedef struct {
    uint64_t first;
    uint32_t count;
    int64_t stamp;
    bool overflow;
    /* The seconds from the first stamp to the burst's true time. */
    double at_s;
} burst_t;

static burst_t bursts[MAX_BURSTS];
static int n_bursts;
static unsigned flags[MAX_BURSTS];
/* The stretch after each burst. */
static rt_stretch_t after[MAX_BURSTS];
static rt_state_t state;

void setUp(void) {}

void tearDown(void) {}

/* make_stream() builds the bursts of a stream. Each reading takes 1e12 / rate
 * microseconds, with the rate of the time at its start. */
static void make_stream(const stream_t *st)
{
    double t = FIRST_STAMP_US;
    uint64_t reading = BURST_LEN - 1;
    bool overflow_done = false;
    n_bursts = 0;
    while (t - FIRST_STAMP_US < st->seconds * 1e6) {
        TEST_ASSERT_LESS_THAN_INT(MAX_BURSTS, n_bursts);
        double elapsed = t - FIRST_STAMP_US;
        burst_t *b = &bursts[n_bursts++];
        b->first = reading + 1 - BURST_LEN;
        b->count = BURST_LEN;
        b->at_s = elapsed / 1e6;
        b->stamp = (int64_t)llround(t);
        for (int i = 0; i < st->n_shifts; i++) {
            if (elapsed >= st->shifts[i].at_s * 1e6) {
                b->stamp += st->shifts[i].shift_us;
            }
        }
        b->overflow = !overflow_done && st->overflow_at_s >= 0.0 && elapsed >= st->overflow_at_s * 1e6;
        overflow_done = overflow_done || b->overflow;
        for (int i = 0; i < BURST_LEN; i++) {
            int index = (int)((t - FIRST_STAMP_US) / (st->rate_s * 1e6));
            index = index < st->n_rates ? index : st->n_rates - 1;
            t += 1e12 / (double)st->rates[index];
            reading++;
        }
    }
}

/* run_stream() feeds every burst to a fresh time rule. */
static void run_stream(void)
{
    rt_init(&state);
    for (int i = 0; i < n_bursts; i++) {
        const burst_t *b = &bursts[i];
        flags[i] = rt_burst(&state, b->first, b->count, b->stamp, b->overflow);
        after[i] = *rt_current(&state);
    }
}

/* steady() builds and runs a stream at one rate with the given shifts. */
static void steady(uint32_t rate, double seconds, const shift_t *shifts, int n_shifts, double overflow_at_s)
{
    static uint32_t one[1];
    one[0] = rate;
    stream_t st = {seconds, one, 1, 1e9, {{0.0, 0}}, n_shifts, overflow_at_s};
    for (int i = 0; i < n_shifts; i++) {
        st.shifts[i] = shifts[i];
    }
    make_stream(&st);
    run_stream();
}

/* formula_rate() gives floor(df * 1e12 / ds + 0.5) from burst a to burst b. */
static uint32_t formula_rate(int a, int b)
{
    double df = (double)(bursts[b].first - bursts[a].first);
    double ds = (double)(bursts[b].stamp - bursts[a].stamp);
    return (uint32_t)floor(df * 1e12 / ds + 0.5);
}

/* first_at() gives the first burst at or after `seconds` from the first stamp. */
static int first_at(double seconds)
{
    for (int i = 0; i < n_bursts; i++) {
        if (bursts[i].at_s >= seconds) {
            return i;
        }
    }
    TEST_FAIL_MESSAGE("no burst at that time");
    return -1;
}

/* rate_burst() gives the first burst whose stamp is at least 10 seconds after t0. */
static int rate_burst(int start)
{
    for (int i = start; i < n_bursts; i++) {
        if (bursts[i].stamp - after[start].t0_us >= RATE_SPAN_US) {
            return i;
        }
    }
    TEST_FAIL_MESSAGE("no burst 10 seconds after t0");
    return -1;
}

static void assert_near_rate(uint32_t want, uint32_t got)
{
    TEST_ASSERT_TRUE_MESSAGE(got >= want - RATE_NEAR && got <= want + RATE_NEAR, "the rate is not within 10");
}

/* half_period_gap() gives how far the burst lies from the stretch's prediction,
 * less half a period. A positive value means the burst lies outside. */
static double half_period_gap(const rt_stretch_t *st, int i)
{
    double predicted = rt_reading_time_us(st, bursts[i].first);
    return fabs((double)bursts[i].stamp - predicted) - 5e11 / (double)st->rate_uhz;
}

static void check_steady(uint32_t rate)
{
    steady(rate, 60.0, NULL, 0, NO_OVERFLOW);
    TEST_ASSERT_EQUAL_UINT(RT_NEW_STRETCH, flags[0]);
    TEST_ASSERT_EQUAL_UINT32(0, after[0].number);
    TEST_ASSERT_EQUAL_UINT64(0, after[0].first_reading);
    TEST_ASSERT_EQUAL_INT64(FIRST_STAMP_US, after[0].t0_us);
    int r = rate_burst(0);
    for (int i = 0; i < r; i++) {
        TEST_ASSERT_EQUAL_UINT32(0, after[i].rate_uhz);
    }
    for (int i = 1; i < r; i++) {
        TEST_ASSERT_EQUAL_UINT(0, flags[i]);
    }
    TEST_ASSERT_EQUAL_UINT(RT_RATE_SET, flags[r]);
    TEST_ASSERT_EQUAL_UINT32(formula_rate(0, r), after[r].rate_uhz);
    assert_near_rate(rate, after[r].rate_uhz);
    for (int i = r + 1; i < n_bursts; i++) {
        TEST_ASSERT_EQUAL_UINT(0, flags[i]);
    }
    const rt_stretch_t *last = &after[n_bursts - 1];
    TEST_ASSERT_EQUAL_UINT32(0, last->number);
    TEST_ASSERT_EQUAL_UINT64(0, last->first_reading);
    TEST_ASSERT_EQUAL_INT64(FIRST_STAMP_US, last->t0_us);
    TEST_ASSERT_EQUAL_UINT32(after[r].rate_uhz, last->rate_uhz);
}

static void test_1_steady(void)
{
    check_steady(BOARD_RATE_UHZ);
}

static void test_2_steady_low_and_high(void)
{
    check_steady(50000000u);
    check_steady(150000000u);
}

static void test_3_shift_near_half_period(void)
{
    const shift_t inside = {30.0, 4353};
    steady(BOARD_RATE_UHZ, 60.0, &inside, 1, NO_OVERFLOW);
    for (int i = 1; i < n_bursts; i++) {
        TEST_ASSERT_EQUAL_UINT(0, flags[i] & RT_NEW_STRETCH);
    }
    TEST_ASSERT_EQUAL_UINT32(0, after[n_bursts - 1].number);

    const int64_t outside[2] = {4393, -4393};
    for (int k = 0; k < 2; k++) {
        const shift_t moved = {30.0, outside[k]};
        steady(BOARD_RATE_UHZ, 60.0, &moved, 1, NO_OVERFLOW);
        int m = first_at(30.0);
        for (int i = 1; i < m; i++) {
            TEST_ASSERT_EQUAL_UINT(0, flags[i] & RT_NEW_STRETCH);
        }
        TEST_ASSERT_TRUE(flags[m] & RT_NEW_STRETCH);
        TEST_ASSERT_EQUAL_UINT32(1, after[m].number);
        TEST_ASSERT_EQUAL_UINT64(bursts[m].first, after[m].first_reading);
        TEST_ASSERT_EQUAL_INT64(bursts[m].stamp, after[m].t0_us);
        TEST_ASSERT_EQUAL_UINT32(1, after[n_bursts - 1].number);
    }
}

static void test_4_overflow(void)
{
    steady(BOARD_RATE_UHZ, 60.0, NULL, 0, 30.0);
    int m = first_at(30.0);
    TEST_ASSERT_TRUE(bursts[m].overflow);
    TEST_ASSERT_EQUAL_UINT32(0, after[m - 1].number);
    TEST_ASSERT_TRUE(flags[m] & RT_NEW_STRETCH);
    TEST_ASSERT_EQUAL_UINT32(1, after[m].number);
    TEST_ASSERT_EQUAL_UINT64(bursts[m].first, after[m].first_reading);
}

static void test_5_rate_from_stretch_before(void)
{
    const shift_t jump = {30.0, 50000};
    steady(BOARD_RATE_UHZ, 60.0, &jump, 1, NO_OVERFLOW);
    int m = first_at(30.0);
    TEST_ASSERT_EQUAL_UINT(RT_NEW_STRETCH | RT_RATE_SET, flags[m]);
    TEST_ASSERT_EQUAL_UINT32(1, after[m].number);
    TEST_ASSERT_EQUAL_UINT32(formula_rate(0, m - 1), after[m].rate_uhz);
}

/* check_own_rate() checks that the stretch that starts at burst m has rate 0
 * until its own first 10 seconds pass. */
static void check_own_rate(int m)
{
    TEST_ASSERT_EQUAL_UINT(RT_NEW_STRETCH, flags[m]);
    TEST_ASSERT_EQUAL_UINT32(0, after[m].rate_uhz);
    int r = rate_burst(m);
    for (int i = m + 1; i < r; i++) {
        TEST_ASSERT_EQUAL_UINT(0, flags[i]);
        TEST_ASSERT_EQUAL_UINT32(0, after[i].rate_uhz);
    }
    TEST_ASSERT_EQUAL_UINT(RT_RATE_SET, flags[r]);
    TEST_ASSERT_EQUAL_UINT32(after[m].number, after[r].number);
    TEST_ASSERT_EQUAL_UINT32(formula_rate(m, r), after[r].rate_uhz);
}

static void test_6_short_stretch_before(void)
{
    const shift_t early = {5.0, 50000};
    steady(BOARD_RATE_UHZ, 60.0, &early, 1, NO_OVERFLOW);
    int m = first_at(5.0);
    TEST_ASSERT_EQUAL_UINT32(0, after[m - 1].rate_uhz);
    TEST_ASSERT_EQUAL_UINT32(1, after[m].number);
    check_own_rate(m);

    const shift_t two[2] = {{30.0, 50000}, {35.0, 50000}};
    steady(BOARD_RATE_UHZ, 60.0, two, 2, NO_OVERFLOW);
    int m1 = first_at(30.0);
    int m2 = first_at(35.0);
    TEST_ASSERT_EQUAL_UINT(RT_NEW_STRETCH | RT_RATE_SET, flags[m1]);
    TEST_ASSERT_EQUAL_UINT32(1, after[m1].number);
    TEST_ASSERT_EQUAL_UINT32(2, after[m2].number);
    check_own_rate(m2);
}

static void test_7_shift_before_one_second(void)
{
    const shift_t early = {0.5, 50000};
    steady(BOARD_RATE_UHZ, 60.0, &early, 1, NO_OVERFLOW);
    int m = first_at(0.5);
    TEST_ASSERT_EQUAL_UINT(0, flags[m]);
    TEST_ASSERT_EQUAL_UINT32(0, after[m].number);
    const rt_stretch_t *last = &after[n_bursts - 1];
    TEST_ASSERT_TRUE(last->t0_us - FIRST_STAMP_US < 25000000);
    for (int i = 0; i < n_bursts; i++) {
        if (bursts[i].stamp > last->t0_us) {
            TEST_ASSERT_EQUAL_UINT(0, flags[i] & RT_NEW_STRETCH);
        }
    }
    TEST_ASSERT_TRUE(last->rate_uhz != 0);
    assert_near_rate(BOARD_RATE_UHZ, last->rate_uhz);
    printf("case 7 ends in stretch %u, which starts %.3f s after the first stamp\n", (unsigned)last->number,
           (double)(last->t0_us - FIRST_STAMP_US) / 1e6);
}

static void test_8_bad_bursts(void)
{
    /* A stamp equal to the stamp before starts a new stretch. */
    steady(BOARD_RATE_UHZ, 20.0, NULL, 0, NO_OVERFLOW);
    const burst_t *last = &bursts[n_bursts - 1];
    TEST_ASSERT_TRUE(rt_current(&state)->rate_uhz != 0);
    unsigned f = rt_burst(&state, last->first + BURST_LEN, BURST_LEN, last->stamp, false);
    TEST_ASSERT_TRUE(f & RT_NEW_STRETCH);
    TEST_ASSERT_EQUAL_UINT32(1, rt_current(&state)->number);

    /* A first reading number that skips one reading starts a new stretch. */
    steady(BOARD_RATE_UHZ, 20.0, NULL, 0, NO_OVERFLOW);
    int64_t on_time = (int64_t)llround(rt_reading_time_us(rt_current(&state), last->first + BURST_LEN));
    f = rt_burst(&state, last->first + BURST_LEN + 1, BURST_LEN, on_time, false);
    TEST_ASSERT_TRUE(f & RT_NEW_STRETCH);
    TEST_ASSERT_EQUAL_UINT32(1, rt_current(&state)->number);

    /* A burst with no readings returns no flag and leaves the stretch unchanged. */
    steady(BOARD_RATE_UHZ, 20.0, NULL, 0, NO_OVERFLOW);
    static rt_state_t saved;
    memcpy(&saved, &state, sizeof state);
    f = rt_burst(&state, last->first + BURST_LEN, 0, on_time, false);
    TEST_ASSERT_EQUAL_UINT(0, f);
    TEST_ASSERT_EQUAL_INT(0, memcmp(&saved, &state, sizeof state));
    f = rt_burst(&state, last->first + BURST_LEN, BURST_LEN, on_time, false);
    TEST_ASSERT_EQUAL_UINT(0, f);
    TEST_ASSERT_EQUAL_UINT32(0, rt_current(&state)->number);
}

static void test_9_times(void)
{
    const rt_stretch_t st = {0, 1000, 5000000000LL, BOARD_RATE_UHZ};
    TEST_ASSERT_TRUE(rt_reading_time_us(&st, 1000) == 5000000000.0);
    TEST_ASSERT_TRUE(rt_reading_time_us(&st, 114331200ULL) == 1005000000000.0);
    TEST_ASSERT_DOUBLE_WITHIN(0.00001, 5000008746.5953877, rt_reading_time_us(&st, 1001));
    TEST_ASSERT_EQUAL_INT64(8600000000LL, rt_sample_time_us(&st, 360000));
}

static void test_10_twenty_minutes(void)
{
    stream_t st = {1200.0, board_minutes, 20, 60.0, {{0.0, 0}}, 0, NO_OVERFLOW};
    make_stream(&st);
    run_stream();

    int starts[64];
    int n_starts = 0;
    TEST_ASSERT_TRUE(flags[0] & RT_NEW_STRETCH);
    starts[n_starts++] = 0;
    for (int i = 1; i < n_bursts; i++) {
        const rt_stretch_t *before = &after[i - 1];
        if (flags[i] & RT_NEW_STRETCH) {
            TEST_ASSERT_TRUE_MESSAGE(before->rate_uhz != 0, "a stretch ends before it has a rate");
            TEST_ASSERT_TRUE_MESSAGE(half_period_gap(before, i) > 0.0, "a new stretch starts within half a period");
            TEST_ASSERT_LESS_THAN_INT(64, n_starts);
            int prev = starts[n_starts - 1];
            TEST_ASSERT_EQUAL_UINT32(formula_rate(prev, i - 1), after[i].rate_uhz);
            starts[n_starts++] = i;
        } else if (before->rate_uhz != 0) {
            TEST_ASSERT_TRUE_MESSAGE(half_period_gap(before, i) <= 0.0, "a burst lies outside half a period");
        }
    }

    printf("twenty minutes make %d stretches\n", n_starts);
    for (int k = 0; k < n_starts; k++) {
        int end = k + 1 < n_starts ? starts[k + 1] - 1 : n_bursts - 1;
        const rt_stretch_t *s = &after[end];
        double length_s = (double)(bursts[end].stamp - s->t0_us) / 1e6;
        printf("stretch %u: starts at %.1f s, lasts %.1f s, rate %u\n", (unsigned)s->number,
               (double)(s->t0_us - FIRST_STAMP_US) / 1e6, length_s, (unsigned)s->rate_uhz);
        if (k + 1 < n_starts) {
            TEST_ASSERT_TRUE_MESSAGE(bursts[end].stamp - s->t0_us >= MIN_STRETCH_US,
                                     "a stretch other than the last lasts less than 60 seconds");
        }
    }
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_steady);
    RUN_TEST(test_2_steady_low_and_high);
    RUN_TEST(test_3_shift_near_half_period);
    RUN_TEST(test_4_overflow);
    RUN_TEST(test_5_rate_from_stretch_before);
    RUN_TEST(test_6_short_stretch_before);
    RUN_TEST(test_7_shift_before_one_second);
    RUN_TEST(test_8_bad_bursts);
    RUN_TEST(test_9_times);
    RUN_TEST(test_10_twenty_minutes);
    return UNITY_END();
}
