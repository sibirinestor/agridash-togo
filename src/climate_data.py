import requests
import pandas as pd
import numpy as np
from pathlib import Path

DATA_DIR = Path(__file__).parent.parent / "data"
CACHE_FILE = DATA_DIR / "togo_climate_nasa_power.csv"

TOGO_REGIONS = {
    "Maritime": {"lat": 6.3, "lon": 1.5},
    "Plateaux": {"lat": 7.5, "lon": 1.1},
    "Centrale": {"lat": 8.5, "lon": 1.0},
    "Kara": {"lat": 9.5, "lon": 1.2},
    "Savanes": {"lat": 10.5, "lon": 0.5},
}

DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


def _days_in_month(year: int, month: int) -> int:
    if month == 2 and (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)):
        return 29
    return DAYS_IN_MONTH[month - 1]


def fetch_nasa_power(lat: float, lon: float, start: int = 2000, end: int = 2024) -> dict:
    base = "https://power.larc.nasa.gov/api/temporal/monthly/point"
    params = {
        "parameters": "PRECTOTCORR,T2M",
        "community": "AG",
        "longitude": lon,
        "latitude": lat,
        "start": str(start),
        "end": str(end),
        "format": "JSON",
    }
    r = requests.get(base, params=params, timeout=30)
    r.raise_for_status()
    data = r.json()
    return data["properties"]["parameter"]


def _cache_climate_data():
    records = []
    for region, coord in TOGO_REGIONS.items():
        try:
            params = fetch_nasa_power(coord["lat"], coord["lon"])
            precip_raw = params["PRECTOTCORR"]
            temp_raw = params["T2M"]

            years = set()
            for k in precip_raw:
                y = int(str(k)[:4])
                if 2000 <= y <= 2025:
                    years.add(y)

            for year in sorted(years):
                annual_precip = 0
                annual_temp = 0
                count = 0
                for m in range(1, 13):
                    key = f"{year}{str(m).zfill(2)}"
                    dim = _days_in_month(year, m)
                    if key in precip_raw:
                        annual_precip += precip_raw[key] * dim
                    if key in temp_raw:
                        annual_temp += temp_raw[key]
                        count += 1
                if count > 0:
                    annual_temp /= count
                records.append({
                    "Year": year,
                    "Region": region,
                    "precip_mm": round(annual_precip, 1),
                    "temp_c": round(annual_temp, 2),
                })
        except Exception as e:
            print(f"  Warning: NASA POWER failed for {region}: {e}")

    df = pd.DataFrame(records)
    national = df.groupby("Year").agg(
        precip_mm=("precip_mm", "mean"),
        temp_c=("temp_c", "mean"),
    ).reset_index()
    national["Region"] = "National"
    result = pd.concat([df, national], ignore_index=True)
    result = result.sort_values(["Region", "Year"]).reset_index(drop=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    result.to_csv(CACHE_FILE, index=False)
    return result


def get_togo_climate_data() -> pd.DataFrame:
    if CACHE_FILE.exists():
        df = pd.read_csv(CACHE_FILE)
        if len(df) > 0:
            return df
    return _cache_climate_data()
