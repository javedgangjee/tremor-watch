/*
 * Unit tests for the face's texts in core/view.c. They hold cases 23 to 36 of
 * feature 11's validation.md.
 *
 * O is 1792713600000000, which is 2026-10-23 00:00:00 in microseconds since
 * 1970. The cases call dose_set_clock() with offset O, so timer value 0 is
 * local midnight at the start of Friday 23 October 2026. The schedule is
 * "Levodopa" at 12:00, 16:00, and 20:00 unless a case says otherwise, and the
 * session starts at timer value 0.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "look.h"
#include "session.h"
#include "unity.h"
#include "view.h"

#define O INT64_C(1792713600000000)
#define SECOND_US INT64_C(1000000)
/* AT() gives the timer value of a clock time on 23 October. */
#define AT(h, m, s) (((INT64_C(h) * 60 + (m)) * 60 + (s)) * SECOND_US)

static sess_t sess;
static view_t view;
static view_input_t input;

void setUp(void)
{
    sess_init(&sess, 0);
    memset(&input, 0, sizeof input);
    input.firmware = 11;
    input.hash = "a1b2c3d4e5f60718";
}

void tearDown(void) {}

static void set_schedule(const char *name, int count)
{
    dose_schedule_t s;
    memset(&s, 0, sizeof s);
    strcpy(s.name, name);
    s.count = (uint8_t)count;
    s.minutes[0] = 12 * 60;
    s.minutes[1] = 16 * 60;
    s.minutes[2] = 20 * 60;
    TEST_ASSERT_TRUE(dose_set_schedule(&sess.dose, &s, 0));
}

static void with_clock(void)
{
    dose_set_clock(&sess.dose, O, 0);
    set_schedule("Levodopa", 3);
}

static void build(int64_t now_us)
{
    view_build(&view, &sess, &input, now_us);
}

/* ------------------------------------------------------------- fit check */

static void fits(const char *text, look_screen_t screen, look_item_t item)
{
    const look_box_t *b = look_box(screen, item);
    TEST_ASSERT_NOT_NULL(b);
    int size = look_fit_size(text, b->w, b->size, b->smallest);
    TEST_ASSERT_TRUE_MESSAGE(size > 0, text);
}

static void fits_cut(const view_cut_t *c, look_screen_t screen, look_item_t item)
{
    const look_box_t *b = look_box(screen, item);
    TEST_ASSERT_NOT_NULL(b);
    if (look_fit_size(c->text, b->w, b->size, b->smallest) > 0) {
        return;
    }
    char out[VIEW_TEXT_MAX + 4];
    size_t n = look_cut(c->text, c->cut_at, c->cut_len, b->w, b->smallest, out, sizeof out);
    TEST_ASSERT_TRUE_MESSAGE(n > 0, c->text);
    TEST_ASSERT_TRUE(look_text_width(out, b->smallest) <= b->w);
}

/* check_fits() is case 36. Every text of the view fits its box at the size
 * look_fit_size() picks, or after look_cut(). */
static void check_fits(void)
{
    fits(view.time, LOOK_HOME, LOOK_ITEM_TIME);
    fits(view.date, LOOK_HOME, LOOK_ITEM_DATE);
    TEST_ASSERT_TRUE(look_text_width(view.battery, 28) >= 0);
    TEST_ASSERT_TRUE(look_text_width(view.battery, 28) <= look_box(LOOK_HOME, LOOK_ITEM_BATTERY)->w);
    fits(view.last_tremor, LOOK_HOME, LOOK_ITEM_LINE);
    fits(look_state(view.face)->word, LOOK_HOME, LOOK_ITEM_CIRCLE_WORD);
    fits(view.label_1, LOOK_MEDICATION, LOOK_ITEM_DOSE_LABEL_1);
    fits(view.label_2, LOOK_MEDICATION, LOOK_ITEM_DOSE_LABEL_2);
    fits_cut(&view.value_1, LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_1);
    fits_cut(&view.value_2, LOOK_MEDICATION, LOOK_ITEM_DOSE_VALUE_2);
    fits_cut(&view.logged_next, LOOK_LOGGED, LOOK_ITEM_LINE);
    fits(view.share, LOOK_SESSION, LOOK_ITEM_SHARE);
    fits(view.share_line, LOOK_SESSION, LOOK_ITEM_SHARE_LINE);
    fits(view.blocks_left, LOOK_SESSION, LOOK_ITEM_BLOCKS_LEFT);
    fits(view.blocks_right, LOOK_SESSION, LOOK_ITEM_BLOCKS_RIGHT);
    for (unsigned i = 0; i < LOOK_STATUS_ROWS; i++) {
        const look_box_t *row = look_box(LOOK_STATUS, (look_item_t)(LOOK_ITEM_STATUS_1 + i));
        int label = look_text_width(view_status_label(i), 28);
        int value = look_text_width(view.status[i], 28);
        TEST_ASSERT_TRUE(label > 0 && value > 0);
        TEST_ASSERT_TRUE(label + 16 + value <= row->w);
    }
}

