#!/usr/bin/env python3
"""Render a Kindle-friendly weather screen (PNG) plus a TRMNL-style /api/display JSON.

Output goes to ./site, ready to be published with GitHub Pages:
  site/api/display            JSON the KOReader TRMNL plugin fetches
  site/screen/<name>.png      the image it points to
  site/.nojekyll              tell GitHub Pages to serve files as-is

Usage:
  python generate.py          # real weather from Open-Meteo (no API key needed)
  python generate.py --demo   # offline sample data, for checking the layout
"""
import argparse
import datetime as dt
import json
import math
import os
import time
import urllib.parse
import urllib.request
from zoneinfo import ZoneInfo

from PIL import Image, ImageDraw, ImageFont

W, H = 1448, 1072  # Kindle Paperwhite 3, 300 ppi, landscape
M = 64
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "site")
WEEK = "一二三四五六日"

FONT_DIRS = ["/usr/share/fonts/opentype/noto", "/usr/share/fonts/truetype/noto"]
BLACK, DARK, MID, LIGHT, PALE = 0, 70, 130, 200, 232

WMO = {
    0: ("晴", "sun"), 1: ("大部晴朗", "sun"), 2: ("多云", "partly"), 3: ("阴", "cloud"),
    45: ("雾", "fog"), 48: ("冻雾", "fog"),
    51: ("小毛毛雨", "rain"), 53: ("毛毛雨", "rain"), 55: ("大毛毛雨", "rain"),
    56: ("冻毛毛雨", "rain"), 57: ("冻毛毛雨", "rain"),
    61: ("小雨", "rain"), 63: ("中雨", "rain"), 65: ("大雨", "rain"),
    66: ("冻雨", "rain"), 67: ("冻雨", "rain"),
    71: ("小雪", "snow"), 73: ("中雪", "snow"), 75: ("大雪", "snow"), 77: ("雪粒", "snow"),
    80: ("小阵雨", "rain"), 81: ("阵雨", "rain"), 82: ("强阵雨", "rain"),
    85: ("小阵雪", "snow"), 86: ("大阵雪", "snow"),
    95: ("雷暴", "storm"), 96: ("雷暴冰雹", "storm"), 99: ("强雷暴冰雹", "storm"),
}


def wmo(code):
    return WMO.get(int(code), ("未知", "cloud"))


# ---------------------------------------------------------------- data
def get_json(url, tries=3):
    last = None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                return json.load(r)
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(2 * (i + 1))
    raise RuntimeError(f"request failed: {url}: {last}")


