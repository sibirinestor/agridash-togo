import pandas as pd
import numpy as np
from pathlib import Path
from src.config import (
    RAW_DATA_DIR, PROCESSED_DATA_DIR, TOGO_COUNTRY_NAME,
    TOGO_COUNTRY_CODE, STRATEGIC_CROPS, WB_INDICATORS
)


def load_world_bank_data(indicator_key: str) -> pd.DataFrame:
    dir_map = {
        "inflation": "API_FP.CPI.TOTL.ZG_DS2_fr_csv_v2_9735",
        "gdp": "API_NY.GDP.MKTP.CD_DS2_fr_csv_v2_499",
    }
    if indicator_key not in dir_map:
        raise ValueError(f"Indicator '{indicator_key}' not found. Available: {list(dir_map.keys())}")

    data_dir = Path(__file__).parent.parent / dir_map[indicator_key]
    csv_file = list(data_dir.glob("API_*.csv"))[0]

    df = pd.read_csv(csv_file, skiprows=4)

    id_vars = ["Country Name", "Country Code", "Indicator Name", "Indicator Code"]
    year_cols = [c for c in df.columns if c not in id_vars]

    df_long = df.melt(
        id_vars=id_vars,
        value_vars=year_cols,
        var_name="Year",
        value_name="Value"
    )
    df_long["Year"] = pd.to_numeric(df_long["Year"], errors="coerce")
    df_long["Value"] = pd.to_numeric(df_long["Value"], errors="coerce")
    df_long = df_long.dropna(subset=["Value"])
    return df_long


def get_togo_data(indicator_key: str) -> pd.DataFrame:
    df = load_world_bank_data(indicator_key)
    togo = df[
        (df["Country Code"] == TOGO_COUNTRY_CODE) |
        (df["Country Name"] == TOGO_COUNTRY_NAME)
    ].copy()
    return togo.sort_values("Year")


def get_west_africa_countries() -> list:
    wa_codes = [
        "BEN", "BFA", "CPV", "CIV", "GMB", "GHA", "GIN",
        "GNB", "LBR", "MLI", "MRT", "NER", "NGA", "SEN",
        "SLE", "TGO",
    ]
    return wa_codes


def get_wa_comparison(indicator_key: str) -> pd.DataFrame:
    df = load_world_bank_data(indicator_key)
    wa_codes = get_west_africa_countries()
    wa = df[df["Country Code"].isin(wa_codes)].copy()
    return wa.sort_values(["Country Name", "Year"])


def load_wb_agri_cache() -> pd.DataFrame:
    cache_path = Path(__file__).parent.parent / "data" / "togo_wb_agriculture.csv"
    if cache_path.exists():
        return pd.read_csv(cache_path)
    return pd.DataFrame()


def load_all_togo_data() -> dict:
    agri_wb = load_wb_agri_cache()
    crop_idx = agri_wb[agri_wb["indicator"] == "crop_production_index"] if len(agri_wb) else pd.DataFrame()

    return {
        "inflation": get_togo_data("inflation"),
        "gdp": get_togo_data("gdp"),
        "agri_wb": agri_wb,
        "crop_index": crop_idx,
    }


def summary_stats(df: pd.DataFrame, value_col: str = "Value") -> pd.DataFrame:
    return df[value_col].describe().to_frame().T
