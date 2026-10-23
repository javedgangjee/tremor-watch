/*
 * Unit tests for the pipeline task's rules in core/pipeline.c.
 *
 * Reading i on axis a is the float ((7i + 13a) mod 101) / 8 - 6. A stream
 * comes in bursts of 23 readings, and each burst goes in two parts of 16 and
 * 7 readings. Only the first part of a burst carries flags. Stream A is
 * stretch 0 with first reading 0, t0 5,000,000 microseconds, and 3,427
 * readings in 149 bursts. Its parts carry rate 0 until the first burst whose
 * first reading is at least 1,144, which carries RT_RATE_SET and the rate on
 * its first part, and every later part carries the rate.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "pipeline.h"
#include "unity.h"

#define RATE_UHZ 114330200u
#define REFUSED_RATE_UHZ 40000000u
#define BURST 23u
#define PART_A 16u
#define PART_B (BURST - PART_A)
/* The bursts of a stream lie about 23 readings apart in time. */
#define BURST_US 201170
#define STREAM_A_T0 5000000
#define STREAM_A_BURSTS 149u
#define STREAM_A_RATE_FROM 1144u
#define STRETCH1_FIRST 3441u
#define STRETCH1_T0 50000000
#define STRETCH1_BURSTS 65u
/* No burst of a stream skips or starts the rate at this burst. */
#define NONE UINT32_MAX
#define MAX_WINDOWS 48

typedef struct {
    uint32_t count;
    uint32_t numbers[MAX_WINDOWS];
    int64_t times[MAX_WINDOWS];
    float values[MAX_WINDOWS][DET_WINDOW_LEN][DET_AXES];
} windows_t;

/* A description of one stream of bursts. */
typedef struct {
    uint32_t stretch;
    uint64_t first;
    int64_t t0;
    uint32_t bursts;
    /* The first part of burst 0 carries these flags. */
    unsigned start_flags;
    /* The parts carry rate_uhz from the first burst whose first reading is
     * at least rate_from. */
    uint64_t rate_from;
    uint32_t rate_uhz;
    /* This burst is left out, or NONE. */
    uint32_t skip;
} stream_t;

/* The flags of every part of the last stream that feed() ran. */
typedef struct {
    uint32_t count;
    unsigned flags[2 * 160];
    uint64_t first[2 * 160];
} results_t;

static pipe_t pipe;
static conv_t ref_conv;
static win_t ref_win;
static float ref_block[CONV_BLOCK_SAMPLES][CONV_AXES];
static float window[DET_WINDOW_LEN][DET_AXES];
static windows_t got;
static windows_t want;
static results_t results;

void setUp(void) {}

void tearDown(void) {}

static void reading(uint64_t i, float out[CONV_AXES])
{
    for (uint64_t a = 0; a < CONV_AXES; a++) {
        out[a] = (float)((7u * i + 13u * a) % 101u) / 8.0f - 6.0f;
    }
}

static void keep(windows_t *w, uint32_t number, int64_t time_us)
{
    TEST_ASSERT_LESS_THAN_UINT32(MAX_WINDOWS, w->count);
    w->numbers[w->count] = number;
    w->times[w->count] = time_us;
    memcpy(w->values[w->count], window, sizeof window);
    w->count++;
}

/* drain() takes every window that the pipe gives. */
static void drain(windows_t *w)
{
    uint32_t number;
    int64_t time_us;
    while (pipe_window(&pipe, window, &number, &time_us)) {
        keep(w, number, time_us);
    }
}

/* feed() sends one stream through pipe_part(), pipe_push(), and pipe_window()
 * after each part. It keeps each part's flags and returns the flags of all
 * pushes ORed together. */
static unsigned feed(const stream_t *s, windows_t *w)
{
    unsigned pushes = 0;
    bool rate_on = false;
    results.count = 0;
    for (uint32_t k = 0; k < s->bursts; k++) {
        if (k == s->skip) {
            continue;
        }
        uint64_t f = s->first + (uint64_t)k * BURST;
        unsigned flags = k == 0 ? s->start_flags : 0u;
        if (!rate_on && f >= s->rate_from) {
            rate_on = true;
            flags |= RT_RATE_SET;
        }
        int64_t stamp = s->t0 + (int64_t)k * BURST_US;
        for (int part = 0; part < 2; part++) {
            pipe_part_t m = {
                .stretch = s->stretch,
                .flags = part == 0 ? flags : 0u,
                .rate_uhz = rate_on ? s->rate_uhz : 0u,
                .stamp_us = stamp,
                .first_reading = f + (part == 0 ? 0u : PART_A),
                .count = part == 0 ? PART_A : PART_B,
            };
            unsigned r = pipe_part(&pipe, &m, stamp);
            results.flags[results.count] = r;
            results.first[results.count] = m.first_reading;
            results.count++;
            if ((r & PIPE_DROP) == 0) {
                for (uint32_t i = 0; i < m.count; i++) {
                    float x[CONV_AXES];
                    reading(m.first_reading + i, x);
                    pushes |= pipe_push(&pipe, x);
                }
            }
            drain(w);
        }
    }
    return pushes;
}

