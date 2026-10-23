/*
 * Unit tests for the result codes and the window rule in core/window.c.
 *
 * In every block that the cases build, sample k on axis a holds the float
 * k + 0.25a.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "unity.h"
#include "window.h"

/* A value that no case writes, so a check can see that nothing was written. */
#define UNTOUCHED (-7.0f)
#define UNTOUCHED_NUMBER 9999u

static win_t win;
static float block[CONV_BLOCK_SAMPLES][CONV_AXES];
static float window[DET_WINDOW_LEN][DET_AXES];

void setUp(void) {}

void tearDown(void) {}

/* make_block() fills the block that starts at sample first. */
static void make_block(uint64_t first)
{
    for (int s = 0; s < CONV_BLOCK_SAMPLES; s++) {
        for (int axis = 0; axis < CONV_AXES; axis++) {
            block[s][axis] = (float)(first + (uint64_t)s) + 0.25f * (float)axis;
        }
    }
}

/* clear_window() fills the window and the number with values no case writes. */
static void clear_window(uint32_t *number)
{
    for (int r = 0; r < DET_WINDOW_LEN; r++) {
        for (int axis = 0; axis < DET_AXES; axis++) {
            window[r][axis] = UNTOUCHED;
        }
    }
    *number = UNTOUCHED_NUMBER;
}

/* push() pushes block b, which starts at sample 100b. */
static bool push(uint64_t b, uint32_t *number)
{
    make_block(b * CONV_BLOCK_SAMPLES);
    return win_push_block(&win, block, b * CONV_BLOCK_SAMPLES, window, number);
}

/* check_window() checks that row r of the window holds sample 100n + r. */
static void check_window(uint32_t n)
{
    for (int r = 0; r < DET_WINDOW_LEN; r++) {
        for (int axis = 0; axis < DET_AXES; axis++) {
            float want = (float)(100u * n + (uint32_t)r) + 0.25f * (float)axis;
            TEST_ASSERT_EQUAL_FLOAT(want, window[r][axis]);
            TEST_ASSERT_TRUE(want == window[r][axis]);
        }
    }
}

static void check_untouched(uint32_t number)
{
    TEST_ASSERT_EQUAL_UINT32(UNTOUCHED_NUMBER, number);
    for (int r = 0; r < DET_WINDOW_LEN; r++) {
        for (int axis = 0; axis < DET_AXES; axis++) {
            TEST_ASSERT_TRUE(window[r][axis] == UNTOUCHED);
        }
    }
}

static void test_1_codes_and_names(void)
{
    TEST_ASSERT_EQUAL_INT(0, RES_TREMOR);
    TEST_ASSERT_EQUAL_INT(1, RES_NO_TREMOR);
    TEST_ASSERT_EQUAL_INT(2, RES_ARM_MOVING);
    TEST_ASSERT_EQUAL_INT(3, RES_WARMING_UP);
    TEST_ASSERT_EQUAL_INT(4, RES_SENSOR_FAULT);
    TEST_ASSERT_EQUAL_INT(5, RES_COUNT);
    TEST_ASSERT_EQUAL_STRING("tremor", res_name(RES_TREMOR));
    TEST_ASSERT_EQUAL_STRING("no tremor", res_name(RES_NO_TREMOR));
    TEST_ASSERT_EQUAL_STRING("arm moving", res_name(RES_ARM_MOVING));
    TEST_ASSERT_EQUAL_STRING("warming up", res_name(RES_WARMING_UP));
    TEST_ASSERT_EQUAL_STRING("sensor fault", res_name(RES_SENSOR_FAULT));
    TEST_ASSERT_EQUAL_STRING("unknown", res_name((res_code_t)5));
}

static void test_2_code_from_answer(void)
{
    det_result_t r;
    memset(&r, 0, sizeof(r));
    r.tremor = true;
    r.at_rest = true;
    TEST_ASSERT_EQUAL_INT(RES_WARMING_UP, res_from_answer(0, &r));
    TEST_ASSERT_EQUAL_INT(RES_TREMOR, res_from_answer(1, &r));
    TEST_ASSERT_EQUAL_INT(RES_TREMOR, res_from_answer(4, &r));
    r.tremor = false;
    r.at_rest = true;
    TEST_ASSERT_EQUAL_INT(RES_WARMING_UP, res_from_answer(0, &r));
    TEST_ASSERT_EQUAL_INT(RES_NO_TREMOR, res_from_answer(1, &r));
    r.tremor = false;
    r.at_rest = false;
    TEST_ASSERT_EQUAL_INT(RES_WARMING_UP, res_from_answer(0, &r));
    TEST_ASSERT_EQUAL_INT(RES_ARM_MOVING, res_from_answer(1, &r));
}

static void test_3_windows_in_order(void)
{
    uint32_t number;
    win_start(&win);
    for (uint64_t b = 0; b < 3; b++) {
        clear_window(&number);
        TEST_ASSERT_FALSE(push(b, &number));
        check_untouched(number);
    }
    clear_window(&number);
    TEST_ASSERT_TRUE(push(3, &number));
    TEST_ASSERT_EQUAL_UINT32(0, number);
    check_window(0);
    for (uint64_t b = 4; b <= 20; b++) {
        clear_window(&number);
        TEST_ASSERT_TRUE(push(b, &number));
        TEST_ASSERT_EQUAL_UINT32((uint32_t)(b - 3), number);
        check_window(number);
    }
}

static void test_4_refuses_a_block_out_of_order(void)
{
    uint32_t number;
    win_start(&win);
    for (uint64_t b = 0; b <= 5; b++) {
        push(b, &number);
    }
    clear_window(&number);
    make_block(700);
    TEST_ASSERT_FALSE(win_push_block(&win, block, 700, window, &number));
    check_untouched(number);
    make_block(500);
    TEST_ASSERT_FALSE(win_push_block(&win, block, 500, window, &number));
    check_untouched(number);
    TEST_ASSERT_TRUE(push(6, &number));
    TEST_ASSERT_EQUAL_UINT32(3, number);
    check_window(3);
}

static void test_5_start_needs_sample_0(void)
{
    uint32_t number;
    win_start(&win);
    for (uint64_t b = 0; b <= 5; b++) {
        push(b, &number);
    }
    win_start(&win);
    clear_window(&number);
    make_block(600);
    TEST_ASSERT_FALSE(win_push_block(&win, block, 600, window, &number));
    check_untouched(number);
    for (uint64_t b = 0; b < 3; b++) {
        TEST_ASSERT_FALSE(push(b, &number));
    }
    TEST_ASSERT_TRUE(push(3, &number));
    TEST_ASSERT_EQUAL_UINT32(0, number);
    check_window(0);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_codes_and_names);
    RUN_TEST(test_2_code_from_answer);
    RUN_TEST(test_3_windows_in_order);
    RUN_TEST(test_4_refuses_a_block_out_of_order);
    RUN_TEST(test_5_start_needs_sample_0);
    return UNITY_END();
}
