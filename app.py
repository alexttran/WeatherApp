from __future__ import annotations
import os
import re
from typing import Dict, Any, List, Tuple

import requests
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

from psycopg2.extras import RealDictCursor
from crud import (
    resolve_location_from_query,
    create_weather_request,
    list_requests_db,
    get_request_db,
    update_request_db,
    relabel_location_db,
    delete_request_db,
)

from datetime import date


load_dotenv()

app = Flask(__name__)

# ====== Configuration ======
GEOCODIFY_API_KEY = os.getenv("GEOCODIFY_API_KEY", "")
OPEN_METEO_BASE = "https://api.open-meteo.com/v1/forecast"
HEADERS = {"Accept": "application/json", "User-Agent": "WeatherApp/1.0 (+local)"}

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

@app.post("/api/requests")
def create_request_api():
    """
    Body can be either:
      {"query":"Eiffel Tower","start_date":"2025-08-01","end_date":"2025-08-05","unit":"fahrenheit"}
    or {"lat":48.8584,"lon":2.2945,"label":"Eiffel Tower","start_date":"...","end_date":"..."}
    """
    p = request.get_json(force=True)
    try:
        if "lat" in p and "lon" in p:
            loc = {
                "label": p.get("label") or f"{p['lat']},{p['lon']}",
                "lat": float(p["lat"]), "lon": float(p["lon"])
            }
        else:
            q = (p.get("query") or "").strip()
            if not q:
                return jsonify({"error": "Provide query or lat/lon"}), 400
            loc = resolve_location_from_query(q)

        req_id = create_weather_request(
            loc,
            p["start_date"],
            p["end_date"],
            p.get("unit", "fahrenheit"),
        )
        return jsonify({"id": req_id, "message": "Saved"}), 201
    except KeyError as ke:
        return jsonify({"error": f"Missing field: {ke}"}), 400
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Create failed: {e}"}), 500
    
@app.get("/api/requests")
def list_requests_api():
    rows = list_requests_db(limit=200)
    return jsonify(rows)


@app.get("/api/requests/<int:req_id>")
def get_request_api(req_id: int):
    row = get_request_db(req_id)
    if not row:
        return jsonify({"error": "Not found"}), 404
    return jsonify(row)

@app.put("/api/requests/<int:req_id>")
def update_request_api(req_id: int):
    p = request.get_json(force=True)
    try:
        ok = update_request_db(
            req_id,
            p.get("start_date"),
            p.get("end_date"),
            p.get("unit"),
        )
        if not ok:
            return jsonify({"error": "Not found"}), 404
        return jsonify({"message": "Updated"})
    except ValueError as ve:
        return jsonify({"error": str(ve)}), 400
    except Exception as e:
        return jsonify({"error": f"Update failed: {e}"}), 500


@app.put("/api/locations/<int:loc_id>")
def relabel_location_api(loc_id: int):
    p = request.get_json(force=True)
    label = (p.get("label") or "").strip()
    if not label:
        return jsonify({"error": "label required"}), 400
    ok = relabel_location_db(loc_id, label)
    if not ok:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"message": "Updated"})


@app.delete("/api/requests/<int:req_id>")
def delete_request_api(req_id: int):
    ok = delete_request_db(req_id)
    if not ok:
        return jsonify({"error": "Not found"}), 404
    return jsonify({"message": "Deleted"})

def _range_weather_from_open_meteo(lat, lon, start_d: date, end_d: date, unit: str):
    """Return list[dict] of daily weather for [start_d, end_d] using the forecast endpoint.
       If Open-Meteo returns partial/empty results (e.g., far past), we just return what we get.
    """
    temp_unit = "fahrenheit" if unit.lower().startswith("f") else "celsius"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": ",".join([
            "weather_code",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_probability_max",
            "wind_speed_10m_max",
            "wind_gusts_10m_max",
        ]),
        "start_date": start_d.isoformat(),
        "end_date": end_d.isoformat(),
        "timezone": "auto",
        "temperature_unit": temp_unit,
        "wind_speed_unit": "mph" if temp_unit == "fahrenheit" else "kmh",
        "precipitation_unit": "inch" if temp_unit == "fahrenheit" else "mm",
    }
    r = requests.get(OPEN_METEO_BASE, params=params, headers=HEADERS, timeout=15)
    r.raise_for_status()
    data = r.json() or {}
    daily = data.get("daily", {}) or {}
    out = []
    times = daily.get("time") or []
    for i, d in enumerate(times):
        code = (daily.get("weather_code") or [None])[i]
        out.append({
            "date": d,
            "t_max": (daily.get("temperature_2m_max") or [None])[i],
            "t_min": (daily.get("temperature_2m_min") or [None])[i],
            "pop": (daily.get("precipitation_probability_max") or [None])[i],
            "wind_max": (daily.get("wind_speed_10m_max") or [None])[i],
            "gust_max": (daily.get("wind_gusts_10m_max") or [None])[i],
            "code": code,
            "code_text": WMO_TEXT.get(code, "") if code is not None else "",
            "icon": wmo_to_icon(code, 1),
        })
    return out, temp_unit


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=int(os.getenv("PORT", 8080)))