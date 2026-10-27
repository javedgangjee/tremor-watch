/* window.c holds the result codes and the window rule. See window.h. */

#include "window.h"

const char *res_name(res_code_t code)
{
    switch (code) {
    case RES_TREMOR:
        return "tremor";
    case RES_NO_TREMOR:
        return "no tremor";
    case RES_ARM_MOVING:
        return "arm moving";
    case RES_WARMING_UP:
        return "warming up";
    case RES_SENSOR_FAULT:
        return "sensor fault";
    default:
        return "unknown";
    }
}

res_code_t res_from_answer(uint32_t window, const det_result_t *r)
{
    if (window == 0) {
        return RES_WARMING_UP;
    }
    if (r->tremor) {
        return RES_TREMOR;
    }
    return r->at_rest ? RES_NO_TREMOR : RES_ARM_MOVING;
}

void win_start(win_t *w)
{
    w->count = 0;
}

bool win_push_block(win_t *w, const float block[CONV_BLOCK_SAMPLES][CONV_AXES], uint64_t first_sample,
    float window[DET_WINDOW_LEN][DET_AXES], uint32_t *number)
{
    if (first_sample != w->count * CONV_BLOCK_SAMPLES) {
        return false;
    }
    float(*slot)[CONV_AXES] = w->blocks[w->count % WIN_BLOCKS];
    for (int s = 0; s < CONV_BLOCK_SAMPLES; s++) {
        for (int axis = 0; axis < CONV_AXES; axis++) {
            slot[s][axis] = block[s][axis];
        }
    }
    w->count++;
    if (w->count < WIN_BLOCKS) {
        return false;
    }

    /* The window starts with the oldest of the four blocks. */
    uint64_t first_block = w->count - WIN_BLOCKS;
    for (uint64_t b = 0; b < WIN_BLOCKS; b++) {
        float(*src)[CONV_AXES] = w->blocks[(first_block + b) % WIN_BLOCKS];
        for (int s = 0; s < CONV_BLOCK_SAMPLES; s++) {
            for (int axis = 0; axis < CONV_AXES; axis++) {
                window[b * CONV_BLOCK_SAMPLES + (uint64_t)s][axis] = src[s][axis];
            }
        }
    }
    *number = (uint32_t)first_block;
    return true;
}