def locate(cfg):
    if cfg.get("latitude") is not None and cfg.get("longitude") is not None:
        return float(cfg["latitude"]), float(cfg["longitude"]), cfg.get("city", "")
    q = {"name": cfg["city"], "count": 1, "language": "zh", "format": "json"}
    if cfg.get("country_code"):
        q["countryCode"] = cfg["country_code"]
    res = get_json("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode(q))
    if not res.get("results"):
        raise RuntimeError(f"city not found: {cfg['city']} (set latitude/longitude in config.json)")
    r = res["results"][0]
    return r["latitude"], r["longitude"], r.get("name", cfg["city"])


def fetch_weather(cfg):
    lat, lon, name = locate(cfg)
    q = {
        "latitude": lat, "longitude": lon, "timezone": cfg["timezone"], "forecast_days": 6,
        "current": "temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m",
        "hourly": "temperature_2m,precipitation_probability",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
    }
    data = get_json("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode(q))
    data["_city"] = name
    return data


def demo_weather(tz):
    now = dt.datetime.now(ZoneInfo(tz)).replace(minute=0, second=0, microsecond=0)
    start = now.replace(hour=0)
    times = [(start + dt.timedelta(hours=i)).strftime("%Y-%m-%dT%H:%M") for i in range(24 * 6)]
    temps = [round(11 + 5 * math.sin((i - 9) / 24 * 2 * math.pi) + (i // 24) * 0.6, 1) for i in range(24 * 6)]
    pops = [max(0, int(50 * math.sin(i / 7.0))) for i in range(24 * 6)]
    days = [(start + dt.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(6)]
    return {
        "_city": "示例城市",
        "current": {"temperature_2m": 12.4, "apparent_temperature": 10.8, "relative_humidity_2m": 68,
                    "weather_code": 2, "wind_speed_10m": 11.2},
        "hourly": {"time": times, "temperature_2m": temps, "precipitation_probability": pops},
        "daily": {"time": days, "weather_code": [2, 61, 3, 0, 95, 71],
                  "temperature_2m_max": [16, 14, 13, 18, 15, 3], "temperature_2m_min": [8, 9, 7, 10, 9, -4],
                  "precipitation_probability_max": [20, 80, 40, 5, 70, 60],
                  "sunrise": [f"{day}T06:20" for day in days],
                  "sunset": [f"{day}T18:05" for day in days]},
    }


# ---------------------------------------------------------------- drawing
def load_font(weight, size):
    name = f"NotoSansCJK-{weight}.ttc"
    for d in FONT_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return ImageFont.truetype(p, size, index=2)  # index 2 = Simplified Chinese
    raise RuntimeError("Noto Sans CJK not found; install fonts-noto-cjk")


def text_w(d, s, f):
    return d.textlength(s, font=f)


def draw_icon(d, kind, cx, cy, s):
    """Simple monochrome weather icons; s is the icon's box size in px."""
    lw = max(3, s // 22)

    def sun(x, y, r, rays=True):
        d.ellipse([x - r, y - r, x + r, y + r], outline=BLACK, width=lw)
        if rays:
            for k in range(8):
                a = k * math.pi / 4
                d.line([x + math.cos(a) * r * 1.45, y + math.sin(a) * r * 1.45,
                        x + math.cos(a) * r * 1.9, y + math.sin(a) * r * 1.9], fill=BLACK, width=lw)

    def cloud(x, y, w, fill=DARK):
        r = w * 0.2
        d.rounded_rectangle([x - w / 2, y - r * 0.2, x + w / 2, y + r * 1.5], radius=r * 0.8, fill=fill)
        d.ellipse([x - w * 0.30, y - r * 1.3, x - w * 0.30 + 2 * r * 0.95, y - r * 1.3 + 2 * r * 0.95], fill=fill)
        d.ellipse([x - w * 0.02, y - r * 1.8, x - w * 0.02 + 2 * r * 1.2, y - r * 1.8 + 2 * r * 1.2], fill=fill)

    if kind == "sun":
        sun(cx, cy, s * 0.24)
    elif kind == "partly":
        sun(cx - s * 0.16, cy - s * 0.14, s * 0.17)
        cloud(cx + s * 0.06, cy + s * 0.06, s * 0.72, fill=DARK)
    elif kind == "cloud":
        cloud(cx, cy, s * 0.8)
    elif kind == "fog":
        for k in range(4):
            y = cy - s * 0.24 + k * s * 0.16
            d.line([cx - s * 0.36, y, cx + s * 0.36, y], fill=BLACK, width=lw)
    else:
        cloud(cx, cy - s * 0.14, s * 0.78)
        if kind == "rain":
            for k in (-1, 0, 1):
                x = cx + k * s * 0.22
                d.line([x, cy + s * 0.2, x - s * 0.07, cy + s * 0.38], fill=BLACK, width=lw)
        elif kind == "snow":
            for k in (-1, 0, 1):
                x, y, r = cx + k * s * 0.22, cy + s * 0.3, s * 0.04
                d.ellipse([x - r, y - r, x + r, y + r], fill=BLACK)
        elif kind == "storm":
            x, y = cx, cy + s * 0.14
            d.polygon([(x + s * 0.05, y), (x - s * 0.1, y + s * 0.2), (x, y + s * 0.2),
                       (x - s * 0.06, y + s * 0.38), (x + s * 0.12, y + s * 0.14), (x + s * 0.02, y + s * 0.14)],
                      fill=BLACK)


def render(data, cfg, now):
    img = Image.new("L", (W, H), 255)
    d = ImageDraw.Draw(img)
    F = lambda wt, s: load_font(wt, s)  # noqa: E731
    cur, hourly, daily = data["current"], data["hourly"], data["daily"]
    city = data["_city"]

    # Header
    d.text((M, 42), f"{now.month}月{now.day}日", font=F("Bold", 76), fill=BLACK)
    weekday = f"星期{WEEK[now.weekday()]}"
    weekday_font = F("Bold" if now.weekday() == 4 else "Regular", 36)
    weekday_color = DARK if now.weekday() == 4 else MID
    d.text((M, 132), weekday, font=weekday_font, fill=weekday_color)
    city_x = M + text_w(d, weekday, weekday_font) + 20
    d.text((city_x, 132), f"·  {city}", font=F("Regular", 36), fill=MID)
    d.line([M, 194, W - M, 194], fill=BLACK, width=4)

    # Current conditions, left column
    text, kind = wmo(cur["weather_code"])
    draw_icon(d, kind, 230, 352, 250)
    temp = f"{round(cur['temperature_2m'])}°"
    f_temp = F("Bold", 190)
    d.text((410, 245), temp, font=f_temp, fill=BLACK)
    d.text((410, 470), text, font=F("Bold", 34), fill=DARK)
    d.text((M, 532),
           f"体感 {round(cur['apparent_temperature'])}°  ·  风 {round(cur['wind_speed_10m'])} km/h",
           font=F("Regular", 32), fill=DARK)
    d.text((M, 582),
           f"今日 {round(daily['temperature_2m_min'][0])}°–{round(daily['temperature_2m_max'][0])}°"
           f"  ·  雨 {daily['precipitation_probability_max'][0] or 0}%",
           font=F("Regular", 32), fill=DARK)

    # Practical timing summary
    floor_now = now.replace(minute=0, second=0, microsecond=0, tzinfo=None)
    hourly_times = [dt.datetime.strptime(t, "%Y-%m-%dT%H:%M") for t in hourly["time"]]
    next_hours = [(i, t) for i, t in enumerate(hourly_times) if floor_now <= t < floor_now + dt.timedelta(hours=24)]
    if next_hours:
        rain_i, rain_time = max(next_hours, key=lambda it: hourly["precipitation_probability"][it[0]] or 0)
        rain_prob = hourly["precipitation_probability"][rain_i] or 0
        rain_text = f"雨峰 {rain_time.strftime('%H')}时 {round(rain_prob)}%" if rain_prob >= 20 else "少雨"
    else:
        rain_text = "暂无降雨数据"
    sunrise = daily.get("sunrise", [None])[0]
    sunset = daily.get("sunset", [None])[0]
    sun_text = "日出 --:--  ·  日落 --:--"
    if sunrise and sunset:
        sun_text = f"日出 {sunrise[-5:]}  ·  日落 {sunset[-5:]}"
    d.text((M, 632), f"{rain_text}  ·  {sun_text}", font=F("Regular", 26), fill=DARK)

    # 24-hour chart, upper right
    rx0, rx1 = 770, W - M
    start = next((i for i, t in enumerate(hourly_times) if t >= floor_now), 0)
    idx = list(range(start, min(start + 25, len(hourly_times))))
    ts = [hourly["temperature_2m"][i] for i in idx]
    ps = [hourly["precipitation_probability"][i] or 0 for i in idx]
    cx0, cx1, cy0, cy1 = rx0 + 12, rx1 - 12, 270, 405
    lo, hi = min(ts), max(ts)
    span = max(hi - lo, 4)
    xs = [cx0 + (cx1 - cx0) * k / max(len(idx) - 1, 1) for k in range(len(idx))]
    ys = [cy1 - (cy1 - cy0) * (t - lo) / span for t in ts]
    bar_base, bar_h = 465, 48
    for k, p in enumerate(ps):
        h = bar_h * p / 100
        d.rectangle([xs[k] - 9, bar_base - h, xs[k] + 9, bar_base], fill=LIGHT)
    d.line([rx0, bar_base, rx1, bar_base], fill=MID, width=2)
    d.line(list(zip(xs, ys)), fill=BLACK, width=5, joint="curve")
    for k in set((ts.index(hi), ts.index(lo))):
        d.ellipse([xs[k] - 7, ys[k] - 7, xs[k] + 7, ys[k] + 7], fill=BLACK)
        label = f"{round(ts[k])}°"
        f = F("Bold", 30)
        ty = ys[k] - 42 if k == ts.index(hi) else ys[k] + 10
        d.text((min(max(xs[k] - text_w(d, label, f) / 2, rx0), rx1 - 54), ty), label, font=f, fill=BLACK)
    for k in range(0, len(idx), 6):
        label = f"{hourly_times[idx[k]].hour}时"
        f = F("Regular", 24)
        d.text((min(max(xs[k] - text_w(d, label, f) / 2, rx0), rx1 - text_w(d, label, f)), bar_base + 8), label, font=f, fill=DARK)

    # Five-day forecast, lower right
    d.line([rx0, 540, rx1, 540], fill=BLACK, width=3)
    rows = list(range(1, min(6, len(daily["time"]))))
    tmin = min(daily["temperature_2m_min"][i] for i in rows)
    tmax = max(daily["temperature_2m_max"][i] for i in rows)
    bx0, bx1 = 1150, 1300
    for n, i in enumerate(rows):
        y = 584 + n * 78
        day = dt.datetime.strptime(daily["time"][i], "%Y-%m-%d")
        name = "明天" if i == 1 else f"周{WEEK[day.weekday()]}"
        _, kind_d = wmo(daily["weather_code"][i])
        d.text((rx0, y), name, font=F("Bold", 28), fill=BLACK)
        draw_icon(d, kind_d, rx0 + 122, y + 18, 44)
        lo_d, hi_d = daily["temperature_2m_min"][i], daily["temperature_2m_max"][i]
        sx = lambda v: bx0 + (bx1 - bx0) * (v - tmin) / max(tmax - tmin, 1)  # noqa: E731
        d.text((1060, y), f"{round(lo_d)}°", font=F("Regular", 28), fill=DARK)
        d.line([bx0, y + 18, bx1, y + 18], fill=PALE, width=9)
        d.line([sx(lo_d), y + 18, sx(hi_d), y + 18], fill=DARK, width=9)
        d.text((1320, y), f"{round(hi_d)}°", font=F("Bold", 28), fill=BLACK)

    d.text((M, H - 44), f"更新 {now.strftime('%H:%M')}", font=F("Regular", 24), fill=MID)
    return img


# ---------------------------------------------------------------- output
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", action="store_true", help="use offline sample data")
    args = ap.parse_args()
    with open(os.path.join(HERE, "config.json"), encoding="utf-8") as fh:
        cfg = json.load(fh)
    tz = cfg.get("timezone", "UTC")
    now = dt.datetime.now(ZoneInfo(tz))
    data = demo_weather(tz) if args.demo else fetch_weather(cfg)

    img = render(data, cfg, now)
    name = "dashboard-" + now.strftime("%Y%m%d-%H%M") + ".png"
    os.makedirs(os.path.join(OUT, "screen"), exist_ok=True)
    os.makedirs(os.path.join(OUT, "api"), exist_ok=True)
    img.save(os.path.join(OUT, "screen", name), optimize=True)
    open(os.path.join(OUT, ".nojekyll"), "w").close()

    base = os.environ.get("SITE_URL", "http://localhost:8000").rstrip("/")
    payload = {
        "status": 0,
        "image_url": f"{base}/screen/{name}",
        "filename": name,
        "refresh_rate": int(cfg.get("refresh_seconds", 3600)),
        "update_firmware": False,
        "firmware_url": "",
        "reset_firmware": False,
    }
    with open(os.path.join(OUT, "api", "display"), "w", encoding="utf-8") as fh:  # no extension on purpose
        json.dump(payload, fh, ensure_ascii=False)
    print("wrote", os.path.join(OUT, "screen", name))
    print(json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    main()
