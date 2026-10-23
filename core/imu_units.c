/*
 * imu_units.c holds the gyroscope's unit rule. imu_units.h describes it, and
 * requirement 27 of feature 7 gives the details.
 */

#include "imu_units.h"

float imu_gyro_dps(int16_t raw)
{
    return (float)raw / (float)IMU_GYRO_COUNTS_PER_DPS;
}
