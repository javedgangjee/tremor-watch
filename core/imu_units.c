/* imu_units.c converts raw gyroscope counts. See imu_units.h. */

#include "imu_units.h"

float imu_gyro_dps(int16_t raw)
{
    return (float)raw / (float)IMU_GYRO_COUNTS_PER_DPS;
}
