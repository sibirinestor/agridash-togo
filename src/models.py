import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split, cross_val_score, TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import joblib
from pathlib import Path


class YieldPredictor:
    def __init__(self, model_type: str = "random_forest"):
        self.model_type = model_type
        self.model = None
        self.scaler = StandardScaler()
        self.features = None
        self._init_model()

    def _init_model(self):
        if self.model_type == "random_forest":
            self.model = RandomForestRegressor(
                n_estimators=200, max_depth=10,
                min_samples_leaf=5, random_state=42
            )
        elif self.model_type == "gradient_boosting":
            self.model = GradientBoostingRegressor(
                n_estimators=200, learning_rate=0.1,
                max_depth=5, random_state=42
            )
        elif self.model_type == "linear":
            self.model = LinearRegression()
        else:
            raise ValueError(f"Unknown model: {self.model_type}")

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["GDP_lag1"] = df["gdp"].shift(1)
        df["GDP_lag2"] = df["gdp"].shift(2)
        df["Inflation_lag1"] = df["inflation"].shift(1)
        df["GDP_growth"] = df["gdp"].pct_change() * 100
        df["Inflation_change"] = df["inflation"].diff()
        df["GDP_rolling_3y"] = df["gdp"].rolling(3).mean()
        df["Inflation_rolling_3y"] = df["inflation"].rolling(3).mean()
        return df.dropna()

    def prepare_data(self, df: pd.DataFrame, target_col: str,
                     feature_cols: list = None):
        if feature_cols is None:
            feature_cols = [
                "GDP_lag1", "GDP_lag2", "Inflation_lag1",
                "GDP_growth", "Inflation_change",
                "GDP_rolling_3y", "Inflation_rolling_3y",
            ]

        self.features = feature_cols
        X = df[feature_cols].values
        y = df[target_col].values
        return X, y

    def train(self, X: np.ndarray, y: np.ndarray, test_size: float = 0.2):
        tscv = TimeSeriesSplit(n_splits=5)
        scores = cross_val_score(self.model, X, y, cv=tscv,
                                 scoring="neg_mean_squared_error")
        rmse_scores = np.sqrt(-scores)
        print(f"Cross-val RMSE: {rmse_scores.mean():.2f} (+/- {rmse_scores.std():.2f})")
        X_scaled = self.scaler.fit_transform(X)
        self.model.fit(X_scaled, y)
        return self.model

    def predict(self, X: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X)
        return self.model.predict(X_scaled)

    def evaluate(self, X: np.ndarray, y: np.ndarray) -> dict:
        X_scaled = self.scaler.transform(X)
        y_pred = self.model.predict(X_scaled)
        return {
            "mae": mean_absolute_error(y, y_pred),
            "rmse": np.sqrt(mean_squared_error(y, y_pred)),
            "r2": r2_score(y, y_pred),
            "y_pred": y_pred,
        }

    def save(self, path: Path):
        joblib.dump({"model": self.model, "scaler": self.scaler,
                     "features": self.features, "model_type": self.model_type},
                    path)

    def load(self, path: Path):
        data = joblib.load(path)
        self.model = data["model"]
        self.scaler = data["scaler"]
        self.features = data["features"]
        self.model_type = data["model_type"]


class SupplyChainRiskModel:
    def __init__(self):
        self.model = RandomForestRegressor(
            n_estimators=100, max_depth=8, random_state=42
        )

    def compute_risk_score(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df = df.dropna(subset=["inflation", "gdp"])
        from sklearn.preprocessing import StandardScaler
        scaler = StandardScaler()
        df["inflation_volatility"] = df["inflation"].rolling(3).std()
        df["gdp_growth"] = df["gdp"].pct_change() * 100
        df["gdp_growth_abs"] = df["gdp_growth"].abs()
        risk_df = df.dropna()
        features = ["inflation_volatility", "inflation", "gdp_growth_abs"]
        X_scaled = scaler.fit_transform(risk_df[features])
        risk_df["risk_score_raw"] = np.mean(
            [X_scaled[:, 0] * 0.4, X_scaled[:, 1] * 0.3, X_scaled[:, 2] * 0.3],
            axis=0,
        )
        risk_df["risk_score"] = (risk_df["risk_score_raw"] - risk_df["risk_score_raw"].min()) / (
            risk_df["risk_score_raw"].max() - risk_df["risk_score_raw"].min()
        )
        risk_df["risk_level"] = pd.cut(
            risk_df["risk_score"],
            bins=[-np.inf, 0.25, 0.5, 0.75, np.inf],
            labels=["Faible", "Modéré", "Élevé", "Critique"],
        )
        return risk_df
