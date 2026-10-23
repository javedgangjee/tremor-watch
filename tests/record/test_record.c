/*
 * Unit tests for the recording lines and the command parser in
 * core/record.c. The cases follow check 1 of
 * specs/features/09-usb-recording/validation.md.
 *
 * HASH is the text of DET_MODEL_SHA256. The test writes it out, because only
 * detector.c may include core/detector_tables.h.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

#include "dose.h"
#include "record.h"
#include "unity.h"

#define HASH "4be2ac2b511c501257ea8186068f06a94d0084d653840e907be72cd103dc5b0e"
/* A buffer larger than any line, so the size never limits a case. */
#define BIG 512

static char buf[BIG];

void setUp(void)
{
    memset(buf, 0, sizeof buf);
}

void tearDown(void) {}

/* check_line() checks the text that a line function wrote and its length. */
static void check_line(const char *want, size_t got)
{
    TEST_ASSERT_EQUAL_STRING(want, buf);
    TEST_ASSERT_EQUAL_size_t(strlen(want), got);
}

static void test_1_constants(void)
{
    TEST_ASSERT_EQUAL_INT(128, REC_LINE_MAX);
    TEST_ASSERT_EQUAL_INT(127, REC_COMMAND_MAX);
    TEST_ASSERT_TRUE(REC_CLOCK_MIN_US == INT64_C(1577836800000000));
    TEST_ASSERT_TRUE(REC_CLOCK_END_US == INT64_C(4102444800000000));
    TEST_ASSERT_EQUAL_INT(-720, REC_OFFSET_MIN);
    TEST_ASSERT_EQUAL_INT(840, REC_OFFSET_MAX);
    TEST_ASSERT_EQUAL_INT(0, REC_CMD_UNKNOWN);
    TEST_ASSERT_EQUAL_INT(1, REC_CMD_CLOCK);
    TEST_ASSERT_EQUAL_INT(2, REC_CMD_SCHEDULE);
    TEST_ASSERT_EQUAL_INT(3, REC_CMD_SESSION);
    TEST_ASSERT_EQUAL_INT(4, REC_CMD_TONE);
    TEST_ASSERT_EQUAL_INT(5, REC_CMD_EMPTY);
    TEST_ASSERT_EQUAL_INT(0, REC_DONE);
    TEST_ASSERT_EQUAL_INT(1, REC_UNKNOWN);
    TEST_ASSERT_EQUAL_INT(2, REC_BAD_FORMAT);
    TEST_ASSERT_EQUAL_INT(3, REC_REFUSED);
    TEST_ASSERT_EQUAL_INT(4, REC_NOT_STORED);
    TEST_ASSERT_EQUAL_INT(5, REC_BUSY);
}

static void test_2_boot_line(void)
{
    check_line("B,305419896,11,9," HASH, rec_boot(buf, BIG, 305419896u, 11u, 9u, HASH));
    check_line("B,4294967295,0,9," HASH, rec_boot(buf, BIG, 4294967295u, 0u, 9u, HASH));
}

static void test_3_stretch_line(void)
{
    check_line("S,0,0,238216,0,1024", rec_stretch(buf, BIG, 0u, 0u, 238216, 0u, 1024u));
    check_line("S,1,3441,50000000,114330200,1024", rec_stretch(buf, BIG, 1u, 3441u, 50000000, 114330200u, 1024u));
}

static void test_4_burst_line(void)
{
    check_line("T,1099511627776,11,9007199254740993",
        rec_burst(buf, BIG, UINT64_C(1099511627776), 11u, INT64_C(9007199254740993)));
    check_line("T,0,11,-5", rec_burst(buf, BIG, 0u, 11u, -5));
}

static void test_5_reading_line(void)
{
    const int16_t gyro[3] = {-32768, 0, 32767};
    const int16_t accel[3] = {-146, -24, -3773};
    check_line("R,17,-32768,0,32767,-146,-24,-3773", rec_reading(buf, BIG, 17u, gyro, accel));
}

/* field_of() gives the start of field k of a line, counted from 1. */
static const char *field_of(const char *line, int k)
{
    const char *p = line;
    for (int i = 1; i < k; i++) {
        p = strchr(p, ',');
        TEST_ASSERT_NOT_NULL(p);
        p++;
    }
    return p;
}

/* check_round_trip() checks that the three numbers of a W line read back bit
 * for bit. */