/* reference() runs the converter and the window rule on `count` readings from
 * `first` with the rate set at the start. */
static void reference(uint64_t first, uint32_t count, windows_t *w, int64_t t0)
{
    rt_stretch_t st = {.number = 0, .first_reading = first, .t0_us = t0, .rate_uhz = RATE_UHZ};
    conv_start(&ref_conv);
    win_start(&ref_win);
    TEST_ASSERT_TRUE(conv_set_rate(&ref_conv, RATE_UHZ));
    w->count = 0;
    for (uint32_t i = 0; i < count; i++) {
        float x[CONV_AXES];
        reading(first + i, x);
        TEST_ASSERT_TRUE(conv_push(&ref_conv, x));
        uint64_t first_sample;
        while (conv_block(&ref_conv, ref_block, &first_sample)) {
            uint32_t number;
            if (win_push_block(&ref_win, ref_block, first_sample, window, &number)) {
                keep(w, number, rt_sample_time_us(&st, 100u * number + 399u));
            }
        }
    }
}

static void check_same(const windows_t *a, const windows_t *b, int64_t t0)
{
    TEST_ASSERT_EQUAL_UINT32(b->count, a->count);
    for (uint32_t i = 0; i < a->count; i++) {
        TEST_ASSERT_EQUAL_UINT32(i, a->numbers[i]);
        TEST_ASSERT_EQUAL_UINT32(b->numbers[i], a->numbers[i]);
        TEST_ASSERT_EQUAL_INT64(t0 + 10000 * (100 * (int64_t)i + 399), a->times[i]);
        TEST_ASSERT_EQUAL_INT64(b->times[i], a->times[i]);
        TEST_ASSERT_EQUAL_MEMORY(b->values[i], a->values[i], sizeof a->values[i]);
    }
}

static stream_t stream_a(void)
{
    stream_t s = {
        .stretch = 0,
        .first = 0,
        .t0 = STREAM_A_T0,
        .bursts = STREAM_A_BURSTS,
        .start_flags = RT_NEW_STRETCH,
        .rate_from = STREAM_A_RATE_FROM,
        .rate_uhz = RATE_UHZ,
        .skip = NONE,
    };
    return s;
}

static stream_t stretch_1(void)
{
    stream_t s = {
        .stretch = 1,
        .first = STRETCH1_FIRST,
        .t0 = STRETCH1_T0,
        .bursts = STRETCH1_BURSTS,
        .start_flags = RT_NEW_STRETCH,
        .rate_from = 0,
        .rate_uhz = RATE_UHZ,
        .skip = NONE,
    };
    return s;
}

static void test_1_constants(void)
{
    TEST_ASSERT_EQUAL_INT64(2000000, PIPE_FAULT_AFTER_US);
    TEST_ASSERT_EQUAL_INT64(1000000, PIPE_FAULT_EVERY_US);
    TEST_ASSERT_EQUAL_UINT(1u, PIPE_STRETCH);
    TEST_ASSERT_EQUAL_UINT(2u, PIPE_END);
    TEST_ASSERT_EQUAL_UINT(4u, PIPE_DROP);
}

static void test_2_stream_a(void)
{
    stream_t s = stream_a();
    pipe_init(&pipe, 0);
    got.count = 0;
    TEST_ASSERT_EQUAL_UINT(0u, feed(&s, &got));
    TEST_ASSERT_EQUAL_UINT32(2u * STREAM_A_BURSTS, results.count);
    TEST_ASSERT_EQUAL_UINT(PIPE_STRETCH, results.flags[0]);
    for (uint32_t i = 1; i < results.count; i++) {
        TEST_ASSERT_EQUAL_UINT(0u, results.flags[i]);
    }
    reference(0, STREAM_A_BURSTS * BURST, &want, STREAM_A_T0);
    TEST_ASSERT_GREATER_OR_EQUAL_UINT32(25u, got.count);
    check_same(&got, &want, STREAM_A_T0);
}

/* run_stretch_1() feeds stretch 1 and checks its windows against the
 * reference. */
