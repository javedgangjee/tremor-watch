/*
 * tasks.h holds the queue items, the queues, and the entry points of the five
 * tasks. Each part of the watch has one owning task, and the tasks talk
 * through these queues.
 *
 * The sensor task reads the IMU and sends readings to the pipeline task. It
 * also sends the USB task a copy of each burst part through the record queue.
 * The pipeline task runs the converter and the detector, and it sends each
 * new stretch and each answer to the state task. It asks the sensor task to
 * end a stretch through the end queue.
 * The state task owns the face state, the session share, the doses, and the
 * settings, and it sends the screen task the view to draw. It applies the
 * laptop's commands and the "Took it" taps.
 * The screen task owns LVGL and the audio codec, and no other task calls
 * LVGL. It sends each "Took it" tap to the state task.
 * The USB task owns the USB port, and no other task writes to it. It writes
 * the recording and reads the laptop's commands.
 * Each task joins the task watchdog before its main loop and checks in once a
 * round, so a task that is stuck for 5 seconds restarts the chip.
 */

#ifndef TASKS_H
#define TASKS_H

#include <stdatomic.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#include "freertos/FreeRTOS.h"
#include "freertos/queue.h"

#include "record.h"
#include "view.h"

/* The firmware version that the B line carries. */
#define FIRMWARE_VERSION 12

/* A sensor message holds at most this many readings. */
#define SENSOR_MSG_READINGS 16
/* A text line holds at most this many characters before its end. The longest
 * line is STATE_MINUTE, which reaches about 550 characters when every count
 * has 10 digits. usb_send() replaces a line that does not fit with a LINE_CUT
 * line and counts it in g_line_cuts. */
#define LINE_CHARS 639
#define MINUTE_US 60000000LL

/* FreeRTOS task priorities. Higher runs first. */
#define SENSOR_PRIORITY 12
#define PIPELINE_PRIORITY 8
#define STATE_PRIORITY 6
#define SCREEN_PRIORITY 5
#define USB_PRIORITY 3

/* The core each task is pinned to. */
#define SENSOR_CORE 1
#define PIPELINE_CORE 1
#define STATE_CORE 0
#define SCREEN_CORE 0
#define USB_CORE 0
/* The screen task pauses the scheduler to keep the state task from running
 * between its queue test and its SCREEN_VIEW line. On ESP-IDF that pause
 * holds only on the calling core, so both tasks must share one. */
_Static_assert(STATE_CORE == SCREEN_CORE, "the state task and the screen task must run on one core");

/*
 * sensor_msg_t carries one part of a burst from the sensor task to the
 * pipeline task. A burst of more than SENSOR_MSG_READINGS readings goes in
 * more than one message, and only the first part carries the flags.
 */
typedef struct {
    /* The flags that rt_burst() returned for the burst. */
    unsigned flags;
    /* The stretch number and its rate after the rt_burst() call. */
    uint32_t stretch;
    uint32_t rate_uhz;
    /* The burst's stamp in microseconds. */
    int64_t stamp_us;
    /* The number of this part's first reading, counted from power-on. */
    uint64_t first_reading;
    uint32_t count;
    /* The raw counts of each reading. Axes 0 to 2 are the accelerometer x, y,
     * and z, and axes 3 to 5 are the gyroscope x, y, and z. */
    int16_t raw[SENSOR_MSG_READINGS][6];
    /* The gyroscope x, y, and z of each reading in degrees a second. */
    float gyro_dps[SENSOR_MSG_READINGS][3];
} sensor_msg_t;

/*
 * record_msg_t carries a copy of one part of a burst from the sensor task to
 * the USB task, which writes the S, T, and R lines from it.
 */
typedef struct {
    /* The flags that rt_burst() returned for the burst. Only the first part
     * carries them. */
    unsigned flags;
    bool first_part;
    /* The stretch number and its rate after the rt_burst() call. */
    uint32_t stretch;
    uint32_t rate_uhz;
    /* The burst's stamp in microseconds. */
    int64_t stamp_us;
    /* The number of this part's first reading, counted from power-on. */
    uint64_t first_reading;
    /* The number of readings in this part and in the whole burst. */
    uint32_t count;
    uint32_t burst_count;
    /* The raw counts of each reading, in the axis order of sensor_msg_t. */
    int16_t raw[SENSOR_MSG_READINGS][6];
} record_msg_t;

