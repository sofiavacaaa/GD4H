import os
import json
import logging
import pandas as pd
import geopandas as gpd
import geopandas as gpd
import openrouteservice
from shapely.geometry import shape
from tqdm import tqdm

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

############################################################
# 1) Paramètres
############################################################
profile = "driving-car"          # foot-walking, cycling-regular, etc.
geography = "Aquitaine"
range_val = 900
interval_val = 300

ORS_URL = "http://localhost:8082/ors"

# Chemin vers shapefile en EPSG:2975
path_carreaux = r"D:\ECOLAB\anciennes_regions\Aquitaine\Aquitaine.shp"

# Fichier de sortie .jsonl
output_dir = "C:\\Users\\selaazdo-24\\Desktop\\out"
os.makedirs(output_dir, exist_ok=True)
output_file = f"{output_dir}\\results_{profile}_{geography}_{range_val}_{interval_val}.jsonl"


############################################################
# 2) Lecture du shapefile (EPSG:2975) et reprojection en EPSG:4326
############################################################
logging.info("Lecture du shapefile et reprojection vers EPSG:4326")
carreaus = gpd.read_file(path_carreaux)
# Reprojection -> EPSG:4326
carreaus = carreaus.to_crs(epsg=4326)

# Calcul du centroïde en WGS84
carreaus["centroid"] = carreaus.geometry.centroid
logging.info(f"Carreaux chargés : {len(carreaus)} lignes.")

############################################################
# 3) Initialisation du client ORS et vérification range
############################################################
try:
    range_val = int(range_val)
    interval_val = int(interval_val)
except Exception as exc:
    logging.error(f"Range et interval doivent être numériques. Erreur: {exc}")
    exit(1)

client = openrouteservice.Client(base_url=ORS_URL)

############################################################
# 4) Boucle : calcul des isochrones et écriture dans JSONL
############################################################
logging.info("Génération des isochrones (lon, lat)")
with open(output_file, "w", encoding="utf-8") as f_out:
    for idx, row in tqdm(carreaus.iterrows(), total=len(carreaus), desc="Isochrones"):
        c = row["centroid"]
        if c.is_empty:
            continue

        # (lon, lat) = (y, x) en EPSG:4326
        lon, lat = round(c.x, 6), round(c.y, 6)
        # Identifiant du carreau
        id_carreau = row.get("Idcar_200m", f"carreau_{idx}")

        try:
            resp = client.isochrones(
                locations=[(lon, lat)],  # OpenRouteService attend (lon, lat) en degrés
                range=[range_val],
                interval=interval_val
            )
            resp["Idcar_200m"] = id_carreau
            f_out.write(json.dumps(resp) + "\n")

        except Exception as e:
            logging.error(f"Erreur carreau={id_carreau}, coords=({lon},{lat}): {e}")

logging.info(f"Isochrones terminées, fichier généré : {output_file}")

############################################################
# 5) Lecture du fichier JSONL et construction du GeoDataFrame
############################################################
logging.info("Lecture du fichier .jsonl et construction du GDF (EPSG:4326)")
records = []
with open(output_file, "r", encoding="utf-8") as f_in:
    for line in f_in:
        rec = json.loads(line.strip())
        records.append(rec)

df_iso = pd.DataFrame(records)

all_features = []
for _, r in df_iso.iterrows():
    if "features" in r:
        for feat in r["features"]:
            feat["Idcar_200m"] = r.get("Idcar_200m", None)
            all_features.append(feat)

df_feats = pd.DataFrame(all_features)
df_feats["geometry"] = df_feats["geometry"].apply(lambda g: shape(g))

# Les isochrones d’ORS sont déjà en WGS84
isochrone_gdf = gpd.GeoDataFrame(df_feats, geometry="geometry", crs="EPSG:4326")
isochrone_gdf["profile"] = profile

logging.info(f"Isochrone_gdf construit avec {len(isochrone_gdf)} features !")
print(isochrone_gdf.head())