import pandas as pd
import numpy as np
import logging
from pathlib import Path
from src.config import ALL_CROPS

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
WB_CACHE = DATA_DIR / "togo_wb_agriculture.csv"

CROP_YIELD_RATIO = {
    "maïs": 1.0, "riz_paddy": 0.85, "sorgho": 0.65, "mil": 0.50,
    "manioc": 7.5, "igname": 9.0,
    "soja": 0.70, "arachide": 0.65, "palme": 5.0,
    "coton": 0.40, "noix_de_cajou": 0.30, "café": 0.25, "cacao": 0.30,
}

CROP_BASE_SHARE = {
    "maïs": 0.25, "riz_paddy": 0.06, "sorgho": 0.07, "mil": 0.03,
    "manioc": 0.28, "igname": 0.22,
    "soja": 0.03, "arachide": 0.02, "palme": 0.01,
    "coton": 0.02,
    "noix_de_cajou": 0.005, "café": 0.002, "cacao": 0.002,
}

EXPORT_CROPS = {"coton", "noix_de_cajou", "café", "cacao", "soja", "palme"}
EXPORT_PRICE_TREND = {
    "coton": 1800, "noix_de_cajou": 1200, "café": 3500,
    "cacao": 2800, "soja": 450, "palme": 650,
}

CROP_PARAMS = {
    "maïs": {"yield_range": (0.7, 2.2), "price_range": (280, 560)},
    "riz_paddy": {"yield_range": (0.6, 2.0), "price_range": (430, 760)},
    "sorgho": {"yield_range": (0.4, 1.6), "price_range": (270, 520)},
    "mil": {"yield_range": (0.3, 1.3), "price_range": (330, 620)},
    "manioc": {"yield_range": (5.0, 16.0), "price_range": (160, 360)},
    "igname": {"yield_range": (6.0, 18.0), "price_range": (300, 620)},
    "soja": {"yield_range": (0.4, 1.8), "price_range": (400, 700)},
    "arachide": {"yield_range": (0.4, 1.7), "price_range": (450, 850)},
    "palme": {"yield_range": (3.0, 10.0), "price_range": (500, 850)},
    "coton": {"yield_range": (0.25, 1.2), "price_range": (1400, 2200)},
    "noix_de_cajou": {"yield_range": (0.15, 0.9), "price_range": (900, 1600)},
    "café": {"yield_range": (0.15, 0.8), "price_range": (2500, 4500)},
    "cacao": {"yield_range": (0.15, 0.9), "price_range": (2200, 3800)},
}


def _load_wb_agri() -> pd.DataFrame:
    if WB_CACHE.exists():
        return pd.read_csv(WB_CACHE)
    return pd.DataFrame()


def get_togo_agriculture_data() -> pd.DataFrame:
    wb = _load_wb_agri()
    cereal_yield = wb[wb["indicator"] == "cereal_yield_kg_ha"].set_index("Year")["value"] if len(wb) else pd.Series(dtype=float)
    prod_index = wb[wb["indicator"] == "crop_production_index"].set_index("Year")["value"] if len(wb) else pd.Series(dtype=float)
    cereal_prod = wb[wb["indicator"] == "AG.PRD.CREL.MT"].set_index("Year")["value"] if len(wb) else pd.Series(dtype=float)
    rice_prod = wb[wb["indicator"] == "AG.PRD.RICE.MT"].set_index("Year")["value"] if len(wb) else pd.Series(dtype=float)
    food_index = wb[wb["indicator"] == "AG.PRD.FOOD.XD"].set_index("Year")["value"] if len(wb) else pd.Series(dtype=float)

    years = list(range(2000, 2026))
    prod_index_base = prod_index.get(2015, 100)

    cereal_share = CROP_BASE_SHARE.get("maïs", 0.25) + CROP_BASE_SHARE.get("riz_paddy", 0.06) + \
                   CROP_BASE_SHARE.get("sorgho", 0.07) + CROP_BASE_SHARE.get("mil", 0.03)

    records = []
    for crop, params in ALL_CROPS.items():
        cat = params["category"]
        is_cereal = cat == "céréale"
        share = CROP_BASE_SHARE.get(crop, 0.01)
        yield_ratio = CROP_YIELD_RATIO.get(crop, 1.0)

        for year in years:
            yield_val = None
            if is_cereal and year in cereal_yield.index:
                yield_val = cereal_yield.loc[year] * yield_ratio / 1000
            else:
                ref_year = min(year, int(cereal_yield.index.max())) if len(cereal_yield) else year
                base_cy = cereal_yield.get(ref_year, 1100)
                trend = 1.0 + (year - 2000) * 0.003
                yield_val = base_cy * yield_ratio * trend / 1000
            yield_val = max(yield_val, 0.1)

            if crop == "riz_paddy" and year in rice_prod.index:
                prod_est = rice_prod.loc[year]
            elif is_cereal and year in cereal_prod.index:
                cereal_total = cereal_prod.loc[year]
                prod_est = (share / cereal_share) * cereal_total
            elif year in prod_index.index:
                idx_val = prod_index.loc[year]
                prod_est = share * (idx_val / prod_index_base) * 4_500_000
            else:
                last_idx = prod_index.loc[prod_index.index.max()] if len(prod_index) > 0 else 100
                growth = 1 + max(0, (year - int(prod_index.index.max())) * 0.015)
                idx_val = last_idx * growth
                prod_est = share * (idx_val / prod_index_base) * 4_500_000

            prod_est = max(prod_est, 1)
            area_est = prod_est / yield_val / 1000 if yield_val > 0 else prod_est / 1.0
            area_est = max(area_est, 1000)
            price = EXPORT_PRICE_TREND.get(crop, np.nan)

            records.append({
                "Year": year, "crop": crop, "category": cat, "staple": params["staple"],
                "yield_t_ha": round(yield_val, 3), "area_ha": round(area_est),
                "production_t": round(prod_est), "price_usd_t": price,
            })

    df = pd.DataFrame(records)
    df["production_t"] = df["production_t"].astype(float)
    return df


TOGO_PRODUCTION_2023 = {}
CROP_PRODUCTION_2023 = TOGO_PRODUCTION_2023
PIA_TRANSFORMATION_POTENTIAL = {
    "soja": {"taux_transfo": 0.35, "produits": ["huile", "tourteau", "lait"]},
    "coton": {"taux_transfo": 0.60, "produits": ["fibre", "huile", "tourteau"]},
    "noix_de_cajou": {"taux_transfo": 0.25, "produits": ["amande", "coque"]},
    "maïs": {"taux_transfo": 0.30, "produits": ["farine", "alimentation animale", "éthanol"]},
    "manioc": {"taux_transfo": 0.25, "produits": ["farine", "amidon", "gari"]},
    "palme": {"taux_transfo": 0.50, "produits": ["huile raffinée", "savon"]},
    "arachide": {"taux_transfo": 0.30, "produits": ["huile", "pâte", "grignons"]},
}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df = get_togo_agriculture_data()
    logger.info(f"Generated {len(df)} rows")
    for year in [2000, 2010, 2020, 2025]:
        sub = df[df["Year"] == year]
        logger.info(f"{year}: {sub['production_t'].sum()/1e6:.3f}M t total")
        logger.info(f"  Maize: {sub[sub.crop=='maïs']['production_t'].sum()/1e3:.0f}t")
        logger.info(f"  Rice: {sub[sub.crop=='riz_paddy']['production_t'].sum()/1e3:.0f}t")
        logger.info(f"  Cereal yield: {sub[sub['category']=='céréale']['yield_t_ha'].mean():.3f} t/ha")
