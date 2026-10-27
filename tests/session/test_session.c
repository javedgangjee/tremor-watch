/*
 * Unit tests for the state task's rules in core/session.c.
 *
 * Session time starts at 1,000,000 microseconds. Window n of a stretch with t0
 * T has the time T + 10,000 * (100n + 399). The dose cases use the clock
 * offset and the times of tests/dose/test_dose.c, so the timer counts
 * microseconds from local midnight at the start of 22 October 2026.
 */

#include <stdbool.h>
#include <stdint.h>
#include <string.h>

#include "record.h"
#include "session.h"
#include "unity.h"

#define SESSION_START_US 1000000
#define STRETCH0_T0 2000000
#define STRETCH1_T0 90000000
#define SECOND_US INT64_C(1000000)
#define DAY_US (INT64_C(86400) * SECOND_US)
#define OFFSET_US (INT64_C(20748) * DAY_US)
/* AT() gives the timer value of a clock time on 22 October. */
#define AT(h, m, s) (((INT64_C(h) * 60 + (m)) * 60 + (s)) * SECOND_US)
/* LOCAL() gives the local time of a clock time on 22 October plus `day` days. */
#define LOCAL(day, h, m) (OFFSET_US + (day) * DAY_US + AT(h, m, 0))

static sess_t sess;
static share_t share;
static face_t face;

void setUp(void) {}

void tearDown(void) {}

static int64_t window_time(int64_t t0, uint32_t n)
{
    return t0 + 10000 * (100 * (int64_t)n + 399);
}

static unsigned answer(uint32_t n, res_code_t code, int64_t t0)
{
    return sess_answer(&sess, true, n, code, window_time(t0, n));
}

/* to_no_tremor() starts stretch 0 and gives windows 0 to 2, so the face shows
 * No tremor. */
static void to_no_tremor(void)
{
    sess_init(&sess, SESSION_START_US);
    TEST_ASSERT_EQUAL_UINT(0u, sess_stretch(&sess, 0));
    answer(0, RES_WARMING_UP, STRETCH0_T0);
    answer(1, RES_NO_TREMOR, STRETCH0_T0);
    answer(2, RES_NO_TREMOR, STRETCH0_T0);
    TEST_ASSERT_EQUAL_INT(FACE_NO_TREMOR, face_shown(&sess.face));
}

static void test_1_init(void)
{
    double percent;
    sess_init(&sess, SESSION_START_US);
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&sess.face));
    TEST_ASSERT_FALSE(share_percent(&sess.share, &percent));
    for (int code = 0; code < RES_COUNT; code++) {
        TEST_ASSERT_EQUAL_UINT32(0u, sess.answers[code]);
    }
    TEST_ASSERT_EQUAL_UINT32(0u, sess.gaps);
    TEST_ASSERT_EQUAL_UINT32(0u, sess.face_changes);
    TEST_ASSERT_EQUAL_UINT32(0u, sess.share.tremor + sess.share.no_tremor + sess.share.moving);
    TEST_ASSERT_EQUAL_UINT32(0u, dose_count(&sess.dose));
}

static void test_2_first_stretch(void)
{
    sess_init(&sess, SESSION_START_US);
    TEST_ASSERT_EQUAL_UINT(0u, sess_stretch(&sess, 0));
    for (uint32_t n = 0; n <= 12; n++) {
        res_code_t code = n == 0 ? RES_WARMING_UP : RES_NO_TREMOR;
        unsigned flags = answer(n, code, STRETCH0_T0);
        unsigned want = 0;
        if (n == 2) {
            want |= SESS_FACE_CHANGED;
        }
        if (n == 4 || n == 8 || n == 12) {
            want |= SESS_COUNTED;
        }
        TEST_ASSERT_EQUAL_UINT(want, flags);
    }
    TEST_ASSERT_EQUAL_INT(FACE_NO_TREMOR, face_shown(&sess.face));
    double percent = -1.0;
    TEST_ASSERT_TRUE(share_percent(&sess.share, &percent));
    TEST_ASSERT_EQUAL_DOUBLE(0.0, percent);
    TEST_ASSERT_EQUAL_UINT32(3u, sess.share.tremor + sess.share.no_tremor);
    TEST_ASSERT_EQUAL_UINT32(1u, sess.face_changes);
}

