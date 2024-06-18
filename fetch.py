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
            current = data['current']
            pollution = current.get('pollution', {})
            weather = current.get('weather', {})
            
            city_data = {
                'City': city,
                'State': state,
                'Country': 'USA',
                'AQI (US)': pollution.get('aqius', -1),
                'Main Pollutant (US)': pollution.get('mainus', 'Error'),
                'AQI (CN)': pollution.get('aqicn', -1),
                'Main Pollutant (CN)': pollution.get('maincn', 'Error'),
                'Temperature (°C)': weather.get('tp', -1),
                'Pressure (hPa)': weather.get('pr', -1),
                'Humidity (%)': weather.get('hu', -1),
                'Wind Speed (m/s)': weather.get('ws', -1),
                'Wind Direction (°)': weather.get('wd', -1),
                'Weather Icon': weather.get('ic', 'Error'),
                'Date': datetime.now().strftime("%Y-%m-%d"),
                'Time': datetime.now().strftime("%H:%M:%S")
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
                'Date': datetime.now().strftime("%Y-%m-%d"),
                'Time': datetime.now().strftime("%H:%M:%S")
            }
        
    except requests.exceptions.RequestException as e:
        print(f"Failed to fetch data for {city}, {state}: {str(e)}")
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
            'Date': datetime.now().strftime("%Y-%m-%d"),
            'Time': datetime.now().strftime("%H:%M:%S")
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
