import pandas as pd
import numpy as np
from src.models import YieldPredictor, SupplyChainRiskModel, detect_outliers_iqr


def test_yield_predictor_engineer_features_adds_climate():
    df = pd.DataFrame({
        "gdp": [100, 110, 120, 130, 140],
        "inflation": [2, 3, 4, 3, 2],
        "precip_mm": [1200, 1100, 1300, 1250, 1150],
        "temp_c": [26, 27, 26, 27, 26],
    })
    predictor = YieldPredictor()
    result = predictor.engineer_features(df)
    assert "GDP_lag1" in result.columns
    assert "precip_lag1" in result.columns
    assert "temp_lag1" in result.columns
    assert len(result) > 2
    assert result["precip_lag1"].iloc[0] == 1100


def test_yield_predictor_train_and_evaluate():
    rng = np.random.default_rng(42)
    n = 50
    df = pd.DataFrame({
        "gdp": np.linspace(100, 200, n) + rng.normal(0, 5, n),
        "inflation": np.sin(np.linspace(0, 4 * np.pi, n)) * 2 + 3,
        "yield_t_ha": np.linspace(1, 2, n) + rng.normal(0, 0.1, n),
    })
    predictor = YieldPredictor(model_type="random_forest")
    df_eng = predictor.engineer_features(df)
    X, y = predictor.prepare_data(df_eng, target_col="yield_t_ha")
    predictor.train(X, y)
    metrics = predictor.evaluate(X, y)
    assert "mae" in metrics
    assert "rmse" in metrics
    assert "r2" in metrics
    assert metrics["r2"] > -1
    assert metrics["rmse"] >= 0
    assert len(metrics["y_pred"]) == len(y)


def test_yield_predictor_predict_returns_correct_shape():
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "gdp": np.linspace(100, 200, 50),
        "inflation": np.sin(np.linspace(0, 4 * np.pi, 50)) * 2 + 3,
        "yield_t_ha": np.linspace(1, 2, 50),
    })
    predictor = YieldPredictor(model_type="linear")
    df_eng = predictor.engineer_features(df)
    X, y = predictor.prepare_data(df_eng, target_col="yield_t_ha")
    predictor.train(X, y)
    preds = predictor.predict(X)
    assert len(preds) == len(y)
    assert (preds > 0).all()


def test_supply_chain_risk_model_compute_risk_score():
    rng = np.random.default_rng(42)
    df = pd.DataFrame({
        "Year": [2000, 2001, 2002, 2003, 2004, 2005],
        "inflation": [2, 3, 4, 5, 3, 2],
        "gdp": [100, 105, 110, 108, 115, 120],
    })
    model = SupplyChainRiskModel()
    result = model.compute_risk_score(df)
    assert "risk_score" in result.columns
    assert "risk_level" in result.columns
    assert result["risk_score"].between(0, 1).all()
    assert result["risk_level"].isin(["Faible", "Modéré", "Élevé", "Critique"]).all()


def test_detect_outliers_iqr():
    s = pd.Series([1, 2, 3, 4, 5, 100])
    outliers = detect_outliers_iqr(s)
    assert outliers.sum() == 1
    assert outliers.iloc[-1] == True


def test_detect_outliers_iqr_no_outliers():
    s = pd.Series([10, 12, 11, 13, 12, 11, 10])
    outliers = detect_outliers_iqr(s)
    assert outliers.sum() == 0