static void check_round_trip(double prob, double below, float peak)
{
    double prob_back = strtod(field_of(buf, 5), NULL);
    double below_back = strtod(field_of(buf, 6), NULL);
    float peak_back = strtof(field_of(buf, 7), NULL);
    TEST_ASSERT_EQUAL_MEMORY(&prob, &prob_back, sizeof prob);
    TEST_ASSERT_EQUAL_MEMORY(&below, &below_back, sizeof below);
    TEST_ASSERT_EQUAL_MEMORY(&peak, &peak_back, sizeof peak);
}

static void test_6_window_line(void)
{
    check_line("W,0,2,1,0.00014912065608801541,0.6326332688331604,21.25",
        rec_window(buf, BIG, 0u, true, 2u, RES_NO_TREMOR, 0.00014912065608801541, 0.6326332688331604, 21.25f));
    check_round_trip(0.00014912065608801541, 0.6326332688331604, 21.25f);

    check_line("W,0,0,3,0.0002778472679054648,0.5469731092453003,19.75",
        rec_window(buf, BIG, 0u, true, 0u, RES_WARMING_UP, 0.0002778472679054648, 0.5469731092453003, 19.75f));
    check_round_trip(0.0002778472679054648, 0.5469731092453003, 19.75f);

    check_line("W,0,12,1,7.817677252158094e-05,0.572318971157074,8",
        rec_window(buf, BIG, 0u, true, 12u, RES_NO_TREMOR, 7.817677252158094e-05, 0.572318971157074, 8.0f));
    check_round_trip(7.817677252158094e-05, 0.572318971157074, 8.0f);
}

static void test_7_fault_window_line(void)
{
    check_line("W,3,,4,,,", rec_window(buf, BIG, 3u, false, 0u, RES_SENSOR_FAULT, 0.5, 10.0, 5.0f));
}

static void test_8_face_line(void)
{
    check_line("F,10276255,1", rec_face(buf, BIG, 10276255, FACE_NO_TREMOR));
    check_line("F,0,4", rec_face(buf, BIG, 0, FACE_DOSE_DUE));
}

static void test_9_dose_line(void)
{
    dose_entry_t dose = {INT64_C(4500000000), INT64_C(1761206400000000)};
    check_line("D,4500000000,1761206400000000", rec_dose(buf, BIG, &dose));
    dose.answers_local_us = DOSE_NONE;
    check_line("D,4500000000,", rec_dose(buf, BIG, &dose));
}

static void test_10_reply_line(void)
{
    check_line("A,2,0", rec_reply(buf, BIG, REC_CMD_SCHEDULE, REC_DONE));
    check_line("A,0,1", rec_reply(buf, BIG, REC_CMD_UNKNOWN, REC_UNKNOWN));
    check_line("A,4,5", rec_reply(buf, BIG, REC_CMD_TONE, REC_BUSY));
}

/* write_first() writes the first line of case `which` with the given size. */
static size_t write_first(int which, size_t size)
{
    static const int16_t gyro[3] = {-32768, 0, 32767};
    static const int16_t accel[3] = {-146, -24, -3773};
    const dose_entry_t dose = {INT64_C(4500000000), INT64_C(1761206400000000)};
    switch (which) {
    case 2:
        return rec_boot(buf, size, 305419896u, 11u, 9u, HASH);
    case 3:
        return rec_stretch(buf, size, 0u, 0u, 238216, 0u, 1024u);
    case 4:
        return rec_burst(buf, size, UINT64_C(1099511627776), 11u, INT64_C(9007199254740993));
    case 5:
        return rec_reading(buf, size, 17u, gyro, accel);
    case 6:
        return rec_window(buf, size, 0u, true, 2u, RES_NO_TREMOR, 0.00014912065608801541, 0.6326332688331604,
            21.25f);
    case 7:
        return rec_window(buf, size, 3u, false, 0u, RES_SENSOR_FAULT, 0.5, 10.0, 5.0f);
    case 8:
        return rec_face(buf, size, 10276255, FACE_NO_TREMOR);
    case 9:
        return rec_dose(buf, size, &dose);
    default:
        return rec_reply(buf, size, REC_CMD_SCHEDULE, REC_DONE);
    }
}

