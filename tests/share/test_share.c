/*
 * Unit tests for the session share and the Session screen's blocks in
 * core/share.c.
 *
 * The session starts at 1,000,000 microseconds. Unless a case says otherwise,
 * window n has the time 1,000,000 + 1,000,000n microseconds.
 */

#include <stdbool.h>
#include <stdint.h>

#include "share.h"
#include "unity.h"

#define START_US INT64_C(1000000)
#define SECOND_US INT64_C(1000000)

static share_t share;

void setUp(void) {}

void tearDown(void) {}

static int64_t window_time(uint32_t n)
{
    return START_US + SECOND_US * (int64_t)n;
}

static void test_1_start_is_empty(void)
{
    double p;
    share_start(&share, START_US);
    TEST_ASSERT_FALSE(share_percent(&share, &p));
    TEST_ASSERT_EQUAL_UINT32(0, share.tremor);
    TEST_ASSERT_EQUAL_UINT32(0, share.no_tremor);
    TEST_ASSERT_EQUAL_UINT32(0, share.moving);
    TEST_ASSERT_EQUAL_UINT32(0, share_block_count(&share));
    TEST_ASSERT_NULL(share_block(&share, 0));
}

static void test_2_counts_every_fourth_window(void)
{
    double p;
    share_start(&share, START_US);
    for (uint32_t n = 0; n <= 40; n++) {
        res_code_t code = RES_NO_TREMOR;
        if (n == 4) {
            code = RES_TREMOR;
        } else if (n == 8) {
            code = RES_WARMING_UP;
        } else if (n == 12) {
            code = RES_SENSOR_FAULT;
        }
        bool want = n == 4 || (n >= 16 && n % 4 == 0);
        TEST_ASSERT_EQUAL_MESSAGE(want, share_add(&share, n, code, window_time(n)), "window");
    }
    TEST_ASSERT_EQUAL_UINT32(1, share.tremor);
    TEST_ASSERT_EQUAL_UINT32(7, share.no_tremor);
    TEST_ASSERT_TRUE(share_percent(&share, &p));
    TEST_ASSERT_TRUE(p == 12.5);
}

/* run_stream() adds the codes as windows 4, 8, 12, and up to a new share, and
 * checks the share. */
static void run_stream(const res_code_t *codes, uint32_t n, double want)
{
    double p;
    share_start(&share, START_US);
    for (uint32_t i = 0; i < n; i++) {
        uint32_t window = 4 * (i + 1);
        TEST_ASSERT_TRUE(share_add(&share, window, codes[i], window_time(window)));
    }
    TEST_ASSERT_TRUE(share_percent(&share, &p));
    TEST_ASSERT_EQUAL_DOUBLE(want, p);
    TEST_ASSERT_TRUE(p == want);
}

static void test_3_share_matches_the_toolbox(void)
{
    const res_code_t T = RES_TREMOR;
    const res_code_t N = RES_NO_TREMOR;
    const res_code_t A = RES_ARM_MOVING;
    const res_code_t a[] = {N, T, A, N, T, N, A, N, T, N};
    const res_code_t b[] = {T, N, N, A, T, N, N};
    const res_code_t c[] = {N, N, T, N, N, N, T, N, N};
    const res_code_t d[] = {A, T, T, A, T, A, T};
    const res_code_t e[] = {N, A, N, N, N, A, N, N};
    const res_code_t a2[] = {A, A, T, T, T, N, N, N, N, N};
    run_stream(a, 10, 37.5);
    run_stream(b, 7, 33.33333333333333);
    run_stream(c, 9, 22.22222222222222);
    run_stream(d, 7, 100.0);
    run_stream(e, 8, 0.0);
    run_stream(a2, 10, 37.5);
}

static void test_4_arm_moving_only_gives_no_share(void)
{
    double p;
    share_start(&share, START_US);
    for (uint32_t i = 1; i <= 5; i++) {
        TEST_ASSERT_TRUE(share_add(&share, 4 * i, RES_ARM_MOVING, window_time(4 * i)));
    }
    TEST_ASSERT_EQUAL_UINT32(5, share.moving);
    TEST_ASSERT_FALSE(share_percent(&share, &p));
}