static void run_stretch_1(void)
{
    stream_t s = stretch_1();
    s.start_flags = RT_NEW_STRETCH | RT_RATE_SET;
    got.count = 0;
    TEST_ASSERT_EQUAL_UINT(0u, feed(&s, &got));
    TEST_ASSERT_EQUAL_UINT(PIPE_STRETCH, results.flags[0]);
    for (uint32_t i = 1; i < results.count; i++) {
        TEST_ASSERT_EQUAL_UINT(0u, results.flags[i]);
    }
    const rt_stretch_t *st = pipe_stretch(&pipe);
    TEST_ASSERT_EQUAL_UINT32(1u, st->number);
    TEST_ASSERT_EQUAL_UINT64(STRETCH1_FIRST, st->first_reading);
    TEST_ASSERT_EQUAL_INT64(STRETCH1_T0, st->t0_us);
    TEST_ASSERT_EQUAL_UINT32(RATE_UHZ, st->rate_uhz);
    reference(STRETCH1_FIRST, STRETCH1_BURSTS * BURST, &want, STRETCH1_T0);
    TEST_ASSERT_GREATER_THAN_UINT32(0u, got.count);
    check_same(&got, &want, STRETCH1_T0);
}

static void test_3_new_stretch(void)
{
    stream_t s = stream_a();
    pipe_init(&pipe, 0);
    got.count = 0;
    feed(&s, &got);
    run_stretch_1();
}

static void test_4_break(void)
{
    stream_t s = stream_a();
    s.skip = 25;
    pipe_init(&pipe, 0);
    got.count = 0;
    feed(&s, &got);
    TEST_ASSERT_EQUAL_UINT32(0u, got.count);
    /* Parts 0 to 49 are bursts 0 to 24. Part 50 starts at reading 598. */
    for (uint32_t i = 1; i < 50; i++) {
        TEST_ASSERT_EQUAL_UINT(0u, results.flags[i]);
    }
    TEST_ASSERT_EQUAL_UINT64(598u, results.first[50]);
    TEST_ASSERT_EQUAL_UINT(PIPE_END | PIPE_DROP, results.flags[50]);
    for (uint32_t i = 51; i < results.count; i++) {
        TEST_ASSERT_EQUAL_UINT(PIPE_DROP, results.flags[i]);
    }
    TEST_ASSERT_EQUAL_UINT32(0u, pipe_end_stretch(&pipe));
    TEST_ASSERT_EQUAL_UINT(PIPE_REASON_BREAK, pipe_end_reason(&pipe));
    run_stretch_1();
}

static void test_5_missed_start(void)
{
    stream_t s = stream_a();
    s.bursts = 10;
    pipe_init(&pipe, 0);
    got.count = 0;
    feed(&s, &got);

    pipe_part_t m = {.stretch = 1, .flags = 0, .rate_uhz = 0, .stamp_us = 7100000, .first_reading = 230, .count = 16};
    TEST_ASSERT_EQUAL_UINT(PIPE_END | PIPE_DROP, pipe_part(&pipe, &m, m.stamp_us));
    TEST_ASSERT_EQUAL_UINT32(1u, pipe_end_stretch(&pipe));
    TEST_ASSERT_EQUAL_UINT(PIPE_REASON_MISSED_START, pipe_end_reason(&pipe));
    m.first_reading = 246;
    m.count = 7;
    TEST_ASSERT_EQUAL_UINT(PIPE_DROP, pipe_part(&pipe, &m, m.stamp_us));

    m.stretch = 2;
    m.flags = RT_NEW_STRETCH;
    m.first_reading = 253;
    m.count = 16;
    m.stamp_us = 7300000;
    TEST_ASSERT_EQUAL_UINT(PIPE_STRETCH, pipe_part(&pipe, &m, m.stamp_us));
    TEST_ASSERT_EQUAL_UINT32(2u, pipe_stretch(&pipe)->number);
}

/* fill() feeds a stretch whose parts carry rate_uhz until the ring is full.
 * It checks that pushes 1 to 2,048 return 0, push 2,049 returns PIPE_END,
 * push 2,050 returns 0, and the next part returns PIPE_DROP. */
