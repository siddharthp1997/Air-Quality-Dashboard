import os
from dotenv import load_dotenv
import requests
import pandas as pd
from datetime import datetime, timezone
from time import sleep
from pymongo import MongoClient
import pytz
from urllib.parse import quote

# ------------------------
# Env & constants
# ------------------------
load_dotenv()

AQICN_TOKEN = os.getenv('AQICN_TOKEN')  # NEW
MONGO_DB = str(os.getenv('MONGO_DB'))
MONGO_COLLECTION = str(os.getenv('MONGO_COLLECTION'))
ATLAS_URI = os.getenv('ATLAS_URI')

AQICN_ENDPOINT = "https://api.waqi.info/feed/{q}/?token={token}"

# Keep your city list
cities = [
    {'city': 'Los Angeles', 'state': 'California'},
    {'city': 'New York City', 'state': 'New York'},
    {'city': 'Chicago', 'state': 'Illinois'},
    {'city': 'Houston', 'state': 'Texas'},
    {'city': 'Phoenix', 'state': 'Arizona'},
    {'city': 'Philadelphia', 'state': 'Pennsylvania'},
    {'city': 'San Antonio', 'state': 'Texas'},
    {'city': 'San Diego', 'state': 'California'},
    {'city': 'Dallas', 'state': 'Texas'},
    {'city': 'San Jose', 'state': 'California'},
    {'city': 'Austin', 'state': 'Texas'},
    {'city': 'Jacksonville', 'state': 'Florida'},
    {'city': 'San Francisco', 'state': 'California'},
    {'city': 'Indianapolis', 'state': 'Indiana'},
    {'city': 'Columbus', 'state': 'Ohio'},
    {'city': 'Fort Worth', 'state': 'Texas'},
    {'city': 'Charlotte', 'state': 'North Carolina'},
    {'city': 'Seattle', 'state': 'Washington'},
    {'city': 'Denver', 'state': 'Colorado'},
    {'city': 'Boston', 'state': 'Massachusetts'},
    {'city': 'El Paso', 'state': 'Texas'},
    {'city': 'Nashville', 'state': 'Tennessee'},
    {'city': 'Detroit', 'state': 'Michigan'},
    {'city': 'Oklahoma City', 'state': 'Oklahoma'},
    {'city': 'Portland', 'state': 'Oregon'},
    {'city': 'Las Vegas', 'state': 'Nevada'},
    {'city': 'Memphis', 'state': 'Tennessee'},
    {'city': 'Louisville', 'state': 'Kentucky'},
    {'city': 'Baltimore', 'state': 'Maryland'},
]

# ------------------------
# Helpers
# ------------------------
def now_est_date_time():
    eastern = pytz.timezone('America/New_York')
    utc_now = datetime.utcnow().replace(tzinfo=pytz.utc)
    now = utc_now.astimezone(eastern)
    return now.strftime("%Y-%m-%d"), now.strftime("%H:%M:%S")

def aqi_category(aqi):
    """US AQI category label."""
    try:
        aqi = float(aqi)
    except (TypeError, ValueError):
        return "Unknown"
    if aqi <= 50: return "Good"
    if aqi <= 100: return "Moderate"
    if aqi <= 150: return "Unhealthy for Sensitive Groups"
    if aqi <= 200: return "Unhealthy"
    if aqi <= 300: return "Very Unhealthy"
    return "Hazardous"

def safe_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None

def flatten_iaqi(iaqi_dict):
    """Turn {'pm25': {'v': 90}, 'o3': {'v': 10}} into {'iaqi_pm25': 90, 'iaqi_o3': 10, ...}"""
    out = {}
    if not isinstance(iaqi_dict, dict):
        return out
    for key, obj in iaqi_dict.items():
        if isinstance(obj, dict) and 'v' in obj:
            out[f'iaqi_{key}'] = obj['v']
    return out

def fetch_feed(query_text):
    url = AQICN_ENDPOINT.format(q=quote(query_text), token=AQICN_TOKEN)
    r = requests.get(url, timeout=20)
    r.raise_for_status()
    return r.json()

