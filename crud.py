import os
import requests
from typing import Optional, Dict, Any, List
from psycopg2.extras import RealDictCursor
from db_raw import get_conn
from validators import validate_range

GEOCODIFY_API_KEY = os.getenv("GEOCODIFY_API_KEY", "")
HEADERS = {"Accept": "application/json", "User-Agent": "WeatherApp/1.0 (+server)"}