/*
 * settings.h keeps the dose schedule and the tone setting in the chip's
 * settings store, so they survive a restart. The store is ESP-IDF's NVS in the
 * nvs partition, and settings.c is the only file that writes it. main.c starts
 * the store before any task runs, and the state task calls these functions.
 *
 * The namespace is "tremor". The key "schedule" holds a blob of one version
 * byte, which is 1, and a dose_schedule_t. The key "tone" holds one byte, 0 or
 * 1. With nothing stored, the schedule is off with an empty name and the tone
 * is on.
 */

#ifndef SETTINGS_H
#define SETTINGS_H

#include <stdbool.h>

#include "dose.h"

typedef struct {
    dose_schedule_t schedule;
    bool tone_on;
} settings_t;

typedef enum {
    /* At least one key was stored, and every stored key was good. */
    SETTINGS_OK,
    /* No key was stored. */
    SETTINGS_EMPTY,
    /* The store failed or held a bad value. The bad value's default stays. */
    SETTINGS_ERROR
} settings_status_t;

/* settings_load() fills the defaults and then reads each key that exists. */
settings_status_t settings_load(settings_t *out);

/* settings_save_schedule() writes the schedule and commits it. It returns
 * false on any error. */
bool settings_save_schedule(const dose_schedule_t *s);

/* settings_save_tone() writes the tone setting and commits it. It returns
 * false on any error. */
bool settings_save_tone(bool on);

#endif /* SETTINGS_H */
