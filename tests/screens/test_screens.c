/*
 * Unit tests for the face's screen rules in core/screens.c. They hold cases
 * 13 to 19 of feature 11's validation.md. Times are in seconds from
 * scr_init() at 0.
 */

#include <stdbool.h>
#include <stdint.h>

#include "screens.h"
#include "unity.h"

/* S() turns seconds into microseconds. */
#define S(sec) ((int64_t)((sec) * 1000000.0 + 0.5))

static scr_t scr;

void setUp(void)
{
    scr_init(&scr, 0);
}

void tearDown(void) {}

/* press() gives the BOOT button one press with reads of up, down, and down,
 * and returns the flags of the last read. */
static unsigned press(int64_t now_us)
{
    TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, false, now_us));
    TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, true, now_us + 20000));
    return scr_button(&scr, true, now_us + 40000);
}

/* to_medication() opens Medication with a tap on Home at 1.0 seconds. */
static void to_medication(void)
{
    TEST_ASSERT_EQUAL_UINT(SCR_ACCEPTED | SCR_CHANGED, scr_tap(&scr, 205, 400, S(1.0)));
    TEST_ASSERT_EQUAL_INT(LOOK_MEDICATION, scr_screen(&scr));
}

static void test_13_home_tap(void)
{
    TEST_ASSERT_EQUAL_INT(LOOK_HOME, scr_screen(&scr));
    TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 400, S(0.5)));
    TEST_ASSERT_EQUAL_INT(LOOK_HOME, scr_screen(&scr));
    TEST_ASSERT_EQUAL_UINT(SCR_ACCEPTED | SCR_CHANGED, scr_tap(&scr, 205, 400, S(1.0)));
    TEST_ASSERT_EQUAL_INT(LOOK_MEDICATION, scr_screen(&scr));
}

static void test_14_took_it(void)
{
    to_medication();
    TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 250, S(2.5)));
    TEST_ASSERT_EQUAL_UINT(SCR_ACCEPTED | SCR_TOOK_IT, scr_tap(&scr, 205, 251, S(2.5)));
    TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 400, S(2.7)));
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, scr_logged(&scr, S(2.75)));
    TEST_ASSERT_EQUAL_INT(LOOK_LOGGED, scr_screen(&scr));
    TEST_ASSERT_EQUAL_UINT(0u, scr_tick(&scr, S(5.749999)));
    TEST_ASSERT_EQUAL_INT(LOOK_LOGGED, scr_screen(&scr));
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, scr_tick(&scr, S(5.75)));
    TEST_ASSERT_EQUAL_INT(LOOK_HOME, scr_screen(&scr));
}

static void test_15_double_tap(void)
{
    to_medication();
    TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 400, S(1.3)));
    TEST_ASSERT_EQUAL_INT(LOOK_MEDICATION, scr_screen(&scr));
}

static void test_16_wait(void)
{
    to_medication();
    TEST_ASSERT_EQUAL_UINT(SCR_ACCEPTED | SCR_TOOK_IT, scr_tap(&scr, 205, 400, S(2.5)));
    TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 400, S(3.4)));
    TEST_ASSERT_EQUAL_UINT(SCR_ACCEPTED | SCR_TOOK_IT, scr_tap(&scr, 205, 400, S(3.5)));
}

static void check_no_taps(look_screen_t want)
{
    TEST_ASSERT_EQUAL_INT(want, scr_screen(&scr));
    TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 400, S(20.0)));
    TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 100, S(21.0)));
    TEST_ASSERT_EQUAL_INT(want, scr_screen(&scr));
}

static void test_17_no_taps(void)
{
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, press(S(2.0)));
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, press(S(3.0)));
    check_no_taps(LOOK_SESSION);
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, press(S(30.0)));
    check_no_taps(LOOK_STATUS);
    scr_init(&scr, 0);
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, scr_logged(&scr, S(19.0)));
    check_no_taps(LOOK_LOGGED);
}

