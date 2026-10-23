/*
 * face.h holds the face state and the two-in-a-row rule.
 *
 * The rule follows the plan's Response time section. The face changes only
 * when two answers in a row agree, so a single odd answer never shows. The
 * rule changes only what the face shows, and every answer still goes into the
 * share and the recording unchanged.
 *
 * The face states follow the plan's Watch face section, under The state
 * circle. Waiting shows while the watch warms up or when the sensor has
 * failed. Dose due takes over the circle while a dose is due, and then the
 * detector state returns. The numbers are fixed, and the F line of the
 * recording writes them.
 *
 * The caller owns the state. The file has no static data that changes. On the
 * watch the state task owns the face.
 */

#ifndef FACE_H
#define FACE_H

#include <stdbool.h>
#include <stdint.h>

#include "window.h"

typedef enum {
    FACE_TREMOR = 0,
    FACE_NO_TREMOR = 1,
    FACE_ARM_MOVING = 2,
    FACE_WAITING = 3,
    FACE_DOSE_DUE = 4
} face_state_t;

typedef struct {
    /* The state that the answers give through the two-in-a-row rule. */
    face_state_t detector;
    /* The state of the answer before, when has_before is true. */
    bool has_before;
    face_state_t before;
    /* dose_due is true while a dose is due. */
    bool dose_due;
    /* The time of the latest tremor answer after which the detector state is
     * Tremor, when has_last_tremor is true. */
    bool has_last_tremor;
    int64_t last_tremor_us;
} face_t;

/* face_init() sets Waiting with no answer before, no dose due, and no last
 * tremor time. */
void face_init(face_t *f);

/* face_from_code() maps tremor, no tremor, and arm moving to the state of the
 * same name, and warming up, sensor fault, and any other value to Waiting. */
face_state_t face_from_code(res_code_t code);

/* face_answer() takes one answer at time_us. The detector state takes the
 * answer's state when the answer before maps to the same state. It returns
 * true when the shown state changes. */
bool face_answer(face_t *f, res_code_t code, int64_t time_us);

/* face_set_dose_due() sets the dose due flag. It returns true when the shown
 * state changes. */
bool face_set_dose_due(face_t *f, bool due);

/* face_shown() gives Dose due while a dose is due and the detector state
 * otherwise. */
face_state_t face_shown(const face_t *f);

/* face_detector() gives the detector state. */
face_state_t face_detector(const face_t *f);

/* face_last_tremor() gives the last tremor time. It returns false when there
 * is none. */
bool face_last_tremor(const face_t *f, int64_t *time_us);

/* face_name() gives the name of a state, or "unknown" for any other value. */
const char *face_name(face_state_t s);

#endif /* FACE_H */
