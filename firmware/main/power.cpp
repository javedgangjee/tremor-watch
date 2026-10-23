/*
 * power.cpp reaches the AXP2101 power chip at address 0x34 through
 * XPowersLib's register callbacks. The chip sits on the board support
 * package's I2C bus, which it shares with the touch chip, the IMU, and the
 * clock chip. ESP-IDF's I2C driver handles the sharing.
 */

#include "power.h"

#include <cstring>

#include "bsp/esp-bsp.h"
#include "driver/i2c_master.h"

#define XPOWERS_CHIP_AXP2101
#include "XPowersLib.h"

namespace {

constexpr uint16_t AXP2101_ADDRESS = 0x34;
constexpr uint32_t AXP2101_SPEED_HZ = 400000;
constexpr int I2C_TIMEOUT_MS = 100;

i2c_master_dev_handle_t pmu_device = nullptr;
esp_err_t pmu_error = ESP_OK;
XPowersPMU pmu;

int register_read(uint8_t, uint8_t reg, uint8_t *data, uint8_t len)
{
    if (pmu_device == nullptr || data == nullptr || len == 0) {
        pmu_error = ESP_ERR_INVALID_STATE;
        return -1;
    }
    esp_err_t err = i2c_master_transmit_receive(pmu_device, &reg, 1, data, len, I2C_TIMEOUT_MS);
    if (err != ESP_OK) {
        pmu_error = err;
        return -1;
    }
    return 0;
}

int register_write(uint8_t, uint8_t reg, uint8_t *data, uint8_t len)
{
    if (pmu_device == nullptr || data == nullptr || len == 0) {
        pmu_error = ESP_ERR_INVALID_STATE;
        return -1;
    }
    uint8_t buffer[UINT8_MAX + 1];
    buffer[0] = reg;
    std::memcpy(buffer + 1, data, len);
    esp_err_t err = i2c_master_transmit(pmu_device, buffer, static_cast<size_t>(len) + 1, I2C_TIMEOUT_MS);
    if (err != ESP_OK) {
        pmu_error = err;
        return -1;
    }
    return 0;
}

}  // namespace

extern "C" esp_err_t power_init(void)
{
    if (pmu_device != nullptr) {
        return ESP_OK;
    }
    i2c_master_bus_handle_t bus = bsp_i2c_get_handle();
    if (bus == nullptr) {
        return ESP_ERR_INVALID_STATE;
    }
    i2c_device_config_t config = {};
    config.dev_addr_length = I2C_ADDR_BIT_LEN_7;
    config.device_address = AXP2101_ADDRESS;
    config.scl_speed_hz = AXP2101_SPEED_HZ;
    esp_err_t err = i2c_master_bus_add_device(bus, &config, &pmu_device);
    if (err != ESP_OK) {
        pmu_device = nullptr;
        return err;
    }
    pmu_error = ESP_OK;
    if (!pmu.begin(AXP2101_ADDRESS, register_read, register_write)) {
        err = pmu_error;
        i2c_master_bus_rm_device(pmu_device);
        pmu_device = nullptr;
        return err == ESP_OK ? ESP_ERR_NOT_FOUND : err;
    }
    return ESP_OK;
}

extern "C" esp_err_t power_read(power_info_t *out)
{
    if (pmu_device == nullptr || out == nullptr) {
        return ESP_ERR_INVALID_STATE;
    }
    pmu_error = ESP_OK;
    out->vbus_in = pmu.isVbusIn();
    out->battery_in = pmu.isBatteryConnect();
    out->battery_mv = pmu.getBattVoltage();
    out->battery_percent = pmu.getBatteryPercent();
    return pmu_error;
}
