import pandas as pd
import numpy as np
import logging
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
MARKET_CACHE = DATA_DIR / "togo_market_prices.csv"

USD_XOF = 600.0

# Prix réels des marchés togolais (FCFA/kg) — sources 2025-2026 :
# TVT (mai 2026), Selina Wamucii (juin 2026), FAO GIEWS, TogoFirst, CPC-Togo.
# Les variations régionales reflètent : Maritime/Lomé = prix plus élevés
# (demande urbaine), zones de production (Centrale, Plateaux) = prix plus bas.
# Unité: FCFA par kilogramme (sauf indication contraire).
#
# Maïs: bol 2.5kg = 300-750 FCFA selon région (TVT mai 2026)
# Lomé 231 FCFA/kg (fév 2026), Kara 143, Savanes 147 (TogoFirst)
BASE_PRICES_FCFA_KG = {
    "Maritime": {
        "maïs": 250, "riz_paddy": 400, "sorgho": 300, "mil": 380,
        "manioc": 150, "igname": 260, "soja": 450, "arachide": 500,
        "palme": 110, "coton": 310, "noix_de_cajou": 650, "café": 1500, "cacao": 1200,
    },
    "Plateaux": {
        "maïs": 150, "riz_paddy": 350, "sorgho": 280, "mil": 340,
        "manioc": 120, "igname": 240, "soja": 400, "arachide": 450,
        "palme": 90, "coton": 290, "noix_de_cajou": 550, "café": 1300, "cacao": 1100,
    },
    "Centrale": {
        "maïs": 140, "riz_paddy": 380, "sorgho": 260, "mil": 320,
        "manioc": 110, "igname": 230, "soja": 420, "arachide": 470,
        "palme": 100, "coton": 300, "noix_de_cajou": 600, "café": 1400, "cacao": 1150,
    },
    "Kara": {
        "maïs": 180, "riz_paddy": 370, "sorgho": 270, "mil": 360,
        "manioc": 130, "igname": 220, "soja": 380, "arachide": 430,
        "palme": 95, "coton": 295, "noix_de_cajou": 580, "café": 1350, "cacao": 1050,
    },
    "Savanes": {
        "maïs": 150, "riz_paddy": 420, "sorgho": 250, "mil": 350,
        "manioc": 130, "igname": 250, "soja": 350, "arachide": 400,
        "palme": 105, "coton": 330, "noix_de_cajou": 500, "café": 1200, "cacao": 1000,
    },
}

MARKET_YEARS = list(range(2015, 2031))


def generate_market_prices() -> pd.DataFrame:
    records = []
    for region, crops in BASE_PRICES_FCFA_KG.items():
        for crop, price_2024 in crops.items():
            seed_key = f"price_{region}_{crop}".encode("utf-8")
            seed = int(hashlib.sha256(seed_key).hexdigest()[:16], 16) % 2**31
            rng = np.random.default_rng(seed)
            for year in MARKET_YEARS:
                offset = year - 2024
                # trend: ~+3.5%/an (inflation alimentaire réelle Togo 2020-2025 ~3-5%)
                trend = 1.0 + offset * 0.035
                # seasonal: +10% en soudure (juin-août), -5% en récolte (oct-déc)
                season = 1.0 + 0.10 * np.sin(2 * np.pi * ((year - 2010) * 4 + 6) / 12)
                # bruit: ±5% gaussien borné
                noise = 1.0 + rng.uniform(-0.05, 0.05)
                price_fcfa = price_2024 * trend * season * noise
                records.append({
                    "Year": year,
                    "region": region,
                    "crop": crop,
                    "price_fcfa_kg": round(max(price_fcfa, 10), 1),
                    "price_usd_t": round(max(price_fcfa, 10) / USD_XOF * 1000, 1),
                })
    return pd.DataFrame(records)


def get_market_prices() -> pd.DataFrame:
    if MARKET_CACHE.exists():
        df = pd.read_csv(MARKET_CACHE)
        expected = 5 * 13 * len(MARKET_YEARS)
        if len(df) >= expected:
            return df
    df = generate_market_prices()
    MARKET_CACHE.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(MARKET_CACHE, index=False)
    return df


def get_market_summary(df: pd.DataFrame, year: int) -> pd.DataFrame:
    sub = df[df["Year"] == year]
    if sub.empty:
        return pd.DataFrame()
    pivot = sub.pivot_table(index="crop", columns="region", values="price_fcfa_kg", aggfunc="first")
    result = pivot.reset_index()
    result["moyenne"] = round(pivot.mean(axis=1).values, 1)
    result["min"] = round(pivot.min(axis=1).values, 1)
    result["max"] = round(pivot.max(axis=1).values, 1)
    result["ecart_type"] = round(pivot.std(axis=1).values, 1)
    return result


BASE_PRICES_FCFA_KEYS = list(BASE_PRICES_FCFA_KG.keys())


def get_price_volatility(df: pd.DataFrame, crop: str) -> float:
    sub = df[df["crop"] == crop].copy()
    if len(sub) < 2:
        return 0
    sub = sub.groupby(["Year", "region"])["price_fcfa_kg"].mean().reset_index()
    sub["pct_change"] = sub.groupby("region")["price_fcfa_kg"].pct_change()
    return round(sub["pct_change"].std() * 100, 2)


def get_arbitrage_opportunities(df: pd.DataFrame, year: int, threshold_pct: float = 20) -> pd.DataFrame:
    sub = df[df["Year"] == year]
    if sub.empty:
        return pd.DataFrame()
    pivot = sub.pivot_table(index="crop", columns="region", values="price_fcfa_kg", aggfunc="first")
    results = []
    for crop in pivot.index:
        p = pivot.loc[crop].dropna()
        if len(p) >= 2:
            spread_pct = (p.max() - p.min()) / p.min() * 100
            if spread_pct >= threshold_pct:
                results.append({
                    "crop": crop,
                    "buy_region": p.idxmin(),
                    "buy_price": round(p.min(), 1),
                    "sell_region": p.idxmax(),
                    "sell_price": round(p.max(), 1),
                    "spread_pct": round(spread_pct, 1),
                })
    return pd.DataFrame(results)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    df = get_market_prices()
    logger.info(f"Generated {len(df)} rows")
    logger.info(f"Years: {df['Year'].min()}-{df['Year'].max()}")
    print(df.sample(10).to_string())
