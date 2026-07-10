import pandas as pd
import numpy as np
import logging
from pathlib import Path
import hashlib

logger = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent.parent / "data"
MARKET_CACHE = DATA_DIR / "togo_market_prices.csv"

USD_XOF = 600.0

BASE_PRICES_FCFA_KG = {
    "Maritime": {
        "maïs": 240, "riz_paddy": 340, "sorgho": 230, "mil": 290,
        "manioc": 150, "igname": 260, "soja": 270, "arachide": 380,
        "palme": 110, "coton": 310, "noix_de_cajou": 440, "café": 850, "cacao": 1050,
    },
    "Plateaux": {
        "maïs": 220, "riz_paddy": 320, "sorgho": 210, "mil": 270,
        "manioc": 120, "igname": 240, "soja": 250, "arachide": 340,
        "palme": 90, "coton": 290, "noix_de_cajou": 380, "café": 750, "cacao": 950,
    },
    "Centrale": {
        "maïs": 260, "riz_paddy": 360, "sorgho": 250, "mil": 300,
        "manioc": 130, "igname": 250, "soja": 280, "arachide": 360,
        "palme": 100, "coton": 300, "noix_de_cajou": 420, "café": 820, "cacao": 1020,
    },
    "Kara": {
        "maïs": 250, "riz_paddy": 350, "sorgho": 240, "mil": 280,
        "manioc": 140, "igname": 230, "soja": 260, "arachide": 350,
        "palme": 95, "coton": 295, "noix_de_cajou": 410, "café": 800, "cacao": 1000,
    },
    "Savanes": {
        "maïs": 290, "riz_paddy": 380, "sorgho": 270, "mil": 320,
        "manioc": 170, "igname": 280, "soja": 290, "arachide": 430,
        "palme": 105, "coton": 330, "noix_de_cajou": 470, "café": 950, "cacao": 1150,
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
                # trend: ~+6%/an nominal en FCFA (inflation + demande)
                trend = 1.0 + offset * 0.06
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
