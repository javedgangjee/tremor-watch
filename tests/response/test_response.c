/*
 * The response time test. It runs the simulated demo through the C
 * converter, the window rule, the C detector, and the face rule, and it checks
 * how fast the face shows Tremor and goes back to No tremor.
 *
 * Each session follows make_session() in reference/demo_test.py, with rest to
 * 30 s, a 20 second shake to 50 s, and rest to the end at 80 s. The readings
 * come at the board's rate of 114330200 millionths of a reading per second,
 * and reading n has the time n * 1e6 / 114330200 seconds. The test makes its
 * own seeded random numbers, so its values differ from numpy's.
 *
 * The session is built in 64-bit floats. Each value is clipped to -1024 and
 * 1023.96875, rounded to the nearest 1/32, and passed to the converter as a
 * 32-bit float, as the sensor's counts would be.
 *
 * An answer's time is the time of the last reading of the burst that
 * completes its window, plus 50,000 microseconds for the run and the redraw,
 * as in reference/demo_test.py.
 */

#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "converter.h"
#include "detector.h"
#include "face.h"
#include "unity.h"
#include "window.h"

#define PI 3.14159265358979323846

/* The rate measured over twenty minutes in firmware/bringup/rate_log.txt. */
#define BOARD_RATE_UHZ 114330200u
#define SESSION_S 80u
/* The session has floor(80 * rate) readings. */
#define N_READINGS ((uint32_t)((uint64_t)SESSION_S * BOARD_RATE_UHZ / 1000000u))
#define BURST_LEN 11u
#define RUNS 10
#define CASES 8
/* The most answers a session gives, which is one a second. */
#define MAX_ANSWERS 128

#define SECOND_US INT64_C(1000000)
#define SHAKE_ON_US (30 * SECOND_US)
#define SHAKE_OFF_US (50 * SECOND_US)
/* The window from 30 s to 51 s in which the lifted and slow cases must show
 * Arm moving. */
#define MOVING_BY_US (51 * SECOND_US)
/* The time for the run and the redraw. */
#define REDRAW_US INT64_C(50000)

/* The limits from check 1 of specs/features/06-state-rules/validation.md. */
#define SHOW_MEDIAN_MIN 2.0
#define SHOW_MEDIAN_MAX 3.5
#define BACK_MEDIAN_MIN 4.0
#define BACK_MEDIAN_MAX 5.5
#define WORST_MAX 6.5

#define REST1_S 30.0
#define SHAKE_S 20.0
#define RAMP_S 0.4
#define CLIP_LOW (-1024.0)
#define CLIP_HIGH 1023.96875
#define COUNTS_PER_DPS 32.0

typedef struct {
    const char *name;
    double amp;
    double f0;
    double wander;
    double sway;
    /* resting is true for the five cases with the forearm on the table. */
    bool resting;
} case_t;

typedef struct {
    int64_t time_us;
    face_state_t state;
} change_t;

typedef struct {
    change_t changes[MAX_ANSWERS];
    int n_changes;
    /* The number of single odd answers that the rule kept off the face. */
    int odd;
} run_t;

static const case_t cases[CASES] = {
    {"5 Hz", 150.0, 5.0, 0.4, 3.0, true},
    {"4 Hz", 150.0, 4.0, 0.4, 3.0, true},
    {"6 Hz", 150.0, 6.0, 0.4, 3.0, true},
    {"gentle", 60.0, 5.0, 0.4, 3.0, true},
    {"hard", 600.0, 5.0, 0.4, 3.0, true},
    {"lifted", 150.0, 5.0, 0.4, 15.0, false},
    {"slow", 200.0, 2.5, 0.0, 3.0, false},
    {"fast", 200.0, 8.0, 0.0, 3.0, false},
};
enum { CASE_LIFTED = 5, CASE_SLOW = 6, CASE_FAST = 7 };

static run_t runs[CASES][RUNS];
/* setup_ok stays true while every converter and detector call works. The
 * sessions run before the tests, so a failure there is checked in case 1. */