static void test_3_same_as_direct(void)
{
    sess_init(&sess, SESSION_START_US);
    share_start(&share, SESSION_START_US);
    face_init(&face);
    for (uint32_t n = 0; n < 40; n++) {
        res_code_t code = (res_code_t)(n % 5);
        int64_t t = window_time(STRETCH0_T0, n);
        unsigned flags = sess_answer(&sess, true, n, code, t);
        bool counted = share_add(&share, n, code, t);
        bool changed = face_answer(&face, code, t);
        TEST_ASSERT_EQUAL(counted, (flags & SESS_COUNTED) != 0);
        TEST_ASSERT_EQUAL(changed, (flags & SESS_FACE_CHANGED) != 0);
        TEST_ASSERT_EQUAL_INT(face_shown(&face), face_shown(&sess.face));
        TEST_ASSERT_EQUAL_INT(face_detector(&face), face_detector(&sess.face));
        TEST_ASSERT_EQUAL_UINT32(share.tremor, sess.share.tremor);
        TEST_ASSERT_EQUAL_UINT32(share.no_tremor, sess.share.no_tremor);
        TEST_ASSERT_EQUAL_UINT32(share.moving, sess.share.moving);
        TEST_ASSERT_EQUAL_UINT32(share_block_count(&share), share_block_count(&sess.share));
        int64_t a = 0;
        int64_t b = 0;
        bool has_a = face_last_tremor(&face, &a);
        bool has_b = face_last_tremor(&sess.face, &b);
        TEST_ASSERT_EQUAL(has_a, has_b);
        TEST_ASSERT_EQUAL_INT64(a, b);
    }
    TEST_ASSERT_EQUAL_UINT32(8u, sess.answers[RES_TREMOR]);
    TEST_ASSERT_EQUAL_UINT32(8u, sess.answers[RES_SENSOR_FAULT]);
}

static void test_4_gap(void)
{
    to_no_tremor();
    TEST_ASSERT_EQUAL_UINT(SESS_FACE_CHANGED, sess_stretch(&sess, 1));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&sess.face));
    TEST_ASSERT_EQUAL_UINT32(1u, sess.gaps);

    TEST_ASSERT_EQUAL_UINT(0u, answer(0, RES_WARMING_UP, STRETCH1_T0));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&sess.face));
    TEST_ASSERT_EQUAL_UINT(0u, answer(1, RES_NO_TREMOR, STRETCH1_T0));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&sess.face));
    TEST_ASSERT_EQUAL_UINT(SESS_FACE_CHANGED, answer(2, RES_NO_TREMOR, STRETCH1_T0));
    TEST_ASSERT_EQUAL_INT(FACE_NO_TREMOR, face_shown(&sess.face));

    static sess_t fresh;
    sess_init(&fresh, SESSION_START_US);
    TEST_ASSERT_EQUAL_UINT(0u, sess_stretch(&fresh, 0));
    TEST_ASSERT_EQUAL_UINT32(0u, fresh.gaps);
}

static void test_5_fault(void)
{
    to_no_tremor();
    share_t before = sess.share;
    TEST_ASSERT_EQUAL_UINT(0u, sess_answer(&sess, false, 0, RES_SENSOR_FAULT, 9000000));
    TEST_ASSERT_EQUAL_INT(FACE_NO_TREMOR, face_shown(&sess.face));
    TEST_ASSERT_EQUAL_UINT(SESS_FACE_CHANGED, sess_answer(&sess, false, 4, RES_SENSOR_FAULT, 10000000));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&sess.face));
    TEST_ASSERT_EQUAL_UINT32(2u, sess.answers[RES_SENSOR_FAULT]);
    TEST_ASSERT_EQUAL_UINT32(before.tremor, sess.share.tremor);
    TEST_ASSERT_EQUAL_UINT32(before.no_tremor, sess.share.no_tremor);
    TEST_ASSERT_EQUAL_UINT32(before.moving, sess.share.moving);
    TEST_ASSERT_EQUAL_UINT32(share_block_count(&before), share_block_count(&sess.share));
}

/* run_dose_day() runs case 6 on the static session. */
static void run_dose_day(void)
{
    sess_init(&sess, SESSION_START_US);
    dose_set_clock(&sess.dose, OFFSET_US, AT(6, 0, 0));
    dose_schedule_t s;
    memset(&s, 0, sizeof s);
    strncpy(s.name, "Levodopa", sizeof s.name - 1);
    s.count = 1;
    s.minutes[0] = 8 * 60;
    TEST_ASSERT_TRUE(dose_set_schedule(&sess.dose, &s, AT(6, 0, 0)));

    for (int64_t t = AT(7, 59, 58); t <= AT(8, 15, 1); t += SECOND_US) {
        unsigned flags = sess_tick(&sess, t);
        if (t == AT(8, 0, 0)) {
            TEST_ASSERT_EQUAL_UINT(SESS_FACE_CHANGED | SESS_TONE, flags);
            TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, face_shown(&sess.face));
        } else if (t == AT(8, 15, 0)) {
            TEST_ASSERT_EQUAL_UINT(SESS_FACE_CHANGED, flags);
            TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&sess.face));
        } else {
            TEST_ASSERT_EQUAL_UINT(0u, flags);
        }
        if (t == AT(8, 1, 0)) {
            unsigned a = sess_answer(&sess, true, 4, RES_TREMOR, AT(8, 1, 0));
            unsigned b = sess_answer(&sess, true, 5, RES_TREMOR, AT(8, 1, 0) + 400000);
            TEST_ASSERT_EQUAL_UINT(0u, a & SESS_FACE_CHANGED);
            TEST_ASSERT_EQUAL_UINT(0u, b & SESS_FACE_CHANGED);
            TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, face_shown(&sess.face));
            TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_detector(&sess.face));
        }
    }
}

static void test_6_dose_due(void)
{
    run_dose_day();
}