static void test_5_session_blocks(void)
{
    uint32_t window = 4;
    double p;
    share_start(&share, START_US);
    /* Block 0 gets 30 no tremor windows from start + 0 to start + 599,999,999. */
    for (int i = 0; i < 29; i++) {
        TEST_ASSERT_TRUE(share_add(&share, window, RES_NO_TREMOR, START_US + INT64_C(20000000) * i));
        window += 4;
    }
    TEST_ASSERT_TRUE(share_add(&share, window, RES_NO_TREMOR, START_US + INT64_C(599999999)));
    window += 4;
    /* Block 1 gets 29 no tremor and 10 arm moving windows. */
    for (int i = 0; i < 39; i++) {
        res_code_t code = i < 29 ? RES_NO_TREMOR : RES_ARM_MOVING;
        TEST_ASSERT_TRUE(share_add(&share, window, code, START_US + INT64_C(600000000) + SECOND_US * 4 * i));
        window += 4;
    }
    /* Block 2 gets none, and block 3 gets 1 tremor and 3 no tremor windows. */
    for (int i = 0; i < 4; i++) {
        res_code_t code = i == 0 ? RES_TREMOR : RES_NO_TREMOR;
        TEST_ASSERT_TRUE(share_add(&share, window, code, START_US + INT64_C(1800000000) + SECOND_US * 4 * i));
        window += 4;
    }

    TEST_ASSERT_EQUAL_UINT32(4, share_block_count(&share));
    for (uint32_t i = 0; i < 4; i++) {
        TEST_ASSERT_EQUAL_UINT32(i, share_block(&share, i)->number);
    }
    TEST_ASSERT_NULL(share_block(&share, 4));

    const share_block_t *b0 = share_block(&share, 0);
    TEST_ASSERT_EQUAL_UINT32(30, b0->still);
    TEST_ASSERT_EQUAL_UINT32(0, b0->moving);
    TEST_ASSERT_FALSE(share_block_hollow(b0));

    const share_block_t *b1 = share_block(&share, 1);
    TEST_ASSERT_EQUAL_UINT32(29, b1->still);
    TEST_ASSERT_EQUAL_UINT32(10, b1->moving);
    TEST_ASSERT_TRUE(share_block_hollow(b1));

    const share_block_t *b2 = share_block(&share, 2);
    TEST_ASSERT_EQUAL_UINT32(0, b2->still);
    TEST_ASSERT_EQUAL_UINT32(0, b2->tremor);
    TEST_ASSERT_EQUAL_UINT32(0, b2->moving);
    TEST_ASSERT_TRUE(share_block_hollow(b2));
    TEST_ASSERT_FALSE(share_block_percent(b2, &p));

    const share_block_t *b3 = share_block(&share, 3);
    TEST_ASSERT_EQUAL_UINT32(4, b3->still);
    TEST_ASSERT_EQUAL_UINT32(1, b3->tremor);
    TEST_ASSERT_TRUE(share_block_percent(b3, &p));
    TEST_ASSERT_TRUE(p == 25.0);
    TEST_ASSERT_TRUE(share_block_hollow(b3));
}

static void test_6_keeps_the_latest_12_blocks(void)
{
    double p;
    share_start(&share, START_US);
    for (uint32_t k = 0; k <= 13; k++) {
        int64_t t = START_US + INT64_C(600000000) * k;
        TEST_ASSERT_TRUE(share_add(&share, 4 * (k + 1), RES_NO_TREMOR, t));
    }
    TEST_ASSERT_EQUAL_UINT32(12, share_block_count(&share));
    TEST_ASSERT_EQUAL_UINT32(2, share_block(&share, 0)->number);
    TEST_ASSERT_EQUAL_UINT32(13, share_block(&share, 11)->number);
    for (uint32_t i = 0; i < 12; i++) {
        TEST_ASSERT_EQUAL_UINT32(1, share_block(&share, i)->still);
    }
    TEST_ASSERT_EQUAL_UINT32(14, share.no_tremor);
    TEST_ASSERT_TRUE(share_percent(&share, &p));
    TEST_ASSERT_TRUE(p == 0.0);
}

static void test_7_early_window_goes_in_block_0(void)
{
    share_start(&share, START_US);
    TEST_ASSERT_TRUE(share_add(&share, 4, RES_NO_TREMOR, START_US - INT64_C(5000000)));
    TEST_ASSERT_EQUAL_UINT32(1, share_block_count(&share));
    TEST_ASSERT_EQUAL_UINT32(0, share_block(&share, 0)->number);
    TEST_ASSERT_EQUAL_UINT32(1, share_block(&share, 0)->still);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_start_is_empty);
    RUN_TEST(test_2_counts_every_fourth_window);
    RUN_TEST(test_3_share_matches_the_toolbox);
    RUN_TEST(test_4_arm_moving_only_gives_no_share);
    RUN_TEST(test_5_session_blocks);
    RUN_TEST(test_6_keeps_the_latest_12_blocks);
    RUN_TEST(test_7_early_window_goes_in_block_0);
    return UNITY_END();
}