static void test_18_button(void)
{
    /* Up, down, down gives one press at the second down, and more downs give
     * no second press. */
    TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, false, S(1.00)));
    TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, true, S(1.02)));
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, scr_button(&scr, true, S(1.04)));
    TEST_ASSERT_EQUAL_INT(LOOK_MEDICATION, scr_screen(&scr));
    for (int i = 0; i < 10; i++) {
        TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, true, S(1.06 + 0.02 * i)));
    }
    TEST_ASSERT_EQUAL_INT(LOOK_MEDICATION, scr_screen(&scr));

    /* Up, down, up, down, down gives one press at the last read. */
    scr_init(&scr, 0);
    TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, false, S(1.00)));
    TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, true, S(1.02)));
    TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, false, S(1.04)));
    TEST_ASSERT_EQUAL_UINT(0u, scr_button(&scr, true, S(1.06)));
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, scr_button(&scr, true, S(1.08)));
    TEST_ASSERT_EQUAL_INT(LOOK_MEDICATION, scr_screen(&scr));

    /* Four presses from Home. */
    scr_init(&scr, 0);
    const look_screen_t order[] = {LOOK_MEDICATION, LOOK_SESSION, LOOK_STATUS, LOOK_HOME};
    for (int i = 0; i < 4; i++) {
        TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, press(S(2.0 + i)));
        TEST_ASSERT_EQUAL_INT(order[i], scr_screen(&scr));
    }

    /* A press on Logged gives Session. */
    scr_init(&scr, 0);
    scr_logged(&scr, S(1.0));
    TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, press(S(2.0)));
    TEST_ASSERT_EQUAL_INT(LOOK_SESSION, scr_screen(&scr));
}

/* show_at() moves from Home to a screen with BOOT presses, the last of which
 * ends at `sec` seconds. */
static void show_at(look_screen_t want, double sec)
{
    scr_init(&scr, 0);
    int presses = want == LOOK_MEDICATION ? 1 : want == LOOK_SESSION ? 2 : 3;
    for (int i = presses; i >= 1; i--) {
        TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, press(S(sec - 0.5 * (i - 1)) - 40000));
    }
    TEST_ASSERT_EQUAL_INT(want, scr_screen(&scr));
}

static void test_19_idle(void)
{
    const look_screen_t screens[] = {LOOK_SESSION, LOOK_MEDICATION, LOOK_STATUS};
    for (int k = 0; k < 3; k++) {
        show_at(screens[k], 10.0);
        TEST_ASSERT_EQUAL_UINT(0u, scr_tick(&scr, S(309.999999)));
        TEST_ASSERT_EQUAL_INT(screens[k], scr_screen(&scr));
        TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, scr_tick(&scr, S(310.0)));
        TEST_ASSERT_EQUAL_INT(LOOK_HOME, scr_screen(&scr));

        show_at(screens[k], 10.0);
        if (screens[k] == LOOK_MEDICATION) {
            /* A tap on the upper half, which the screen ignores. */
            TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 100, S(130.0)));
        } else {
            TEST_ASSERT_EQUAL_UINT(0u, scr_tap(&scr, 205, 400, S(130.0)));
        }
        TEST_ASSERT_EQUAL_UINT(0u, scr_tick(&scr, S(310.0)));
        TEST_ASSERT_EQUAL_UINT(0u, scr_tick(&scr, S(429.999999)));
        TEST_ASSERT_EQUAL_INT(screens[k], scr_screen(&scr));
        TEST_ASSERT_EQUAL_UINT(SCR_CHANGED, scr_tick(&scr, S(430.0)));
        TEST_ASSERT_EQUAL_INT(LOOK_HOME, scr_screen(&scr));
    }
    scr_init(&scr, 0);
    TEST_ASSERT_EQUAL_UINT(0u, scr_tick(&scr, S(10000.0)));
    TEST_ASSERT_EQUAL_INT(LOOK_HOME, scr_screen(&scr));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_13_home_tap);
    RUN_TEST(test_14_took_it);
    RUN_TEST(test_15_double_tap);
    RUN_TEST(test_16_wait);
    RUN_TEST(test_17_no_taps);
    RUN_TEST(test_18_button);
    RUN_TEST(test_19_idle);
    return UNITY_END();
}