static bool setup_ok = true;

static double values[N_READINGS][CONV_AXES];
static float readings[N_READINGS][CONV_AXES];
static conv_t conv;
static win_t win;
static float block[CONV_BLOCK_SAMPLES][CONV_AXES];
static float window[DET_WINDOW_LEN][DET_AXES];

/* The random number generator is splitmix64 with the Box-Muller method for
 * normal numbers. */
static uint64_t rng_state;
static bool have_spare;
static double spare;

static void rng_seed(uint64_t seed)
{
    rng_state = seed;
    have_spare = false;
}

static uint64_t rng_next(void)
{
    uint64_t z = (rng_state += UINT64_C(0x9E3779B97F4A7C15));
    z = (z ^ (z >> 30)) * UINT64_C(0xBF58476D1CE4E5B9);
    z = (z ^ (z >> 27)) * UINT64_C(0x94D049BB133111EB);
    return z ^ (z >> 31);
}

/* rng_uniform() gives a number from lo up to but not including hi. */
static double rng_uniform(double lo, double hi)
{
    double u = (double)(rng_next() >> 11) * (1.0 / 9007199254740992.0);
    return lo + (hi - lo) * u;
}

static double rng_normal(void)
{
    if (have_spare) {
        have_spare = false;
        return spare;
    }
    double u1 = 1.0 - rng_uniform(0.0, 1.0);
    double u2 = rng_uniform(0.0, 1.0);
    double r = sqrt(-2.0 * log(u1));
    spare = r * sin(2.0 * PI * u2);
    have_spare = true;
    return r * cos(2.0 * PI * u2);
}

static double clip(double v, double lo, double hi)
{
    return v < lo ? lo : (v > hi ? hi : v);
}

/* make_session() follows make_session() in reference/demo_test.py. */
static void make_session(const case_t *c, uint64_t seed)
{
    const double rate = (double)BOARD_RATE_UHZ / 1e6;
    const double tremor_axes[CONV_AXES] = {0.5, 0.3, 0.3};
    const double shake_axes[CONV_AXES] = {1.0, 0.35, 0.2};
    const double sway_axes[CONV_AXES] = {0.4, 1.0, 0.6};
    rng_seed(seed);
    for (uint32_t i = 0; i < N_READINGS; i++) {
        for (int a = 0; a < CONV_AXES; a++) {
            values[i][a] = rng_normal();
        }
    }
    double drift[CONV_AXES];
    for (int a = 0; a < CONV_AXES; a++) {
        drift[a] = rng_uniform(0.5, 1.5);
    }
    double freq_phase = rng_uniform(0.0, 6.0);
    double size_phase = rng_uniform(0.0, 6.0);

    double freq_sum = 0.0;
    for (uint32_t i = 0; i < N_READINGS; i++) {
        double t = (double)i * 1e6 / (double)BOARD_RATE_UHZ;
        double on = clip((t - REST1_S) / RAMP_S, 0.0, 1.0) * clip((REST1_S + SHAKE_S - t) / RAMP_S, 0.0, 1.0);
        double freq = c->f0 + c->wander * sin(2.0 * PI * 0.15 * t + freq_phase);
        freq_sum += freq;
        double phase = 2.0 * PI * freq_sum / rate;
        double size = c->amp * (1.0 + 0.25 * sin(2.0 * PI * 0.3 * t + size_phase));
        double tremor9 = sin(2.0 * PI * 9.0 * t);
        double slow = sin(2.0 * PI * 0.2 * t + 1.0);
        double shake = sin(phase) * size * on;
        double sway = sin(2.0 * PI * 0.8 * t + 0.5) * c->sway * on;
        for (int a = 0; a < CONV_AXES; a++) {
            double v = values[i][a] + tremor9 * tremor_axes[a] + slow * drift[a] + shake * shake_axes[a]
                + sway * sway_axes[a];
            v = clip(v, CLIP_LOW, CLIP_HIGH);
            readings[i][a] = (float)(round(v * COUNTS_PER_DPS) / COUNTS_PER_DPS);
        }
    }
}

