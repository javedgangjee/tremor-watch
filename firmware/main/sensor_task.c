/*
 * sensor_task.c reads the QMI8658 into timed stretches.
 *
 * The sensor runs rate code 0x06 with the gyroscope and the accelerometer on,
 * and the gyroscope range is plus or minus 1024 degrees a second. Its buffer
 * raises a watermark interrupt on INT1, which the board wires to GPIO21, when
 * it holds 11 readings. The interrupt handler stamps the burst with the 64-bit
 * microsecond timer. The task then reads the buffer, gives the burst to the
 * time rule in core/reading_time.c, and sends the readings to the pipeline
 * task.
 *
 * The register details come from SensorLib's SensorQMI8658.hpp in Waveshare's
 * Arduino libraries. The SENSOR_SETUP line reads them back on the watch.
 *
 * A burst cannot be trusted when the buffer overflowed or filled, when a bus
 * read fails, when no interrupt comes for 1 second, or when INT1 is still high
 * 1 millisecond after a read. The task then drops the burst's readings, resets the buffer,
 * and gives no numbers to the dropped readings. The next good burst carries
 * the overflow flag, so every loss ends a stretch exactly once.
 */

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/gpio.h"
#include "esp_attr.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"
#include "freertos/task.h"

#include "bsp/esp-bsp.h"
#include "imu_units.h"
#include "qmi8658.h"
#include "reading_time.h"
#include "tasks.h"

/* The board wires the sensor's INT1 pin to this GPIO. */
#define INT1_GPIO GPIO_NUM_21

/* Registers from SensorLib's QMI8658Constants.h. */
#define REG_FIFO_WTM_TH 0x13
#define REG_FIFO_CTRL 0x14
#define REG_FIFO_COUNT 0x15
#define REG_FIFO_STATUS 0x16
#define REG_FIFO_DATA 0x17
#define REG_STATUS_INT 0x2D
#define REG_RST_RESULT 0x4D
#define REG_RESET 0x60

/* Writing RESET_VALUE to REG_RESET resets the sensor, and REG_RST_RESULT
 * reads RST_RESULT_DONE when the reset is done, as in SensorLib's reset(). */
#define RESET_VALUE 0xB0
#define RST_RESULT_DONE 0x80
#define RESET_TRIES 50
/* qmi8658_init() writes this value to CTRL1, which turns on the address
 * increment. */
#define CTRL1_AFTER_INIT 0x60

/* CTRL9 commands from SensorLib's SensorQMI8658.hpp. */
#define CMD_ACK 0x00
#define CMD_RST_FIFO 0x04
#define CMD_REQ_FIFO 0x05

/* CTRL8 bit 7 makes STATUS_INT bit 7 the CTRL9 handshake, as SensorLib's
 * setup does. Without it the sensor uses INT1 for the handshake. */
#define CTRL8_HANDSHAKE_STATUSINT 0x80
/* CTRL1 bit 3 turns INT1 on, and bit 2 sends the buffer interrupt to INT1. */
#define CTRL1_INT1_ON 0x08
#define CTRL1_FIFO_ON_INT1 0x04
/* FIFO_CTRL holds 128 readings (3 << 2) in FIFO mode (1). */
#define FIFO_CTRL_VALUE 0x0D
/* FIFO_STATUS bits. */
#define FIFO_STATUS_OVERFLOW 0x20
#define FIFO_STATUS_FULL 0x80
/* STATUS_INT bit 7 shows that a CTRL9 command is done. */
#define STATUS_INT_CMD_DONE 0x80

/* The buffer raises its interrupt when it holds this many readings. */
#define FIFO_WTM 11
/* The buffer holds at most this many readings. */
#define FIFO_READINGS 128
/* One reading is the accelerometer x, y, and z and then the gyroscope x, y,
 * and z, each a little-endian 16-bit count. */
#define READING_BYTES 12
/* qmi8658_read_register() takes a uint8_t length, so the buffer is read in
 * parts of at most 240 bytes, which is 20 readings. */
#define READ_PART_BYTES 240

