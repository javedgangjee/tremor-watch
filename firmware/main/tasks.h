/*
 * tasks.h holds the queue items, the queues, and the entry points of the five
 * tasks. Each part of the watch has one owning task, and the tasks talk
 * through these queues.
 *
 * The sensor task reads the IMU and sends readings to the pipeline task.
 * The pipeline task takes the readings. Feature 8 adds the converter and the
 * detector to it.
 * The state task sends the screen task what to draw.
 * The screen task owns LVGL, and no other task calls LVGL.
 * The USB task owns the serial port, and no other task writes to it.
 */

#ifndef TASKS_H
#define TASKS_H

#include <stdatomic.h>
#include <stdbool.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

/* A sensor message holds at most this many readings. */
#define SENSOR_MSG_READINGS 16
/* A text line holds at most this many characters before its end. */
#define LINE_CHARS 255
/* One minute of uptime in microseconds. */
#define MINUTE_US 60000000LL

/* The task priorities. The sensor task has the highest, and the USB task has
 * the lowest. */
#define SENSOR_PRIORITY 12
#define PIPELINE_PRIORITY 8
#define STATE_PRIORITY 6
#define SCREEN_PRIORITY 5
#define USB_PRIORITY 3

/*
 * sensor_msg_t carries one part of a burst from the sensor task to the
 * pipeline task. A burst of more than SENSOR_MSG_READINGS readings goes in
 * more than one message, and only the first part carries the flags.
 */
typedef struct {
    /* The flags that rt_burst() returned for the burst. */
    unsigned flags;
    /* overflow is true when the burst carried the overflow flag. */
    bool overflow;
    /* The stretch number and its rate after the rt_burst() call. */
    uint32_t stretch;
    uint32_t rate_uhz;
    /* The burst's stamp in microseconds. */
    int64_t stamp_us;
    /* The number of this part's first reading, counted from power-on. */
    uint64_t first_reading;
    /* The number of readings in this part. */
    uint32_t count;
    /* The raw counts of each reading. Axes 0 to 2 are the accelerometer x, y,
     * and z, and axes 3 to 5 are the gyroscope x, y, and z. */
    int16_t raw[SENSOR_MSG_READINGS][6];
    /* The gyroscope x, y, and z of each reading in degrees a second. */
    float gyro_dps[SENSOR_MSG_READINGS][3];
} sensor_msg_t;

/* line_t holds one text line for the USB task, with no newline. */
typedef struct {
    char text[LINE_CHARS + 1];
} line_t;

/* screen_msg_t tells the screen task what to draw. */
typedef struct {
    uint32_t uptime_s;
} screen_msg_t;

/* The queues. main.c makes them before any task starts. */
extern QueueHandle_t g_sensor_queue;
extern QueueHandle_t g_line_queue;
extern QueueHandle_t g_screen_queue;

/* The number of lines that the other tasks dropped since boot, because the
 * line queue was full. */
extern atomic_uint g_line_drops;

/*
 * usb_send() formats one line and puts it on the line queue with no wait.
 * It returns false and counts the drop when the queue is full.
 */
bool usb_send(const char *fmt, ...) __attribute__((format(__printf__, 1, 2)));

/* send_task_line() sends the TASK line of the calling task. */
void send_task_line(const char *name);

/* The task entry points. */
void sensor_task(void *arg);
void pipeline_task(void *arg);
void state_task(void *arg);
void screen_task(void *arg);
void usb_task(void *arg);

#endif /* TASKS_H */
