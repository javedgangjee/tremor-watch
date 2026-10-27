/*
 * Rate program. It sets the QMI8658 to output rate code 0x06 with the
 * gyroscope and the accelerometer on, which the datasheet gives as 112.1
 * readings a second. It then counts readings with the sensor's own reading
 * counter and times them with the 64-bit microsecond timer. It prints one line
 * a minute for 20 minutes, then a summary line. The screen stays on and shows
 * the rate.
 */
#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "esp_err.h"
#include "esp_timer.h"
#include "bsp/esp-bsp.h"
#include "lvgl.h"
#include "qmi8658.h"

#define SKIP_US       (2LL * 1000000LL)
#define MINUTE_US     (60LL * 1000000LL)
#define MINUTES       20
#define DRIFT_SPAN    5
#define NOMINAL_HZ    112.1
#define PASS_FRACTION 0.02
#define COUNTER_MASK  0xFFFFFFu

typedef struct {
    int64_t t_us;
    uint64_t count;
} mark_t;

static qmi8658_dev_t s_imu;
static lv_obj_t *s_rate_label;
static lv_obj_t *s_note_label;

static double rate_between(const mark_t *a, const mark_t *b)
{
    return (double)(b->count - a->count) * 1e6 / (double)(b->t_us - a->t_us);
}

static void show(const char *rate_text, const char *note_text)
{
    if (bsp_display_lock(0)) {
        lv_label_set_text(s_rate_label, rate_text);
        lv_label_set_text(s_note_label, note_text);
        bsp_display_unlock();
    }
}

static void build_screen(void)
{
    bsp_display_lock(0);
    lv_obj_t *scr = lv_screen_active();

    s_rate_label = lv_label_create(scr);
    lv_obj_set_style_text_font(s_rate_label, &lv_font_montserrat_48, 0);
    lv_obj_align(s_rate_label, LV_ALIGN_CENTER, 0, -40);

    s_note_label = lv_label_create(scr);
    lv_obj_set_width(s_note_label, 380);
    lv_obj_set_style_text_font(s_note_label, &lv_font_montserrat_28, 0);
    lv_obj_set_style_text_align(s_note_label, LV_TEXT_ALIGN_CENTER, 0);
    lv_obj_align(s_note_label, LV_ALIGN_CENTER, 0, 50);

    bsp_display_unlock();
    show("Measuring", "first minute");
}

/*
 * Reads the 24-bit reading counter. The counter can change during a read,
 * so the function reads it twice and keeps the value only when both agree.
 */
static esp_err_t read_counter(uint32_t *out)
{
    uint8_t a[3];
    uint8_t b[3];
    for (int tries = 0; tries < 5; tries++) {
        esp_err_t err = qmi8658_read_register(&s_imu, QMI8658_TIMESTAMP_L, a, 3);
        if (err != ESP_OK) {
            return err;
        }
        err = qmi8658_read_register(&s_imu, QMI8658_TIMESTAMP_L, b, 3);
        if (err != ESP_OK) {
            return err;
        }
        if (a[0] == b[0] && a[1] == b[1] && a[2] == b[2]) {
            *out = (uint32_t)a[0] | ((uint32_t)a[1] << 8) | ((uint32_t)a[2] << 16);
            return ESP_OK;
        }
    }
    return ESP_ERR_INVALID_STATE;
}

static void setup_imu(void)
{
    ESP_ERROR_CHECK(qmi8658_init(&s_imu, bsp_i2c_get_handle(), QMI8658_ADDRESS_HIGH));
    ESP_ERROR_CHECK(qmi8658_enable_sensors(&s_imu, QMI8658_DISABLE_ALL));

    /* The driver's range calls also write a rate code, so the rate is set last. */
    ESP_ERROR_CHECK(qmi8658_set_accel_range(&s_imu, QMI8658_ACCEL_RANGE_8G));
    ESP_ERROR_CHECK(qmi8658_set_gyro_range(&s_imu, QMI8658_GYRO_RANGE_1024DPS));
    ESP_ERROR_CHECK(qmi8658_set_accel_odr(&s_imu, QMI8658_ACCEL_ODR_125HZ));
    ESP_ERROR_CHECK(qmi8658_set_gyro_odr(&s_imu, QMI8658_GYRO_ODR_125HZ));
    ESP_ERROR_CHECK(qmi8658_enable_sensors(&s_imu, QMI8658_ENABLE_ACCEL | QMI8658_ENABLE_GYRO));

    uint8_t ctrl2 = 0;
    uint8_t ctrl3 = 0;
    uint8_t ctrl7 = 0;
    ESP_ERROR_CHECK(qmi8658_read_register(&s_imu, QMI8658_CTRL2, &ctrl2, 1));
    ESP_ERROR_CHECK(qmi8658_read_register(&s_imu, QMI8658_CTRL3, &ctrl3, 1));
    ESP_ERROR_CHECK(qmi8658_read_register(&s_imu, QMI8658_CTRL7, &ctrl7, 1));

    unsigned gyro_range_dps = 16u << ((ctrl3 >> 4) & 0x07);
    printf("SETTINGS ctrl2=0x%02X ctrl3=0x%02X ctrl7=0x%02X\n", ctrl2, ctrl3, ctrl7);
    printf("SETTINGS accel_on=%d gyro_on=%d accel_rate_code=0x%02X gyro_rate_code=0x%02X "
           "gyro_range=+/-%u dps\n",
           ctrl7 & 0x01, (ctrl7 >> 1) & 0x01, ctrl2 & 0x0F, ctrl3 & 0x0F, gyro_range_dps);
}

