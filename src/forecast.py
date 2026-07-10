import pandas as pd
import numpy as np
import logging
from pathlib import Path
import hashlib
import os
import tempfile

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "matplotlib"))

logger = logging.getLogger(__name__)

try:
    from prophet import Prophet
except ImportError:
    Prophet = None

from src.agriculture_data import get_togo_agriculture_data, CROP_PARAMS
from src.climate_data import get_togo_climate_data
from src.config import ALL_CROPS, DATA_DIR

FORECAST_YEARS = list(range(2025, 2031))
CACHE_FILE = DATA_DIR / "togo_forecasts.csv"


def _train_prophet(y: np.ndarray, years: np.ndarray):
    if Prophet is None:
        raise RuntimeError("Prophet is not installed")
    df = pd.DataFrame({"ds": pd.to_datetime(years, format="%Y"), "y": y})
    m = Prophet(
        changepoint_prior_scale=0.3,
        seasonality_prior_scale=0.1,
        yearly_seasonality=False,
        weekly_seasonality=False,
        daily_seasonality=False,
    )
    m.add_seasonality(name="decade", period=10, fourier_order=3)
    m.add_seasonality(name="cycle_5yr", period=5, fourier_order=2)
    m.fit(df)
    return m


def _predict_prophet(m: Prophet, years: list) -> pd.DataFrame:
    future = pd.DataFrame({"ds": pd.to_datetime(years, format="%Y")})
    fcst = m.predict(future)
    return fcst


def _predict_trend(y: np.ndarray, years: np.ndarray, future_years: list) -> pd.DataFrame:
    degree = 2 if len(years) >= 8 else 1
    coeffs = np.polyfit(years, y, degree)
    model = np.poly1d(coeffs)
    fitted = model(years)
    residual_std = float(np.std(y - fitted)) if len(y) > degree + 1 else 0.0
    residual_std = max(residual_std, float(np.mean(y)) * 0.05)
    yhat = model(np.asarray(future_years))
    yhat = np.maximum(yhat, 0.01)
    return pd.DataFrame({
        "ds": pd.to_datetime(future_years, format="%Y"),
        "yhat": yhat,
        "yhat_lower": np.maximum(yhat - residual_std, 0.01),
        "yhat_upper": yhat + residual_std,
    })


def _forecast_yields(yields: np.ndarray, years: np.ndarray) -> pd.DataFrame:
    if Prophet is not None:
        model = _train_prophet(yields, years)
        return _predict_prophet(model, FORECAST_YEARS)
    return _predict_trend(yields, years, FORECAST_YEARS)


def _rng_for(*parts: str) -> np.random.Generator:
    seed_key = "|".join(parts).encode("utf-8")
    seed = int(hashlib.sha256(seed_key).hexdigest()[:16], 16) % 2**31
    return np.random.default_rng(seed)


def _apply_climate_scenario(
    base_fcst: pd.DataFrame, scenario: str,
) -> pd.DataFrame:
    fcst = base_fcst.copy()
    if scenario == "optimiste":
        fcst["yhat"] = fcst["yhat"] * 1.12
        fcst["yhat_lower"] = fcst["yhat_lower"] * 1.08
        fcst["yhat_upper"] = fcst["yhat_upper"] * 1.15
    elif scenario == "pessimiste":
        fcst["yhat"] = fcst["yhat"] * 0.85
        fcst["yhat_lower"] = fcst["yhat_lower"] * 0.80
        fcst["yhat_upper"] = fcst["yhat_upper"] * 0.90
    return fcst


def generate_forecasts(use_cache: bool = True) -> pd.DataFrame:
    if use_cache and CACHE_FILE.exists():
        df = pd.read_csv(CACHE_FILE)
        if len(df) > 0:
            return df

    agri = get_togo_agriculture_data()
    climate = get_togo_climate_data()
    natl = climate[climate["Region"] == "National"]

    records = []
    for crop in sorted(ALL_CROPS):
        df_crop = agri[agri["crop"] == crop].copy()
        if len(df_crop) < 5:
            continue

        df_crop = df_crop.sort_values("Year")
        years = df_crop["Year"].values
        yields = df_crop["yield_t_ha"].values

        try:
            fcst = _forecast_yields(yields, years)

            for scenario in ["modéré", "optimiste", "pessimiste"]:
                sfcst = _apply_climate_scenario(fcst, scenario) if scenario != "modéré" else fcst
                params = CROP_PARAMS.get(crop, {
                    "yield_range": (max(float(yields.min()) * 0.5, 0.01), float(yields.max()) * 1.5),
                    "price_range": (200, 1000),
                })
                base_yield = yields[-1]
                base_area = df_crop["area_ha"].values[-1]
                rng = _rng_for(crop, scenario)

                for i, year in enumerate(FORECAST_YEARS):
                    yhat = sfcst.iloc[i]["yhat"]
                    yhat = max(yhat, params["yield_range"][0] * 0.5)

                    area_growth = 1.0 + (i / len(FORECAST_YEARS)) * 0.08
                    area = base_area * area_growth * rng.uniform(0.95, 1.05)

                    price = rng.uniform(params["price_range"][0], params["price_range"][1])
                    price_trend = price * (1 + i * 0.02)

                    production = yhat * area

                    records.append({
                        "Year": year,
                        "crop": crop,
                        "category": ALL_CROPS[crop]["category"],
                        "staple": ALL_CROPS[crop]["staple"],
                        "scenario": scenario,
                        "yield_t_ha": round(yhat, 3),
                        "yield_lower": round(max(sfcst.iloc[i]["yhat_lower"], params["yield_range"][0] * 0.3), 3),
                        "yield_upper": round(sfcst.iloc[i]["yhat_upper"], 3),
                        "area_ha": round(area),
                        "production_t": round(production),
                        "price_usd_t": round(price_trend, 1),
                    })
        except Exception as e:
            logger.warning(f"  Prophet failed for {crop}: {e}")

    df = pd.DataFrame(records)
    df["production_t"] = df["production_t"].astype(float)
    if len(df) > 0:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE_FILE, index=False)
    return df


def get_forecast_summary(forecasts: pd.DataFrame) -> pd.DataFrame:
    if forecasts.empty:
        return pd.DataFrame()
    moderate = forecasts[forecasts["scenario"] == "modéré"].copy()
    summary = moderate.groupby("crop").agg(
        yield_2025=("yield_t_ha", lambda x: x.iloc[0] if len(x) > 0 else 0),
        yield_2030=("yield_t_ha", lambda x: x.iloc[-1] if len(x) > 0 else 0),
        prod_2025=("production_t", lambda x: x.iloc[0] if len(x) > 0 else 0),
        prod_2030=("production_t", lambda x: x.iloc[-1] if len(x) > 0 else 0),
        category=("category", "first"),
    ).reset_index()
    summary["yield_change_pct"] = (
        (summary["yield_2030"] - summary["yield_2025"]) / summary["yield_2025"] * 100
    )
    summary["prod_change_pct"] = (
        (summary["prod_2030"] - summary["prod_2025"]) / summary["prod_2025"] * 100
    )
    return summary


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    fcst = generate_forecasts()
    logger.info(f"Prévisions générées: {len(fcst)} lignes")
    if len(fcst):
        logger.info(f"Cultures: {fcst['crop'].nunique()}")
        logger.info(f"Scénarios: {fcst['scenario'].unique()}")
        summary = get_forecast_summary(fcst)
        print(summary.to_string())
