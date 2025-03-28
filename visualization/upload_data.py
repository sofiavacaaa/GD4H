# Command line tool to convert .jsonl files to .geojson files
#-----------------------------------------------------
#pv isochrone_file.jsonl | jq -c '
#    . as $item | $item.features[] | .properties += (
#        { "metadata": $item.metadata } +
#        (if $item.bbox then { "carreaux": ($item.bbox | tostring) } else { "carreaux": "null" } end) +
#        (if $item.Idcar_200m then { "Idcar_200m": $item.Idcar_200m } else {} end)
#    )' > ischrone_file.geojson 


import pandas as pd
import geopandas as gpd
import numpy as np
from shapely.geometry import Point, shape, box
from joblib import Parallel, delayed
from tqdm import tqdm
import fiona
import matplotlib.pyplot as plt
from datetime import datetime
import requests
import zipfile
import io
import os
from thefuzz import process
import folium
import sys

REUN_file_path = "carreaus_reun.geojson"
MET_file_path = "/home/onyxia/work/carreaus_met.geojson"
REUN_isochrones_paths = ["results_driving-car_laReunion_900_300.geojson"]
CORSE_isochrones_paths = ["/home/onyxia/work/results_driving-car_corse_900_300.geojson"]
BRETAGNE_isochrones_paths = ["/home/onyxia/work/results_foot-walking_bretagne_900_300.geojson"]
IDF_isochrones_paths = ["results_driving-car_ile-de-france_900_300.geojson"]
PACA_isochrones_paths = ["results_driving-car_paca_900_300.geojson"]
PAYSLOIRE_isochrones_paths = ["results_driving-car_pays-de-la-loire_900_300.geojson"]
CENTLOIRE_isochrones_paths = ["results_driving-car_centre-val-de-loire_900_300.geojson"]
ALSACE_isochrones_paths = ["results_driving-car_alsace_900_300.geojson"]
LORRAINE_isochrones_paths = ["results_driving-car_lorraine_900_300.geojson"]

