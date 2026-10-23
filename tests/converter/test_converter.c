/*
 * Unit tests for the converter in core/converter.c.
 *
 * The saved stretches, their readings, and the toolbox's samples come from
 * tests/converter/make_cases.py. The match limit comes from Build order step 8
 * of the plan, and requirement 28 of feature 5 applies it to every sample from
 * sample 100 on.
 */

#include <math.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "converter.h"
#include "unity.h"

#define N_STRETCHES 8
#define MAX_READINGS 4500
#define MAX_SAMPLES 3000
#define LINE_MAX_CHARS 256

/* The match limit in degrees per second. */
#define LIMIT 0.001
/* Samples from this one on lie outside window 0 of the stretch. */
#define FIRST_CHECKED_SAMPLE 100
/* The rate measured over twenty minutes in firmware/bringup/rate_log.txt. */
#define BOARD_RATE_UHZ 114330200u

typedef struct {
    char name[32];
    uint32_t rate_uhz;
    int readings;
    int samples;
} stretch_t;

typedef struct {
    float samples[MAX_SAMPLES][CONV_AXES];
    int count;
} result_t;

static stretch_t stretches[N_STRETCHES];
static float readings[N_STRETCHES][MAX_READINGS][CONV_AXES];
static double expected[N_STRETCHES][MAX_SAMPLES][CONV_AXES];
static result_t results[N_STRETCHES];
static result_t other;
static conv_t conv;
static bool loaded;

void setUp(void) {}

void tearDown(void) {}

static FILE *open_data(const char *name)
{
    char path[1024];
    snprintf(path, sizeof path, "%s/%s", CONVERTER_TEST_DIR, name);
    FILE *file = fopen(path, "r");
    TEST_ASSERT_NOT_NULL_MESSAGE(file, path);
    return file;
}

/* next_field() reads one number and steps past the comma after it. */
static double next_field(char **p)
{
    char *end = NULL;
    double v = strtod(*p, &end);
    TEST_ASSERT_TRUE(end != *p);
    *p = end + 1;
    return v;
}

static void read_stretches(void)
{
    FILE *file = open_data("stretches.csv");
    char line[LINE_MAX_CHARS];
    TEST_ASSERT_NOT_NULL(fgets(line, sizeof line, file));
    TEST_ASSERT_EQUAL_STRING("stretch,name,rate_uhz,readings\n", line);
    int n = 0;
    while (fgets(line, sizeof line, file) != NULL) {
        TEST_ASSERT_LESS_THAN_INT(N_STRETCHES, n);
        stretch_t *s = &stretches[n];
        unsigned long rate = 0;
        int index = -1;
        TEST_ASSERT_EQUAL_INT(4, sscanf(line, "%d,%31[^,],%lu,%d", &index, s->name, &rate, &s->readings));
        TEST_ASSERT_EQUAL_INT(n, index);
        TEST_ASSERT_TRUE(s->readings <= MAX_READINGS);
        s->rate_uhz = (uint32_t)rate;
        n++;
    }
    fclose(file);
    TEST_ASSERT_EQUAL_INT(N_STRETCHES, n);
}

static void read_readings(void)
{
    FILE *file = open_data("readings.csv");
    char line[LINE_MAX_CHARS];
    TEST_ASSERT_NOT_NULL(fgets(line, sizeof line, file));
    TEST_ASSERT_EQUAL_STRING("stretch,gyroscope_x,gyroscope_y,gyroscope_z\n", line);
    int counts[N_STRETCHES] = {0};
    while (fgets(line, sizeof line, file) != NULL) {
        char *p = line;
        int s = (int)next_field(&p);
        TEST_ASSERT_TRUE(s >= 0 && s < N_STRETCHES);
        TEST_ASSERT_LESS_THAN_INT(MAX_READINGS, counts[s]);
        for (int axis = 0; axis < CONV_AXES; axis++) {
            char *end = NULL;
            readings[s][counts[s]][axis] = strtof(p, &end);
            TEST_ASSERT_TRUE(end != p);
            p = end + 1;
        }
        counts[s]++;
    }
    fclose(file);
    for (int s = 0; s < N_STRETCHES; s++) {
        TEST_ASSERT_EQUAL_INT(stretches[s].readings, counts[s]);
    }
}

static void read_expected(void)
{
    FILE *file = open_data("expected.csv");
    char line[LINE_MAX_CHARS];
    TEST_ASSERT_NOT_NULL(fgets(line, sizeof line, file));
    TEST_ASSERT_EQUAL_STRING("stretch,sample,gyroscope_x,gyroscope_y,gyroscope_z\n", line);
    while (fgets(line, sizeof line, file) != NULL) {
        char *p = line;
        int s = (int)next_field(&p);
        int k = (int)next_field(&p);
        TEST_ASSERT_TRUE(s >= 0 && s < N_STRETCHES);
        TEST_ASSERT_EQUAL_INT(stretches[s].samples, k);
        TEST_ASSERT_LESS_THAN_INT(MAX_SAMPLES, k);
        for (int axis = 0; axis < CONV_AXES; axis++) {
            expected[s][k][axis] = next_field(&p);
        }
        stretches[s].samples++;
    }
    fclose(file);
}

