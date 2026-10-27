/*
 * reading_time.h is the time rule, which gives each gyroscope reading its time.
 *
 * The readings arrive in bursts, and each burst has a 64-bit microsecond
 * stamp. The readings form stretches with no gap. Within a stretch, reading n
 * has the time t0 + (n - f0) / r, where t0 is the stamp of the first burst, f0
 * is its first reading number, and r is one fixed rate.
 *
 * A rate is a whole number of millionths of a reading per second. For example,
 * 114.3302 readings a second is 114330200.
 *
 * The caller owns the state. The file has no static data that changes.
 */

#ifndef READING_TIME_H
#define READING_TIME_H

#include <stdbool.h>
#include <stdint.h>

/* rt_burst() sets this flag when the burst starts a new stretch. */
#define RT_NEW_STRETCH 1u
/* rt_burst() sets this flag when the current stretch gets its rate. */
#define RT_RATE_SET 2u

typedef struct {
    /* The stretch number, which counts from 0 after rt_init(). */
    uint32_t number;
    /* The number of the stretch's first reading, counted from power-on. */
    uint64_t first_reading;
    /* The stamp of the stretch's first burst in microseconds. */
    int64_t t0_us;
    /* The rate in millionths of a reading per second. 0 means that the rate
     * is not known yet. */
    uint32_t rate_uhz;
} rt_stretch_t;

typedef struct {
    /* The number of the burst's first reading, counted from power-on. */
    uint64_t first_reading;
    /* The number of readings in the burst. */
    uint32_t count;
    /* The burst's stamp in microseconds. */
    int64_t stamp_us;
} rt_burst_t;

typedef struct {
    /* started is false until the first burst after rt_init(). */
    bool started;
    rt_stretch_t stretch;
    /* The first and the last burst of the current stretch. */
    rt_burst_t first;
    rt_burst_t last;
    /* The first and the last burst of the stretch before. They are valid when
     * stretch.number is more than 0. */
    rt_burst_t before_first;
    rt_burst_t before_last;
} rt_state_t;

/* rt_init() clears the state, so the next burst starts stretch 0. */
void rt_init(rt_state_t *s);

/* rt_burst() applies the time rule to one burst and returns the flags.
 * first_reading is the number of the burst's first reading, counted from
 * power-on. stamp_us is the burst's stamp. overflow is true when the sensor's
 * buffer overflowed before this burst. A burst with no readings changes
 * nothing and returns 0. */
unsigned rt_burst(rt_state_t *s, uint64_t first_reading, uint32_t count, int64_t stamp_us, bool overflow);

const rt_stretch_t *rt_current(const rt_state_t *s);

/* rt_reading_time_us() gives the time of reading `reading` in microseconds,
 * which is t0 + (reading - first_reading) * 1e12 / rate_uhz. The stretch must
 * have a rate, and the function returns NAN when it has none. */
double rt_reading_time_us(const rt_stretch_t *st, uint64_t reading);

/* rt_sample_time_us() gives the time of 100 Hz sample `sample` of the stretch
 * in microseconds, which is t0 + 10000 * sample. */
int64_t rt_sample_time_us(const rt_stretch_t *st, uint64_t sample);

#endif /* READING_TIME_H */