/* After a read, INT1 must drop within this many microseconds. */
#define INT1_SETTLE_US 1000
/* The stamp queue holds this many stamps. */
#define STAMP_QUEUE_LEN 8
/* With no interrupt for this long, the task counts a stall. */
#define STALL_MS 1000
/* A CTRL9 command waits at most this long for each handshake step. */
#define CMD_TIMEOUT_US 100000

typedef enum {
    LOSS_NONE,
    LOSS_OVERFLOW,
    LOSS_FULL,
    LOSS_READ_ERROR,
    LOSS_STALL,
    LOSS_LATE,
    LOSS_PIPELINE,
    LOSS_KINDS
} loss_t;

/* The reason names on the STRETCH line. A stretch end with no loss comes
 * from the time rule alone. A pipeline end comes when the pipeline task lost
 * readings and asked through the end queue. */
static const char *const LOSS_NAMES[LOSS_KINDS] = {"time", "overflow", "full", "read_error", "stall", "late",
                                                   "pipeline"};

typedef struct {
    uint64_t readings;
    uint32_t bursts;
    uint32_t bursts_at_wtm;
    uint32_t largest_burst;
    uint32_t losses[LOSS_KINDS];
    uint32_t msg_drops;
    uint32_t record_drops;
    int64_t largest_delay_us;
    uint32_t kind1_ends;
    uint32_t kind2_ends;
} sensor_counts_t;

static qmi8658_dev_t s_imu;
static QueueHandle_t s_stamps;
static uint8_t s_fifo[FIFO_READINGS * READING_BYTES];
static rt_state_t s_rt;
static sensor_msg_t s_msg;
static record_msg_t s_record;
static sensor_counts_t s_counts;
/* The number of the next reading, counted from power-on. */
static uint64_t s_next_reading;

static void IRAM_ATTR on_int1(void *arg)
{
    (void)arg;
    int64_t now = esp_timer_get_time();
    BaseType_t woken = pdFALSE;
    xQueueSendFromISR(s_stamps, &now, &woken);
    if (woken == pdTRUE) {
        portYIELD_FROM_ISR();
    }
}

static esp_err_t write_reg(uint8_t reg, uint8_t value)
{
    return qmi8658_write_register(&s_imu, reg, value);
}

static esp_err_t read_reg(uint8_t reg, uint8_t *value)
{
    return qmi8658_read_register(&s_imu, reg, value, 1);
}

/* wait_cmd_done() polls STATUS_INT until bit 7 equals done. */
static esp_err_t wait_cmd_done(bool done)
{
    int64_t start = esp_timer_get_time();
    for (;;) {
        uint8_t status = 0;
        esp_err_t err = read_reg(REG_STATUS_INT, &status);
        if (err != ESP_OK) {
            return err;
        }
        if (((status & STATUS_INT_CMD_DONE) != 0) == done) {
            return ESP_OK;
        }
        if (esp_timer_get_time() - start > CMD_TIMEOUT_US) {
            return ESP_ERR_TIMEOUT;
        }
    }
}

/* write_command() sends one CTRL9 command with the acknowledge step of
 * SensorLib's writeCommand(). */
static esp_err_t write_command(uint8_t cmd)
{
    esp_err_t err = write_reg(QMI8658_CTRL9, cmd);
    if (err == ESP_OK) {
        err = wait_cmd_done(true);
    }
    if (err == ESP_OK) {
        err = write_reg(QMI8658_CTRL9, CMD_ACK);
    }
    if (err == ESP_OK) {
        err = wait_cmd_done(false);
    }
    return err;
}

/* soft_reset() resets the sensor as SensorLib's reset() does. The sensor keeps
 * its settings when the ESP32-S3 restarts, and its CTRL9 commands did not
 * answer on the watch until it was reset. The reset clears CTRL1, so the
 * function writes the value that qmi8658_init() writes. */
