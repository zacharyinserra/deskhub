// Weather: now, next 24 hours, next 6 days (Open-Meteo).
#include <stdio.h>
#include <string.h>

#include "icons.h"
#include "sdkconfig.h"

#ifndef CONFIG_HUB_FAHRENHEIT
#define CONFIG_HUB_FAHRENHEIT 0
#endif
#include "ui_internal.h"
#include "weather.h"

#define CELL_W 72
#define DAY_W ((CONTENT_W - 32) / HUB_DAYS)

static lv_obj_t *s_icon, *s_temp, *s_cond, *s_city, *s_details, *s_updated;
static lv_obj_t *s_h_time[HUB_HOURS], *s_h_icon[HUB_HOURS], *s_h_temp[HUB_HOURS], *s_h_rain[HUB_HOURS];
static lv_obj_t *s_d_name[HUB_DAYS], *s_d_icon[HUB_DAYS], *s_d_range[HUB_DAYS], *s_d_rain[HUB_DAYS];

static lv_obj_t *centered(lv_obj_t *parent, const lv_font_t *f, uint32_t color, int w)
{
    lv_obj_t *l = ui_label(parent, f, color, "");
    lv_obj_set_width(l, w);
    lv_obj_set_style_text_align(l, LV_TEXT_ALIGN_CENTER, 0);
    return l;
}

