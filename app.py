from __future__ import annotations
import os
import re
from typing import Dict, Any, List, Tuple

import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# ====== Configuration ======
GEOCODIFY_API_KEY = os.getenv("GEOCODIFY_API_KEY", "")
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
HEADERS = {"Accept": "application/json", "User-Agent": "BreezeWeather/1.0 (+local)"}

# ====== Helpers ======
COORDS_RE = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d+)?)),\s*([+-]?(?:\d+(?:\.\d+)?))\s*$")

WMO_TEXT = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

def wmo_to_icon(code: int, is_day: int | None = 1) -> str:
    """Map WMO weather code to a Weather Icons CSS class."""
    day = (is_day or 1) == 1
    if code == 0:
        return "wi wi-day-sunny" if day else "wi wi-night-clear"
    if code in (1, 2):
        return "wi wi-day-cloudy" if day else "wi wi-night-alt-cloudy"
    if code == 3:
        return "wi wi-cloudy"
    if code in (45, 48):
        return "wi wi-fog"
    if code in (51, 53, 55, 56, 57):
        return "wi wi-sprinkle"
    if code in (61, 63, 65, 66, 67, 80, 81, 82):
        return "wi wi-rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "wi wi-snow"
    if code in (95, 96, 99):
        return "wi wi-thunderstorm"
    return "wi wi-na"


def deg_to_compass(deg: float | None) -> str:
    if deg is None:
        return "—"
    val = int((deg / 22.5) + 0.5)
    arr = [
        "N","NNE","NE","ENE","E","ESE","SE","SSE",
        "S","SSW","SW","WSW","W","WNW","NW","NNW"
    ]
    return arr[(val % 16)]

def parse_coords(text: str) -> Tuple[float, float] | None:
    match = COORDS_RE.match(text)
    if match:
        lat = float(match.group(1))
        lon = float(match.group(2))
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return (lat, lon)
    return None


@app.route("/")
def index():
    return render_template("index.html")

