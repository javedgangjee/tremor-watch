/*
 * converter.h is the converter, which turns one stretch of gyroscope readings
 * into 100 readings a second.
 *
 * The converter follows the plan's Sensor and converter section, under
 * Converting to 100 readings a second. Block b makes the 100 Hz samples 100b
 * to 100b + 99 of the stretch. It fits a natural cubic spline through the
 * block's readings plus 16 extra readings on each side, reads the curve at
 * each sample, and throws away the extra readings. The 100 Hz grid starts at
 * the stretch's first reading. The converter adds no filter.
 *
 * Readings and samples are in degrees per second as 32-bit floats. A rate is a
 * whole number of millionths of a reading per second.
 *
 * The caller owns the state. The file has no static data that changes.
 */

#ifndef CONVERTER_H
#define CONVERTER_H

#include <stdbool.h>
#include <stdint.h>

/* The converter takes the three gyroscope axes. */
#define CONV_AXES 3
/* The converter gives 100 samples a second. */
#define CONV_OUT_HZ 100
/* Each block has 16 extra readings on each side. */
#define CONV_MARGIN 16
/* Each block gives 100 samples, which is one second. */
#define CONV_BLOCK_SAMPLES 100
/* The ring holds 2048 readings, which is more than 10 seconds at the highest
 * rate plus one full sensor buffer. */
#define CONV_RING_LEN 2048
/* A block holds at most 192 readings. */
#define CONV_MAX_BLOCK 192
/* The lowest and the highest rate the converter accepts, in millionths of a
 * reading per second. */
#define CONV_RATE_MIN_UHZ 50000000u
#define CONV_RATE_MAX_UHZ 150000000u

typedef struct {
    /* The ring of readings. Reading n of the stretch sits at n % CONV_RING_LEN. */
    float ring[CONV_RING_LEN][CONV_AXES];
    /* The stretch's rate, or 0 when it is not set yet. */
    uint32_t rate_uhz;
    /* The number of readings pushed in this stretch. */
    uint64_t count;
    /* The number of the oldest reading the ring still holds. */
    uint64_t base;
    /* The number of the next block. */
    uint64_t next_block;
    /* The work arrays for one block. They hold the readings, the second
     * derivatives, and the forward sweep's factors and values. */
    float y[CONV_AXES][CONV_MAX_BLOCK];
    float m[CONV_AXES][CONV_MAX_BLOCK];
    float factor[CONV_MAX_BLOCK];
    float sweep[CONV_MAX_BLOCK];
} conv_t;

/* conv_start() starts a new stretch. It drops every reading, the rate, and any
 * part block. It must run before the first use. */
void conv_start(conv_t *c);

/* conv_set_rate() sets the stretch's rate once. It returns false for a rate
 * outside the range or for a second call in the same stretch. */
bool conv_set_rate(conv_t *c, uint32_t rate_uhz);

/* conv_push() adds the stretch's next reading. It returns false and keeps
 * nothing when the ring has no free place. */
bool conv_push(conv_t *c, const float reading[CONV_AXES]);

/* conv_block() makes the next block when the rate is known and all its
 * readings are in. It writes 100 samples and the number of the first one. It
 * returns false and writes nothing otherwise. */
bool conv_block(conv_t *c, float out[CONV_BLOCK_SAMPLES][CONV_AXES], uint64_t *first_sample);

/* conv_position() gives the position of 100 Hz sample `sample` as the reading
 * before it and the fraction of a reading after that reading. */
void conv_position(uint32_t rate_uhz, uint64_t sample, uint64_t *reading, float *frac);

#endif /* CONVERTER_H */
