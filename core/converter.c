/* converter.c resamples IMU readings to 100 Hz with a cubic spline. See
 * converter.h. */

#include "converter.h"

#include <stddef.h>

/* Sample k sits at k * rate_uhz / 1e8 readings: the reading rate in micro-Hz
 * divided by the 100 Hz output rate gives readings per sample. */
#define UHZ_PER_OUT_HZ 100000000u
#define UHZ_PER_OUT_HZ_F 1e8
/* A block's spline runs to the reading after the last sample's reading, plus
 * CONV_MARGIN more. */
#define RIGHT_EXTRA (CONV_MARGIN + 1)

void conv_start(conv_t *c)
{
    c->rate_uhz = 0;
    c->count = 0;
    c->base = 0;
    c->next_block = 0;
}

bool conv_set_rate(conv_t *c, uint32_t rate_uhz)
{
    if (c->rate_uhz != 0 || rate_uhz < CONV_RATE_MIN_UHZ || rate_uhz > CONV_RATE_MAX_UHZ) {
        return false;
    }
    c->rate_uhz = rate_uhz;
    return true;
}

bool conv_push(conv_t *c, const float reading[CONV_AXES])
{
    if (c->count - c->base >= CONV_RING_LEN) {
        return false;
    }
    float *slot = c->ring[c->count % CONV_RING_LEN];
    for (int axis = 0; axis < CONV_AXES; axis++) {
        slot[axis] = reading[axis];
    }
    c->count++;
    return true;
}

void conv_position(uint32_t rate_uhz, uint64_t sample, uint64_t *reading, float *frac)
{
    uint64_t scaled = sample * (uint64_t)rate_uhz;
    *reading = scaled / UHZ_PER_OUT_HZ;
    *frac = (float)((double)(scaled % UHZ_PER_OUT_HZ) / UHZ_PER_OUT_HZ_F);
}

/* Gives the first reading that block b uses. */
static uint64_t first_reading(uint32_t rate_uhz, uint64_t block)
{
    uint64_t reading;
    float frac;
    conv_position(rate_uhz, block * CONV_BLOCK_SAMPLES, &reading, &frac);
    return reading >= CONV_MARGIN ? reading - CONV_MARGIN : 0;
}

/* Finds the second derivatives of a natural cubic spline through the n values
 * in y, with the reading period folded in. Follows natural_spline_block() in
 * reference/spline_test.py. factor holds the forward sweep's factors, which
 * are the same for every axis. sweep is scratch space for the sweep. */
static void solve(const float *y, float *m, const float *factor, float *sweep, size_t n)
{
    for (size_t i = 1; i + 1 < n; i++) {
        float rhs = ((y[i + 1] - 2.0f * y[i]) + y[i - 1]) * 6.0f;
        float denom = 4.0f - (i > 1 ? factor[i - 1] : 0.0f);
        sweep[i] = (rhs - (i > 1 ? sweep[i - 1] : 0.0f)) / denom;
    }
    m[0] = 0.0f;
    m[n - 1] = 0.0f;
    for (size_t i = n - 2; i > 0; i--) {
        m[i] = sweep[i] - factor[i] * m[i + 1];
    }
}

bool conv_block(conv_t *c, float out[CONV_BLOCK_SAMPLES][CONV_AXES], uint64_t *first_sample)
{
    if (c->rate_uhz == 0) {
        return false;
    }
    uint64_t k0 = c->next_block * CONV_BLOCK_SAMPLES;
    uint64_t last_pos;
    float frac;
    conv_position(c->rate_uhz, k0 + CONV_BLOCK_SAMPLES - 1, &last_pos, &frac);
    uint64_t lo = first_reading(c->rate_uhz, c->next_block);
    uint64_t hi = last_pos + RIGHT_EXTRA;
    if (hi >= c->count || lo < c->base || hi - lo + 1 > CONV_MAX_BLOCK) {
        return false;
    }
    size_t n = (size_t)(hi - lo + 1);

    for (size_t i = 0; i < n; i++) {
        const float *slot = c->ring[(lo + i) % CONV_RING_LEN];
        for (int axis = 0; axis < CONV_AXES; axis++) {
            c->y[axis][i] = slot[axis];
        }
    }
    for (size_t i = 1; i + 1 < n; i++) {
        float denom = 4.0f - (i > 1 ? c->factor[i - 1] : 0.0f);
        c->factor[i] = 1.0f / denom;
    }
    for (int axis = 0; axis < CONV_AXES; axis++) {
        solve(c->y[axis], c->m[axis], c->factor, c->sweep, n);
    }

    for (uint64_t s = 0; s < CONV_BLOCK_SAMPLES; s++) {
        uint64_t reading;
        float u;
        conv_position(c->rate_uhz, k0 + s, &reading, &u);
        size_t j = (size_t)(reading - lo);
        float a = 1.0f - u;
        float a3 = a * a * a;
        float u3 = u * u * u;
        for (int axis = 0; axis < CONV_AXES; axis++) {
            const float *y = c->y[axis];
            const float *m = c->m[axis];
            out[s][axis] = (m[j] * a3 + m[j + 1] * u3) / 6.0f + (y[j] - m[j] / 6.0f) * a
                + (y[j + 1] - m[j + 1] / 6.0f) * u;
        }
    }

    *first_sample = k0;
    c->next_block++;
    /* A reading leaves the ring only when no later block needs it. */
    uint64_t keep = first_reading(c->rate_uhz, c->next_block);
    if (keep > c->base) {
        c->base = keep;
    }
    return true;
}
