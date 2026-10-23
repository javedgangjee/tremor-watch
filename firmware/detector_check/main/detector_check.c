/*
 * detector_check.c runs the C detector on the saved windows on the chip.
 *
 * The program embeds tests/detector/windows.csv as 32-bit floats. A task on
 * core 1 at the pipeline task's priority checks the CRC-32 of the data, then
 * runs every window twice and prints each result. tests/firmware/chip_windows.py
 * judges the output on the laptop with the rule of tests/detector/test_detector.c.
 * The program has no USB task, so it prints with printf.
 */

#include <inttypes.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "esp_rom_crc.h"
#include "esp_timer.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

#include "detector.h"

#define WINDOWS 322
#define PASSES 2
#define WINDOW_BYTES (DET_WINDOW_LEN * DET_AXES * sizeof(float))
/* The task runs where the pipeline task runs, at the same priority. */
#define CHECK_CORE 1
#define CHECK_PRIORITY 8
#define CHECK_STACK 8192

extern const uint8_t windows_start[] asm("_binary_windows_bin_start");
extern const uint8_t windows_end[] asm("_binary_windows_bin_end");

/* Each window is copied here, so the detector reads aligned floats. */
static _Alignas(16) float s_window[DET_WINDOW_LEN][DET_AXES];

static void print_result(int pass, int window, int64_t run_us, const det_result_t *r)
{
    printf("CHECK_WINDOW pass=%d window=%d run_us=%" PRId64 " mfcc=", pass, window, run_us);
    for (int i = 0; i < DET_MFCC_COUNT; i++) {
        printf(i == 0 ? "%.9g" : ",%.9g", (double)r->mfcc[i]);
    }
    printf(" prob=%.17g below=%.17g peak=%.9g logreg=%d at_rest=%d tremor=%d\n", r->prob, r->below,
           (double)r->peak_hz, r->logreg ? 1 : 0, r->at_rest ? 1 : 0, r->tremor ? 1 : 0);
}

static void check_task(void *arg)
{
    (void)arg;
    static const uint8_t digits[] = "123456789";
    printf("CHECK_CRC value=0x%08" PRIx32 "\n", esp_rom_crc32_le(0, digits, 9));

    size_t bytes = (size_t)(windows_end - windows_start);
    printf("CHECK_START windows=%d bytes=%u crc32=0x%08" PRIx32 "\n", WINDOWS, (unsigned)bytes,
           esp_rom_crc32_le(0, windows_start, bytes));
    if (bytes != WINDOWS * WINDOW_BYTES || !det_init()) {
        printf("CHECK_ERROR bytes=%u\n", (unsigned)bytes);
        vTaskDelete(NULL);
        return;
    }

    int runs = 0;
    for (int pass = 1; pass <= PASSES; pass++) {
        for (int w = 0; w < WINDOWS; w++) {
            memcpy(s_window, windows_start + (size_t)w * WINDOW_BYTES, WINDOW_BYTES);
            det_result_t r;
            int64_t start_us = esp_timer_get_time();
            det_run(s_window, &r);
            int64_t run_us = esp_timer_get_time() - start_us;
            print_result(pass, w, run_us, &r);
            runs++;
            /* The idle task runs here and feeds the watchdog. */
            vTaskDelay(1);
        }
    }
    printf("CHECK_END runs=%d\n", runs);
    vTaskDelete(NULL);
}

void app_main(void)
{
    xTaskCreatePinnedToCore(check_task, "check", CHECK_STACK, NULL, CHECK_PRIORITY, NULL, CHECK_CORE);
}
