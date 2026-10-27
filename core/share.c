/* share.c holds the session share and the Session screen's blocks. See
 * share.h. */

#include "share.h"

#include <stddef.h>

/* The highest block number. It leaves room to count one past it. */
#define LAST_BLOCK_NUMBER (UINT32_MAX - 1u)

void share_start(share_t *s, int64_t start_us)
{
    s->start_us = start_us;
    s->tremor = 0;
    s->no_tremor = 0;
    s->moving = 0;
    s->head = 0;
    s->count = 0;
}

/* Gives the block that a window ending at time_us goes in. */
static uint32_t block_number(const share_t *s, int64_t time_us)
{
    if (time_us <= s->start_us) {
        return 0;
    }
    int64_t k = (time_us - s->start_us) / SHARE_BLOCK_US;
    return k > (int64_t)LAST_BLOCK_NUMBER ? LAST_BLOCK_NUMBER : (uint32_t)k;
}

/* Adds an empty block after the newest one. Drops the oldest block when the
 * ring is full. */
static void append(share_t *s, uint32_t number)
{
    uint32_t slot;
    if (s->count < SHARE_BLOCKS) {
        slot = (s->head + s->count) % SHARE_BLOCKS;
        s->count++;
    } else {
        slot = s->head;
        s->head = (s->head + 1) % SHARE_BLOCKS;
    }
    s->blocks[slot].number = number;
    s->blocks[slot].tremor = 0;
    s->blocks[slot].still = 0;
    s->blocks[slot].moving = 0;
}

bool share_add(share_t *s, uint32_t window, res_code_t code, int64_t time_us)
{
    if (window == 0 || window % SHARE_EVERY != 0) {
        return false;
    }
    if (code != RES_TREMOR && code != RES_NO_TREMOR && code != RES_ARM_MOVING) {
        return false;
    }

    /* A window in a later block adds the blocks up to it. The ring keeps only
     * SHARE_BLOCKS blocks, so adding starts no earlier than SHARE_BLOCKS - 1
     * before it. */
    uint32_t k = block_number(s, time_us);
    uint32_t next = 0;
    if (s->count > 0) {
        next = s->blocks[(s->head + s->count - 1) % SHARE_BLOCKS].number + 1;
    }
    if (k >= next && k - next >= SHARE_BLOCKS) {
        next = k - (SHARE_BLOCKS - 1);
    }
    for (uint32_t n = next; n <= k; n++) {
        append(s, n);
    }

    if (code == RES_TREMOR) {
        s->tremor++;
    } else if (code == RES_NO_TREMOR) {
        s->no_tremor++;
    } else {
        s->moving++;
    }

    /* A window in a block that has dropped out counts in the session only. */
    uint32_t oldest = s->blocks[s->head].number;
    if (k >= oldest) {
        share_block_t *b = &s->blocks[(s->head + (k - oldest)) % SHARE_BLOCKS];
        if (code == RES_TREMOR) {
            b->tremor++;
            b->still++;
        } else if (code == RES_NO_TREMOR) {
            b->still++;
        } else {
            b->moving++;
        }
    }
    return true;
}

/* Divides first and then multiplies by 100, as the toolbox's
 * aggregate_tremor() does, so the results match. */
static bool percent(uint32_t tremor, uint32_t still, double *out)
{
    if (still == 0) {
        return false;
    }
    *out = (double)tremor / (double)still * 100.0;
    return true;
}

bool share_percent(const share_t *s, double *out)
{
    return percent(s->tremor, s->tremor + s->no_tremor, out);
}

uint32_t share_block_count(const share_t *s)
{
    return s->count;
}

const share_block_t *share_block(const share_t *s, uint32_t i)
{
    if (i >= s->count) {
        return NULL;
    }
    return &s->blocks[(s->head + i) % SHARE_BLOCKS];
}

bool share_block_percent(const share_block_t *b, double *out)
{
    return percent(b->tremor, b->still, out);
}

bool share_block_hollow(const share_block_t *b)
{
    return (int64_t)b->still * SHARE_WINDOW_STILL_US < SHARE_HOLLOW_BELOW_US;
}