static void print_summary(const mark_t *marks, const double *minute_hz, uint32_t big_steps,
                          uint32_t max_step, uint32_t read_errors)
{
    double lowest = minute_hz[1];
    double highest = minute_hz[1];
    for (int m = 2; m <= MINUTES; m++) {
        if (minute_hz[m] < lowest) {
            lowest = minute_hz[m];
        }
        if (minute_hz[m] > highest) {
            highest = minute_hz[m];
        }
    }
    double full = rate_between(&marks[0], &marks[MINUTES]);
    double first = rate_between(&marks[0], &marks[DRIFT_SPAN]);
    double last = rate_between(&marks[MINUTES - DRIFT_SPAN], &marks[MINUTES]);
    double drift_ppm = (last - first) / first * 1e6;
    double offset = (full - NOMINAL_HZ) / NOMINAL_HZ;
    bool within = offset <= PASS_FRACTION && offset >= -PASS_FRACTION;

    printf("SUMMARY rate_20min_hz=%.4f lowest_1min_hz=%.4f highest_1min_hz=%.4f "
           "first5_hz=%.4f last5_hz=%.4f drift_ppm=%+.1f within_2_percent=%s\n",
           full, lowest, highest, first, last, drift_ppm, within ? "yes" : "no");
    printf("COUNTER steps_over_one=%" PRIu32 " largest_step=%" PRIu32 " read_errors=%" PRIu32 "\n",
           big_steps, max_step, read_errors);

    char rate_text[32];
    char note_text[64];
    snprintf(rate_text, sizeof rate_text, "%.4f Hz", minute_hz[MINUTES]);
    snprintf(note_text, sizeof note_text, "minute %d of %d\n20 min %.4f Hz", MINUTES, MINUTES, full);
    show(rate_text, note_text);
}

static void rate_task(void *arg)
{
    (void)arg;
    mark_t marks[MINUTES + 1];
    double minute_hz[MINUTES + 1] = {0};
    uint64_t count = 0;
    uint32_t big_steps = 0;
    uint32_t max_step = 0;
    uint32_t read_errors = 0;

    uint32_t last_raw = 0;
    while (read_counter(&last_raw) != ESP_OK) {
        read_errors++;
        vTaskDelay(1);
    }

    int next = 0;
    int64_t next_due = esp_timer_get_time() + SKIP_US;
    TickType_t wake = xTaskGetTickCount();

    while (next <= MINUTES) {
        xTaskDelayUntil(&wake, 1);

        uint32_t raw = 0;
        if (read_counter(&raw) != ESP_OK) {
            read_errors++;
            continue;
        }
        int64_t now = esp_timer_get_time();
        if (raw == last_raw) {
            continue;
        }

        uint32_t step = (raw - last_raw) & COUNTER_MASK;
        last_raw = raw;
        count += step;
        if (step > 1) {
            big_steps++;
            if (step > max_step) {
                max_step = step;
            }
        }

        if (now < next_due) {
            continue;
        }
        marks[next] = (mark_t){.t_us = now, .count = count};

        if (next == 0) {
            printf("START t_us=%" PRId64 " count=%" PRIu64 "\n", now, count);
        } else {
            minute_hz[next] = rate_between(&marks[next - 1], &marks[next]);
            double since_start = rate_between(&marks[0], &marks[next]);
            printf("MINUTE %02d one_minute_hz=%.4f since_start_hz=%.4f\n", next, minute_hz[next],
                   since_start);

            char rate_text[32];
            char note_text[64];
            snprintf(rate_text, sizeof rate_text, "%.4f Hz", minute_hz[next]);
            snprintf(note_text, sizeof note_text, "minute %d of %d", next, MINUTES);
            show(rate_text, note_text);
        }

        next++;
        next_due = marks[0].t_us + (int64_t)next * MINUTE_US;
    }

    print_summary(marks, minute_hz, big_steps, max_step, read_errors);
    vTaskDelete(NULL);
}

void app_main(void)
{
    if (bsp_display_start() == NULL) {
        printf("ERROR display did not start\n");
        return;
    }
    build_screen();
    setup_imu();
    xTaskCreatePinnedToCore(rate_task, "rate", 4096, NULL, 10, NULL, 1);
}
