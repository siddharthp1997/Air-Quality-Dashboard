import os
from dotenv import load_dotenv
import requests
import pandas as pd
from datetime import datetime
from time import sleep
from pymongo import MongoClient

# Load environment variables from .env file
load_dotenv()

# AirVisual API key
API_KEY = os.getenv('API_KEY')

# MongoDB connection settings
#MONGO_DB = os.getenv('MONGO_DB')
#MONGO_COLLECTION = os.getenv('MONGO_COLLECTION')
MONGO_DB = str(os.getenv('MONGO_DB'))
MONGO_COLLECTION = str(os.getenv('MONGO_COLLECTION'))
#MONGO_DB="air_quality"
#MONGO_COLLECTION="city_data"
ATLAS_URI = os.getenv('ATLAS_URI')

# List of major cities in the USA
cities = [
    {'city': 'Los Angeles', 'state': 'California'},
    {'city': 'New York City', 'state': 'New York'},
    {'city': 'Chicago', 'state': 'Illinois'},
    {'city': 'Houston', 'state': 'Texas'},
]

# AirVisual API endpoint
API_ENDPOINT = "http://api.airvisual.com/v2/city"

# Function to fetch air quality data for a single city
def fetch_air_quality_data(city_info):
    city = city_info['city']
    state = city_info['state']
    url = f"{API_ENDPOINT}?city={city}&state={state}&country=USA&key={API_KEY}"
    
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raise error for bad response status
        
        result = response.json()
        data = result.get('data')
        
        if data:
            aqi_us = data['current']['pollution'].get('aqius', -1)
            main_pollutant_us = data['current']['pollution'].get('mainus', 'Error')
            aqi_cn = data['current']['pollution'].get('aqicn', -1)
            main_pollutant_cn = data['current']['pollution'].get('maincn', 'Error')
            temperature = data['current']['weather'].get('tp', -1)
            pressure = data['current']['weather'].get('pr', -1)
            humidity = data['current']['weather'].get('hu', -1)
            wind_speed = data['current']['weather'].get('ws', -1)
            wind_direction = data['current']['weather'].get('wd', -1)
            weather_icon = data['current']['weather'].get('ic', 'Error')
            
            # Get current date and time separately
            now = datetime.now()
            date = now.strftime("%Y-%m-%d")
            time = now.strftime("%H:%M:%S")
            
            city_data = {
                'City': city,
                'State': state,
                'Country': 'USA',
                'AQI (US)': aqi_us,
                'Main Pollutant (US)': main_pollutant_us,
                'AQI (CN)': aqi_cn,
                'Main Pollutant (CN)': main_pollutant_cn,
                'Temperature (°C)': temperature,
                'Pressure (hPa)': pressure,
                'Humidity (%)': humidity,
                'Wind Speed (m/s)': wind_speed,
                'Wind Direction (°)': wind_direction,
                'Weather Icon': weather_icon,
                'Date': date,  # Add date field
                'Time': time   # Add time field
            }
            
            return city_data
        
        else:
            print(f"No data available for {city}, {state}")
            return {
                'City': city,
                'State': state,
                'Country': 'USA',
                'AQI (US)': -1,
                'Main Pollutant (US)': 'Error',
                'AQI (CN)': -1,
                'Main Pollutant (CN)': 'Error',
                'Temperature (°C)': -1,
                'Pressure (hPa)': -1,
                'Humidity (%)': -1,
                'Wind Speed (m/s)': -1,
                'Wind Direction (°)': -1,
                'Weather Icon': 'Error',
                'Date': date,  # Add date field
                'Time': time   # Add time field
            }
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data for {city}, {state}: {str(e)}")
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        return {
            'City': city,
            'State': state,
            'Country': 'USA',
            'AQI (US)': -1,
            'Main Pollutant (US)': 'Error',
            'AQI (CN)': -1,
            'Main Pollutant (CN)': 'Error',
            'Temperature (°C)': -1,
            'Pressure (hPa)': -1,
            'Humidity (%)': -1,
            'Wind Speed (m/s)': -1,
            'Wind Direction (°)': -1,
            'Weather Icon': 'Error',
            'Date': date,  # Add date field
            'Time': time   # Add time field
        }

# Function to process cities in batches and wait between batches
def process_cities_in_batches(cities, batch_size=4, delay=60):
    all_city_data = []
    for i in range(0, len(cities), batch_size):
        cities_batch = cities[i:i+batch_size]
        batch_data = []
        for city_info in cities_batch:
            city_data = fetch_air_quality_data(city_info)
            batch_data.append(city_data)
        all_city_data.extend(batch_data)
        if i + batch_size < len(cities):
            print(f"Processed batch {i//batch_size + 1}/{len(cities)//batch_size}")
            sleep(delay)  # Wait before making the next batch request
    return all_city_data

# Function to save data to MongoDB
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

# Process cities in batches and fetch air quality data
all_city_data = process_cities_in_batches(cities)

# Save data to MongoDB
save_to_mongodb(all_city_data)

# Create a pandas DataFrame from the fetched data (optional)
df = pd.DataFrame(all_city_data)
print(df)