/* run_session() runs the readings through the converter, the window rule,
 * the detector, and the face rule. */
static void run_session(run_t *out)
{
    static face_state_t states[MAX_ANSWERS];
    static face_state_t shown_after[MAX_ANSWERS];
    int n_answers = 0;
    face_t face;
    det_result_t result;
    uint64_t first_sample;
    uint32_t number;

    conv_start(&conv);
    setup_ok = conv_set_rate(&conv, BOARD_RATE_UHZ) && setup_ok;
    win_start(&win);
    face_init(&face);
    out->n_changes = 0;

    for (uint32_t start = 0; start < N_READINGS; start += BURST_LEN) {
        uint32_t end = start + BURST_LEN < N_READINGS ? start + BURST_LEN : N_READINGS;
        for (uint32_t i = start; i < end; i++) {
            setup_ok = conv_push(&conv, readings[i]) && setup_ok;
        }
        int64_t burst_us = (int64_t)((uint64_t)(end - 1) * UINT64_C(1000000000000) / BOARD_RATE_UHZ);
        while (conv_block(&conv, block, &first_sample)) {
            if (!win_push_block(&win, block, first_sample, window, &number)) {
                continue;
            }
            det_run(window, &result);
            res_code_t code = res_from_answer(number, &result);
            int64_t time_us = burst_us + REDRAW_US;
            if (n_answers >= MAX_ANSWERS) {
                setup_ok = false;
                return;
            }
            if (face_answer(&face, code, time_us)) {
                out->changes[out->n_changes].time_us = time_us;
                out->changes[out->n_changes].state = face_shown(&face);
                out->n_changes++;
            }
            states[n_answers] = face_from_code(code);
            shown_after[n_answers] = face_shown(&face);
            n_answers++;
        }
    }

    /* A single odd answer differs from the state the face shows after it,
     * and the answer after it does not agree with it. */
    out->odd = 0;
    for (int i = 0; i < n_answers; i++) {
        bool alone = i + 1 == n_answers || states[i + 1] != states[i];
        if (states[i] != shown_after[i] && alone) {
            out->odd++;
        }
    }
}

static void run_all(void)
{
    setup_ok = det_init();
    for (int c = 0; c < CASES; c++) {
        for (int r = 0; r < RUNS; r++) {
            make_session(&cases[c], (uint64_t)(1000 * (c + 1) + r));
            run_session(&runs[c][r]);
        }
    }
}

/* first_change() gives the index of the first change to state after after_us,
 * or -1 when there is none. */
static int first_change(const run_t *run, face_state_t state, int64_t after_us)
{
    for (int i = 0; i < run->n_changes; i++) {
        if (run->changes[i].time_us > after_us && run->changes[i].state == state) {
            return i;
        }
    }
    return -1;
}

/* shown_at() gives the state the face shows at time_us. */
static face_state_t shown_at(const run_t *run, int64_t time_us)
{
    face_state_t s = FACE_WAITING;
    for (int i = 0; i < run->n_changes && run->changes[i].time_us <= time_us; i++) {
        s = run->changes[i].state;
    }
    return s;
}

/* shows_between() is true when the face shows state at some time from lo_us
 * to hi_us. */
static bool shows_between(const run_t *run, face_state_t state, int64_t lo_us, int64_t hi_us)
{
    if (shown_at(run, lo_us) == state) {
        return true;
    }
    for (int i = 0; i < run->n_changes; i++) {
        const change_t *ch = &run->changes[i];
        if (ch->time_us >= lo_us && ch->time_us <= hi_us && ch->state == state) {
            return true;
        }
    }
    return false;
}

static int compare_double(const void *a, const void *b)
{
    double x = *(const double *)a;
    double y = *(const double *)b;
    return (x > y) - (x < y);
}

/* delays() gives the delays in seconds from from_us to the first change to
 * state after from_us, and it returns how many runs have one. */
