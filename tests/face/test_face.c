/*
 * Unit tests for the face state and the two-in-a-row rule in core/face.c.
 *
 * Unless a case says otherwise, answer i has the time 1,000,000i microseconds.
 */

#include <stdbool.h>
#include <stdint.h>

#include "face.h"
#include "unity.h"

#define SECOND_US INT64_C(1000000)

static face_t face;
/* The number of the next answer, which sets its time. */
static int64_t next_answer;

void setUp(void) {}

void tearDown(void) {}

static void start(void)
{
    face_init(&face);
    next_answer = 0;
}

static bool answer(res_code_t code)
{
    bool changed = face_answer(&face, code, next_answer * SECOND_US);
    next_answer++;
    return changed;
}

/* code_of() gives the code that maps to a face state, for the states that
 * answers can reach. */
static res_code_t code_of(face_state_t s)
{
    switch (s) {
    case FACE_TREMOR:
        return RES_TREMOR;
    case FACE_NO_TREMOR:
        return RES_NO_TREMOR;
    case FACE_ARM_MOVING:
        return RES_ARM_MOVING;
    default:
        return RES_WARMING_UP;
    }
}

/* reach() gives a new face in state s, with no answer for Waiting and with two
 * answers of s's code for the others. */
static void reach(face_state_t s)
{
    start();
    if (s != FACE_WAITING) {
        answer(code_of(s));
        answer(code_of(s));
    }
    TEST_ASSERT_EQUAL_INT(s, face_shown(&face));
    TEST_ASSERT_EQUAL_INT(s, face_detector(&face));
}

static void test_1_states_names_and_codes(void)
{
    TEST_ASSERT_EQUAL_INT(0, FACE_TREMOR);
    TEST_ASSERT_EQUAL_INT(1, FACE_NO_TREMOR);
    TEST_ASSERT_EQUAL_INT(2, FACE_ARM_MOVING);
    TEST_ASSERT_EQUAL_INT(3, FACE_WAITING);
    TEST_ASSERT_EQUAL_INT(4, FACE_DOSE_DUE);
    TEST_ASSERT_EQUAL_STRING("Tremor Detected", face_name(FACE_TREMOR));
    TEST_ASSERT_EQUAL_STRING("Rest", face_name(FACE_NO_TREMOR));
    TEST_ASSERT_EQUAL_STRING("Arm moving", face_name(FACE_ARM_MOVING));
    TEST_ASSERT_EQUAL_STRING("Waiting", face_name(FACE_WAITING));
    TEST_ASSERT_EQUAL_STRING("Dose due", face_name(FACE_DOSE_DUE));
    TEST_ASSERT_EQUAL_STRING("unknown", face_name((face_state_t)5));
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_from_code(RES_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_NO_TREMOR, face_from_code(RES_NO_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_ARM_MOVING, face_from_code(RES_ARM_MOVING));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_from_code(RES_WARMING_UP));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_from_code(RES_SENSOR_FAULT));
}

static void test_2_init_is_waiting(void)
{
    int64_t t;
    start();
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_detector(&face));
    TEST_ASSERT_FALSE(face_last_tremor(&face, &t));
}

static void test_3_every_state_change(void)
{
    const face_state_t starts[] = {FACE_WAITING, FACE_TREMOR, FACE_NO_TREMOR, FACE_ARM_MOVING};
    for (int i = 0; i < 4; i++) {
        face_state_t s = starts[i];
        for (int c = 0; c < RES_COUNT; c++) {
            res_code_t code = (res_code_t)c;
            face_state_t want = face_from_code(code);
            reach(s);
            TEST_ASSERT_FALSE(answer(code));
            TEST_ASSERT_EQUAL_INT(s, face_shown(&face));
            TEST_ASSERT_EQUAL_INT(s, face_detector(&face));
            TEST_ASSERT_EQUAL(want != s, answer(code));
            TEST_ASSERT_EQUAL_INT(want, face_shown(&face));
            TEST_ASSERT_EQUAL_INT(want, face_detector(&face));
        }
    }
}

/* check_never_changes() gives the answers from state s and checks that the
 * state never changes and every call returns false. */
static void check_never_changes(face_state_t s, const res_code_t *codes, int n)
{
    reach(s);
    for (int i = 0; i < n; i++) {
        TEST_ASSERT_FALSE(answer(codes[i]));
        TEST_ASSERT_EQUAL_INT(s, face_shown(&face));
    }
}

static void test_4_single_odd_answers_never_show(void)
{
    const res_code_t a[] = {RES_TREMOR, RES_NO_TREMOR, RES_NO_TREMOR, RES_TREMOR, RES_NO_TREMOR};
    const res_code_t b[] = {RES_ARM_MOVING, RES_TREMOR, RES_NO_TREMOR, RES_TREMOR};
    check_never_changes(FACE_NO_TREMOR, a, 5);
    check_never_changes(FACE_TREMOR, b, 4);
}