def compute_score_columns(gdf_grid, gdf_iso, max_jobs=160, threshold=500):
    if len(gdf_grid) < threshold:
        n_jobs = 1
        print(f"🔍 Using single-threaded scoring (grid size={len(gdf_grid)})")
    else:
        n_jobs = min(max_jobs, max(1, len(gdf_grid) // 50))
        print(f"⚡ Using parallel scoring with {n_jobs} jobs (grid size={len(gdf_grid)})")

    def process_chunk(grid_chunk):
        joined = gpd.sjoin(grid_chunk, gdf_iso, predicate="intersects", how="left")
        if joined.empty:
            print("⚠️ No intersections in this chunk.")
        return joined.groupby(["Idcar_200m", "value", "profile"]).size().reset_index(name="score")

    if n_jobs == 1:
        score_counts = process_chunk(gdf_grid)
    else:
        chunks = np.array_split(gdf_grid, n_jobs)
        score_counts_chunks = Parallel(n_jobs=n_jobs)(
            delayed(process_chunk)(chunk) for chunk in chunks
        )
        score_counts = pd.concat(score_counts_chunks)

    score_counts = (
        score_counts
        .groupby(["Idcar_200m", "value", "profile"])["score"]
        .sum()
        .reset_index()
    )
    score_counts["column_name"] = score_counts.apply(
        lambda row: f"score_{row['profile']}_{int(row['value'])}", axis=1
    )

    score_pivot = (
        score_counts.pivot(index="Idcar_200m", columns="column_name", values="score")
        .fillna(0)
        .astype(int)
    )
    score_pivot.columns.name = None
    return score_pivot

def download_bpe():
    zip_url = 'https://www.insee.fr/fr/statistiques/fichier/8217525/BPE23.zip'
    response = requests.get(zip_url)
    with zipfile.ZipFile(io.BytesIO(response.content)) as z:
        file_name = z.namelist()[0]
        with z.open(file_name) as csv_file:
            df_bpe = pd.read_csv(csv_file, delimiter=';')
    df_bpe.rename(columns={'LATITUDE': "latitude", 'LONGITUDE': "longitude", "NOMRS": "location", "DOM": "category"}, inplace=True)
    df_bpe = df_bpe.filter(items=["latitude", "longitude", "location", "category"])
    return df_to_geo(df_bpe)

def df_to_geo(df):
    df["geometry"] = df.apply(lambda row: Point(row["longitude"], row["latitude"]), axis=1)
    return gpd.GeoDataFrame(df, geometry="geometry", crs="EPSG:4326")

def download_carreaus():
    if os.path.exists(MET_file_path):
        carreaus_geo = gpd.read_file(MET_file_path)
    else:
        raise FileNotFoundError("MET_file_path not found")

    if "updated_at" not in carreaus_geo.columns:
        carreaus_geo["updated_at"] = np.nan

    carreaus_geo["longitude"] = carreaus_geo.geometry.centroid.x
    carreaus_geo["latitude"] = carreaus_geo.geometry.centroid.y
    return carreaus_geo

def process_isochrone_file(path, gdf):
    features = []
    print("# Unpack nested columns - a")
    with fiona.open(path) as src:
        print(f"🔍 Total features in file: {len(src)}")
        crs = src.crs
        for feature in src:
            properties = feature["properties"]
            geometry = shape(feature["geometry"])
            metadata = properties.get("metadata", {})
            query = metadata.get("query", {})
            flat_properties = {
                "value": properties.get("value"),
                "Idcar_200m": properties.get("Idcar_200m"),
                "profile": query.get("profile"),
                "locations": query.get("locations"),
                "geometry": geometry
            }
            features.append(flat_properties)

    gdf_iso = gpd.GeoDataFrame(features, crs=crs)
    gdf_iso = gdf_iso[gdf_iso.is_valid & ~gdf_iso.is_empty]

    if gdf_iso.empty:
        return gpd.GeoDataFrame()

    score_pivot = compute_score_columns(gdf, gdf_iso)
    gdf_iso_unique = gdf_iso.drop_duplicates(subset="Idcar_200m").set_index("Idcar_200m")
    return gdf_iso_unique.join(score_pivot, how="left").fillna(0)

def map_carreaus_osrm_local(carr_geo, gdf):
    results = [process_isochrone_file(path, gdf) for path in tqdm(LORRAINE_isochrones_paths, desc="Isochrones")]

    partial_concats = [df for df in results if not df.empty]
    if not partial_concats:
        raise ValueError("All partial chunks are empty!")

    df = pd.concat(partial_concats, ignore_index=True)

    df[['lon', 'lat']] = pd.DataFrame(
        df['locations'].apply(lambda x: x[0] if isinstance(x, list) and len(x) > 0 else [None, None]).tolist(),
        index=df.index
    )
    df['lon'] = df['lon'].apply(lambda x: round(x, 6))
    df['lat'] = df['lat'].apply(lambda x: round(x, 6))

    carr_geo['lon'] = carr_geo['longitude'].apply(lambda x: round(x, 6))
    carr_geo['lat'] = carr_geo['latitude'].apply(lambda x: round(x, 6))
    carr_geo = carr_geo[['Ind', 'Men', 'Log_soc', 'lat', 'lon', 'geometry']]

    carr_geo_subset = carr_geo[
        carr_geo.set_index(['lat', 'lon']).index.isin(df.set_index(['lat', 'lon']).index)
    ].copy()

    print("Before merge:", len(df), len(carr_geo_subset))
    merged = df.merge(
        carr_geo_subset, on=['lat', 'lon'], how='inner', validate='one_to_one'
    )
    print("After merge:", len(merged))

    merged = gpd.GeoDataFrame(merged, geometry="geometry_y", crs="EPSG:4326")
    merged = merged.drop(columns="geometry_x")

    example_column = next((col for col in merged.columns if col.startswith("score_")), None)
    if example_column:
        fig, ax = plt.subplots(figsize=(15, 15))
        merged.plot(column=example_column, ax=ax, cmap="OrRd", edgecolor="black", legend=True, alpha=0.7)
        ax.set_xlabel("Longitude")
        ax.set_ylabel("Latitude")
        ax.set_aspect("equal")
        plt.title(f"Carreaux - {example_column}")
        plt.show()

    return merged

#m = folium.Map(location=[2.3522, 48.8566], zoom_start=12)

#folium.GeoJson(isochrone_gdf, style_function=lambda x: {"color": "blue"}).add_to(m)

#df_user = accept_user_file()
#def calculate_carreaus(df_user, weight_1, weight_2):
#identify_lat_long(df_user)
#df_user_geo = df_to_geo(df_user)
df_bpe = download_bpe()
carreaus = download_carreaus()
carreaus_copy = carreaus.copy()
combined_carreaus = map_carreaus_osrm_local(carreaus_copy, df_bpe)
    
combined_carreaus.to_file("/home/onyxia/work/lorraine_car.geojson", driver="GeoJSON")


        