static void fill(uint32_t rate_uhz)
{
    pipe_init(&pipe, 0);
    got.count = 0;
    uint32_t pushes = 0;
    uint64_t next = 0;
    bool full_seen = false;
    for (uint32_t k = 0;; k++) {
        TEST_ASSERT_LESS_THAN_UINT32(200u, k);
        int64_t stamp = (int64_t)k * BURST_US;
        for (int part = 0; part < 2; part++) {
            unsigned flags = 0;
            if (k == 0 && part == 0) {
                flags = RT_NEW_STRETCH | (rate_uhz != 0 ? RT_RATE_SET : 0u);
            }
            pipe_part_t m = {
                .stretch = 0,
                .flags = flags,
                .rate_uhz = rate_uhz,
                .stamp_us = stamp,
                .first_reading = next,
                .count = part == 0 ? PART_A : PART_B,
            };
            unsigned r = pipe_part(&pipe, &m, stamp);
            if (full_seen) {
                TEST_ASSERT_GREATER_THAN_UINT32(2049u, pushes);
                TEST_ASSERT_EQUAL_UINT(PIPE_DROP, r);
                TEST_ASSERT_EQUAL_UINT32(0u, got.count);
                return;
            }
            TEST_ASSERT_EQUAL_UINT((k == 0 && part == 0) ? PIPE_STRETCH : 0u, r);
            for (uint32_t i = 0; i < m.count; i++) {
                float x[CONV_AXES];
                reading(next + i, x);
                unsigned p = pipe_push(&pipe, x);
                pushes++;
                if (pushes == 2049u) {
                    TEST_ASSERT_EQUAL_UINT(PIPE_END, p);
                    TEST_ASSERT_EQUAL_UINT(PIPE_REASON_RING_FULL, pipe_end_reason(&pipe));
                    TEST_ASSERT_EQUAL_UINT32(0u, pipe_end_stretch(&pipe));
                    full_seen = true;
                } else {
                    TEST_ASSERT_EQUAL_UINT(0u, p);
                }
            }
            next += m.count;
            drain(&got);
        }
    }
}

static void test_6_ring_full_without_rate(void)
{
    fill(0);
    TEST_ASSERT_EQUAL_UINT32(0u, pipe.rate_refused);
}

static void test_7_refused_rate(void)
{
    fill(REFUSED_RATE_UHZ);
    TEST_ASSERT_EQUAL_UINT32(1u, pipe.rate_refused);
    TEST_ASSERT_EQUAL_UINT32(0u, got.count);
}

static void test_8_fault_times(void)
{
    pipe_init(&pipe, 1000000);
    TEST_ASSERT_EQUAL_INT64(3000000, pipe_next_fault_us(&pipe));
    TEST_ASSERT_FALSE(pipe_fault_due(&pipe, 2999999));
    TEST_ASSERT_TRUE(pipe_fault_due(&pipe, 3000000));
    TEST_ASSERT_FALSE(pipe_fault_due(&pipe, 3000000));
    TEST_ASSERT_FALSE(pipe_fault_due(&pipe, 3999999));
    TEST_ASSERT_TRUE(pipe_fault_due(&pipe, 4000000));

    pipe_part_t m = {.stretch = 0, .flags = RT_NEW_STRETCH, .rate_uhz = 0, .stamp_us = 4500000, .first_reading = 0,
        .count = 16};
    TEST_ASSERT_EQUAL_UINT(PIPE_STRETCH, pipe_part(&pipe, &m, 4500000));
    TEST_ASSERT_EQUAL_INT64(6500000, pipe_next_fault_us(&pipe));
    TEST_ASSERT_FALSE(pipe_fault_due(&pipe, 6499999));
    TEST_ASSERT_TRUE(pipe_fault_due(&pipe, 6500000));

    /* A part that breaks the stretch returns PIPE_DROP and still moves the
     * fault time. */
    m.flags = 0;
    m.first_reading = 40;
    TEST_ASSERT_TRUE((pipe_part(&pipe, &m, 7200000) & PIPE_DROP) != 0);
    TEST_ASSERT_EQUAL_INT64(9200000, pipe_next_fault_us(&pipe));
    TEST_ASSERT_TRUE((pipe_part(&pipe, &m, 7700000) & PIPE_DROP) != 0);
    TEST_ASSERT_EQUAL_INT64(9700000, pipe_next_fault_us(&pipe));
    TEST_ASSERT_FALSE(pipe_fault_due(&pipe, 9699999));
    TEST_ASSERT_TRUE(pipe_fault_due(&pipe, 9700000));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_constants);
    RUN_TEST(test_2_stream_a);
    RUN_TEST(test_3_new_stretch);
    RUN_TEST(test_4_break);
    RUN_TEST(test_5_missed_start);
    RUN_TEST(test_6_ring_full_without_rate);
    RUN_TEST(test_7_refused_rate);
    RUN_TEST(test_8_fault_times);
    return UNITY_END();
}