static esp_err_t soft_reset(void)
{
    esp_err_t err = write_reg(REG_RESET, RESET_VALUE);
    if (err != ESP_OK) {
        return err;
    }
    for (int tries = 0; tries < RESET_TRIES; tries++) {
        vTaskDelay(pdMS_TO_TICKS(10));
        uint8_t result = 0;
        if (read_reg(REG_RST_RESULT, &result) == ESP_OK && result == RST_RESULT_DONE) {
            return write_reg(QMI8658_CTRL1, CTRL1_AFTER_INIT);
        }
    }
    return ESP_ERR_TIMEOUT;
}

/* setup_imu() sets the sensor up as firmware/bringup/main/main.c does, with
 * the rate code set last. */
static esp_err_t setup_imu(void)
{
    esp_err_t err = qmi8658_init(&s_imu, bsp_i2c_get_handle(), QMI8658_ADDRESS_HIGH);
    if (err == ESP_OK) {
        err = soft_reset();
    }
    if (err == ESP_OK) {
        err = qmi8658_enable_sensors(&s_imu, QMI8658_DISABLE_ALL);
    }
    /* The driver's range calls also write a rate code, so the rate is set last. */
    if (err == ESP_OK) {
        err = qmi8658_set_accel_range(&s_imu, QMI8658_ACCEL_RANGE_8G);
    }
    if (err == ESP_OK) {
        err = qmi8658_set_gyro_range(&s_imu, QMI8658_GYRO_RANGE_1024DPS);
    }
    if (err == ESP_OK) {
        err = qmi8658_set_accel_odr(&s_imu, QMI8658_ACCEL_ODR_125HZ);
    }
    if (err == ESP_OK) {
        err = qmi8658_set_gyro_odr(&s_imu, QMI8658_GYRO_ODR_125HZ);
    }
    if (err == ESP_OK) {
        err = qmi8658_enable_sensors(&s_imu, QMI8658_ENABLE_ACCEL | QMI8658_ENABLE_GYRO);
    }
    return err;
}

/* setup_fifo() sets the buffer up as SensorLib's configFIFO() does. */
static esp_err_t setup_fifo(void)
{
    esp_err_t err = qmi8658_enable_sensors(&s_imu, QMI8658_DISABLE_ALL);
    if (err == ESP_OK) {
        err = write_reg(QMI8658_CTRL8, CTRL8_HANDSHAKE_STATUSINT);
    }
    if (err == ESP_OK) {
        err = write_command(CMD_RST_FIFO);
    }
    uint8_t ctrl1 = 0;
    if (err == ESP_OK) {
        err = read_reg(QMI8658_CTRL1, &ctrl1);
    }
    if (err == ESP_OK) {
        err = write_reg(QMI8658_CTRL1, ctrl1 | CTRL1_INT1_ON | CTRL1_FIFO_ON_INT1);
    }
    if (err == ESP_OK) {
        err = write_reg(REG_FIFO_CTRL, FIFO_CTRL_VALUE);
    }
    if (err == ESP_OK) {
        err = write_reg(REG_FIFO_WTM_TH, FIFO_WTM);
    }
    if (err == ESP_OK) {
        xQueueReset(s_stamps);
        err = qmi8658_enable_sensors(&s_imu, QMI8658_ENABLE_ACCEL | QMI8658_ENABLE_GYRO);
    }
    return err;
}

/* send_setup_line() reads the settings back and sends them. */
static void send_setup_line(void)
{
    uint8_t ctrl[3] = {0};
    uint8_t ctrl7 = 0;
    uint8_t fifo_ctrl = 0;
    uint8_t fifo_wtm = 0;
    esp_err_t err = qmi8658_read_register(&s_imu, QMI8658_CTRL1, ctrl, 3);
    if (err == ESP_OK) {
        err = read_reg(QMI8658_CTRL7, &ctrl7);
    }
    if (err == ESP_OK) {
        err = read_reg(REG_FIFO_CTRL, &fifo_ctrl);
    }
    if (err == ESP_OK) {
        err = read_reg(REG_FIFO_WTM_TH, &fifo_wtm);
    }
    if (err != ESP_OK) {
        usb_send("SENSOR_ERROR readback err=%s", esp_err_to_name(err));
        return;
    }
    unsigned gyro_range_dps = 16u << ((ctrl[2] >> 4) & 0x07);
    usb_send("SENSOR_SETUP ctrl1=0x%02X ctrl2=0x%02X ctrl3=0x%02X ctrl7=0x%02X fifo_ctrl=0x%02X fifo_wtm=%u "
             "gyro_range_dps=%u int1_level=%d",
             ctrl[0], ctrl[1], ctrl[2], ctrl7, fifo_ctrl, (unsigned)fifo_wtm, gyro_range_dps,
             gpio_get_level(INT1_GPIO));
    if (gyro_range_dps != IMU_GYRO_RANGE_DPS) {
        usb_send("SENSOR_ERROR range");
    }
}

