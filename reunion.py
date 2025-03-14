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
ORS_BASE_URL = "http://localhost:8082/ors"
profile = "foot-walking"          # foot-walking, cycling-regular, etc.
geography = "laReunion"
range_val = 900
interval_val = 300

# Chemin vers shapefile en EPSG:2975
path_carreaux = r"D:\ECOLAB\GD4H\lareunion_carreaux_200m_shp\Filosofi2015_carreaux_200m_shp\Filosofi2015_carreaux_200m_reg04.shp"

# Fichier de sortie .jsonl
output_file = f"out/results_{profile}_{geography}_{range_val}_{interval_val}.jsonl"
os.makedirs("out", exist_ok=True)

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

client = openrouteservice.Client(base_url=ORS_BASE_URL)

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
        lon, lat = round(c.y, 6), round(c.x, 6)
        # Identifiant du carreau
        id_carreau = row.get("Idcar_200m", f"carreau_{idx}")

        try:
            resp = client.isochrones(
                locations=[(lon, lat)],  # OpenRouteService attend (lon, lat) en degrés
                profile=profile,
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

############################################################
# 6) Chargement des équipements BPE et jointure spatiale
############################################################
logging.info("Chargement du fichier BPE et transformation en GeoDataFrame")

# Chemin vers le fichier des équipements
bpe_file = r"D:\ECOLAB\GD4H\data\insee\bpe_unique_Martinique_Reunion.csv"

# Lecture du fichier CSV contenant les équipements BPE
df_bpe = pd.read_csv(bpe_file)

# Transformation en GeoDataFrame (EPSG:4326)
gdf_bpe = gpd.GeoDataFrame(
    df_bpe,
    geometry=gpd.points_from_xy(df_bpe.LONGITUDE, df_bpe.LATITUDE),
    crs="EPSG:4326"
)

logging.info(f"Nombre d'équipements BPE chargés : {len(gdf_bpe)}")

############################################################
# 7) Jointure spatiale entre BPE et isochrones
############################################################
logging.info("Réalisation de la jointure spatiale entre BPE et isochrones")

# Jointure spatiale (left join pour conserver tous les équipements)
joined = gpd.sjoin(gdf_bpe, isochrone_gdf, how="left", predicate="intersects")

# Ajout d'une colonne indiquant si l’équipement est couvert par un isochrone
joined["is_covered"] = joined["Idcar_200m"].notna()

logging.info(f"Nombre d'équipements couverts par un isochrone : {joined['is_covered'].sum()}")

############################################################
# 8) Export des résultats
############################################################
logging.info("Export des résultats")

# Dossier de sortie
output_dir = "out"
os.makedirs(output_dir, exist_ok=True)

# Export en GeoJSON
geojson_path = os.path.join(output_dir, f"bpe_coverage_{profile}_{geography}.geojson")
joined.to_file(geojson_path, driver="GeoJSON")

# Export en CSV
csv_path = os.path.join(output_dir, f"bpe_coverage_{profile}_{geography}.csv")
joined.drop(columns="geometry").to_csv(csv_path, index=False)

logging.info(f"Fichiers exportés :\n - {geojson_path}\n - {csv_path}")




