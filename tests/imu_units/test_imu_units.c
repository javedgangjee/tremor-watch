/*
 * Unit tests for the gyroscope's unit rule in core/imu_units.c.
 */

#include <stdint.h>
#include <string.h>

#include "imu_units.h"
#include "unity.h"

void setUp(void) {}

void tearDown(void) {}

/* bits() gives the bits of a float, so a check can compare floats exactly. */
static uint32_t bits(float f)
{
    uint32_t u;
    memcpy(&u, &f, sizeof u);
    return u;
}

/* Case 1 checks the two constants. */
static void test_constants(void)
{
    TEST_ASSERT_EQUAL_INT(1024, IMU_GYRO_RANGE_DPS);
    TEST_ASSERT_EQUAL_INT(32, IMU_GYRO_COUNTS_PER_DPS);
}

/* Case 2 checks six counts against their exact values. */
static void test_known_counts(void)
{
    TEST_ASSERT_EQUAL_UINT32(bits(0.0f), bits(imu_gyro_dps(0)));
    TEST_ASSERT_EQUAL_UINT32(bits(1.0f), bits(imu_gyro_dps(32)));
    TEST_ASSERT_EQUAL_UINT32(bits(-1.0f), bits(imu_gyro_dps(-32)));
    TEST_ASSERT_EQUAL_UINT32(bits(0.03125f), bits(imu_gyro_dps(1)));
    TEST_ASSERT_EQUAL_UINT32(bits(1023.96875f), bits(imu_gyro_dps(32767)));
    TEST_ASSERT_EQUAL_UINT32(bits(-1024.0f), bits(imu_gyro_dps(-32768)));
}

/* Case 3 checks every count, and checks that each result is exact. */
static void test_every_count(void)
{
    for (int32_t raw = INT16_MIN; raw <= INT16_MAX; raw++) {
        float got = imu_gyro_dps((int16_t)raw);
        float want = (float)raw / 32.0f;
        if (bits(got) != bits(want)) {
            TEST_FAIL_MESSAGE("a count gives different bits from (float)raw / 32.0f");
        }
        if (got * 32.0f != (float)raw) {
            TEST_FAIL_MESSAGE("a count does not give an exact float");
        }
    }
}

int main(void)
{
    UNITY_BEGIN();
    RUN_TEST(test_constants);
    RUN_TEST(test_known_counts);
    RUN_TEST(test_every_count);
    return UNITY_END();
}
