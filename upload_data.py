import tkinter as tk
from tkinter import filedialog
import pandas as pd
import sys
import zipfile
import io
import requests
import openrouteservice
import geopandas as gpd
from shapely.geometry import Point, Polygon
import folium

API_KEY = "5b3ce3597851110001cf6248e1c21942e51e45a9ba5e6081a595bc3d"  # Replace with your actual key
client = openrouteservice.Client(key=API_KEY)

center_point = [2.3522, 48.8566]

def accept_user_file():
    root = tk.Tk()
    root.withdraw()
    file_path = filedialog.askopenfilename(title="Select a file", filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt")])
    
    if not file_path:
        sys.exit()
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    elif file_path.endswith('.txt'):
        df = pd.read_csv(file_path, delimiter="\t")
    else:
        raise ValueError("Unsupported file format. Please provide a .csv or .txt file.")
    return df

def identify_lat_long(df):
    predefined_lat = ['latitude', 'lat', 'lattitude', 'latitide', 'latitude_fr']
    predefined_lon = ['longitude', 'long', 'lng', 'longtitude', 'longitude_fr']

    lat_candidates = [col for col in df_user_add.columns if col.lower() in predefined_lat]
    lon_candidates = [col for col in df_user_add.columns if col.lower() in predefined_lon]

    if not lat_candidates:
        lat_candidates = [col for col in df_user_add.columns if pd.api.types.is_numeric_dtype(df_user_add[col]) and df_user_add[col].apply(lambda x: -90 <= float(x) <= 90 if pd.notna(x) else False).any()]
        
    if not lon_candidates:
        lon_candidates = [col for col in df_user_add.columns if pd.api.types.is_numeric_dtype(df_user_add[col]) and df_user_add[col].apply(lambda x: -180 <= float(x) <= 180 if pd.notna(x) else False).any()]

    if len(lat_candidates) == 1 and len(lon_candidates) == 1:
        df_user_add.rename(columns={lat_candidates[0]: 'latitude', lon_candidates[0]: 'longitude'}, inplace=True)
        
    else:
       print("Potential Latitude columns: ", lat_candidates)
       print("Potential Longitude columns: ", lon_candidates)

       lat_column = input("Please select the correct Latitude column from the options above: ")
       lon_column = input("Please select the correct Longitude column from the options above: ")

       if lat_column not in lat_candidates or lon_column not in lon_candidates:
           raise ValueError("Selected columns do not match the identified candidates.")

       df_user_add.rename(columns={lat_column: 'latitude', lon_column: 'longitude'}, inplace=True)

def download_bpe():
    zip_url = 'https://www.insee.fr/fr/statistiques/fichier/8217525/BPE23.zip'

    response = requests.get(zip_url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        file_name = z.namelist()[0]
        with z.open(file_name) as csv_file:
            df_bpe = pd.read_csv(csv_file, delimiter = ';')
    df_bpe["geometry"] = df_bpe.apply(lambda row: Point(row["longitude"], row["latitude"]), axis=1)
    return df_bpe


isochrone = client.isochrones(
    locations=[center_point],  # Paris
    profile="driving-car",
    range=[300],  # 5, 10, 15 min in seconds
)

m = folium.Map(location=[2.3522, 48.8566], zoom_start=12)

isochrone_polygon = Polygon(isochrone["features"][0]["geometry"]["coordinates"][0])

folium.GeoJson(isochrone_polygon, name="Isochrone").add_to(m)

df_user_add = accept_user_file()
identify_lat_long(df_user_add)
df_bpe = download_bpe()
gdf = gpd.GeoDataFrame(df_bpe, geometry="geometry", crs="EPSG:4326")
points_within_isochrone = gdf[gdf.geometry.within(isochrone_polygon)]

for idx, row in points_within_isochrone.iterrows():
    folium.Marker(
        location=[row["latitude"], row["longitude"]],
        popup=row["name"],
        icon=folium.Icon(color="blue", icon="info-sign")
    ).add_to(m)
    
m.save("isochrone_map.html")
        

        