/*
 * pipeline.h holds the pipeline task's rules for the stretches, the converter,
 * the windows, and the sensor fault answers.
 *
 * The pipeline task takes the sensor task's messages. Each message is one part
 * of a burst, and only the first part of a burst carries the time rule's
 * flags. pipe_part() takes the fields of one part before its readings,
 * pipe_push() takes each reading, and pipe_window() gives each complete window
 * with its number and the time of its last 100 Hz sample. The pipeline task
 * runs the detector on each window itself.
 *
 * A stretch drops when its readings no longer follow on, when its first part
 * is lost, or when the converter's ring is full. The pipe then asks once that
 * the sensor task end the stretch, and it drops every later part of the
 * stretch until the next new stretch.
 *
 * A sensor fault answer is due when no part has come for 2 seconds, and then
 * once a second until a part comes.
 *
 * The feature 8 requirements 20, 21, and 23 give the details. The caller owns
 * the state. The file has no static data that changes.
 */

#ifndef PIPELINE_H
#define PIPELINE_H

#include <stdbool.h>
#include <stdint.h>

#include "converter.h"
#include "reading_time.h"
#include "window.h"

/* A sensor fault answer is due this long after the last part. */
#define PIPE_FAULT_AFTER_US 2000000
/* After that, a sensor fault answer is due this often. */
#define PIPE_FAULT_EVERY_US 1000000

/* pipe_part() sets this flag when the part starts a new stretch. */
#define PIPE_STRETCH 1u
/* pipe_part() and pipe_push() set this flag when the stretch must end. */
#define PIPE_END 2u
/* pipe_part() sets this flag when the part's readings must not be pushed. */
#define PIPE_DROP 4u

/* The reasons for an end request. */
#define PIPE_REASON_NONE 0u
#define PIPE_REASON_BREAK 1u
#define PIPE_REASON_MISSED_START 2u
#define PIPE_REASON_RING_FULL 3u

typedef struct {
    /* The stretch number that the time rule gave the burst. */
    uint32_t stretch;
    /* The time rule's flags, which only the first part of a burst carries. */
    unsigned flags;
    /* The stretch's rate, or 0 when it is not known yet. */
    uint32_t rate_uhz;
    /* The burst's stamp in microseconds. */
    int64_t stamp_us;
    /* The number of the part's first reading, counted from power-on. */
    uint64_t first_reading;
    /* The number of readings in the part. */
    uint32_t count;
} pipe_part_t;

typedef struct {
    conv_t conv;
    win_t win;
    /* The current stretch. Its rate is 0 until the converter accepts one. */
    rt_stretch_t stretch;
    /* started is false until the first new stretch. */
    bool started;
    /* in_sync is true while the current stretch's parts follow on. */
    bool in_sync;
    /* rate_tried is true once the stretch has offered the converter a rate. */
    bool rate_tried;
    /* The number of the next reading that the stretch expects. */
    uint64_t next_reading;
    /* end_asked is true once an end request has been made. The reason and
     * the stretch number belong to the last request. */
    bool end_asked;
    unsigned end_reason;
    uint32_t end_stretch;
    /* The time of the last part and the time the next fault answer is due. */
    int64_t last_part_us;
    int64_t next_fault_us;
    /* One converter block. */
    float block[CONV_BLOCK_SAMPLES][CONV_AXES];
    /* The counts since pipe_init(). */
    uint32_t stretches;
    uint32_t end_requests;
    uint32_t rate_refused;
    uint32_t faults;
} pipe_t;

/* pipe_init() clears the pipe. The first fault answer is due at now_us plus
 * PIPE_FAULT_AFTER_US. */
void pipe_init(pipe_t *p, int64_t now_us);

/* pipe_part() takes one part before its readings and returns the flags. Every
 * part moves the next fault time to now_us plus PIPE_FAULT_AFTER_US. */
unsigned pipe_part(pipe_t *p, const pipe_part_t *m, int64_t now_us);

/* pipe_push() adds the stretch's next reading. It returns PIPE_END once when
 * the converter's ring is full, and 0 otherwise. Out of sync it does
 * nothing. */
unsigned pipe_push(pipe_t *p, const float reading[CONV_AXES]);

/* pipe_window() makes blocks until a window is complete or no block is left.
 * It returns true and writes the window, its number, and the time of its last
 * 100 Hz sample when a window is complete. Out of sync it returns false. */
bool pipe_window(pipe_t *p, float window[DET_WINDOW_LEN][DET_AXES], uint32_t *number, int64_t *time_us);

/* pipe_fault_due() returns true when now_us has reached the next fault time,
 * and it then moves the next fault time on by PIPE_FAULT_EVERY_US. */
bool pipe_fault_due(pipe_t *p, int64_t now_us);

/* pipe_next_fault_us() gives the time the next fault answer is due. */
int64_t pipe_next_fault_us(const pipe_t *p);

/* pipe_stretch() gives the current stretch. */
const rt_stretch_t *pipe_stretch(const pipe_t *p);

/* pipe_end_stretch() gives the stretch number of the last end request. */
uint32_t pipe_end_stretch(const pipe_t *p);

/* pipe_end_reason() gives the reason of the last end request, or
 * PIPE_REASON_NONE when there has been none. */
unsigned pipe_end_reason(const pipe_t *p);

#endif /* PIPELINE_H */