static void load(void)
{
    if (!loaded) {
        read_stretches();
        read_readings();
        read_expected();
        loaded = true;
    }
}

/* expected_blocks() counts the b from 0 up with
 * floor((100b + 99) * rate_uhz / 1e8) + 17 at most readings - 1. */
static int expected_blocks(uint32_t rate_uhz, int readings_in)
{
    int b = 0;
    while ((100u * (uint64_t)b + 99u) * rate_uhz / 100000000u + 17u <= (uint64_t)(readings_in - 1)) {
        b++;
    }
    return b;
}

/* drain() makes every block that is ready and stores its samples. */
static void drain(conv_t *c, result_t *r)
{
    float out[CONV_BLOCK_SAMPLES][CONV_AXES];
    uint64_t first = 0;
    while (conv_block(c, out, &first)) {
        TEST_ASSERT_EQUAL_UINT64((uint64_t)r->count, first);
        TEST_ASSERT_TRUE(r->count + CONV_BLOCK_SAMPLES <= MAX_SAMPLES);
        memcpy(r->samples[r->count], out, sizeof out);
        r->count += CONV_BLOCK_SAMPLES;
    }
}

/* run_stretch() pushes the readings in bursts of the given sizes, which repeat,
 * and makes the blocks after each burst. The rate is set after `rate_after`
 * readings. */
static void run_stretch(conv_t *c, result_t *r, int s, const int *sizes, int n_sizes, int rate_after)
{
    const stretch_t *st = &stretches[s];
    r->count = 0;
    conv_start(c);
    if (rate_after == 0) {
        TEST_ASSERT_TRUE(conv_set_rate(c, st->rate_uhz));
    }
    int i = 0;
    int burst = 0;
    while (i < st->readings) {
        int size = sizes[burst % n_sizes];
        burst++;
        for (int j = 0; j < size && i < st->readings; j++, i++) {
            TEST_ASSERT_TRUE(conv_push(c, readings[s][i]));
            if (i + 1 == rate_after) {
                TEST_ASSERT_TRUE(conv_set_rate(c, st->rate_uhz));
            }
        }
        drain(c, r);
    }
}

static void assert_same(const result_t *a, const result_t *b, const char *what)
{
    TEST_ASSERT_EQUAL_INT_MESSAGE(a->count, b->count, what);
    TEST_ASSERT_EQUAL_INT_MESSAGE(0, memcmp(a->samples, b->samples, sizeof(float) * CONV_AXES * (size_t)a->count),
                                  what);
}

static void test_1_set_rate(void)
{
    conv_start(&conv);
    TEST_ASSERT_FALSE(conv_set_rate(&conv, 49999999u));
    TEST_ASSERT_FALSE(conv_set_rate(&conv, 150000001u));
    TEST_ASSERT_TRUE(conv_set_rate(&conv, 50000000u));
    conv_start(&conv);
    TEST_ASSERT_TRUE(conv_set_rate(&conv, 150000000u));
    TEST_ASSERT_FALSE(conv_set_rate(&conv, 150000000u));
    TEST_ASSERT_FALSE(conv_set_rate(&conv, 100000000u));
}

static void test_2_position(void)
{
    uint64_t reading = 99;
    float frac = -1.0f;
    conv_position(BOARD_RATE_UHZ, 0, &reading, &frac);
    TEST_ASSERT_EQUAL_UINT64(0, reading);
    TEST_ASSERT_TRUE(frac == 0.0f);
    conv_position(BOARD_RATE_UHZ, 12345, &reading, &frac);
    TEST_ASSERT_EQUAL_UINT64(14114, reading);
    TEST_ASSERT_TRUE(frac == (float)0.06319);
    conv_position(BOARD_RATE_UHZ, 1000000000u, &reading, &frac);
    TEST_ASSERT_EQUAL_UINT64(1143302000u, reading);
    TEST_ASSERT_TRUE(frac == 0.0f);
    conv_position(50000000u, 3, &reading, &frac);
    TEST_ASSERT_EQUAL_UINT64(1, reading);
    TEST_ASSERT_TRUE(frac == 0.5f);
}

static void test_3_zeros(void)
{
    static const float zero[CONV_AXES];
    other.count = 0;
    conv_start(&conv);
    TEST_ASSERT_TRUE(conv_set_rate(&conv, BOARD_RATE_UHZ));
    for (int i = 0; i < 2000; i++) {
        TEST_ASSERT_TRUE(conv_push(&conv, zero));
        drain(&conv, &other);
    }
    TEST_ASSERT_EQUAL_INT(expected_blocks(BOARD_RATE_UHZ, 2000) * CONV_BLOCK_SAMPLES, other.count);
    TEST_ASSERT_TRUE(other.count > 0);
    for (int k = 0; k < other.count; k++) {
        for (int axis = 0; axis < CONV_AXES; axis++) {
            TEST_ASSERT_TRUE(other.samples[k][axis] == 0.0f);
        }
    }
}