static esp_err_t setup_int1(void)
{
    gpio_config_t config = {
        .pin_bit_mask = 1ULL << INT1_GPIO,
        .mode = GPIO_MODE_INPUT,
        .pull_up_en = GPIO_PULLUP_DISABLE,
        .pull_down_en = GPIO_PULLDOWN_DISABLE,
        .intr_type = GPIO_INTR_POSEDGE,
    };
    esp_err_t err = gpio_config(&config);
    if (err == ESP_OK) {
        err = gpio_isr_handler_add(INT1_GPIO, on_int1, NULL);
    }
    return err;
}

static int16_t le16(const uint8_t *p)
{
    return (int16_t)((uint16_t)p[0] | ((uint16_t)p[1] << 8));
}

/* read_burst() reads the buffer after a stamp. It gives the number of
 * readings in *count, and it returns the loss when the burst cannot be
 * trusted. */
static loss_t read_burst(uint32_t *count)
{
    *count = 0;
    uint8_t level[2] = {0};
    if (qmi8658_read_register(&s_imu, REG_FIFO_COUNT, level, 2) != ESP_OK) {
        return LOSS_READ_ERROR;
    }
    uint8_t status = level[1];
    if ((status & FIFO_STATUS_FULL) != 0) {
        return LOSS_FULL;
    }
    if ((status & FIFO_STATUS_OVERFLOW) != 0) {
        return LOSS_OVERFLOW;
    }
    uint32_t bytes = 2u * ((((uint32_t)status & 0x03u) << 8) | level[0]);
    if (bytes % READING_BYTES != 0 || bytes > sizeof s_fifo) {
        return LOSS_READ_ERROR;
    }
    if (write_command(CMD_REQ_FIFO) != ESP_OK) {
        return LOSS_READ_ERROR;
    }
    for (uint32_t done = 0; done < bytes;) {
        uint32_t part = bytes - done;
        if (part > READ_PART_BYTES) {
            part = READ_PART_BYTES;
        }
        if (qmi8658_read_register(&s_imu, REG_FIFO_DATA, s_fifo + done, (uint8_t)part) != ESP_OK) {
            return LOSS_READ_ERROR;
        }
        done += part;
    }
    if (write_reg(REG_FIFO_CTRL, FIFO_CTRL_VALUE) != ESP_OK) {
        return LOSS_READ_ERROR;
    }
    /* INT1 drops about 90 microseconds after the read ends, so the task
     * gives it up to INT1_SETTLE_US. */
    int64_t read_end = esp_timer_get_time();
    while (gpio_get_level(INT1_GPIO) != 0) {
        if (esp_timer_get_time() - read_end > INT1_SETTLE_US) {
            return LOSS_LATE;
        }
    }
    *count = bytes / READING_BYTES;
    return LOSS_NONE;
}

/* reset_fifo() empties the buffer after a loss, so the next stamp comes from
 * a clean rising edge. */
static void reset_fifo(void)
{
    write_command(CMD_RST_FIFO);
    write_reg(REG_FIFO_CTRL, FIFO_CTRL_VALUE);
    xQueueReset(s_stamps);
}


/* send_readings() sends the burst to the pipeline task in parts of at most
 * SENSOR_MSG_READINGS readings. Only the first part carries the flags. It
 * sends the USB task a copy of each part through the record queue, and it
 * waits on neither queue. */
