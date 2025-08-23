# WeatherApp
This weather app allows you to access the weather, both current and a few days in the future. \
The app uses Geocodify to geocode various locations into coordinates, which the Open-Mateo api uses to return weather data. \
Users can input cities, zip codes, landmarks, and coordinates to recieve weather data. \
I implemented technical assessment #1 and #2.1

# Database
This web app uses Supabase for a postgreSQL database, allowing for CRUD functionalities. \
You can store weather data for a given location within a given time frame.

# Quick Start
python -m venv .venv \
source .venv/bin/activate \
pip install -r requirements.txt \
python app.py 

OR

Go to this site: \
https://weatherapp-np1t.onrender.com/