static void entries(const char *label_1, const char *value_1, const char *label_2, const char *value_2)
{
    TEST_ASSERT_EQUAL_STRING(label_1, view.label_1);
    TEST_ASSERT_EQUAL_STRING(value_1, view.value_1.text);
    TEST_ASSERT_EQUAL_STRING(label_2, view.label_2);
    TEST_ASSERT_EQUAL_STRING(value_2, view.value_2.text);
}

/* ----------------------------------------------------------------- cases */

static void test_23_no_clock(void)
{
    set_schedule("Levodopa", 3);
    build(AT(9, 0, 0));
    TEST_ASSERT_EQUAL_STRING("--:--", view.time);
    TEST_ASSERT_EQUAL_STRING("--- -- ---", view.date);
    TEST_ASSERT_EQUAL_STRING("", view.last_tremor);
    entries("Last dose", "None yet", "Next dose", "Levodopa, --:--");
    check_fits();
}

static void test_24_time_and_date(void)
{
    with_clock();
    build(AT(15, 58, 0));
    TEST_ASSERT_EQUAL_STRING("15:58", view.time);
    TEST_ASSERT_EQUAL_STRING("Fri 23 Oct", view.date);
    check_fits();
    build(INT64_C(86460000000));
    TEST_ASSERT_EQUAL_STRING("00:01", view.time);
    TEST_ASSERT_EQUAL_STRING("Sat 24 Oct", view.date);
    check_fits();
}

static void two_tremors(void)
{
    sess_answer(&sess, true, 1, RES_TREMOR, AT(14, 32, 5));
    sess_answer(&sess, true, 2, RES_TREMOR, AT(14, 32, 10));
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&sess.face));
}

static void test_25_last_tremor(void)
{
    with_clock();
    two_tremors();
    build(AT(14, 33, 0));
    TEST_ASSERT_EQUAL_STRING("Last tremor 14:32", view.last_tremor);
    check_fits();

    sess_init(&sess, 0);
    set_schedule("Levodopa", 3);
    two_tremors();
    build(AT(14, 33, 0));
    TEST_ASSERT_EQUAL_STRING("Last tremor --:--", view.last_tremor);
    check_fits();
}

static void test_26_medication(void)
{
    with_clock();
    build(AT(13, 0, 0));
    entries("Last dose", "None yet", "Next dose", "Levodopa, 16:00");
    check_fits();
}

/* due_at_four() is case 27 up to the due state. */
static void due_at_four(void)
{
    with_clock();
    two_tremors();
    TEST_ASSERT_EQUAL_UINT(0u, sess_tick(&sess, AT(15, 59, 59)) & SESS_TONE);
    TEST_ASSERT_TRUE((sess_tick(&sess, AT(16, 0, 0)) & SESS_TONE) != 0);
}

static void test_27_due(void)
{
    due_at_four();
    build(AT(16, 0, 0));
    TEST_ASSERT_TRUE(view.due);
    TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, view.face);
    entries("Dose due", "Levodopa, 16:00", "Last dose", "None yet");
    check_fits();
    TEST_ASSERT_TRUE((sess_took_it(&sess, AT(16, 3, 0)) & SESS_DOSE_LOGGED) != 0);
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&sess.face));
}

static void test_28_after_dose(void)
{
    due_at_four();
    TEST_ASSERT_TRUE((sess_took_it(&sess, AT(16, 3, 0)) & SESS_DOSE_LOGGED) != 0);
    build(AT(16, 3, 0));
    TEST_ASSERT_FALSE(view.due);
    entries("Last dose", "Levodopa, 16:03", "Next dose", "Levodopa, 20:00");
    TEST_ASSERT_EQUAL_STRING("Next dose Levodopa, 20:00", view.logged_next.text);
    check_fits();
}

static void test_29_hour_rule(void)
{
    with_clock();
    TEST_ASSERT_TRUE((sess_took_it(&sess, AT(15, 10, 0)) & SESS_DOSE_LOGGED) != 0);
    build(AT(15, 30, 0));
    TEST_ASSERT_EQUAL_STRING("Next dose", view.label_2);
    TEST_ASSERT_EQUAL_STRING("Levodopa, 20:00", view.value_2.text);
    check_fits();
    for (int64_t t = AT(15, 59, 59); t <= AT(16, 0, 1); t += SECOND_US) {
        TEST_ASSERT_EQUAL_UINT(0u, sess_tick(&sess, t) & SESS_TONE);
    }
}

static void test_30_due_ends(void)
{
    with_clock();
    TEST_ASSERT_EQUAL_UINT(0u, sess_tick(&sess, AT(15, 59, 59)) & SESS_TONE);
    TEST_ASSERT_TRUE((sess_tick(&sess, AT(16, 0, 0)) & SESS_TONE) != 0);
    build(AT(16, 14, 59));
    TEST_ASSERT_TRUE(view.due);
    sess_tick(&sess, AT(16, 15, 0));
    build(AT(16, 15, 0));
    TEST_ASSERT_FALSE(view.due);
    entries("Last dose", "None yet", "Next dose", "Levodopa, 20:00");
    check_fits();
    TEST_ASSERT_EQUAL_UINT(0u, sess_tick(&sess, AT(16, 30, 0)) & SESS_TONE);
}

