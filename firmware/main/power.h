/*
 * power.h gives C functions for the AXP2101 power chip. power.cpp reaches the
 * chip through XPowersLib on the board support package's I2C bus, as
 * Waveshare's factory example does. The functions do not change the charge
 * settings.
 */

#ifndef POWER_H
#define POWER_H

#include <stdbool.h>
#include <stdint.h>

#include "esp_err.h"

#ifdef __cplusplus
extern "C" {
#endif

typedef struct {
    /* vbus_in is true when USB power is in. */
    bool vbus_in;
    /* battery_in is true when a battery is in. */
    bool battery_in;
    /* The battery voltage in millivolts, or 0 when no battery is in. */
    uint16_t battery_mv;
    /* The battery percentage, or -1 when no battery is in. */
    int battery_percent;
} power_info_t;

/* power_init() adds the power chip to the I2C bus and checks its chip ID. */
esp_err_t power_init(void);

/* power_read() reads the power state into out. */
esp_err_t power_read(power_info_t *out);

#ifdef __cplusplus
}
#endif

#endif /* POWER_H */
