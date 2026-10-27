/*
 * face.c holds the face state and the two-in-a-row rule. face.h describes
 * them, and the feature 6 requirements 28 and 29 give the details.
 */

#include "face.h"

void face_init(face_t *f)
{
    f->detector = FACE_WAITING;
    f->has_before = false;
    f->before = FACE_WAITING;
    f->dose_due = false;
    f->has_last_tremor = false;
    f->last_tremor_us = 0;
}

face_state_t face_from_code(res_code_t code)
{
    switch (code) {
    case RES_TREMOR:
        return FACE_TREMOR;
    case RES_NO_TREMOR:
        return FACE_NO_TREMOR;
    case RES_ARM_MOVING:
        return FACE_ARM_MOVING;
    default:
        return FACE_WAITING;
    }
}

bool face_answer(face_t *f, res_code_t code, int64_t time_us)
{
    face_state_t shown = face_shown(f);
    face_state_t state = face_from_code(code);
    if (f->has_before && f->before == state) {
        f->detector = state;
    }
    f->before = state;
    f->has_before = true;
    if (state == FACE_TREMOR && f->detector == FACE_TREMOR) {
        f->has_last_tremor = true;
        f->last_tremor_us = time_us;
    }
    return face_shown(f) != shown;
}

bool face_gap(face_t *f)
{
    face_state_t shown = face_shown(f);
    f->detector = FACE_WAITING;
    f->has_before = false;
    f->before = FACE_WAITING;
    return face_shown(f) != shown;
}

bool face_set_dose_due(face_t *f, bool due)
{
    face_state_t shown = face_shown(f);
    f->dose_due = due;
    return face_shown(f) != shown;
}

face_state_t face_shown(const face_t *f)
{
    return f->dose_due ? FACE_DOSE_DUE : f->detector;
}

face_state_t face_detector(const face_t *f)
{
    return f->detector;
}

bool face_last_tremor(const face_t *f, int64_t *time_us)
{
    if (!f->has_last_tremor) {
        return false;
    }
    *time_us = f->last_tremor_us;
    return true;
}

const char *face_name(face_state_t s)
{
    switch (s) {
    case FACE_TREMOR:
        return "Tremor Detected";
    case FACE_NO_TREMOR:
        return "Rest";
    case FACE_ARM_MOVING:
        return "Arm moving";
    case FACE_WAITING:
        return "Waiting";
    case FACE_DOSE_DUE:
        return "Dose due";
    default:
        return "unknown";
    }
}
