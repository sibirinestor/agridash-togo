import pandas as pd

from src.config import ALL_CROPS
from src import forecast as forecast_module
from src.forecast import FORECAST_YEARS, get_forecast_summary


def test_generate_forecasts_without_cache_has_expected_shape(tmp_path, monkeypatch):
    monkeypatch.setattr(forecast_module, "CACHE_FILE", tmp_path / "forecasts.csv")
    forecasts = forecast_module.generate_forecasts(use_cache=False)

    assert not forecasts.empty
    assert set(forecasts["Year"].unique()) == set(FORECAST_YEARS)
    assert set(forecasts["scenario"].unique()) == {"modéré", "optimiste", "pessimiste"}
    assert forecasts["crop"].nunique() == len(ALL_CROPS)
    assert (forecasts["yield_t_ha"] > 0).all()
    assert (forecasts["production_t"] > 0).all()


def test_forecast_summary_reports_changes(tmp_path, monkeypatch):
    monkeypatch.setattr(forecast_module, "CACHE_FILE", tmp_path / "forecasts.csv")
    forecasts = forecast_module.generate_forecasts(use_cache=False)
    summary = get_forecast_summary(forecasts)

    assert not summary.empty
    assert summary["crop"].nunique() == len(ALL_CROPS)
    assert pd.api.types.is_numeric_dtype(summary["yield_change_pct"])
    assert pd.api.types.is_numeric_dtype(summary["prod_change_pct"])
