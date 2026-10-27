/* reading_time.c gives each sensor reading a time. See reading_time.h. */

#include "reading_time.h"

#include <math.h>
#include <stddef.h>
#include <string.h>

/* A rate comes from at least 10 seconds of stamps. */
#define RATE_SPAN_US 10000000
/* Before a stretch has its rate, the line test starts once the stretch spans
 * 1 second. */
#define LINE_SPAN_US 1000000
/* This number divided by a rate in micro-Hz gives microseconds per reading. */
#define UHZ_US 1e12
/* Half a reading period in microseconds is this number divided by the rate. A
 * stamp more than half a period off its predicted time ends the stretch. */
#define HALF_PERIOD_UHZ_US 5e11
/* A 100 Hz sample lasts 10000 microseconds. */
#define SAMPLE_US 10000

void rt_init(rt_state_t *s)
{
    memset(s, 0, sizeof *s);
}

/* Gives the rate in micro-Hz from burst a to burst b, rounded half up. */
static uint32_t measured_rate(const rt_burst_t *a, const rt_burst_t *b)
{
    double df = (double)(b->first_reading - a->first_reading);
    double ds = (double)(b->stamp_us - a->stamp_us);
    double rate = floor(df * UHZ_US / ds + 0.5);
    /* A rate that does not fit stays unknown. Real sensor rates never come
     * near these ends. */
    if (!(rate >= 1.0 && rate <= (double)UINT32_MAX)) {
        return 0;
    }
    return (uint32_t)rate;
}

/* Says whether the burst ends the current stretch. */
static bool ends_stretch(const rt_state_t *s, const rt_burst_t *b, bool overflow)
{
    const rt_burst_t *first = &s->first;
    const rt_burst_t *last = &s->last;
    if (overflow || b->stamp_us <= last->stamp_us || b->first_reading != last->first_reading + last->count) {
        return true;
    }
    if (s->stretch.rate_uhz != 0) {
        double predicted = rt_reading_time_us(&s->stretch, b->first_reading);
        return fabs((double)b->stamp_us - predicted) > HALF_PERIOD_UHZ_US / (double)s->stretch.rate_uhz;
    }
    /* With no rate yet, the burst is tested against the line through the
     * stretch's first burst and the burst before, once that line spans 1 second. */
    if (last->stamp_us - first->stamp_us >= LINE_SPAN_US) {
        double period = (double)(last->stamp_us - first->stamp_us) / (double)(last->first_reading - first->first_reading);
        double predicted = (double)first->stamp_us + (double)(b->first_reading - first->first_reading) * period;
        return fabs((double)b->stamp_us - predicted) > period / 2.0;
    }
    return false;
}

/* Starts a new stretch at the burst and returns the RT_ flags. */
static unsigned start_stretch(rt_state_t *s, const rt_burst_t *b)
{
    unsigned flags = RT_NEW_STRETCH;
    if (s->started) {
        s->before_first = s->first;
        s->before_last = s->last;
        s->stretch.number++;
    } else {
        s->started = true;
        s->stretch.number = 0;
    }
    s->stretch.first_reading = b->first_reading;
    s->stretch.t0_us = b->stamp_us;
    s->stretch.rate_uhz = 0;
    s->first = *b;
    s->last = *b;
    if (s->stretch.number > 0 && s->before_last.stamp_us - s->before_first.stamp_us >= RATE_SPAN_US) {
        s->stretch.rate_uhz = measured_rate(&s->before_first, &s->before_last);
        if (s->stretch.rate_uhz != 0) {
            flags |= RT_RATE_SET;
        }
    }
    return flags;
}

unsigned rt_burst(rt_state_t *s, uint64_t first_reading, uint32_t count, int64_t stamp_us, bool overflow)
{
    if (count == 0) {
        return 0;
    }
    rt_burst_t b = {first_reading, count, stamp_us};
    if (!s->started || ends_stretch(s, &b, overflow)) {
        return start_stretch(s, &b);
    }
    s->last = b;
    if (s->stretch.rate_uhz == 0 && stamp_us - s->stretch.t0_us >= RATE_SPAN_US) {
        s->stretch.rate_uhz = measured_rate(&s->first, &b);
        if (s->stretch.rate_uhz != 0) {
            return RT_RATE_SET;
        }
    }
    return 0;
}

const rt_stretch_t *rt_current(const rt_state_t *s)
{
    return &s->stretch;
}

double rt_reading_time_us(const rt_stretch_t *st, uint64_t reading)
{
    if (st->rate_uhz == 0) {
        return NAN;
    }
    return (double)st->t0_us + (double)(int64_t)(reading - st->first_reading) * UHZ_US / (double)st->rate_uhz;
}

int64_t rt_sample_time_us(const rt_stretch_t *st, uint64_t sample)
{
    return st->t0_us + SAMPLE_US * (int64_t)sample;
}
