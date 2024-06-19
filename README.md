# Air-Quality-Dashboard
This Python-based project uses the AirVisual API to fetch real-time air quality data for major US cities. Data is stored in MongoDB and visualized with Streamlit, offering interactive graphs and tables for monitoring AQI, pollutants, and weather conditions. Securely deployed on GitHub, it ensures reliable data access and analysis.

## Features
Fetches air quality data from AirVisual API for major cities in the USA.
Stores fetched data in MongoDB for persistent storage.
Visualizes air quality data using a Streamlit web application.
Automates data fetching and visualization with GitHub Actions every 6 hours.

## Usage
### Prerequisites
Python 3.11 or higher
MongoDB Atlas account (for data storage)
GitHub repository (for code hosting and automation)

### Installation
1. Clone the repository:
   
git clone https://github.com/your-username/air-quality-dashboard.git](https://github.com/siddharthp1997/Air-Quality-Dashboard.git

cd air-quality-dashboard

2. Install dependencies:

pip install -r requirements.txt

3. Set up environment variables:

Create a .env file and add your MongoDB URI and AirVisual API key:

ATLAS_URI=mongodb+srv://your-username:your-password@cluster0.rnvys22.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
API_KEY=your-airvisual-api-key
MONGO_DB=air_quality
MONGO_COLLECTION=city_data

Add these variables to your GitHub repository Secrets for secure access.

4. Running the Scripts

#### Fetch Air Quality Data
To fetch air quality data and store it in MongoDB:
python fetch.py
#### Run Streamlit App
To run the Streamlit app for visualizing air quality data:
streamlit run app.py

## GitHub Actions Workflow
The project includes GitHub Actions workflows for automation:

Fetch Air Quality Data: Fetches data every 6 hours and stores it in MongoDB.
Run Streamlit App: Runs the Streamlit app to display fetched data.

## Live Demo
Explore the live Air Quality Dashboard:

https://air-quality-dashboard-nbx2nvgermtrpweyadgjqh.streamlit.app/?embed_options=show_toolbar,show_padding,show_footer,light_theme,show_colored_line


## Credits
API: AirVisual API by IQAir (https://www.iqair.com/)
Icons: Icons made by Freepik from www.flaticon.com

## License
This project is licensed under the MIT License - see the LICENSE file for details.