static int delays(int c, face_state_t state, int64_t from_us, double out[RUNS])
{
    int n = 0;
    for (int r = 0; r < RUNS; r++) {
        int i = first_change(&runs[c][r], state, from_us);
        if (i >= 0) {
            out[n++] = (double)(runs[c][r].changes[i].time_us - from_us) / 1e6;
        }
    }
    qsort(out, (size_t)n, sizeof(double), compare_double);
    return n;
}

/* The median over ten runs is the mean of the fifth and sixth values in order. */
static double median10(const double sorted[RUNS])
{
    return (sorted[4] + sorted[5]) / 2.0;
}

static char msg[160];

static const char *where(int c, int r, const char *what)
{
    snprintf(msg, sizeof(msg), "case %s, run %d: %s", cases[c].name, r, what);
    return msg;
}

void setUp(void) {}

void tearDown(void) {}

static void test_1_rest_before_the_shake(void)
{
    TEST_ASSERT_TRUE_MESSAGE(setup_ok, "a converter or detector call failed");
    for (int c = 0; c < CASES; c++) {
        for (int r = 0; r < RUNS; r++) {
            const run_t *run = &runs[c][r];
            TEST_ASSERT_TRUE_MESSAGE(run->n_changes >= 1, where(c, r, "no change"));
            TEST_ASSERT_EQUAL_INT_MESSAGE(FACE_NO_TREMOR, run->changes[0].state, where(c, r, "first change"));
            TEST_ASSERT_TRUE_MESSAGE(run->changes[0].time_us < SHAKE_ON_US, where(c, r, "first change time"));
            if (run->n_changes >= 2) {
                TEST_ASSERT_TRUE_MESSAGE(run->changes[1].time_us >= SHAKE_ON_US, where(c, r, "second change before 30 s"));
            }
        }
    }
}

static void test_2_shows_tremor(void)
{
    for (int c = 0; c < CASES; c++) {
        if (!cases[c].resting) {
            continue;
        }
        for (int r = 0; r < RUNS; r++) {
            const run_t *run = &runs[c][r];
            int i = first_change(run, FACE_TREMOR, SHAKE_ON_US);
            TEST_ASSERT_TRUE_MESSAGE(i >= 0, where(c, r, "never shows Tremor"));
            TEST_ASSERT_TRUE_MESSAGE(run->changes[i].time_us < SHAKE_OFF_US, where(c, r, "Tremor after 50 s"));
            if (i + 1 < run->n_changes) {
                TEST_ASSERT_TRUE_MESSAGE(run->changes[i + 1].time_us >= SHAKE_OFF_US, where(c, r, "drops Tremor during the shake"));
            }
        }
        double d[RUNS];
        TEST_ASSERT_EQUAL_INT(RUNS, delays(c, FACE_TREMOR, SHAKE_ON_US, d));
        double median = median10(d);
        snprintf(msg, sizeof(msg), "case %s: show median %.2f s, worst %.2f s", cases[c].name, median, d[RUNS - 1]);
        TEST_ASSERT_TRUE_MESSAGE(median >= SHOW_MEDIAN_MIN && median <= SHOW_MEDIAN_MAX, msg);
        TEST_ASSERT_TRUE_MESSAGE(d[RUNS - 1] <= WORST_MAX, msg);
    }
}

static void test_3_back_to_no_tremor(void)
{
    for (int c = 0; c < CASES; c++) {
        if (!cases[c].resting) {
            continue;
        }
        for (int r = 0; r < RUNS; r++) {
            TEST_ASSERT_TRUE_MESSAGE(first_change(&runs[c][r], FACE_NO_TREMOR, SHAKE_OFF_US) >= 0,
                where(c, r, "never back to No tremor"));
        }
        double d[RUNS];
        TEST_ASSERT_EQUAL_INT(RUNS, delays(c, FACE_NO_TREMOR, SHAKE_OFF_US, d));
        double median = median10(d);
        snprintf(msg, sizeof(msg), "case %s: back median %.2f s, worst %.2f s", cases[c].name, median, d[RUNS - 1]);
        TEST_ASSERT_TRUE_MESSAGE(median >= BACK_MEDIAN_MIN && median <= BACK_MEDIAN_MAX, msg);
        TEST_ASSERT_TRUE_MESSAGE(d[RUNS - 1] <= WORST_MAX, msg);
    }
}

