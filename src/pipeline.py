import logging
import pandas as pd
import numpy as np
from src.data_loader import load_all_togo_data
from src.agriculture_data import get_togo_agriculture_data
from src.climate_data import get_togo_climate_data
from src.models import YieldPredictor, SupplyChainRiskModel
from src.config import ALL_CROPS

logger = logging.getLogger(__name__)


def run_analysis_pipeline():
    logger.info("=" * 60)
    logger.info("Pipeline d'Analyse - Chaîne de Valeur Agricole Togo")
    logger.info("=" * 60)

    logger.info("[1/4] Chargement des données macroéconomiques...")
    togo_data = load_all_togo_data()
    inflation = togo_data["inflation"]
    gdp = togo_data["gdp"]
    agri_wb = togo_data["agri_wb"]
    logger.info(f"  Inflation: {len(inflation)} obs")
    logger.info(f"  PIB: {len(gdp)} obs")
    logger.info(f"  WB Agriculture: {len(agri_wb)} obs indicators")
    logger.info(f"  Agriculture Togo: {len(ALL_CROPS)} cultures suivies")

    logger.info("[2/4] Chargement des données climatiques réelles (NASA POWER)...")
    climate = get_togo_climate_data()
    natl = climate[climate["Region"] == "National"]
    logger.info(f"  {len(natl)} années nationales")
    logger.info(f"  Precip: {natl['precip_mm'].min():.0f}-{natl['precip_mm'].max():.0f} mm/an")
    logger.info(f"  Temp: {natl['temp_c'].min():.1f}-{natl['temp_c'].max():.1f} °C")

    logger.info("[3/4] Analyse des risques d'approvisionnement...")
    merged = inflation.rename(columns={"Value": "inflation"})
    gdp_r = gdp.rename(columns={"Value": "gdp"})
    merged = merged.merge(gdp_r[["Year", "gdp"]], on="Year")

    risk_model = SupplyChainRiskModel()
    risk_df = risk_model.compute_risk_score(merged)

    risk_counts = risk_df["risk_level"].value_counts()
    logger.info(f"  Niveaux de risque:")
    for level, count in risk_counts.items():
        logger.info(f"    {level}: {count} années ({count/len(risk_df)*100:.1f}%)")

    logger.info("[4/4] Modèles prédictifs de rendement (toutes cultures)...")
    natl_climate = natl[["Year", "precip_mm", "temp_c"]]
    feature_data = merged.merge(natl_climate, on="Year", how="inner")
    agri = get_togo_agriculture_data()
    feature_data = feature_data.merge(agri, on="Year", how="inner")

    results = []

    for crop in ALL_CROPS:
        df_crop = feature_data[feature_data["crop"] == crop]
        if len(df_crop) < 5:
            logger.info(f"  {crop}: données insuffisantes ({len(df_crop)} obs)")
            continue

        predictor = YieldPredictor(model_type="random_forest")
        df_eng = predictor.engineer_features(df_crop)

        if len(df_eng) < 5:
            logger.warning(f"  {crop}: trop de NaN après feature engineering ({len(df_eng)} obs)")
            continue

        X, y = predictor.prepare_data(df_eng, target_col="yield_t_ha")

        if len(X) > 5:
            predictor.train(X, y)
            metrics = predictor.evaluate(X, y)
            results.append({"crop": crop, "r2": metrics["r2"], "rmse": metrics["rmse"],
                            "category": ALL_CROPS[crop]["category"]})
            logger.info(f"  {crop:15s} R² = {metrics['r2']:.3f}, RMSE = {metrics['rmse']:.3f}")

    if results:
        r2_avg = np.mean([r["r2"] for r in results])
        logger.info(f"  R² moyen toutes cultures: {r2_avg:.3f}")

    logger.info("=" * 60)
    logger.info("Pipeline terminé avec succès.")
    logger.info(f"  {len(results)} cultures modélisées")
    logger.info("=" * 60)
    return risk_df, agri, merged


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    run_analysis_pipeline()