static void test_4_saved_cases(void)
{
    load();
    static const int one[] = {1};
    double worst_after = 0.0;
    double worst_before = 0.0;
    long compared = 0;
    char message[256];
    for (int s = 0; s < N_STRETCHES; s++) {
        const stretch_t *st = &stretches[s];
        result_t *r = &results[s];
        run_stretch(&conv, r, s, one, 1, 0);
        snprintf(message, sizeof message, "stretch %s gives the wrong number of blocks", st->name);
        TEST_ASSERT_EQUAL_INT_MESSAGE(expected_blocks(st->rate_uhz, st->readings) * CONV_BLOCK_SAMPLES, r->count,
                                      message);
        snprintf(message, sizeof message, "stretch %s gives a sample past the toolbox's last sample", st->name);
        TEST_ASSERT_TRUE_MESSAGE(r->count <= st->samples, message);

        double after = 0.0;
        double before = 0.0;
        for (int k = 0; k < r->count; k++) {
            for (int axis = 0; axis < CONV_AXES; axis++) {
                double d = fabs((double)r->samples[k][axis] - expected[s][k][axis]);
                if (k < FIRST_CHECKED_SAMPLE) {
                    before = d > before ? d : before;
                    continue;
                }
                after = d > after ? d : after;
                compared++;
                snprintf(message, sizeof message, "stretch %s sample %d axis %d differs by %.3g", st->name, k, axis,
                         d);
                TEST_ASSERT_TRUE_MESSAGE(d <= LIMIT, message);
            }
        }
        printf("stretch %s: %d samples, largest gap from sample 100 on %.3g, before sample 100 %.3g\n", st->name,
               r->count, after, before);
        worst_after = after > worst_after ? after : worst_after;
        worst_before = before > worst_before ? before : worst_before;
    }
    printf("largest gap from sample 100 on: %.3g deg/s\n", worst_after);
    printf("largest gap before sample 100: %.3g deg/s\n", worst_before);
    printf("samples compared: %ld values in %ld samples\n", compared, compared / CONV_AXES);
}

static void test_5_burst_sizes_and_late_rate(void)
{
    load();
    static conv_t fresh;
    static const int elevens[] = {11};
    static const int turns[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13};
    run_stretch(&fresh, &other, 0, elevens, 1, 0);
    assert_same(&results[0], &other, "bursts of 11");
    memset(&fresh, 0xA5, sizeof fresh);
    run_stretch(&fresh, &other, 0, turns, 13, 0);
    assert_same(&results[0], &other, "bursts of 1 to 13");
    memset(&fresh, 0x5A, sizeof fresh);
    run_stretch(&fresh, &other, 0, elevens, 1, 1200);
    assert_same(&results[0], &other, "rate set after 1200 readings");
}

static void test_6_ring_full(void)
{
    static const float zero[CONV_AXES];
    conv_start(&conv);
    for (int i = 0; i < CONV_RING_LEN; i++) {
        TEST_ASSERT_TRUE(conv_push(&conv, zero));
    }
    TEST_ASSERT_FALSE(conv_push(&conv, zero));
    conv_start(&conv);
    TEST_ASSERT_TRUE(conv_set_rate(&conv, BOARD_RATE_UHZ));
    for (int i = 0; i < CONV_RING_LEN; i++) {
        TEST_ASSERT_TRUE(conv_push(&conv, zero));
    }
    TEST_ASSERT_FALSE(conv_push(&conv, zero));
}

static void test_7_new_stretch_after_part(void)
{
    load();
    static conv_t fresh;
    float out[CONV_BLOCK_SAMPLES][CONV_AXES];
    uint64_t first = 0;
    conv_start(&fresh);
    TEST_ASSERT_TRUE(conv_set_rate(&fresh, stretches[0].rate_uhz));
    for (int i = 0; i < 1000; i++) {
        TEST_ASSERT_TRUE(conv_push(&fresh, readings[0][i]));
        while (conv_block(&fresh, out, &first)) {
        }
    }
    other.count = 0;
    conv_start(&fresh);
    TEST_ASSERT_TRUE(conv_set_rate(&fresh, stretches[1].rate_uhz));
    for (int i = 0; i < stretches[1].readings; i++) {
        TEST_ASSERT_TRUE(conv_push(&fresh, readings[1][i]));
        drain(&fresh, &other);
    }
    assert_same(&results[1], &other, "mix_50 after part of mix_114");
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_set_rate);
    RUN_TEST(test_2_position);
    RUN_TEST(test_3_zeros);
    RUN_TEST(test_4_saved_cases);
    RUN_TEST(test_5_burst_sizes_and_late_rate);
    RUN_TEST(test_6_ring_full);
    RUN_TEST(test_7_new_stretch_after_part);
    return UNITY_END();
}
