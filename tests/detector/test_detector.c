/*
 * Unit tests for the C detector in core/detector.c.
 *
 * The saved windows in windows.csv and the toolbox's answers in answers.csv
 * come from tests/detector/make_windows.py. The match limits come from Build
 * order step 5 of the plan.
 */

#include <math.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "detector.h"
#include "kissfft/kiss_fftr.h"
#include "unity.h"

#define N_WINDOWS 322
#define N_FIELDS 20
#define LINE_MAX_CHARS 2048

/* The match limit for the 12 numbers and the probability. */
#define LIMIT 0.0001
/* The toolbox's cut-off, which is pkg.threshold in its model file. */
#define CUT_OFF 0.029570239921802
/* A probability within this distance of the cut-off is near a cut-off. */
#define PROB_NEAR 0.0001
/* A low-frequency sum within this distance of 50 is near a cut-off. */
#define BELOW_NEAR 0.005
/* Two peak steps whose relative gap is below this are near a peak tie. */
#define GAP_NEAR 0.0001

#define PI 3.14159265358979323846

typedef struct {
    double mfcc[DET_MFCC_COUNT];
    double prob;
    double below;
    double peak;
    int at_rest;
    int tremor;
    double gap;
} answer_t;

static float windows[N_WINDOWS][DET_WINDOW_LEN][DET_AXES];
static answer_t answers[N_WINDOWS];

void setUp(void) {}

void tearDown(void) {}

static FILE *open_data(const char *name)
{
    char path[1024];
    snprintf(path, sizeof path, "%s/%s", DETECTOR_TEST_DIR, name);
    FILE *file = fopen(path, "r");
    TEST_ASSERT_NOT_NULL_MESSAGE(file, path);
    return file;
}

/* read_windows() reads 322 windows of 400 readings on three axes. */
static void read_windows(void)
{
    FILE *file = open_data("windows.csv");
    char line[LINE_MAX_CHARS];
    TEST_ASSERT_NOT_NULL(fgets(line, sizeof line, file));
    TEST_ASSERT_EQUAL_STRING("gyroscope_x,gyroscope_y,gyroscope_z\n", line);
    int n = 0;
    while (fgets(line, sizeof line, file) != NULL) {
        TEST_ASSERT_LESS_THAN_INT(N_WINDOWS * DET_WINDOW_LEN, n);
        char *p = line;
        for (int axis = 0; axis < DET_AXES; axis++) {
            char *end = NULL;
            windows[n / DET_WINDOW_LEN][n % DET_WINDOW_LEN][axis] = strtof(p, &end);
            TEST_ASSERT_TRUE(end != p);
            p = end + 1;
        }
        n++;
    }
    fclose(file);
    TEST_ASSERT_EQUAL_INT(N_WINDOWS * DET_WINDOW_LEN, n);
}

/* read_answers() reads the toolbox's 322 answers. */
static void read_answers(void)
{
    FILE *file = open_data("answers.csv");
    char line[LINE_MAX_CHARS];
    TEST_ASSERT_NOT_NULL(fgets(line, sizeof line, file));
    TEST_ASSERT_EQUAL_INT(0, strncmp(line, "window,group,mfcc_1,", 20));
    int n = 0;
    while (fgets(line, sizeof line, file) != NULL) {
        TEST_ASSERT_LESS_THAN_INT(N_WINDOWS, n);
        double v[N_FIELDS];
        char *p = line;
        for (int f = 0; f < N_FIELDS; f++) {
            if (f == 1) {
                p = strchr(p, ',');
                TEST_ASSERT_NOT_NULL(p);
                p++;
                v[f] = 0.0;
                continue;
            }
            char *end = NULL;
            v[f] = strtod(p, &end);
            TEST_ASSERT_TRUE(end != p);
            p = end + 1;
        }
        TEST_ASSERT_EQUAL_INT(n, (int)v[0]);
        answer_t *a = &answers[n];
        for (int i = 0; i < DET_MFCC_COUNT; i++) {
            a->mfcc[i] = v[2 + i];
        }
        a->prob = v[14];
        a->below = v[15];
        a->peak = v[16];
        a->at_rest = (int)v[17];
        a->tremor = (int)v[18];
        a->gap = v[19];
        n++;
    }
    fclose(file);
    TEST_ASSERT_EQUAL_INT(N_WINDOWS, n);
}

/* check_cosine() runs a KISS FFT of a cosine on step `step` and checks every
 * magnitude. */