static void test_31_no_times(void)
{
    dose_set_clock(&sess.dose, O, 0);
    set_schedule("Levodopa", 0);
    build(AT(13, 0, 0));
    TEST_ASSERT_EQUAL_STRING("Next dose", view.label_2);
    TEST_ASSERT_EQUAL_STRING("No schedule", view.value_2.text);
    check_fits();
}

/* add_windows() counts tremor and no tremor windows in block 0. */
static void add_windows(uint32_t tremor, uint32_t no_tremor)
{
    for (uint32_t k = 1; k <= tremor + no_tremor; k++) {
        res_code_t code = k <= tremor ? RES_TREMOR : RES_NO_TREMOR;
        TEST_ASSERT_TRUE((sess_answer(&sess, true, 4 * k, code, (int64_t)k * 4 * SECOND_US) & SESS_COUNTED) != 0);
    }
}

static void test_32_share(void)
{
    with_clock();
    build(AT(0, 5, 0));
    TEST_ASSERT_EQUAL_STRING("Tremor --%", view.share);
    TEST_ASSERT_EQUAL_INT(-1, view.percent);
    TEST_ASSERT_EQUAL_STRING("of still time this session", view.share_line);
    check_fits();

    add_windows(3, 22);
    build(AT(0, 5, 0));
    TEST_ASSERT_EQUAL_STRING("Tremor 12%", view.share);
    TEST_ASSERT_EQUAL_INT(12, view.percent);
    check_fits();

    sess_init(&sess, 0);
    with_clock();
    add_windows(1, 7);
    build(AT(0, 5, 0));
    TEST_ASSERT_EQUAL_STRING("Tremor 13%", view.share);
    check_fits();
}

static void test_33_hollow(void)
{
    with_clock();
    add_windows(0, 29);
    build(AT(0, 5, 0));
    TEST_ASSERT_EQUAL_UINT32(1u, view.block_count);
    TEST_ASSERT_TRUE(view.hollow[0]);

    sess_init(&sess, 0);
    with_clock();
    add_windows(3, 27);
    build(AT(0, 5, 0));
    TEST_ASSERT_FALSE(view.hollow[0]);
    TEST_ASSERT_EQUAL_INT(10, view.block_percent[0]);
    check_fits();
}

static void test_34_twelve_blocks(void)
{
    with_clock();
    for (uint32_t b = 0; b < 13; b++) {
        int64_t t = (int64_t)b * SHARE_BLOCK_US + 60 * SECOND_US;
        sess_answer(&sess, true, 4 * (b + 1), RES_NO_TREMOR, t);
    }
    build(AT(2, 11, 0));
    TEST_ASSERT_EQUAL_UINT32(12u, view.block_count);
    TEST_ASSERT_EQUAL_STRING("00:10", view.blocks_left);
    TEST_ASSERT_EQUAL_STRING("Now", view.blocks_right);
    check_fits();
}

static void test_35_status(void)
{
    with_clock();
    input.battery_known = true;
    input.battery_percent = 68;
    input.battery_mv = 3912;
    input.uptime_s = 22320;
    input.has_answer = true;
    input.rate_uhz = 114348497;
    input.stretch = 3;
    input.run_us = 6912;
    input.recording = true;
    input.firmware = 11;
    input.hash = "a1b2c3d4e5f60718";
    build(AT(12, 0, 0));
    static const char *const WANT[LOOK_STATUS_ROWS] = {
        "68%", "3.9 V", "6 h 12 m", "114.348 Hz", "3", "6.9 ms", "On", "11", "a1b2c3d4",
    };
    for (unsigned i = 0; i < LOOK_STATUS_ROWS; i++) {
        TEST_ASSERT_EQUAL_STRING(WANT[i], view.status[i]);
    }
    TEST_ASSERT_EQUAL_STRING("68%", view.battery);
    check_fits();

    input.battery_known = false;
    input.has_answer = false;
    input.recording = false;
    build(AT(12, 0, 0));
    TEST_ASSERT_EQUAL_STRING("--", view.status[0]);
    TEST_ASSERT_EQUAL_STRING("--", view.status[1]);
    TEST_ASSERT_EQUAL_STRING("--", view.status[3]);
    TEST_ASSERT_EQUAL_STRING("--", view.status[4]);
    TEST_ASSERT_EQUAL_STRING("--", view.status[5]);
    TEST_ASSERT_EQUAL_STRING("Off", view.status[6]);
    TEST_ASSERT_EQUAL_STRING("--%", view.battery);
    check_fits();
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_23_no_clock);
    RUN_TEST(test_24_time_and_date);
    RUN_TEST(test_25_last_tremor);
    RUN_TEST(test_26_medication);
    RUN_TEST(test_27_due);
    RUN_TEST(test_28_after_dose);
    RUN_TEST(test_29_hour_rule);
    RUN_TEST(test_30_due_ends);
    RUN_TEST(test_31_no_times);
    RUN_TEST(test_32_share);
    RUN_TEST(test_33_hollow);
    RUN_TEST(test_34_twelve_blocks);
    RUN_TEST(test_35_status);
    return UNITY_END();
}