static void test_11_line_must_fit(void)
{
    static const char *const want[] = {
        ("B,305419896,11,9," HASH),
        "S,0,0,238216,0,1024",
        "T,1099511627776,11,9007199254740993",
        "R,17,-32768,0,32767,-146,-24,-3773",
        "W,0,2,1,0.00014912065608801541,0.6326332688331604,21.25",
        "W,3,,4,,,",
        "F,10276255,1",
        "D,4500000000,1761206400000000",
        "A,2,0",
    };
    for (int which = 2; which <= 10; which++) {
        const char *line = want[which - 2];
        size_t len = strlen(line);
        memset(buf, 0, sizeof buf);
        TEST_ASSERT_EQUAL_size_t_MESSAGE(0, write_first(which, len), line);
        memset(buf, 0, sizeof buf);
        TEST_ASSERT_EQUAL_size_t_MESSAGE(len, write_first(which, len + 1), line);
        TEST_ASSERT_EQUAL_STRING(line, buf);
    }
}

/* parse_ok() parses a line that must give REC_DONE and the kind. */
static rec_command_t parse_ok(const char *line, rec_cmd_t kind)
{
    rec_command_t cmd;
    TEST_ASSERT_EQUAL_INT_MESSAGE(REC_DONE, rec_parse_command(line, &cmd), line);
    TEST_ASSERT_EQUAL_INT_MESSAGE(kind, cmd.kind, line);
    return cmd;
}

static void test_12_good_commands(void)
{
    rec_command_t cmd = parse_ok("CLOCK,1761206400000000,60", REC_CMD_CLOCK);
    TEST_ASSERT_TRUE(cmd.utc_us == INT64_C(1761206400000000));
    TEST_ASSERT_EQUAL_INT32(60, cmd.offset_min);
    cmd = parse_ok("CLOCK,1577836800000000,-720", REC_CMD_CLOCK);
    TEST_ASSERT_TRUE(cmd.utc_us == INT64_C(1577836800000000));
    TEST_ASSERT_EQUAL_INT32(-720, cmd.offset_min);
    cmd = parse_ok("CLOCK,4102444799999999,840", REC_CMD_CLOCK);
    TEST_ASSERT_TRUE(cmd.utc_us == INT64_C(4102444799999999));
    TEST_ASSERT_EQUAL_INT32(840, cmd.offset_min);

    cmd = parse_ok("SCHEDULE,Levodopa,480,720,1200", REC_CMD_SCHEDULE);
    TEST_ASSERT_EQUAL_STRING("Levodopa", cmd.schedule.name);
    TEST_ASSERT_EQUAL_UINT8(3, cmd.schedule.count);
    TEST_ASSERT_EQUAL_UINT16(480, cmd.schedule.minutes[0]);
    TEST_ASSERT_EQUAL_UINT16(720, cmd.schedule.minutes[1]);
    TEST_ASSERT_EQUAL_UINT16(1200, cmd.schedule.minutes[2]);

    cmd = parse_ok("SCHEDULE,Sinemet-CR.25/100+,600", REC_CMD_SCHEDULE);
    TEST_ASSERT_EQUAL_STRING("Sinemet-CR.25/100+", cmd.schedule.name);
    TEST_ASSERT_EQUAL_UINT8(1, cmd.schedule.count);
    TEST_ASSERT_EQUAL_UINT16(600, cmd.schedule.minutes[0]);

    cmd = parse_ok("SCHEDULE,ABCDEFGHIJKLMNOPQRST,0,1,2,3,4,1439", REC_CMD_SCHEDULE);
    TEST_ASSERT_EQUAL_STRING("ABCDEFGHIJKLMNOPQRST", cmd.schedule.name);
    TEST_ASSERT_EQUAL_UINT8(6, cmd.schedule.count);

    cmd = parse_ok("SCHEDULE,Levodopa", REC_CMD_SCHEDULE);
    TEST_ASSERT_EQUAL_STRING("Levodopa", cmd.schedule.name);
    TEST_ASSERT_EQUAL_UINT8(0, cmd.schedule.count);
    cmd = parse_ok("SCHEDULE", REC_CMD_SCHEDULE);
    TEST_ASSERT_EQUAL_STRING("", cmd.schedule.name);
    TEST_ASSERT_EQUAL_UINT8(0, cmd.schedule.count);

    cmd = parse_ok("SCHEDULE,Levodopa,480,480", REC_CMD_SCHEDULE);
    TEST_ASSERT_EQUAL_UINT8(2, cmd.schedule.count);
    dose_t dose;
    dose_init(&dose);
    TEST_ASSERT_FALSE(dose_set_schedule(&dose, &cmd.schedule, 0));

    parse_ok("SESSION", REC_CMD_SESSION);

    cmd = parse_ok("TONE,0", REC_CMD_TONE);
    TEST_ASSERT_FALSE(cmd.tone_on);
    cmd = parse_ok("TONE,1", REC_CMD_TONE);
    TEST_ASSERT_TRUE(cmd.tone_on);
    cmd = parse_ok("TONE,1\r", REC_CMD_TONE);
    TEST_ASSERT_TRUE(cmd.tone_on);

    parse_ok("", REC_CMD_EMPTY);
    parse_ok("\r", REC_CMD_EMPTY);
}