static void check_cosine(int nfft, int step)
{
    static _Alignas(max_align_t) unsigned char mem[16384];
    static float in[400];
    static kiss_fft_cpx out[201];
    size_t len = sizeof mem;
    kiss_fftr_cfg cfg = kiss_fftr_alloc(nfft, 0, mem, &len);
    TEST_ASSERT_NOT_NULL(cfg);
    for (int i = 0; i < nfft; i++) {
        in[i] = (float)cos(2.0 * PI * step * i / nfft);
    }
    kiss_fftr(cfg, in, out);
    for (int k = 0; k <= nfft / 2; k++) {
        double mag = hypot((double)out[k].r, (double)out[k].i);
        if (k == step) {
            TEST_ASSERT_DOUBLE_WITHIN(0.001, nfft / 2.0, mag);
        } else {
            TEST_ASSERT_TRUE_MESSAGE(mag < 0.001, "a magnitude off the cosine's step is 0.001 or more");
        }
    }
}

static void test_1_init_runs_twice(void)
{
    TEST_ASSERT_TRUE(det_init());
    TEST_ASSERT_TRUE(det_init());
}

static void test_2_fft_400(void)
{
    check_cosine(400, 20);
}

static void test_3_fft_200(void)
{
    check_cosine(200, 10);
}

static void test_4_zero_window(void)
{
    static const float zeros[DET_WINDOW_LEN][DET_AXES];
    det_result_t r;
    TEST_ASSERT_TRUE(det_init());
    det_run(zeros, &r);
    TEST_ASSERT_EQUAL_FLOAT(1.0f, r.peak_hz);
    TEST_ASSERT_EQUAL_DOUBLE(0.0, r.below);
    TEST_ASSERT_TRUE(r.at_rest);
    TEST_ASSERT_FALSE(r.tremor);
    TEST_ASSERT_DOUBLE_WITHIN(0.1e-10, 2.3e-10, r.prob);
}

static void test_5_saved_windows(void)
{
    read_windows();
    read_answers();
    TEST_ASSERT_TRUE(det_init());

    double worst_mfcc = 0.0;
    double worst_prob = 0.0;
    double worst_below = 0.0;
    int near_cut_off = 0;
    int near_tie = 0;
    int answer_diffs = 0;
    int peak_diffs = 0;
    char message[256];
    for (int w = 0; w < N_WINDOWS; w++) {
        det_result_t r;
        const answer_t *a = &answers[w];
        det_run(windows[w], &r);

        for (int i = 0; i < DET_MFCC_COUNT; i++) {
            double d = fabs((double)r.mfcc[i] - a->mfcc[i]);
            worst_mfcc = d > worst_mfcc ? d : worst_mfcc;
            snprintf(message, sizeof message, "window %d mfcc_%d differs by %.3g", w, i + 1, d);
            TEST_ASSERT_TRUE_MESSAGE(d <= LIMIT, message);
        }
        double dp = fabs(r.prob - a->prob);
        worst_prob = dp > worst_prob ? dp : worst_prob;
        snprintf(message, sizeof message, "window %d probability differs by %.3g", w, dp);
        TEST_ASSERT_TRUE_MESSAGE(dp <= LIMIT, message);
        if (a->below != 0.0) {
            double db = fabs(r.below - a->below) / fabs(a->below);
            worst_below = db > worst_below ? db : worst_below;
        }

        bool tie = a->gap < GAP_NEAR;
        bool near = fabs(a->prob - CUT_OFF) <= PROB_NEAR || fabs(a->below - 50.0) <= BELOW_NEAR || tie;
        near_cut_off += near ? 1 : 0;
        near_tie += tie ? 1 : 0;
        if ((int)r.tremor != a->tremor || (int)r.at_rest != a->at_rest) {
            answer_diffs++;
        }
        if ((double)r.peak_hz != a->peak) {
            peak_diffs++;
        }
        if (!near) {
            snprintf(message, sizeof message, "window %d tremor answer differs", w);
            TEST_ASSERT_EQUAL_INT_MESSAGE(a->tremor, (int)r.tremor, message);
            snprintf(message, sizeof message, "window %d arm at rest answer differs", w);
            TEST_ASSERT_EQUAL_INT_MESSAGE(a->at_rest, (int)r.at_rest, message);
        }
        if (!tie) {
            snprintf(message, sizeof message, "window %d peak differs", w);
            TEST_ASSERT_EQUAL_DOUBLE_MESSAGE(a->peak, (double)r.peak_hz, message);
        }
    }
    printf("largest difference in the 12 numbers: %.3g\n", worst_mfcc);
    printf("largest difference in the probability: %.3g\n", worst_prob);
    printf("largest relative difference in the low-frequency sum: %.3g\n", worst_below);
    printf("windows near a cut-off: %d, of which near a peak tie: %d\n", near_cut_off, near_tie);
    printf("windows where an answer differs: %d, where the peak differs: %d\n", answer_diffs, peak_diffs);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_init_runs_twice);
    RUN_TEST(test_2_fft_400);
    RUN_TEST(test_3_fft_200);
    RUN_TEST(test_4_zero_window);
    RUN_TEST(test_5_saved_windows);
    return UNITY_END();
}
