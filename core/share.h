/*
 * share.h holds the session share and the Session screen's blocks.
 *
 * The share follows aggregate_tremor() in ParaDigMa 1.1.2. It counts only the
 * windows whose number divides by 4,
 * because these are the windows the toolbox cuts. It leaves out window 0 of
 * each stretch, which is warming up. It counts only tremor, no tremor, and arm
 * moving answers. The share is the number of tremor windows divided by the
 * number of still windows, times 100, where a still window is a tremor or a no
 * tremor window. An arm moving window is counted, but it is in neither part.
 *
 * The Session screen shows one block for each 10 minutes of the session, and
 * a block with under two minutes of still time is drawn hollow.
 *
 * The caller owns the state. The file has no static data that changes. On the
 * watch the state task owns the share.
 */

#ifndef SHARE_H
#define SHARE_H

#include <stdbool.h>
#include <stdint.h>

#include "window.h"

/* The share counts the windows whose number divides by this. */
#define SHARE_EVERY 4
/* The share keeps the latest 12 blocks. */
#define SHARE_BLOCKS 12
/* Each block covers 10 minutes. */
#define SHARE_BLOCK_US 600000000
/* Each still window adds 4 seconds of still time, because counted windows lie
 * 4 seconds apart. */
#define SHARE_WINDOW_STILL_US 4000000
/* A block is hollow when its still time is under 2 minutes. */
#define SHARE_HOLLOW_BELOW_US 120000000

typedef struct {
    /* The block's number, where block k starts k * 10 minutes after the
     * session start. */
    uint32_t number;
    /* The counted tremor windows. */
    uint32_t tremor;
    /* The counted tremor and no tremor windows. */
    uint32_t still;
    /* The counted arm moving windows. */
    uint32_t moving;
} share_block_t;

typedef struct {
    /* The session start in microseconds. */
    int64_t start_us;
    /* The session counts. */
    uint32_t tremor;
    uint32_t no_tremor;
    uint32_t moving;
    /* The ring of kept blocks. The oldest sits at head, and the blocks have
     * numbers in a row with no gap. */
    share_block_t blocks[SHARE_BLOCKS];
    uint32_t head;
    uint32_t count;
} share_t;

/* share_start() clears the share and sets the session start. */
void share_start(share_t *s, int64_t start_us);

/* share_add() takes one answer. window is the window number in its stretch,
 * and time_us is the time of the window's last 100 Hz sample. It returns true
 * when it counts the answer. A window with a time before the session start
 * goes in block 0. */
bool share_add(share_t *s, uint32_t window, res_code_t code, int64_t time_us);

/* share_percent() gives the session share. It returns false when no still
 * window has been counted. */
bool share_percent(const share_t *s, double *percent);

/* share_block_count() gives the number of blocks kept, from 0 to 12. */
uint32_t share_block_count(const share_t *s);

/* share_block() gives kept block i, where 0 is the oldest. It returns NULL
 * when i is not less than the count. */
const share_block_t *share_block(const share_t *s, uint32_t i);

/* share_block_percent() gives a block's share. It returns false when the
 * block has no still window. */
bool share_block_percent(const share_block_t *b, double *percent);

/* share_block_hollow() is true when a block has under 2 minutes of still time. */
bool share_block_hollow(const share_block_t *b);

#endif /* SHARE_H */
