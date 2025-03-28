#!/usr/bin/env python
# coding: utf-8

# In[1]:


import pandas as pd
import geopandas as gpd

path = "/Users/salma/Desktop/met/Filosofi2017_carreaux_200m_met.shp"
france = gpd.read_file(path)
columns = france.columns


# In[8]:


# Charger le shapefile des régions de France 
regions_path = "/Users/salma/Desktop/france_2015/contours-des-regions-francaises-sur-openstreetmap.shp"
regions = gpd.read_file(regions_path)


# In[9]:


print(france.crs)
print(regions.crs)


# In[10]:


regions = regions.to_crs(france.crs)


# In[11]:


regions.columns


# In[12]:


print(regions['nom'].unique())


# In[13]:


# Jointure spatiale pour attribuer chaque carreau à sa région
france_with_regions = gpd.sjoin(france, regions, how="left", predicate="intersects")


# In[14]:


# Vérifier les colonnes après la jointure
print(france_with_regions.columns)


# In[16]:


france_with_regions


# In[16]:


# Définir le chemin de sortie
import os
output_folder = "/Users/salma/Desktop/carreaux_region_2"
os.makedirs(output_folder, exist_ok=True)  # Créer le dossier s'il n'existe pas


# In[17]:


for region_name, group in france_with_regions.groupby("nom"):
    # Remplacer les caractères spéciaux dans les noms de région pour éviter les erreurs de fichier
    safe_region_name = region_name.replace(" ", "_").replace("’", "_").replace("Î", "I").replace("é", "e")
    output_path = os.path.join(output_folder, f"{safe_region_name}.shp")
    group.to_file(output_path)
    print(f"Région {region_name} enregistrée dans {output_path}")

print("Séparation des régions terminée.")


# In[ ]:




