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

CONFIDENCE_LEVEL = 1.96


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
    n = len(y)
    degree = min(2, n - 2) if n >= 4 else 1
    coeffs = np.polyfit(years, y, degree)
    model = np.poly1d(coeffs)
    fitted = model(years)
    residuals = y - fitted
    residual_std = float(np.std(residuals)) if n > degree + 1 else 0.0
    residual_std = max(residual_std, float(np.mean(y)) * 0.05)
    yhat = model(np.asarray(future_years))
    yhat = np.maximum(yhat, 0.01)
    margin = CONFIDENCE_LEVEL * residual_std
    return pd.DataFrame({
        "ds": pd.to_datetime(future_years, format="%Y"),
        "yhat": yhat,
        "yhat_lower": np.maximum(yhat - margin, 0.01),
        "yhat_upper": yhat + margin,
    })


def _forecast_yields(yields: np.ndarray, years: np.ndarray) -> pd.DataFrame:
    if Prophet is not None:
        try:
            model = _train_prophet(yields, years)
            return _predict_prophet(model, FORECAST_YEARS)
        except Exception as e:
            logger.warning(f"Prophet failed: {e}, falling back to trend")
    return _predict_trend(yields, years, FORECAST_YEARS)


def _rng_for(*parts: str) -> np.random.Generator:
    seed_key = "|".join(parts).encode("utf-8")
    seed = int(hashlib.sha256(seed_key).hexdigest()[:16], 16) % 2**31
    return np.random.default_rng(seed)


def _estimate_area_trend(areas: np.ndarray, years: np.ndarray) -> float:
    if len(areas) < 3:
        return 0.015
    coeffs = np.polyfit(years, np.log(areas), 1)
    annual_growth = float(coeffs[0])
    return np.clip(annual_growth, -0.02, 0.06)


def _estimate_price_trend(prices: np.ndarray, years: np.ndarray) -> float:
    valid = prices[~np.isnan(prices)]
    if len(valid) < 3:
        return 0.02
    coeffs = np.polyfit(years[-len(valid):], np.log(valid), 1)
    return float(np.clip(coeffs[0], -0.03, 0.08))


def _climate_scenario_multipliers(climate: pd.DataFrame, scenario: str) -> float:
    if climate.empty:
        return 1.12 if scenario == "optimiste" else 0.85 if scenario == "pessimiste" else 1.0
    natl = climate[climate["Region"] == "National"].sort_values("Year")
    if len(natl) < 5:
        return 1.12 if scenario == "optimiste" else 0.85 if scenario == "pessimiste" else 1.0
    recent = natl[natl["Year"] >= 2015]
    if len(recent) < 3:
        return 1.12 if scenario == "optimiste" else 0.85 if scenario == "pessimiste" else 1.0
    precip_std = recent["precip_mm"].std()
    temp_range = recent["temp_c"].max() - recent["temp_c"].min()
    precip_var = np.clip(precip_std / recent["precip_mm"].mean(), 0.05, 0.30)
    temp_var = np.clip(temp_range / 2.0, 0.01, 0.08)
    total_var = precip_var + temp_var
    if scenario == "optimiste":
        return 1.0 + total_var
    elif scenario == "pessimiste":
        return 1.0 - total_var * 1.2
    return 1.0


def generate_forecasts(use_cache: bool = True) -> pd.DataFrame:
    if use_cache and CACHE_FILE.exists():
        df = pd.read_csv(CACHE_FILE)
        if len(df) > 0:
            return df

    agri = get_togo_agriculture_data()
    climate = get_togo_climate_data()

    agri_by_crop = {}
    for crop in sorted(ALL_CROPS):
        df_crop = agri[agri["crop"] == crop].sort_values("Year")
        if len(df_crop) >= 3:
            agri_by_crop[crop] = df_crop
        else:
            logger.info(f"  {crop}: seulement {len(df_crop)} points, on utilise la moyenne du groupe")

    global_means = agri.groupby("Year").agg(
        yield_t_ha=("yield_t_ha", "mean"),
        area_ha=("area_ha", "mean"),
        production_t=("production_t", "mean"),
    ).reset_index()

    records = []
    for crop in sorted(ALL_CROPS):
        if crop in agri_by_crop:
            df_crop = agri_by_crop[crop]
        else:
            df_crop = global_means.copy()
            df_crop["crop"] = crop
            df_crop["category"] = ALL_CROPS[crop]["category"]
            df_crop["staple"] = ALL_CROPS[crop]["staple"]

        df_crop = df_crop.sort_values("Year")
        years = df_crop["Year"].values
        yields = df_crop["yield_t_ha"].values
        areas = df_crop["area_ha"].values

        try:
            fcst = _forecast_yields(yields, years)

            optim_mult = _climate_scenario_multipliers(climate, "optimiste")
            pess_mult = _climate_scenario_multipliers(climate, "pessimiste")

            area_trend = _estimate_area_trend(areas, years)
            base_price = CROP_PARAMS.get(crop, {}).get("price_range", (200, 1000))
            price_mid = (base_price[0] + base_price[1]) / 2

            for scenario in ["modéré", "optimiste", "pessimiste"]:
                if scenario == "optimiste":
                    y_mult = optim_mult
                    a_rate = area_trend + 0.01
                elif scenario == "pessimiste":
                    y_mult = pess_mult
                    a_rate = max(area_trend - 0.01, -0.02)
                else:
                    y_mult = 1.0
                    a_rate = area_trend

                params = CROP_PARAMS.get(crop, {
                    "yield_range": (max(float(yields.min()) * 0.5, 0.01), float(yields.max()) * 1.5),
                    "price_range": (200, 1000),
                })
                base_area = areas[-1]
                rng = _rng_for(crop, scenario)

                for i, year in enumerate(FORECAST_YEARS):
                    yhat = fcst.iloc[i]["yhat"] * y_mult
                    yhat = max(yhat, params["yield_range"][0] * 0.5)

                    area = base_area * (1 + a_rate) ** (i + 1) * rng.uniform(0.97, 1.03)

                    price = price_mid * rng.uniform(0.90, 1.10)
                    price_trend = price * (1 + i * 0.025)

                    production = yhat * area

                    records.append({
                        "Year": year,
                        "crop": crop,
                        "category": ALL_CROPS[crop]["category"],
                        "staple": ALL_CROPS[crop]["staple"],
                        "scenario": scenario,
                        "yield_t_ha": round(yhat, 3),
                        "yield_lower": round(max(fcst.iloc[i]["yhat_lower"] * y_mult, params["yield_range"][0] * 0.3), 3),
                        "yield_upper": round(fcst.iloc[i]["yhat_upper"] * y_mult, 3),
                        "area_ha": round(area),
                        "production_t": round(production),
                        "price_usd_t": round(price_trend, 1),
                    })
        except Exception as e:
            logger.warning(f"  Forecast failed for {crop}: {e}")

    df = pd.DataFrame(records)
    df["production_t"] = df["production_t"].astype(float)
    if len(df) > 0:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        df.to_csv(CACHE_FILE, index=False)
    logger.info(f"Prévisions: {df['crop'].nunique()}/13 cultures, {len(df)} lignes")
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
        (summary["yield_2030"] - summary["yield_2025"]) / summary["yield_2025"].replace(0, pd.NA) * 100
    )
    summary["prod_change_pct"] = (
        (summary["prod_2030"] - summary["prod_2025"]) / summary["prod_2025"].replace(0, pd.NA) * 100
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