/* refused() parses each line, which must give the kind and the result. */
static void refused(const char *const *lines, size_t n, rec_cmd_t kind, rec_result_t result)
{
    for (size_t i = 0; i < n; i++) {
        rec_command_t cmd;
        TEST_ASSERT_EQUAL_INT_MESSAGE(result, rec_parse_command(lines[i], &cmd), lines[i]);
        TEST_ASSERT_EQUAL_INT_MESSAGE(kind, cmd.kind, lines[i]);
    }
}

#define REFUSED(kind, result, ...)                                                                                 \
    do {                                                                                                           \
        static const char *const lines_[] = {__VA_ARGS__};                                                       \
        refused(lines_, sizeof lines_ / sizeof lines_[0], kind, result);                                         \
    } while (0)

static void test_13_bad_commands(void)
{
    REFUSED(REC_CMD_UNKNOWN, REC_UNKNOWN, "HELLO", "clock,1761206400000000,60", "CLOCKS,1", "TONE 1", "SESSION ");
    REFUSED(REC_CMD_CLOCK, REC_BAD_FORMAT, "CLOCK", "CLOCK,1761206400000000", "CLOCK,1761206400000000,60,1",
        "CLOCK,abc,60", "CLOCK,,60", "CLOCK,+1761206400000000,60", "CLOCK,1761206400000000,6 0",
        "CLOCK,17612064000000000000,0");
    REFUSED(REC_CMD_CLOCK, REC_REFUSED, "CLOCK,1577836799999999,0", "CLOCK,4102444800000000,0",
        "CLOCK,1761206400000000,841", "CLOCK,1761206400000000,-721");
    REFUSED(REC_CMD_SCHEDULE, REC_BAD_FORMAT, "SCHEDULE,", "SCHEDULE,,480", "SCHEDULE,Levo dopa,480",
        "SCHEDULE,Levodopa,8am", "SCHEDULE,Levodopa,480,", "SCHEDULE,L\xc3\xa9vodopa");
    REFUSED(REC_CMD_SCHEDULE, REC_REFUSED, "SCHEDULE,ABCDEFGHIJKLMNOPQRSTU", "SCHEDULE,Levodopa,1440",
        "SCHEDULE,Levodopa,-1", "SCHEDULE,Levodopa,1,2,3,4,5,6,7");
    REFUSED(REC_CMD_SESSION, REC_BAD_FORMAT, "SESSION,1", "SESSION,");
    REFUSED(REC_CMD_TONE, REC_BAD_FORMAT, "TONE", "TONE,", "TONE,1,1", "TONE,x");
    REFUSED(REC_CMD_TONE, REC_REFUSED, "TONE,2", "TONE,-1");

    char long_line[129];
    memset(long_line, 'A', 128);
    long_line[128] = '\0';
    rec_command_t cmd;
    TEST_ASSERT_EQUAL_INT(REC_BAD_FORMAT, rec_parse_command(long_line, &cmd));
    TEST_ASSERT_EQUAL_INT(REC_CMD_UNKNOWN, cmd.kind);
}

static void test_14_clock_offset(void)
{
    TEST_ASSERT_TRUE(rec_clock_offset_us(INT64_C(1761206400000000), 60, 5000000) == INT64_C(1761209995000000));
    TEST_ASSERT_TRUE(rec_clock_offset_us(INT64_C(1761206400000000), -720, 0) == INT64_C(1761163200000000));
    TEST_ASSERT_TRUE(rec_clock_offset_us(INT64_C(1577836800000000), 840, INT64_C(7200000000)) ==
        INT64_C(1577880000000000));
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_1_constants);
    RUN_TEST(test_2_boot_line);
    RUN_TEST(test_3_stretch_line);
    RUN_TEST(test_4_burst_line);
    RUN_TEST(test_5_reading_line);
    RUN_TEST(test_6_window_line);
    RUN_TEST(test_7_fault_window_line);
    RUN_TEST(test_8_face_line);
    RUN_TEST(test_9_dose_line);
    RUN_TEST(test_10_reply_line);
    RUN_TEST(test_11_line_must_fit);
    RUN_TEST(test_12_good_commands);
    RUN_TEST(test_13_bad_commands);
    RUN_TEST(test_14_clock_offset);
    return UNITY_END();
}