static void test_7_new_session(void)
{
    run_dose_day();
    TEST_ASSERT_TRUE(dose_took_it(&sess.dose, AT(8, 20, 0)));
    TEST_ASSERT_EQUAL_UINT32(1u, dose_count(&sess.dose));
    sess_new_session(&sess, AT(8, 30, 0));

    double percent;
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&sess.face));
    TEST_ASSERT_FALSE(share_percent(&sess.share, &percent));
    for (int code = 0; code < RES_COUNT; code++) {
        TEST_ASSERT_EQUAL_UINT32(0u, sess.answers[code]);
    }
    TEST_ASSERT_EQUAL_UINT32(0u, dose_count(&sess.dose));
    int64_t next = 0;
    TEST_ASSERT_TRUE(dose_next(&sess.dose, AT(8, 30, 0), &next));
    TEST_ASSERT_EQUAL_INT64(LOCAL(1, 8, 0), next);
}

/* Cases 20 to 22 follow specs/features/11-watch-face/validation.md and use
 * the clock of tests/view/test_view.c. The offset O is 2026-10-23 00:00:00 in
 * microseconds since 1970, so timer value 0 is local midnight at the start of
 * 23 October 2026. */
#define F11_O INT64_C(1792713600000000)
#define F11_AT(h, m, s) (((INT64_C(h) * 60 + (m)) * 60 + (s)) * SECOND_US)

/* due_at_four() starts a session at 0 with the clock set and "Levodopa" at
 * 12:00, 16:00, and 20:00, and ticks until the 16:00 dose is due. */
static void due_at_four(void)
{
    sess_init(&sess, 0);
    dose_set_clock(&sess.dose, F11_O, 0);
    dose_schedule_t s;
    memset(&s, 0, sizeof s);
    strcpy(s.name, "Levodopa");
    s.count = 3;
    s.minutes[0] = 12 * 60;
    s.minutes[1] = 16 * 60;
    s.minutes[2] = 20 * 60;
    TEST_ASSERT_TRUE(dose_set_schedule(&sess.dose, &s, 0));
    TEST_ASSERT_EQUAL_UINT(0u, sess_tick(&sess, F11_AT(15, 59, 59)));
    TEST_ASSERT_EQUAL_UINT(SESS_TONE | SESS_FACE_CHANGED, sess_tick(&sess, F11_AT(16, 0, 0)));
    TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, face_shown(&sess.face));
}

static void test_20_took_it(void)
{
    due_at_four();
    TEST_ASSERT_EQUAL_UINT(SESS_DOSE_LOGGED | SESS_FACE_CHANGED, sess_took_it(&sess, F11_AT(16, 3, 0)));
    TEST_ASSERT_EQUAL_INT(face_detector(&sess.face), face_shown(&sess.face));
    dose_entry_t last;
    TEST_ASSERT_TRUE(dose_last(&sess.dose, &last));
    TEST_ASSERT_EQUAL_INT64(INT64_C(57780000000), last.time_us);
    TEST_ASSERT_EQUAL_INT64(F11_O + INT64_C(57600000000), last.answers_local_us);
    char line[REC_LINE_MAX];
    TEST_ASSERT_TRUE(rec_dose(line, sizeof line, &last) > 0);
    TEST_ASSERT_EQUAL_STRING("D,57780000000,1792771200000000", line);
}

static void test_21_lock(void)
{
    due_at_four();
    TEST_ASSERT_EQUAL_UINT(SESS_DOSE_LOGGED | SESS_FACE_CHANGED, sess_took_it(&sess, F11_AT(16, 3, 0)));
    TEST_ASSERT_EQUAL_UINT(0u, sess_took_it(&sess, F11_AT(16, 3, 3) - 1));
    TEST_ASSERT_EQUAL_UINT32(1u, dose_count(&sess.dose));
    TEST_ASSERT_EQUAL_UINT(SESS_DOSE_LOGGED, sess_took_it(&sess, F11_AT(16, 3, 3)));
    TEST_ASSERT_EQUAL_UINT32(2u, dose_count(&sess.dose));
}

static void test_22_no_schedule(void)
{
    sess_init(&sess, 0);
    TEST_ASSERT_EQUAL_UINT(SESS_DOSE_LOGGED, sess_took_it(&sess, 5 * SECOND_US));
    dose_entry_t last;
    TEST_ASSERT_TRUE(dose_last(&sess.dose, &last));
    char line[REC_LINE_MAX];
    TEST_ASSERT_TRUE(rec_dose(line, sizeof line, &last) > 0);
    TEST_ASSERT_EQUAL_STRING("D,5000000,", line);
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_init);
    RUN_TEST(test_2_first_stretch);
    RUN_TEST(test_3_same_as_direct);
    RUN_TEST(test_4_gap);
    RUN_TEST(test_5_fault);
    RUN_TEST(test_6_dose_due);
    RUN_TEST(test_7_new_session);
    RUN_TEST(test_20_took_it);
    RUN_TEST(test_21_lock);
    RUN_TEST(test_22_no_schedule);
    return UNITY_END();
}
