import json
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
GEOJSON_PATH = DATA_DIR / "togo_regions.geojson"

REGION_SHORT = {
    "Savanes": "Savanes",
    "Kara": "Kara",
    "Centrale": "Centrale",
    "Plateaux": "Plateaux",
    "Maritime": "Maritime",
}

REGION_CENTROIDS = {
    "Savanes": {"lat": 10.47, "lon": 0.32},
    "Kara": {"lat": 9.49, "lon": 0.58},
    "Centrale": {"lat": 8.51, "lon": 0.81},
    "Plateaux": {"lat": 7.40, "lon": 0.83},
    "Maritime": {"lat": 6.54, "lon": 1.48},
}

REGION_SHARES = {
    "Maritime": 0.25,
    "Plateaux": 0.35,
    "Centrale": 0.20,
    "Kara": 0.12,
    "Savanes": 0.08,
}

def load_geojson() -> dict:
    with open(GEOJSON_PATH) as f:
        return json.load(f)

def get_region_map() -> dict:
    geojson = load_geojson()
    mapping = {}
    for feat in geojson["features"]:
        raw = feat["properties"]["shapeName"]
        for k, v in REGION_SHORT.items():
            if k.lower() in raw.lower():
                mapping[raw] = v
                break
        else:
            mapping[raw] = raw.replace(" Region", "")
    return mapping

def get_region_production_data(agri_data: pd.DataFrame, year: int) -> pd.DataFrame:
    total_prod = agri_data[agri_data["Year"] == year]["production_t"].sum()
    records = []
    for region, share in REGION_SHARES.items():
        records.append({
            "region": region,
            "production_t": round(total_prod * share),
            "production_pct": round(share * 100, 1),
        })
    return pd.DataFrame(records)

def get_region_crops(agri_data: pd.DataFrame, region: str, year: int) -> pd.DataFrame:
    share = REGION_SHARES.get(region, 0.1)
    total_prod = agri_data[agri_data["Year"] == year]["production_t"].sum()
    region_total = total_prod * share
    crops = agri_data[agri_data["Year"] == year][["crop", "production_t"]].copy()
    crops["region_prod_t"] = (crops["production_t"] / crops["production_t"].sum() * region_total).round()
    crops = crops.drop(columns=["production_t"]).sort_values("region_prod_t", ascending=False)
    return crops
