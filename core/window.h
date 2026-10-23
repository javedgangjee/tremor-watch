/*
 * window.h holds the result codes and the window rule.
 *
 * The rule follows the plan's Windows section. Window n of a stretch holds the
 * 100 Hz samples 100n to 100n + 399. The converter gives the samples in blocks
 * of 100, and block b starts at sample 100b, so window n is complete when
 * block n + 3 arrives. The detector runs on each window as soon as it is
 * complete, so the runs follow the readings and never a timer.
 *
 * Every answer carries one result code from the list below, as the plan's
 * Firmware design section says. The numbers are fixed, and the W line of the
 * recording writes them.
 *
 * The caller owns the state. The file has no static data that changes. On the
 * watch the pipeline task owns the window rule.
 */

#ifndef WINDOW_H
#define WINDOW_H

#include <stdbool.h>
#include <stdint.h>

#include "converter.h"
#include "detector.h"

/* A window holds four blocks. */
#define WIN_BLOCKS (DET_WINDOW_LEN / CONV_BLOCK_SAMPLES)

typedef enum {
    RES_TREMOR = 0,
    RES_NO_TREMOR = 1,
    RES_ARM_MOVING = 2,
    RES_WARMING_UP = 3,
    RES_SENSOR_FAULT = 4,
    RES_COUNT = 5
} res_code_t;

typedef struct {
    /* The last four blocks of the stretch. Block b sits at b % WIN_BLOCKS. */
    float blocks[WIN_BLOCKS][CONV_BLOCK_SAMPLES][CONV_AXES];
    /* The number of blocks taken in this stretch. */
    uint64_t count;
} win_t;

/* res_name() gives the name of a code, or "unknown" for any other value. */
const char *res_name(res_code_t code);

/* res_from_answer() gives warming up for window 0. For any other window it
 * gives tremor when the detector says tremor, no tremor when the arm is at
 * rest, and arm moving otherwise. */
res_code_t res_from_answer(uint32_t window, const det_result_t *r);

/* win_start() starts a new stretch, so the next block must start at sample 0. */
void win_start(win_t *w);

/* win_push_block() takes the stretch's next block, whose first sample is
 * first_sample. It returns true and writes the window in sample order and its
 * number when a window is complete. It returns false and writes nothing
 * otherwise. It refuses a block whose first sample is not the next one, and
 * the refusal changes nothing. */
bool win_push_block(win_t *w, const float block[CONV_BLOCK_SAMPLES][CONV_AXES], uint64_t first_sample,
    float window[DET_WINDOW_LEN][DET_AXES], uint32_t *number);

#endif /* WINDOW_H */