void weather_page_create(lv_obj_t *page)
{
    const int W = CONTENT_W;

    lv_obj_t *now = ui_card(page);
    const bool c = UI_COMPACT;   // 372 px above the bottom bar instead of 440
    lv_obj_set_size(now, W, c ? 120 : 150);
    if (c) lv_obj_set_style_pad_all(now, 12, 0);
    lv_obj_set_pos(now, 0, 0);
    s_icon = ui_label(now, g_icon_80, COL_WARN, ICON_CLOUD);
    lv_obj_align(s_icon, LV_ALIGN_LEFT_MID, 4, 0);
    s_temp = ui_label(now, g_font_48, COL_TEXT, "--");
    lv_obj_set_pos(s_temp, 110, c ? 0 : 6);
    s_cond = ui_label(now, g_font_20, COL_TEXT, "Loading weather");
    lv_obj_set_pos(s_cond, 112, c ? 52 : 64);
    s_city = ui_label(now, g_font_16, COL_MUTED, CONFIG_HUB_CITY);
    lv_obj_set_pos(s_city, 112, c ? 76 : 94);
    s_details = ui_label(now, g_font_16, COL_TEXT, "");
    lv_obj_set_style_text_line_space(s_details, 8, 0);
    lv_obj_align(s_details, LV_ALIGN_TOP_RIGHT, 0, 6);
    s_updated = ui_label(now, g_font_14, COL_DIM, "");
    lv_obj_align(s_updated, LV_ALIGN_BOTTOM_RIGHT, 0, 4);

    lv_obj_t *hourly = ui_card(page);
    lv_obj_set_size(hourly, W, c ? 112 : 128);
    lv_obj_set_pos(hourly, 0, c ? 130 : 162);
    lv_obj_set_style_pad_all(hourly, 10, 0);
    lv_obj_add_flag(hourly, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_scroll_dir(hourly, LV_DIR_HOR);
    lv_obj_set_scrollbar_mode(hourly, LV_SCROLLBAR_MODE_OFF);
    for (int i = 0; i < HUB_HOURS; i++) {
        int x = i * CELL_W;
        s_h_time[i] = centered(hourly, g_font_14, COL_MUTED, CELL_W);
        lv_obj_set_pos(s_h_time[i], x, 0);
        s_h_icon[i] = centered(hourly, g_icon_32, COL_TEXT, CELL_W);
        lv_obj_set_pos(s_h_icon[i], x, c ? 20 : 22);
        s_h_temp[i] = centered(hourly, g_font_20, COL_TEXT, CELL_W);
        lv_obj_set_pos(s_h_temp[i], x, c ? 54 : 60);
        s_h_rain[i] = centered(hourly, g_font_14, COL_ACCENT2, CELL_W);
        lv_obj_set_pos(s_h_rain[i], x, c ? 76 : 86);
    }

    lv_obj_t *daily = ui_card(page);
    lv_obj_set_size(daily, W, c ? 120 : 138);
    if (c) lv_obj_set_style_pad_all(daily, 12, 0);
    lv_obj_set_pos(daily, 0, c ? 252 : 302);
    for (int i = 0; i < HUB_DAYS; i++) {
        int x = i * DAY_W;
        s_d_name[i] = centered(daily, g_font_16, COL_MUTED, DAY_W);
        lv_obj_set_pos(s_d_name[i], x, 0);
        s_d_icon[i] = centered(daily, g_icon_32, COL_TEXT, DAY_W);
        lv_obj_set_pos(s_d_icon[i], x, c ? 22 : 24);
        s_d_range[i] = centered(daily, g_font_16, COL_TEXT, DAY_W);
        lv_obj_set_pos(s_d_range[i], x, c ? 56 : 62);
        s_d_rain[i] = centered(daily, g_font_14, COL_ACCENT2, DAY_W);
        lv_obj_set_pos(s_d_rain[i], x, c ? 76 : 86);
    }
}

void weather_page_refresh(void)
{
    const hub_weather_t *w = &g_weather;
    if (!w->valid) return;
    char buf[96], a[12], b[12];

    lv_label_set_text(s_icon, weather_icon(w->code, w->is_day));
    lv_obj_set_style_text_color(s_icon, lv_color_hex(weather_color(w->code, w->is_day)), 0);
    ui_fmt_temp(buf, sizeof(buf), w->temp);
    lv_label_set_text(s_temp, buf);
    lv_label_set_text(s_cond, weather_text(w->code));

    ui_fmt_temp(a, sizeof(a), w->feels);
    snprintf(buf, sizeof(buf), "Feels like %s\nHumidity %d%%\nWind %d %s", a, w->humidity, (int)(w->wind + 0.5f),
             CONFIG_HUB_FAHRENHEIT ? "mph" : "km/h");
    lv_label_set_text(s_details, buf);
    ui_fmt_clock(a, sizeof(a), w->fetched);
    snprintf(buf, sizeof(buf), "Updated %s", a);
    lv_label_set_text(s_updated, buf);

    for (int i = 0; i < HUB_HOURS; i++) {
        if (i == 0) strlcpy(a, "Now", sizeof(a));
        else ui_fmt_hour(a, sizeof(a), w->hour_t[i]);
        lv_label_set_text(s_h_time[i], a);
        struct tm tm;
        localtime_r(&w->hour_t[i], &tm);
        bool day = tm.tm_hour >= 6 && tm.tm_hour < 19;
        lv_label_set_text(s_h_icon[i], weather_icon(w->hour_code[i], day));
        lv_obj_set_style_text_color(s_h_icon[i], lv_color_hex(weather_color(w->hour_code[i], day)), 0);
        ui_fmt_temp(a, sizeof(a), w->hour_temp[i]);
        lv_label_set_text(s_h_temp[i], a);
        if (w->hour_precip[i] >= 10) snprintf(a, sizeof(a), "%d%%", w->hour_precip[i]);
        else a[0] = 0;
        lv_label_set_text(s_h_rain[i], a);
    }

    for (int i = 0; i < HUB_DAYS; i++) {
        struct tm tm;
        // Daily timestamps are local midnight; add a few hours to stay on the right date.
        time_t t = w->day_t[i] + 6 * 3600;
        localtime_r(&t, &tm);
        if (i == 0) strlcpy(a, "Today", sizeof(a));
        else strftime(a, sizeof(a), "%a", &tm);
        lv_label_set_text(s_d_name[i], a);
        lv_label_set_text(s_d_icon[i], weather_icon(w->day_code[i], true));
        lv_obj_set_style_text_color(s_d_icon[i], lv_color_hex(weather_color(w->day_code[i], true)), 0);
        ui_fmt_temp(a, sizeof(a), w->day_hi[i]);
        ui_fmt_temp(b, sizeof(b), w->day_lo[i]);
        snprintf(buf, sizeof(buf), "%s / %s", a, b);
        lv_label_set_text(s_d_range[i], buf);
        if (w->day_precip[i] >= 10) snprintf(a, sizeof(a), "%d%%", w->day_precip[i]);
        else a[0] = 0;
        lv_label_set_text(s_d_rain[i], a);
    }
}
