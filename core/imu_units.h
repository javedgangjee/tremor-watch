/*
 * imu_units.h is the gyroscope's unit rule for the watch and for replay.
 *
 * The QMI8658 runs its gyroscope at a range of plus or minus 1024 degrees a
 * second. A raw count is a signed 16-bit number, so 32 counts make one degree
 * a second. Every count divided by 32 gives an exact 32-bit float.
 *
 * The file has no static data that changes.
 */

#ifndef IMU_UNITS_H
#define IMU_UNITS_H

#include <stdint.h>

/* The gyroscope range in degrees a second. */
#define IMU_GYRO_RANGE_DPS 1024
/* The number of raw counts in one degree a second, which is 32768 / 1024. */
#define IMU_GYRO_COUNTS_PER_DPS 32

/* imu_gyro_dps() turns one raw gyroscope count into degrees a second. It
 * returns raw / 32 as a 32-bit float. */
float imu_gyro_dps(int16_t raw);

#endif /* IMU_UNITS_H */
