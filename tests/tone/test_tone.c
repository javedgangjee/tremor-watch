/*
 * Unit tests for the tone samples in core/tone.c. They hold cases 37 to 40 of
 * specs/features/11-watch-face/validation.md.
 */

#include <stdint.h>
#include <stdlib.h>

#include "tone.h"
#include "unity.h"

#define DOSE_LEN 24000

static int16_t whole[DOSE_LEN];
static int16_t parts[DOSE_LEN];

void setUp(void) {}

void tearDown(void) {}

/* sign_changes() counts the changes of sign from one non-zero sample to the
 * next non-zero sample. */
static int sign_changes(const int16_t *s, size_t n)
{
    int changes = 0;
    int last = 0;
    for (size_t i = 0; i < n; i++) {
        int sign = s[i] > 0 ? 1 : s[i] < 0 ? -1 : 0;
        if (sign != 0) {
            if (last != 0 && sign != last) {
                changes++;
            }
            last = sign;
        }
    }
    return changes;
}

static void test_37_lengths(void)
{
    TEST_ASSERT_EQUAL_size_t(1920, tone_length(TONE_TAP));
    TEST_ASSERT_EQUAL_size_t(24000, tone_length(TONE_DOSE));
}

static void test_38_tap(void)
{
    TEST_ASSERT_EQUAL_size_t(1920, tone_fill(TONE_TAP, 0, whole, 1920));
    TEST_ASSERT_EQUAL_INT16(0, whole[0]);
    TEST_ASSERT_INT_WITHIN(125, 0, whole[1919]);
    int peak = 0;
    for (size_t i = 0; i < 1920; i++) {
        int a = abs(whole[i]);
        peak = a > peak ? a : peak;
    }
    TEST_ASSERT_TRUE(peak >= 9700 && peak <= 9830);
    TEST_ASSERT_INT_WITHIN(2, 158, sign_changes(whole, 1920));
}

static void test_39_dose(void)
{
    TEST_ASSERT_EQUAL_size_t(DOSE_LEN, tone_fill(TONE_DOSE, 0, whole, DOSE_LEN));
    for (size_t t = 0; t < 3; t++) {
        for (size_t i = 8000 * t + 4000; i < 8000 * t + 8000; i++) {
            TEST_ASSERT_EQUAL_INT16(0, whole[i]);
        }
        TEST_ASSERT_INT_WITHIN(2, 440, sign_changes(whole + 8000 * t, 4000));
    }
}

static void test_40_parts(void)
{
    TEST_ASSERT_EQUAL_size_t(DOSE_LEN, tone_fill(TONE_DOSE, 0, whole, DOSE_LEN));
    for (size_t start = 0; start < DOSE_LEN; start += 320) {
        size_t n = tone_fill(TONE_DOSE, start, parts + start, 320);
        TEST_ASSERT_EQUAL_size_t(320, n);
    }
    TEST_ASSERT_EQUAL_INT16_ARRAY(whole, parts, DOSE_LEN);
    int16_t buf[320];
    TEST_ASSERT_EQUAL_size_t(100, tone_fill(TONE_DOSE, 23900, buf, 320));
    TEST_ASSERT_EQUAL_size_t(0, tone_fill(TONE_DOSE, 24000, buf, 320));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_37_lengths);
    RUN_TEST(test_38_tap);
    RUN_TEST(test_39_dose);
    RUN_TEST(test_40_parts);
    return UNITY_END();
}