/* line_t holds one text line for the USB task, with no newline. */
typedef struct {
    char text[LINE_CHARS + 1];
} line_t;

typedef enum {
    STATE_MSG_STRETCH,
    STATE_MSG_ANSWER,
    STATE_MSG_COMMAND,
    STATE_MSG_TOOK_IT
} state_msg_kind_t;

/*
 * state_msg_t carries a new stretch or an answer from the pipeline task to
 * the state task, a command from the USB task, or a "Took it" tap from the
 * screen task. A stretch message uses only kind, stretch, and rate_uhz. A
 * sensor fault answer has no window and no detector numbers. A command
 * message uses only kind, command, and at_us. A "Took it" message uses only
 * kind and at_us, which is the tap's timer value.
 */
typedef struct {
    state_msg_kind_t kind;
    /* The stretch number and the stretch's rate in millionths of a reading
     * per second, which is 0 while the stretch has no rate. */
    uint32_t stretch;
    uint32_t rate_uhz;
    bool has_window;
    uint32_t window;
    /* The result code, as a res_code_t from core/window.h. */
    uint8_t code;
    /* The detector's probability, low-frequency sum, and peak in Hz. */
    double prob;
    double below;
    float peak_hz;
    /* The time of the window's last 100 Hz sample, or the time a fault answer
     * became due. */
    int64_t time_us;
    /* The detector's run time. */
    int64_t run_us;
    /* The timer value at the end of the run. For a command message, the timer
     * value when the command's newline arrived. */
    int64_t at_us;
    /* The end of the run minus the stamp of the burst that completed the
     * window. */
    int64_t delay_us;
    /* The command of a command message. */
    rec_command_t command;
} state_msg_t;

/* The queues. main.c makes them before any task starts. The screen queue
 * carries view_t items from core/view.h and lives in PSRAM. The end queue holds
 * one stretch number, which the pipeline task writes with xQueueOverwrite()
 * when a stretch must end. The record queue carries record_msg_t items from
 * the sensor task to the USB task. */
extern QueueHandle_t g_sensor_queue;
extern QueueHandle_t g_line_queue;
extern QueueHandle_t g_screen_queue;
extern QueueHandle_t g_state_queue;
extern QueueHandle_t g_end_queue;
extern QueueHandle_t g_record_queue;

/* The number of lines that the other tasks dropped since boot, because the
 * line queue was full. */
extern atomic_uint g_line_drops;

/* The number of lines that did not fit their buffer since boot. Each one
 * went out as a LINE_CUT line or not at all, and USB_MINUTE gives the count. */
extern atomic_uint g_line_cuts;

/* line_made() takes the length that a rec_ line function in core/record.h
 * returned. A length of 0 means the line did not fit, and line_made() counts
 * it in g_line_cuts. It gives the length back. */
static inline size_t line_made(size_t len)
{
    if (len == 0) {
        atomic_fetch_add(&g_line_cuts, 1u);
    }
    return len;
}

/* g_recording_on is true while the last line that the USB task wrote fitted
 * in the port's send buffer. The USB task sets it. */
extern atomic_bool g_recording_on;

/* screen_took_it() sends a "Took it" tap at the timer value at_us to the
 * state task with no wait, and counts a drop. firmware/main/face_draw.c calls
 * it. */
void screen_took_it(int64_t at_us);

/*
 * usb_send() formats one line and places it on the line queue with no wait.
 * It returns false and counts the drop when the queue is full.
 */
bool usb_send(const char *fmt, ...) __attribute__((format(__printf__, 1, 2)));

/* send_task_line() sends the TASK line of the calling task. */
void send_task_line(const char *name);

void sensor_task(void *arg);
void pipeline_task(void *arg);
void state_task(void *arg);
void screen_task(void *arg);
void usb_task(void *arg);

#endif /* TASKS_H */
