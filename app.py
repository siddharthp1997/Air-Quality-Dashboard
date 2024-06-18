import os
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.express as px

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

# MongoDB connection settings
ATLAS_URI = str(os.getenv('ATLAS_URI'))
MONGO_DB = str(os.getenv('MONGO_DB'))
MONGO_COLLECTION = str(os.getenv('MONGO_COLLECTION'))

# Connect to MongoDB
client = MongoClient(ATLAS_URI)
db = client[MONGO_DB]
collection = db[MONGO_COLLECTION]

# Fetch data from MongoDB
data = list(collection.find())

# Close MongoDB connection
client.close()

# Convert data to DataFrame
df = pd.DataFrame(data)

# Streamlit dashboard
st.title("Air Quality Dashboard")

# Show the latest data for each city
st.header("Latest Air Quality Data for Each City")
latest_df = df.sort_values(by=['City', 'Date', 'Time']).groupby('City').tail(1)
st.write(latest_df[['City', 'State', 'Country', 'AQI (US)', 'Main Pollutant (US)', 'AQI (CN)', 'Main Pollutant (CN)',
                    'Temperature (°C)', 'Pressure (hPa)', 'Humidity (%)', 'Wind Speed (m/s)', 'Wind Direction (°)',
                    'Weather Icon', 'Date', 'Time']])

# Dropdown to select a city to see variation
st.header("Variation of Air Quality Data Over Time")
city = st.selectbox("Select a city", df['City'].unique(), index=0)
city_df = df[df['City'] == city]

# Display graphs for all columns
for col in city_df.columns:
    if col not in ['_id', 'City', 'State', 'Country', 'Date', 'Time']:  # Exclude non-numeric columns
        fig = px.line(city_df, x='Date', y=col, title=f'{col} Variation in {city}', markers=True)
        fig.update_layout(xaxis_title='Date', yaxis_title=col)
        st.plotly_chart(fig)
