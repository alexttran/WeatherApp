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