import pandas as pd
import os

INPUT = os.path.join("data", "external", "local_prices_normalized.csv")
OUT = os.path.join("data", "external", "summary_stats_local_prices.csv")

def main():
    df = pd.read_csv(INPUT)
    # consider observed years <= 2024 as historical
    observed = df[df["Year"] <= 2024].copy()
    # group by crop and compute stats on FCFA and real USD/kg when available
    def_stats = observed.groupby("crop").agg(
        n_obs=("Year", "count"),
        mean_fcfa_kg=("price_fcfa_kg", "mean"),
        median_fcfa_kg=("price_fcfa_kg", "median"),
        std_fcfa_kg=("price_fcfa_kg", "std"),
        mean_usd_kg_real=("usd_kg_real", "mean"),
        median_usd_kg_real=("usd_kg_real", "median"),
        std_usd_kg_real=("usd_kg_real", "std"),
    ).reset_index()

    def_stats.to_csv(OUT, index=False)
    print(f"Résumé sauvegardé: {OUT}")
    print(def_stats.head(20).to_string(index=False))

if __name__ == '__main__':
    main()
