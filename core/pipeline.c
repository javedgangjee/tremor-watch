/* pipeline.c holds the pipeline task's rules. See pipeline.h. */

#include "pipeline.h"

/* The last sample of window n is sample 100n + 399. */
#define LAST_SAMPLE_OFFSET (DET_WINDOW_LEN - 1)

void pipe_init(pipe_t *p, int64_t now_us)
{
    conv_start(&p->conv);
    win_start(&p->win);
    p->stretch.number = 0;
    p->stretch.first_reading = 0;
    p->stretch.t0_us = 0;
    p->stretch.rate_uhz = 0;
    p->started = false;
    p->in_sync = false;
    p->rate_tried = false;
    p->next_reading = 0;
    p->end_asked = false;
    p->end_reason = PIPE_REASON_NONE;
    p->end_stretch = 0;
    p->last_part_us = now_us;
    p->next_fault_us = now_us + PIPE_FAULT_AFTER_US;
    p->stretches = 0;
    p->end_requests = 0;
    p->rate_refused = 0;
    p->faults = 0;
}

/* Makes an end request for stretch `number`, unless that stretch has already
 * asked. Returns PIPE_END when it makes the request. */
static unsigned ask_end(pipe_t *p, uint32_t number, unsigned reason)
{
    if (p->end_asked && p->end_stretch == number) {
        return 0;
    }
    p->end_asked = true;
    p->end_stretch = number;
    p->end_reason = reason;
    p->end_requests++;
    return PIPE_END;
}

unsigned pipe_part(pipe_t *p, const pipe_part_t *m, int64_t now_us)
{
    p->last_part_us = now_us;
    p->next_fault_us = now_us + PIPE_FAULT_AFTER_US;

    unsigned result = 0;
    if ((m->flags & RT_NEW_STRETCH) != 0) {
        conv_start(&p->conv);
        win_start(&p->win);
        p->stretch.number = m->stretch;
        p->stretch.first_reading = m->first_reading;
        p->stretch.t0_us = m->stamp_us;
        p->stretch.rate_uhz = 0;
        p->started = true;
        p->in_sync = true;
        p->rate_tried = false;
        p->next_reading = m->first_reading;
        p->stretches++;
        result = PIPE_STRETCH;
    } else if (!p->started || m->stretch != p->stretch.number) {
        /* The part belongs to a stretch whose first part was lost. */
        p->in_sync = false;
        return ask_end(p, m->stretch, PIPE_REASON_MISSED_START) | PIPE_DROP;
    } else if (!p->in_sync) {
        return PIPE_DROP;
    } else if (m->first_reading != p->next_reading) {
        p->in_sync = false;
        return ask_end(p, m->stretch, PIPE_REASON_BREAK) | PIPE_DROP;
    }

    if (!p->rate_tried && m->rate_uhz != 0) {
        p->rate_tried = true;
        if (conv_set_rate(&p->conv, m->rate_uhz)) {
            p->stretch.rate_uhz = m->rate_uhz;
        } else {
            p->rate_refused++;
        }
    }
    p->next_reading = m->first_reading + m->count;
    return result;
}

unsigned pipe_push(pipe_t *p, const float reading[CONV_AXES])
{
    if (!p->in_sync) {
        return 0;
    }
    if (!conv_push(&p->conv, reading)) {
        p->in_sync = false;
        return ask_end(p, p->stretch.number, PIPE_REASON_RING_FULL);
    }
    return 0;
}

bool pipe_window(pipe_t *p, float window[DET_WINDOW_LEN][DET_AXES], uint32_t *number, int64_t *time_us)
{
    if (!p->in_sync) {
        return false;
    }
    uint64_t first_sample;
    while (conv_block(&p->conv, p->block, &first_sample)) {
        if (win_push_block(&p->win, p->block, first_sample, window, number)) {
            uint64_t last = (uint64_t)*number * CONV_BLOCK_SAMPLES + LAST_SAMPLE_OFFSET;
            *time_us = rt_sample_time_us(&p->stretch, last);
            return true;
        }
    }
    return false;
}

bool pipe_fault_due(pipe_t *p, int64_t now_us)
{
    if (now_us < p->next_fault_us) {
        return false;
    }
    p->next_fault_us += PIPE_FAULT_EVERY_US;
    p->faults++;
    return true;
}

int64_t pipe_next_fault_us(const pipe_t *p)
{
    return p->next_fault_us;
}

const rt_stretch_t *pipe_stretch(const pipe_t *p)
{
    return &p->stretch;
}

uint32_t pipe_end_stretch(const pipe_t *p)
{
    return p->end_stretch;
}

unsigned pipe_end_reason(const pipe_t *p)
{
    return p->end_reason;
}
