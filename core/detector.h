/*
 * detector.h is the interface of the tremor detector.
 *
 * The detector follows detect() in reference/plain_detector.py in its 32-bit
 * float case, step for step. It takes one window of 400 readings on three
 * gyroscope axes, at 100 readings a second, in degrees per second.
 *
 * The detector keeps its work buffers in static memory. So only one task may
 * call it, and on the watch that task is the pipeline task.
 */

#ifndef DETECTOR_H
#define DETECTOR_H

#include <stdbool.h>

#define DET_WINDOW_LEN 400
#define DET_AXES 3
#define DET_MFCC_COUNT 12

typedef struct {
    /* The 12 numbers that the toolbox calls mfcc_1 to mfcc_12. */
    float mfcc[DET_MFCC_COUNT];
    /* The model's probability, which the toolbox calls pred_tremor_proba. */
    double prob;
    /* The low-frequency sum, which the toolbox calls below_tremor_power. */
    double below;
    /* The peak frequency in Hz, which the toolbox calls freq_peak. */
    float peak_hz;
    /* The model says yes when the probability is at least the cut-off. */
    bool logreg;
    /* The arm is at rest when the low-frequency sum is 50 or less. */
    bool at_rest;
    /* The window is tremor when the model says yes, the peak lies from 3 to 7 Hz,
     * and the arm is at rest. */
    bool tremor;
} det_result_t;

/* det_init() sets up the two FFT configurations in static buffers. It returns
 * false if a configuration does not fit its buffer. It can run more than once. */
bool det_init(void);

/* det_run() scores one window. det_init() must have returned true first. */
void det_run(const float window[DET_WINDOW_LEN][DET_AXES], det_result_t *out);

/* det_decide() gives the three answers from prob, below, and peak_hz, which
 * it leaves as they are. The model says yes when prob is at least the
 * toolbox's cut-off. The arm is at rest when below is 50 or less. The window
 * is tremor when both hold and peak_hz lies from 3 to 7 Hz, with both ends
 * included. det_run() calls it, and it needs no det_init(). */
void det_decide(det_result_t *r);

#endif /* DETECTOR_H */
