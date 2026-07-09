import pandas as pd
import numpy as np
from pathlib import Path
from src.data_loader import load_all_togo_data
from src.agriculture_data import get_togo_agriculture_data, CROP_PARAMS, CROP_PRODUCTION_2023
from src.climate_data import get_togo_climate_data
from src.models import YieldPredictor, SupplyChainRiskModel
from src.config import ALL_CROPS


def run_analysis_pipeline():
    print("=" * 60)
    print("Pipeline d'Analyse - Chaîne de Valeur Agricole Togo")
    print("=" * 60)

    print("\n[1/4] Chargement des données macroéconomiques...")
    togo_data = load_all_togo_data()
    inflation = togo_data["inflation"]
    gdp = togo_data["gdp"]
    agri_wb = togo_data["agri_wb"]
    print(f"  Inflation: {len(inflation)} obs")
    print(f"  PIB: {len(gdp)} obs")
    print(f"  WB Agriculture: {len(agri_wb)} obs indicators")
    print(f"  Agriculture Togo: {len(ALL_CROPS)} cultures suivies")

    print("\n[2/4] Chargement des données climatiques réelles (NASA POWER)...")
    climate = get_togo_climate_data()
    natl = climate[climate["Region"] == "National"]
    print(f"  {len(natl)} années nationales")
    print(f"  Precip: {natl['precip_mm'].min():.0f}-{natl['precip_mm'].max():.0f} mm/an")
    print(f"  Temp: {natl['temp_c'].min():.1f}-{natl['temp_c'].max():.1f} °C")

    print("\n[3/4] Analyse des risques d'approvisionnement...")
    merged = inflation.rename(columns={"Value": "inflation"})
    gdp_r = gdp.rename(columns={"Value": "gdp"})
    merged = merged.merge(gdp_r[["Year", "gdp"]], on="Year")

    risk_model = SupplyChainRiskModel()
    risk_df = risk_model.compute_risk_score(merged)

    risk_counts = risk_df["risk_level"].value_counts()
    print(f"  Niveaux de risque:")
    for level, count in risk_counts.items():
        print(f"    {level}: {count} années ({count/len(risk_df)*100:.1f}%)")

    print("\n[4/4] Modèles prédictifs de rendement (toutes cultures)...")
    natl_climate = natl[["Year", "precip_mm", "temp_c"]]
    feature_data = merged.merge(natl_climate, on="Year", how="inner")
    agri = get_togo_agriculture_data()
    feature_data = feature_data.merge(agri, on="Year", how="inner")

    predictor = YieldPredictor(model_type="random_forest")
    results = []

    for crop in ALL_CROPS:
        df_crop = feature_data[feature_data["crop"] == crop]
        if len(df_crop) < 5:
            print(f"  {crop}: données insuffisantes ({len(df_crop)} obs)")
            continue

        features = ["gdp", "inflation", "precip_mm", "temp_c"]
        available = [f for f in features if f in df_crop.columns]
        X = df_crop[available].values
        y = df_crop["yield_t_ha"].values

        if len(X) > 5:
            predictor.train(X, y, test_size=0.2)
            metrics = predictor.evaluate(X, y)
            results.append({"crop": crop, "r2": metrics["r2"], "rmse": metrics["rmse"],
                            "category": ALL_CROPS[crop]["category"]})
            print(f"  {crop:15s} R² = {metrics['r2']:.3f}, RMSE = {metrics['rmse']:.3f}")

    if results:
        r2_avg = np.mean([r["r2"] for r in results])
        print(f"\n  R² moyen toutes cultures: {r2_avg:.3f}")

    print("\n" + "=" * 60)
    print("Pipeline terminé avec succès.")
    print(f"  {len(results)} cultures modélisées")
    print("=" * 60)
    return risk_df, agri, merged


if __name__ == "__main__":
    run_analysis_pipeline()
