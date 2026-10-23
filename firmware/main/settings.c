/*
 * settings.c keeps the dose schedule and the tone setting in the chip's
 * settings store. settings.h describes the keys and the defaults.
 */

#include "settings.h"

#include <stdint.h>
#include <string.h>

#include "esp_err.h"
#include "nvs.h"

#define NAMESPACE "tremor"
#define KEY_SCHEDULE "schedule"
#define KEY_TONE "tone"
/* The version byte at the start of the schedule blob. */
#define SCHEDULE_VERSION 1

/* The schedule blob is the version byte and then the schedule's bytes. */
#define SCHEDULE_BLOB_SIZE (1 + sizeof(dose_schedule_t))

static void fill_defaults(settings_t *out)
{
    memset(out, 0, sizeof *out);
    out->tone_on = true;
}

/* load_schedule() reads the schedule key. It gives SETTINGS_EMPTY when the key
 * does not exist. */
static settings_status_t load_schedule(nvs_handle_t h, dose_schedule_t *s)
{
    uint8_t blob[SCHEDULE_BLOB_SIZE];
    size_t size = sizeof blob;
    esp_err_t err = nvs_get_blob(h, KEY_SCHEDULE, blob, &size);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return SETTINGS_EMPTY;
    }
    if (err != ESP_OK || size != sizeof blob || blob[0] != SCHEDULE_VERSION) {
        return SETTINGS_ERROR;
    }
    memcpy(s, blob + 1, sizeof *s);
    return SETTINGS_OK;
}

/* load_tone() reads the tone key. It gives SETTINGS_EMPTY when the key does
 * not exist. */
static settings_status_t load_tone(nvs_handle_t h, bool *on)
{
    uint8_t value = 0;
    esp_err_t err = nvs_get_u8(h, KEY_TONE, &value);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return SETTINGS_EMPTY;
    }
    if (err != ESP_OK || value > 1) {
        return SETTINGS_ERROR;
    }
    *on = value == 1;
    return SETTINGS_OK;
}

settings_status_t settings_load(settings_t *out)
{
    fill_defaults(out);
    nvs_handle_t h;
    esp_err_t err = nvs_open(NAMESPACE, NVS_READONLY, &h);
    if (err == ESP_ERR_NVS_NOT_FOUND) {
        return SETTINGS_EMPTY;
    }
    if (err != ESP_OK) {
        return SETTINGS_ERROR;
    }
    dose_schedule_t schedule;
    settings_status_t from_schedule = load_schedule(h, &schedule);
    if (from_schedule == SETTINGS_OK) {
        out->schedule = schedule;
    }
    settings_status_t from_tone = load_tone(h, &out->tone_on);
    nvs_close(h);
    if (from_schedule == SETTINGS_ERROR || from_tone == SETTINGS_ERROR) {
        return SETTINGS_ERROR;
    }
    if (from_schedule == SETTINGS_EMPTY && from_tone == SETTINGS_EMPTY) {
        return SETTINGS_EMPTY;
    }
    return SETTINGS_OK;
}

bool settings_save_schedule(const dose_schedule_t *s)
{
    uint8_t blob[SCHEDULE_BLOB_SIZE];
    blob[0] = SCHEDULE_VERSION;
    memcpy(blob + 1, s, sizeof *s);
    nvs_handle_t h;
    if (nvs_open(NAMESPACE, NVS_READWRITE, &h) != ESP_OK) {
        return false;
    }
    esp_err_t err = nvs_set_blob(h, KEY_SCHEDULE, blob, sizeof blob);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err == ESP_OK;
}

bool settings_save_tone(bool on)
{
    nvs_handle_t h;
    if (nvs_open(NAMESPACE, NVS_READWRITE, &h) != ESP_OK) {
        return false;
    }
    esp_err_t err = nvs_set_u8(h, KEY_TONE, on ? 1 : 0);
    if (err == ESP_OK) {
        err = nvs_commit(h);
    }
    nvs_close(h);
    return err == ESP_OK;
}