# ------------------------
# Main fetch/normalize
# ------------------------
def fetch_air_quality_data(city_info):
    city_label = city_info['city']
    state = city_info['state']
    date_est, time_est = now_est_date_time()

    try:
        payload = fetch_feed(city_label)
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data for {city_label}, {state}: {e}")
        return {
            'City': city_label, 'State': state, 'Country': 'USA',
            'AQI (US)': 'NA', 'AQI Category': 'Unknown',
            'Main Pollutant (US)': 'Error',
            'AQI (CN)': 'NA', 'Main Pollutant (CN)': 'NA',
            'Date': date_est, 'Time': time_est,
            'Source': 'aqicn', 'status': 'error'
        }

    status = payload.get('status')
    data = payload.get('data') or {}

    if status != 'ok':
        return {
            'City': city_label, 'State': state, 'Country': 'USA',
            'AQI (US)': 'NA', 'AQI Category': 'Unknown',
            'Main Pollutant (US)': 'Error',
            'AQI (CN)': 'NA', 'Main Pollutant (CN)': 'NA',
            'Date': date_est, 'Time': time_est,
            'Source': 'aqicn', 'status': status or 'unknown'
        }

    # Top-level basics
    aqi_us = data.get('aqi')
    dominentpol = data.get('dominentpol')
    idx = data.get('idx')

    # City/station block
    city_block = data.get('city') or {}
    station_name = city_block.get('name') or city_label
    station_url = city_block.get('url')
    station_geo = city_block.get('geo') or []
    lat = station_geo[0] if len(station_geo) > 0 else None
    lon = station_geo[1] if len(station_geo) > 1 else None

    # Time block from WAQI
    time_block = data.get('time') or {}
    time_station_local = time_block.get('s')  # e.g., "2024-10-08 11:00:00"
    time_station_tz = time_block.get('tz')    # e.g., "+05:30"
    time_station_v = time_block.get('v')      # epoch-like integer sometimes used by AQICN

    # Attributions (array of {name,url})
    attribs = data.get('attributions') or []
    attribution_names = [a.get('name') for a in attribs if isinstance(a, dict) and a.get('name')]
    attribution_urls = [a.get('url') for a in attribs if isinstance(a, dict) and a.get('url')]

    # iaqi flatten
    iaqi_flat = flatten_iaqi(data.get('iaqi') or {})

    # Weather-ish convenience fields from iaqi (if present)
    temp_c = iaqi_flat.get('iaqi_t')
    humidity_pct = iaqi_flat.get('iaqi_h')
    wind_mps = iaqi_flat.get('iaqi_w')
    pressure_hpa = iaqi_flat.get('iaqi_p')

    # Build record
    record = {
        # Your existing schema (kept for compatibility)
        'City': station_name,
        'State': state,
        'Country': 'USA',
        'AQI (US)': aqi_us,
        'AQI Category': aqi_category(aqi_us),
        'Main Pollutant (US)': dominentpol,
        'AQI (CN)': 'NA',                 # You previously stored both; AQICN exposes a single AQI
        'Main Pollutant (CN)': 'NA',

        # Extra station metadata
        'Station IDX': idx,
        'Station URL': station_url,
        'Station Geo Lat': safe_float(lat),
        'Station Geo Lon': safe_float(lon),

        # AQICN time fields (as provided)
        'Station Time (local)': time_station_local,
        'Station Time TZ': time_station_tz,
        'Station Time (v)': time_station_v,

        # Convenience ingest timestamp (UTC + EST strings)
        'Ingested At UTC': datetime.now(timezone.utc).isoformat(),
        'Date': date_est,        # EST date (your original)
        'Time': time_est,        # EST time (your original)

        # Attribution
        'Attribution Names': attribution_names,
        'Attribution URLs': attribution_urls,

        # Weather-like metrics (if present)
        'Temperature (°C)': temp_c,
        'Pressure (hPa)': pressure_hpa,
        'Humidity (%)': humidity_pct,
        'Wind Speed (m/s)': wind_mps,

        'Source': 'aqicn',
        'status': 'ok'
    }

    # Merge full iaqi flatten (adds iaqi_pm25, iaqi_pm10, iaqi_o3, iaqi_no2, iaqi_so2, iaqi_co, iaqi_t, iaqi_h, iaqi_w, iaqi_p, etc.)
    record.update(iaqi_flat)

    # Replace None with 'NA' for uniformity in your DF/UI
    for k, v in list(record.items()):
        if v is None:
            record[k] = 'NA'

    return record

# ------------------------
# Batch, save, print
# ------------------------
def process_cities_in_batches(cities, batch_size=4, delay=60):
    all_city_data = []
    for i in range(0, len(cities), batch_size):
        cities_batch = cities[i:i+batch_size]
        batch_data = []
        for city_info in cities_batch:
            batch_data.append(fetch_air_quality_data(city_info))
        all_city_data.extend(batch_data)
        if i + batch_size < len(cities):
            print(f"Processed batch {i//batch_size + 1}/{(len(cities) + batch_size - 1)//batch_size}")
            sleep(delay)
    return all_city_data

def save_to_mongodb(data):
    client = MongoClient(ATLAS_URI)
    db = client[MONGO_DB]
    collection = db[MONGO_COLLECTION]
    try:
        collection.insert_many(data)
    except Exception as e:
        print(f"Failed to save data to MongoDB: {str(e)}")
    finally:
        client.close()

# Run
all_city_data = process_cities_in_batches(cities)
save_to_mongodb(all_city_data)

df = pd.DataFrame(all_city_data)
print(df)