static void send_readings(uint32_t count, unsigned flags, bool overflow, int64_t stamp_us, uint64_t first)
{
    const rt_stretch_t *st = rt_current(&s_rt);
    for (uint32_t done = 0; done < count;) {
        uint32_t part = count - done;
        if (part > SENSOR_MSG_READINGS) {
            part = SENSOR_MSG_READINGS;
        }
        s_msg.flags = done == 0 ? flags : 0u;
        s_msg.overflow = done == 0 ? overflow : false;
        s_msg.stretch = st->number;
        s_msg.rate_uhz = st->rate_uhz;
        s_msg.stamp_us = stamp_us;
        s_msg.first_reading = first + done;
        s_msg.count = part;
        for (uint32_t i = 0; i < part; i++) {
            const uint8_t *p = s_fifo + (size_t)(done + i) * READING_BYTES;
            for (int axis = 0; axis < 6; axis++) {
                s_msg.raw[i][axis] = le16(p + 2 * axis);
            }
            for (int axis = 0; axis < 3; axis++) {
                s_msg.gyro_dps[i][axis] = imu_gyro_dps(s_msg.raw[i][3 + axis]);
            }
        }
        if (xQueueSend(g_sensor_queue, &s_msg, 0) != pdTRUE) {
            s_counts.msg_drops++;
        }
        s_record.flags = s_msg.flags;
        s_record.first_part = done == 0;
        s_record.stretch = st->number;
        s_record.rate_uhz = st->rate_uhz;
        s_record.stamp_us = stamp_us;
        s_record.first_reading = first + done;
        s_record.count = part;
        s_record.burst_count = count;
        memcpy(s_record.raw, s_msg.raw, sizeof s_record.raw);
        if (xQueueSend(g_record_queue, &s_record, 0) != pdTRUE) {
            s_counts.record_drops++;
        }
        done += part;
    }
}

/* take_burst() gives a good burst its numbers and its time. */
static void take_burst(uint32_t count, int64_t stamp_us, bool overflow, loss_t reason)
{
    const rt_stretch_t *st = rt_current(&s_rt);
    uint64_t first = s_next_reading;
    bool skipped = s_rt.started && first != s_rt.last.first_reading + s_rt.last.count;
    uint32_t old_rate = s_rt.started ? st->rate_uhz : 0;
    double error_us = old_rate != 0 ? (double)stamp_us - rt_reading_time_us(st, first) : 0.0;

    unsigned flags = rt_burst(&s_rt, first, count, stamp_us, overflow);
    st = rt_current(&s_rt);

    if ((flags & RT_NEW_STRETCH) != 0 && st->number == 0) {
        usb_send("STRETCH number=0 first=%llu t0_us=%lld kind=start reason=start prev_span_us=0 prev_readings=0 "
                 "prev_rate_uhz=0 error_us=none",
                 (unsigned long long)st->first_reading, (long long)st->t0_us);
    } else if ((flags & RT_NEW_STRETCH) != 0) {
        bool kind1 = overflow || skipped;
        const char *why = overflow ? LOSS_NAMES[reason] : skipped ? "skip" : LOSS_NAMES[LOSS_NONE];
        if (kind1) {
            s_counts.kind1_ends++;
        } else {
            s_counts.kind2_ends++;
        }
        const rt_burst_t *a = &s_rt.before_first;
        const rt_burst_t *b = &s_rt.before_last;
        char error_text[24] = "none";
        if (!kind1 && old_rate != 0) {
            snprintf(error_text, sizeof error_text, "%.1f", error_us);
        }
        usb_send("STRETCH number=%lu first=%llu t0_us=%lld kind=%d reason=%s prev_span_us=%lld prev_readings=%llu "
                 "prev_rate_uhz=%lu error_us=%s",
                 (unsigned long)st->number, (unsigned long long)st->first_reading, (long long)st->t0_us,
                 kind1 ? 1 : 2, why, (long long)(b->stamp_us - a->stamp_us),
                 (unsigned long long)(b->first_reading + b->count - a->first_reading), (unsigned long)old_rate,
                 error_text);
    }
    if ((flags & RT_RATE_SET) != 0) {
        usb_send("RATE number=%lu rate_uhz=%lu", (unsigned long)st->number, (unsigned long)st->rate_uhz);
    }

    send_readings(count, flags, overflow, stamp_us, first);

    s_next_reading += count;
    s_counts.readings += count;
    s_counts.bursts++;
    if (count == FIFO_WTM) {
        s_counts.bursts_at_wtm++;
    }
    if (count > s_counts.largest_burst) {
        s_counts.largest_burst = count;
    }
}

