from src.pipeline import run_analysis_pipeline


def test_pipeline_returns_expected_types():
    risk_df, agri, merged = run_analysis_pipeline()
    assert "risk_score" in risk_df.columns
    assert "risk_level" in risk_df.columns
    assert "crop" in agri.columns
    assert "yield_t_ha" in agri.columns
    assert "Year" in merged.columns
    assert "inflation" in merged.columns
    assert "gdp" in merged.columns


def test_pipeline_risk_levels_are_valid():
    risk_df, _, _ = run_analysis_pipeline()
    valid_levels = {"Faible", "Modéré", "Élevé", "Critique"}
    assert set(risk_df["risk_level"].dropna().unique()).issubset(valid_levels)
    assert risk_df["risk_score"].between(0, 1).all()
