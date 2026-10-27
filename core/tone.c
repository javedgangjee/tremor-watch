/*
 * tone.c fills the samples of the face's two tones. tone.h describes them,
 * and feature 11's requirement 59 gives the details.
 */

#include "tone.h"

#include <math.h>

#define MS_SAMPLES(ms) ((size_t)(ms) * TONE_RATE / 1000)
/* The fade at each end of a tone lasts 5 milliseconds. */
#define FADE_SAMPLES MS_SAMPLES(5)
#define TWO_PI 6.283185307179586

typedef struct {
    /* The frequency in Hz. */
    uint32_t hz;
    /* The samples of one tone and of the silence after it. */
    size_t on;
    size_t off;
    /* The number of tones. */
    size_t count;
} pattern_t;

static const pattern_t PATTERNS[] = {
    [TONE_TAP] = {660, MS_SAMPLES(120), 0, 1},
    [TONE_DOSE] = {880, MS_SAMPLES(250), MS_SAMPLES(250), 3},
};

static const pattern_t *pattern_of(tone_kind_t kind)
{
    return (unsigned)kind < sizeof PATTERNS / sizeof PATTERNS[0] ? &PATTERNS[kind] : NULL;
}

size_t tone_length(tone_kind_t kind)
{
    const pattern_t *p = pattern_of(kind);
    return p == NULL ? 0 : p->count * (p->on + p->off);
}

/* sample() gives sample k of one tone. The phase uses the whole number
 * k * hz modulo the rate, so it stays exact for every k. */
static int16_t sample(const pattern_t *p, size_t k)
{
    size_t from_end = p->on - 1 - k;
    size_t edge = k < from_end ? k : from_end;
    float fade = edge < FADE_SAMPLES ? (float)edge / (float)FADE_SAMPLES : 1.0f;
    uint32_t turn = (uint32_t)(((uint64_t)k * p->hz) % TONE_RATE);
    float phase = (float)(TWO_PI * (double)turn / (double)TONE_RATE);
    float value = sinf(phase) * (float)TONE_PEAK * fade;
    return (int16_t)lroundf(value);
}

size_t tone_fill(tone_kind_t kind, size_t start, int16_t *out, size_t n)
{
    const pattern_t *p = pattern_of(kind);
    size_t length = tone_length(kind);
    if (p == NULL || start >= length) {
        return 0;
    }
    if (n > length - start) {
        n = length - start;
    }
    size_t period = p->on + p->off;
    for (size_t i = 0; i < n; i++) {
        size_t k = (start + i) % period;
        out[i] = k < p->on ? sample(p, k) : 0;
    }
    return n;
}