static void send_minute_line(uint32_t minute)
{
    const sensor_counts_t *c = &s_counts;
    uint32_t stretches = s_rt.started ? rt_current(&s_rt)->number + 1 : 0;
    usb_send("SENSOR_MINUTE minute=%lu readings=%llu bursts=%lu bursts_at_wtm=%lu largest_burst=%lu overflow=%lu "
             "full=%lu read_error=%lu stall=%lu late=%lu msg_drops=%lu largest_delay_us=%lld stretches=%lu "
             "kind1_ends=%lu kind2_ends=%lu pipeline=%lu record_drops=%lu",
             (unsigned long)minute, (unsigned long long)c->readings, (unsigned long)c->bursts,
             (unsigned long)c->bursts_at_wtm, (unsigned long)c->largest_burst,
             (unsigned long)c->losses[LOSS_OVERFLOW], (unsigned long)c->losses[LOSS_FULL],
             (unsigned long)c->losses[LOSS_READ_ERROR], (unsigned long)c->losses[LOSS_STALL],
             (unsigned long)c->losses[LOSS_LATE], (unsigned long)c->msg_drops, (long long)c->largest_delay_us,
             (unsigned long)stretches, (unsigned long)c->kind1_ends, (unsigned long)c->kind2_ends,
             (unsigned long)c->losses[LOSS_PIPELINE], (unsigned long)c->record_drops);
}

void sensor_task(void *arg)
{
    (void)arg;
    send_task_line("sensor");

    s_stamps = xQueueCreate(STAMP_QUEUE_LEN, sizeof(int64_t));
    esp_err_t err = s_stamps != NULL ? ESP_OK : ESP_ERR_NO_MEM;
    if (err == ESP_OK) {
        err = setup_int1();
    }
    if (err == ESP_OK) {
        err = setup_imu();
    }
    if (err == ESP_OK) {
        err = setup_fifo();
    }
    if (err != ESP_OK) {
        usb_send("SENSOR_ERROR setup err=%s", esp_err_to_name(err));
        vTaskDelete(NULL);
        return;
    }
    send_setup_line();
    rt_init(&s_rt);

    bool overflow = false;
    loss_t reason = LOSS_NONE;
    uint32_t minute = 1;
    for (;;) {
        int64_t stamp_us = 0;
        loss_t loss = LOSS_NONE;
        uint32_t count = 0;
        if (xQueueReceive(s_stamps, &stamp_us, pdMS_TO_TICKS(STALL_MS)) != pdTRUE) {
            loss = LOSS_STALL;
        } else {
            loss = read_burst(&count);
            int64_t delay_us = esp_timer_get_time() - stamp_us;
            if (delay_us > s_counts.largest_delay_us) {
                s_counts.largest_delay_us = delay_us;
            }
        }

        if (loss != LOSS_NONE) {
            s_counts.losses[loss]++;
            reset_fifo();
            overflow = true;
            reason = loss;
        } else if (count > 0) {
            /* The pipeline task asks to end a stretch when it lost readings.
             * The burst then carries the overflow flag, so the time rule ends
             * the stretch as it does after a lost burst. */
            uint32_t end_stretch = 0;
            if (xQueueReceive(g_end_queue, &end_stretch, 0) == pdTRUE && s_rt.started &&
                end_stretch == rt_current(&s_rt)->number && !overflow) {
                overflow = true;
                reason = LOSS_PIPELINE;
                s_counts.losses[LOSS_PIPELINE]++;
            }
            take_burst(count, stamp_us, overflow, reason);
            overflow = false;
            reason = LOSS_NONE;
        }

        if (esp_timer_get_time() >= (int64_t)minute * MINUTE_US) {
            send_minute_line(minute);
            minute++;
        }
    }
}
