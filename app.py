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