import os
from dotenv import load_dotenv
import requests
import pandas as pd
from datetime import datetime
from time import sleep
from pymongo import MongoClient
import pytz  # Import pytz library for timezone handling

# Load environment variables from .env file
load_dotenv()

# AirVisual API key
API_KEY = os.getenv('API_KEY')

# MongoDB connection settings
MONGO_DB = str(os.getenv('MONGO_DB'))
MONGO_COLLECTION = str(os.getenv('MONGO_COLLECTION'))
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
            aqi_us = data['current']['pollution'].get('aqius', None)
            main_pollutant_us = data['current']['pollution'].get('mainus', None)
            aqi_cn = data['current']['pollution'].get('aqicn', None)
            main_pollutant_cn = data['current']['pollution'].get('maincn', None)
            temperature = data['current']['weather'].get('tp', None)
            pressure = data['current']['weather'].get('pr', None)
            humidity = data['current']['weather'].get('hu', None)
            wind_speed = data['current']['weather'].get('ws', None)
            wind_direction = data['current']['weather'].get('wd', None)
            weather_icon = data['current']['weather'].get('ic', None)
            
            # Set timezone to Eastern Standard Time (EST)
            eastern = pytz.timezone('America/New_York')

            # Get current UTC time
            utc_now = datetime.utcnow()

            # Convert UTC time to EST
            now = utc_now.replace(tzinfo=pytz.utc).astimezone(eastern)
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
            
            # Replace None with 'NA' string
            for key, value in city_data.items():
                if value is None:
                    city_data[key] = 'NA'
            
            return city_data
        
        else:
            print(f"No data available for {city}, {state}")
            return {
                'City': city,
                'State': state,
                'Country': 'USA',
                'AQI (US)': 'NA',
                'Main Pollutant (US)': 'Error',
                'AQI (CN)': 'NA',
                'Main Pollutant (CN)': 'Error',
                'Temperature (°C)': 'NA',
                'Pressure (hPa)': 'NA',
                'Humidity (%)': 'NA',
                'Wind Speed (m/s)': 'NA',
                'Wind Direction (°)': 'NA',
                'Weather Icon': 'Error',
                'Date': date,  # Add date field
                'Time': time   # Add time field
            }
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data for {city}, {state}: {str(e)}")
        now = datetime.now(eastern)
        date = now.strftime("%Y-%m-%d")
        time = now.strftime("%H:%M:%S")
        return {
            'City': city,
            'State': state,
            'Country': 'USA',
            'AQI (US)': 'NA',
            'Main Pollutant (US)': 'Error',
            'AQI (CN)': 'NA',
            'Main Pollutant (CN)': 'Error',
            'Temperature (°C)': 'NA',
            'Pressure (hPa)': 'NA',
            'Humidity (%)': 'NA',
            'Wind Speed (m/s)': 'NA',
            'Wind Direction (°)': 'NA',
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