static void test_5_warming_up_and_sensor_fault_agree(void)
{
    reach(FACE_TREMOR);
    TEST_ASSERT_FALSE(answer(RES_WARMING_UP));
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&face));
    TEST_ASSERT_TRUE(answer(RES_SENSOR_FAULT));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));

    reach(FACE_WAITING);
    TEST_ASSERT_FALSE(answer(RES_SENSOR_FAULT));
    TEST_ASSERT_FALSE(answer(RES_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
    TEST_ASSERT_TRUE(answer(RES_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&face));
}

static void test_6_dose_due_takes_over(void)
{
    reach(FACE_NO_TREMOR);
    TEST_ASSERT_TRUE(face_set_dose_due(&face, true));
    TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, face_shown(&face));
    TEST_ASSERT_FALSE(face_set_dose_due(&face, true));
    TEST_ASSERT_FALSE(answer(RES_TREMOR));
    TEST_ASSERT_FALSE(answer(RES_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_detector(&face));
    TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, face_shown(&face));
    TEST_ASSERT_TRUE(face_set_dose_due(&face, false));
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&face));

    reach(FACE_WAITING);
    TEST_ASSERT_TRUE(face_set_dose_due(&face, true));
    TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, face_shown(&face));
    TEST_ASSERT_TRUE(face_set_dose_due(&face, false));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
}

/* answer_at() gives an answer at a whole second and checks the last tremor time. */
static void answer_at(res_code_t code, int64_t second, int64_t want_second)
{
    int64_t t = -1;
    face_answer(&face, code, second * SECOND_US);
    TEST_ASSERT_TRUE(face_last_tremor(&face, &t));
    TEST_ASSERT_EQUAL_INT64(want_second * SECOND_US, t);
}

static void test_7_last_tremor_time(void)
{
    int64_t t;
    start();
    face_answer(&face, RES_TREMOR, 5 * SECOND_US);
    TEST_ASSERT_FALSE(face_last_tremor(&face, &t));
    answer_at(RES_TREMOR, 6, 6);
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&face));
    answer_at(RES_TREMOR, 7, 7);
    answer_at(RES_NO_TREMOR, 8, 7);
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&face));
    answer_at(RES_TREMOR, 9, 9);
    answer_at(RES_NO_TREMOR, 10, 9);
    answer_at(RES_NO_TREMOR, 11, 9);
    TEST_ASSERT_EQUAL_INT(FACE_NO_TREMOR, face_shown(&face));
    answer_at(RES_TREMOR, 12, 9);
    TEST_ASSERT_EQUAL_INT(FACE_NO_TREMOR, face_shown(&face));
}

static void test_8_gap_shows_waiting_at_once(void)
{
    int64_t t = -1;
    start();
    face_answer(&face, RES_TREMOR, 0 * SECOND_US);
    answer_at(RES_TREMOR, 1, 1);
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&face));
    TEST_ASSERT_TRUE(face_gap(&face));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_detector(&face));
    TEST_ASSERT_TRUE(face_last_tremor(&face, &t));
    TEST_ASSERT_EQUAL_INT64(1 * SECOND_US, t);
    TEST_ASSERT_FALSE(face_gap(&face));
    TEST_ASSERT_FALSE(face_answer(&face, RES_WARMING_UP, 2 * SECOND_US));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
    TEST_ASSERT_FALSE(face_answer(&face, RES_TREMOR, 3 * SECOND_US));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
    TEST_ASSERT_TRUE(face_last_tremor(&face, &t));
    TEST_ASSERT_EQUAL_INT64(1 * SECOND_US, t);
    TEST_ASSERT_TRUE(face_answer(&face, RES_TREMOR, 4 * SECOND_US));
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&face));
    TEST_ASSERT_TRUE(face_last_tremor(&face, &t));
    TEST_ASSERT_EQUAL_INT64(4 * SECOND_US, t);

    reach(FACE_TREMOR);
    TEST_ASSERT_TRUE(face_gap(&face));
    TEST_ASSERT_FALSE(answer(RES_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
    TEST_ASSERT_TRUE(answer(RES_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_TREMOR, face_shown(&face));

    start();
    TEST_ASSERT_FALSE(face_gap(&face));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_detector(&face));
    TEST_ASSERT_FALSE(face_last_tremor(&face, &t));
}

static void test_9_gap_while_dose_due(void)
{
    reach(FACE_NO_TREMOR);
    TEST_ASSERT_TRUE(face_set_dose_due(&face, true));
    TEST_ASSERT_FALSE(face_gap(&face));
    TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, face_shown(&face));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_detector(&face));
    TEST_ASSERT_FALSE(answer(RES_WARMING_UP));
    TEST_ASSERT_FALSE(answer(RES_NO_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_DOSE_DUE, face_shown(&face));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_detector(&face));
    TEST_ASSERT_TRUE(face_set_dose_due(&face, false));
    TEST_ASSERT_EQUAL_INT(FACE_WAITING, face_shown(&face));
    TEST_ASSERT_TRUE(answer(RES_NO_TREMOR));
    TEST_ASSERT_EQUAL_INT(FACE_NO_TREMOR, face_shown(&face));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_states_names_and_codes);
    RUN_TEST(test_2_init_is_waiting);
    RUN_TEST(test_3_every_state_change);
    RUN_TEST(test_4_single_odd_answers_never_show);
    RUN_TEST(test_5_warming_up_and_sensor_fault_agree);
    RUN_TEST(test_6_dose_due_takes_over);
    RUN_TEST(test_7_last_tremor_time);
    RUN_TEST(test_8_gap_shows_waiting_at_once);
    RUN_TEST(test_9_gap_while_dose_due);
    return UNITY_END();
}