def _geo_get(endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
    url = f"https://api.geocodify.com/v2/{endpoint}"
    try:
        r = requests.get(url, params=params, headers=HEADERS, timeout=10)
        if r.status_code == 429:
           return {"_error": "rate_limited"}
        r.raise_for_status()
        return r.json()
    except Exception as e:
        return {"_error": str(e)}

def _extract_suggestions(data: Dict[str, Any], limit: int = 10):
    out = []
    if not data:
        return out
    if data.get("_error") == "rate_limited":
        return [{"label": "Rate-limited: pause typing for a second…", "lat": None, "lon": None, "disabled": True}]
    feats = data.get("features") or data.get("results") or data.get("data") or []
    if isinstance(feats, dict):
        feats = [feats]
    for f in feats[:limit]:
        props = (f or {}).get("properties", {})
        geom = (f or {}).get("geometry", {})
        label = props.get("label") or props.get("name") or props.get("formatted") or f.get("text") or f.get("name")
        lat = None
        lon = None
        coords = geom.get("coordinates")
        if isinstance(coords, (list, tuple)) and len(coords) >= 2:
            lon, lat = coords[0], coords[1]
        else:
            lat = (f or {}).get("lat") or props.get("lat") or props.get("latitude")
            lon = (f or {}).get("lng") or props.get("lon") or props.get("longitude")
        if label and lat is not None and lon is not None:
            out.append({"label": label, "lat": float(lat), "lon": float(lon)})
    return out

@app.route("/api/autocomplete")
def autocomplete():
    q = request.args.get("q", "").strip()
    if len(q) < 3:
        return jsonify({"suggestions": []})
    if not GEOCODIFY_API_KEY:
        return jsonify({"error": "Missing GEOCODIFY_API_KEY on server"}), 500
    data = _geo_get("autocomplete", {"api_key": GEOCODIFY_API_KEY, "q": q})
    if data.get("_error") == "rate_limited":
        return jsonify({"suggestions": [{"label": "Rate-limited: pause typing for a second…", "lat": None, "lon": None, "disabled": True}]})
    if "_error" in data:
        return jsonify({"error": f"Autocomplete failed: {data['_error']}"}), 502
    suggestions = _extract_suggestions(data)
    return jsonify({"suggestions": suggestions})

@app.route("/api/geocode")
def geocode():
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify({"error": "Missing query"}), 400

    coords = parse_coords(q)
    if coords:
        return jsonify({"label": q, "lat": coords[0], "lon": coords[1]})
    if not GEOCODIFY_API_KEY:
        return jsonify({"error": "Missing GEOCODIFY_API_KEY on server"}), 500
    
    data = _geo_get("geocode", {"api_key": GEOCODIFY_API_KEY, "q": q})
    if data.get("_error") == "rate_limited":
        return jsonify({"error": "Geocodify rate limit hit. Type slower or upgrade the plan."}), 429
    if "_error" in data:
        return jsonify({"error": f"Geocoding failed: {data['_error']}"}), 502
    c = data['response']['features'][0]['geometry']['coordinates']
    return jsonify({"label": q, "lat": c[1], "lon": c[0]})

@app.route("/api/weather")
def weather():
    try:
        lat = float(request.args.get("lat"))
        lon = float(request.args.get("lon"))
    except Exception:
        return jsonify({"error": "Invalid or missing lat/lon"}), 400

    unit = request.args.get("unit", "fahrenheit")
    temp_unit = "fahrenheit" if unit.lower().startswith("f") else "celsius"

    params = {
        "latitude": lat,
        "longitude": lon,
        "current": ",".join([
            "temperature_2m",
            "relative_humidity_2m",
            "apparent_temperature",
            "weather_code",
            "wind_speed_10m",
            "wind_direction_10m",
            "is_day",
            "precipitation",
            "cloud_cover",
            "pressure_msl",
        ]),
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
        ]),
        "timezone": "auto",
        "forecast_days": 7,
        "temperature_unit": temp_unit,
        "wind_speed_unit": "mph" if temp_unit == "fahrenheit" else "kmh",
        "precipitation_unit": "inch" if temp_unit == "fahrenheit" else "mm",
    }

    try:
        r = requests.get(OPEN_METEO_BASE, params=params, headers=HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        return jsonify({"error": f"Open-Meteo request failed: {e}"}), 502

    cur = (data or {}).get("current", {})
    current = {
        "temperature": cur.get("temperature_2m"),
        "apparent_temperature": cur.get("apparent_temperature"),
        "humidity": cur.get("relative_humidity_2m"),
        "precipitation": cur.get("precipitation"),
        "cloud_cover": cur.get("cloud_cover"),
        "pressure": cur.get("pressure_msl"),
        "wind_speed": cur.get("wind_speed_10m"),
        "wind_dir": cur.get("wind_direction_10m"),
        "is_day": cur.get("is_day", 1),
        "code": cur.get("weather_code"),
        "code_text": WMO_TEXT.get(cur.get("weather_code"), "Unknown"),
        "icon": wmo_to_icon(cur.get("weather_code", 0), cur.get("is_day", 1)),
        "time": cur.get("time"),
        "unit_labels": data.get("current_units", {}),
    }
    daily = data.get("daily", {})
    days = []
    for i, date in enumerate(daily.get("time", [])[2:7]):
        code = (daily.get("weather_code", []) or [None])[i]
        days.append({
            "date": date,
            "t_max": (daily.get("temperature_2m_max", []) or [None])[i],
            "t_min": (daily.get("temperature_2m_min", []) or [None])[i],
            "pop": (daily.get("precipitation_probability_max", []) or [None])[i],
            "wind_max": (daily.get("wind_speed_10m_max", []) or [None])[i],
            "gust_max": (daily.get("wind_gusts_10m_max", []) or [None])[i],
            "code": code,
            "code_text": WMO_TEXT.get(code, ""),
            "icon": wmo_to_icon(code, 1),
        })
    return jsonify({
        "location": {"lat": lat, "lon": lon},
        "unit": temp_unit,
        "current": current,
        "daily": days,
    })

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))