static void test_4_lifted_shows_arm_moving(void)
{
    for (int r = 0; r < RUNS; r++) {
        TEST_ASSERT_TRUE_MESSAGE(shows_between(&runs[CASE_LIFTED][r], FACE_ARM_MOVING, SHAKE_ON_US, MOVING_BY_US),
            where(CASE_LIFTED, r, "never shows Arm moving"));
    }
}

/* never_tremor() is true when a run never shows Tremor. */
static bool never_tremor(const run_t *run)
{
    return first_change(run, FACE_TREMOR, INT64_MIN) < 0;
}

static void test_5_slow_shows_arm_moving(void)
{
    for (int r = 0; r < RUNS; r++) {
        const run_t *run = &runs[CASE_SLOW][r];
        TEST_ASSERT_TRUE_MESSAGE(never_tremor(run), where(CASE_SLOW, r, "shows Tremor"));
        TEST_ASSERT_TRUE_MESSAGE(shows_between(run, FACE_ARM_MOVING, SHAKE_ON_US, MOVING_BY_US),
            where(CASE_SLOW, r, "never shows Arm moving"));
    }
}

static void test_6_fast_stays_no_tremor(void)
{
    for (int r = 0; r < RUNS; r++) {
        const run_t *run = &runs[CASE_FAST][r];
        TEST_ASSERT_TRUE_MESSAGE(never_tremor(run), where(CASE_FAST, r, "shows Tremor"));
        int i = first_change(run, FACE_NO_TREMOR, INT64_MIN);
        TEST_ASSERT_TRUE_MESSAGE(i >= 0, where(CASE_FAST, r, "never shows No tremor"));
        TEST_ASSERT_EQUAL_INT_MESSAGE(i + 1, run->n_changes, where(CASE_FAST, r, "changes after No tremor"));
    }
}

/* print_delays() prints the median and the worst of the delays, or "none". */
static void print_delays(int c, face_state_t state, int64_t from_us)
{
    double d[RUNS];
    int n = delays(c, state, from_us, d);
    if (n == RUNS) {
        printf(" %6.2f %6.2f", median10(d), d[RUNS - 1]);
    } else if (n > 0) {
        printf("   (%2d) %6.2f", n, d[n - 1]);
    } else {
        printf("   none   none");
    }
}

static void test_7_print_the_numbers(void)
{
    printf("\ncase     tremor show_med show_worst back_med back_worst odd\n");
    for (int c = 0; c < CASES; c++) {
        int shows = 0;
        int odd = 0;
        for (int r = 0; r < RUNS; r++) {
            shows += never_tremor(&runs[c][r]) ? 0 : 1;
            odd += runs[c][r].odd;
        }
        printf("%-8s %2d/%d ", cases[c].name, shows, RUNS);
        print_delays(c, FACE_TREMOR, SHAKE_ON_US);
        printf("  ");
        print_delays(c, FACE_NO_TREMOR, SHAKE_OFF_US);
        printf("  %3d\n", odd);
    }
    printf("(n) gives the number of runs with a delay when fewer than 10 have one.\n");
}

int main(void)
{
    UNITY_BEGIN();
    run_all();
    RUN_TEST(test_1_rest_before_the_shake);
    RUN_TEST(test_2_shows_tremor);
    RUN_TEST(test_3_back_to_no_tremor);
    RUN_TEST(test_4_lifted_shows_arm_moving);
    RUN_TEST(test_5_slow_shows_arm_moving);
    RUN_TEST(test_6_fast_stays_no_tremor);
    RUN_TEST(test_7_print_the_numbers);
    return UNITY_END();
}
