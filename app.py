import os
import streamlit as st
from pymongo import MongoClient
import pandas as pd
import plotly.express as px
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MongoDB connection settings
ATLAS_URI = os.getenv('ATLAS_URI')
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

# Weather icon mapping (example, you need to have these images)
icon_mapping = {
    '01d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/01d.png', 'Clear sky (day)'),
    '01n': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/01n.png', 'Clear sky (night)'),
    '02d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/02d.png', 'Few clouds (day)'),
    '02n': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/02n.png', 'Few clouds (night)'),
    '03d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/03d.png', 'Scattered clouds'),
    '04d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/04d.png', 'Broken clouds'),
    '09d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/09d.png', 'Shower rain'),
    '10d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/10d.png', 'Rain (day time)'),
    '10n': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/10n.png', 'Rain (night time)'),
    '11d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/11d.png', 'Thunderstorm'),
    '13d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/13d.png', 'Snow'),
    '50d': ('https://github.com/siddharthp1997/Air-Quality-Dashboard/blob/8983373f0950fea44865a1b3cfa58f67e166df57/Images/50d.png', 'Mist'),
}

# Replace Weather Icon codes with image URLs and descriptions
df['Weather Icon URL'] = df['Weather Icon'].map(lambda x: icon_mapping[x][0] if x in icon_mapping else None)
df['Weather Icon Description'] = df['Weather Icon'].map(lambda x: icon_mapping[x][1] if x in icon_mapping else 'Error')

# Streamlit dashboard
st.title("Air Quality Dashboard")

# Show the latest data for each city
st.header("Latest Air Quality Data for Each City")
latest_df = df.sort_values(by=['City', 'Date', 'Time']).groupby('City').tail(1)

# Filter out rows with '-1' or 'Error'
filtered_latest_df = latest_df.replace({'-1': pd.NA, 'Error': pd.NA}).dropna()

# Display the latest data for each city with images and descriptions
for index, row in filtered_latest_df.iterrows():
    st.write(f"**City:** {row['City']}")
    st.write(f"**State:** {row['State']}")
    st.write(f"**Country:** {row['Country']}")
    st.write(f"**AQI (US):** {row['AQI (US)']}")
    st.write(f"**Main Pollutant (US):** {row['Main Pollutant (US)']}")
    st.write(f"**AQI (CN):** {row['AQI (CN)']}")
    st.write(f"**Main Pollutant (CN):** {row['Main Pollutant (CN)']}")
    st.write(f"**Temperature (°C):** {row['Temperature (°C)']}")
    st.write(f"**Pressure (hPa):** {row['Pressure (hPa)']}")
    st.write(f"**Humidity (%):** {row['Humidity (%)']}")
    st.write(f"**Wind Speed (m/s):** {row['Wind Speed (m/s)']}")
    st.write(f"**Wind Direction (°):** {row['Wind Direction (°)']}")
    if row['Weather Icon URL'] and pd.notna(row['Weather Icon URL']):
        st.image(row['Weather Icon URL'], caption=row['Weather Icon Description'])
    st.write(f"**Date:** {row['Date']}")
    st.write(f"**Time:** {row['Time']}")
    st.write("---")

# Dropdown to select a city to see variation
st.header("Variation of Air Quality Data Over Time")
city = st.selectbox("Select a city", df['City'].unique(), index=0)
city_df = df[df['City'] == city]

# Display graphs for all columns
for col in city_df.columns:
    if col not in ['_id', 'City', 'State', 'Country', 'Date', 'Time', 'Weather Icon', 'Weather Icon URL', 'Weather Icon Description']:  # Exclude non-numeric columns and icon columns
        filtered_city_df = city_df.replace({'-1': pd.NA, 'Error': pd.NA}).dropna(subset=[col])
        if not filtered_city_df.empty:
            fig = px.line(filtered_city_df, x='Date', y=col, title=f'{col} Variation in {city}', markers=True)
            fig.update_layout(xaxis_title='Date', yaxis_title=col)
            
            # Add weather icons to the plot
            for i, row in filtered_city_df.iterrows():
                if row['Weather Icon URL'] and pd.notna(row['Weather Icon URL']):
                    fig.add_layout_image(
                        dict(
                            source=row['Weather Icon URL'],
                            x=row['Date'],
                            y=row[col],
                            xref="x",
                            yref="y",
                            sizex=0.1,
                            sizey=0.1,
                            xanchor="center",
                            yanchor="middle"
                        )
                    )
            st.plotly_chart(fig)
