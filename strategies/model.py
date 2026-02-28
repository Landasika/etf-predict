"""
Machine Learning Signal Model

Uses factor matrix to predict signal direction and strength.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
from sklearn.linear_model import Ridge, Lasso
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import pickle


class SignalModel:
    """
    Signal direction model

    Input: Factor matrix X
    Output: Predicted strength (continuous value)
    """

    def __init__(self, model_type: str = 'ridge', alpha: float = 1.0):
        """
        Initialize signal model

        Args:
            model_type: Type of model ('ridge' or 'lasso')
            alpha: Regularization strength (default 1.0)
        """
        self.model_type = model_type
        self.alpha = alpha
        self.scaler = StandardScaler()
        self.feature_names = []

        # Initialize model
        if model_type == 'ridge':
            self.model = Ridge(alpha=alpha)
        elif model_type == 'lasso':
            self.model = Lasso(alpha=alpha)
        else:
            raise ValueError(f"Unknown model type: {model_type}")

    def prepare_training_data(self, df: pd.DataFrame,
                              forward_days: int = 5,
                              feature_cols: List[str] = None) -> Tuple[np.ndarray, np.ndarray]:
        """
        Prepare training data

        Args:
            df: DataFrame with factors
            forward_days: Days to look forward for returns (default 5)
            feature_cols: List of feature column names (auto-detected if None)

        Returns:
            X, y: Feature matrix and labels
        """
        # Auto-detect feature columns if not provided
        if feature_cols is None:
            feature_cols = [col for col in df.columns if col.startswith('f_')]

        self.feature_names = feature_cols

        # Build feature matrix
        X = df[feature_cols].fillna(0).values

        # Calculate future returns as label
        future_return = df['close'].shift(-forward_days) / df['close'] - 1
        y = future_return.fillna(0).values

        return X, y

    def train(self, X: np.ndarray, y: np.ndarray,
              test_size: float = 0.2,
              random_state: int = 42) -> Dict:
        """
        Train the model

        Args:
            X: Feature matrix
            y: Target values (future returns)
            test_size: Proportion of data for testing (default 0.2)
            random_state: Random seed (default 42)

        Returns:
            Dictionary with training metrics
        """
        # Split data
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, shuffle=False
        )

        # Scale features
        X_train_scaled = self.scaler.fit_transform(X_train)
        X_test_scaled = self.scaler.transform(X_test)

        # Train model
        self.model.fit(X_train_scaled, y_train)

        # Calculate metrics
        train_score = self.model.score(X_train_scaled, y_train)
        test_score = self.model.score(X_test_scaled, y_test)

        # Predictions
        y_pred_train = self.model.predict(X_train_scaled)
        y_pred_test = self.model.predict(X_test_scaled)

        # Calculate RMSE
        train_rmse = np.sqrt(np.mean((y_train - y_pred_train) ** 2))
        test_rmse = np.sqrt(np.mean((y_test - y_pred_test) ** 2))

        return {
            'train_r2': train_score,
            'test_r2': test_score,
            'train_rmse': train_rmse,
            'test_rmse': test_rmse,
            'n_features': len(self.feature_names),
            'n_samples': len(X)
        }

    def predict(self, df: pd.DataFrame) -> pd.Series:
        """
        Predict signal strength

        Args:
            df: DataFrame with factor columns

        Returns:
            Series: Predicted strength values (continuous)
        """
        feature_cols = [col for col in df.columns if col.startswith('f_')]

        if len(feature_cols) == 0:
            raise ValueError("No factor columns found in DataFrame")

        X = df[feature_cols].fillna(0).values
        X_scaled = self.scaler.transform(X)
        strength = self.model.predict(X_scaled)

        return pd.Series(strength, index=df.index)

    def get_feature_importance(self) -> pd.DataFrame:
        """
        Get feature weights/importance

        Returns:
            DataFrame with features and their weights
        """
        if not self.feature_names:
            raise ValueError("Model not trained yet")

        importance = pd.DataFrame({
            'feature': self.feature_names,
            'weight': self.model.coef_
        }).sort_values('weight', ascending=False)

        return importance

    def save(self, filepath: str):
        """
        Save model to file

        Args:
            filepath: Path to save model
        """
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_names,
            'model_type': self.model_type,
            'alpha': self.alpha
        }

        with open(filepath, 'wb') as f:
            pickle.dump(model_data, f)

    def load(self, filepath: str):
        """
        Load model from file

        Args:
            filepath: Path to load model from
        """
        with open(filepath, 'rb') as f:
            model_data = pickle.load(f)

        self.model = model_data['model']
        self.scaler = model_data['scaler']
        self.feature_names = model_data['feature_names']
        self.model_type = model_data['model_type']
        self.alpha = model_data['alpha']


class RollingSignalModel:
    """
    Rolling window signal model for adaptive learning

    Retrains periodically to adapt to changing market conditions.
    """

    def __init__(self,
                 model_type: str = 'ridge',
                 alpha: float = 1.0,
                 window_size: int = 252,
                 retrain_freq: int = 20):
        """
        Initialize rolling model

        Args:
            model_type: Type of model ('ridge' or 'lasso')
            alpha: Regularization strength
            window_size: Training window size in days (default 252 = 1 year)
            retrain_freq: Retrain frequency in days (default 20 = monthly)
        """
        self.base_model = SignalModel(model_type, alpha)
        self.window_size = window_size
        self.retrain_freq = retrain_freq
        self.last_retrain_idx = 0

    def predict_rolling(self, df: pd.DataFrame,
                        forward_days: int = 5) -> pd.Series:
        """
        Predict with rolling retraining

        Args:
            df: DataFrame with factors
            forward_days: Days to look forward for returns

        Returns:
            Series: Predicted strength values
        """
        predictions = np.zeros(len(df))

        for i in range(self.window_size, len(df)):
            # Get training window
            train_df = df.iloc[i-self.window_size:i]

            # Check if we need to retrain
            if i - self.last_retrain_idx >= self.retrain_freq or self.last_retrain_idx == 0:
                X, y = self.base_model.prepare_training_data(train_df, forward_days)
                self.base_model.train(X, y)
                self.last_retrain_idx = i

            # Predict for current point
            current_df = df.iloc[[i]]
            pred = self.base_model.predict(current_df)
            predictions[i] = pred.values[0]

        # Fill initial values with 0
        predictions[:self.window_size] = 0

        return pd.Series(predictions, index=df.index)


class EnsembleSignalModel:
    """
    Ensemble of multiple models for robust predictions
    """

    def __init__(self, models: List[SignalModel] = None, weights: List[float] = None):
        """
        Initialize ensemble model

        Args:
            models: List of SignalModel instances
            weights: List of weights for each model (equal if None)
        """
        self.models = models or []
        self.weights = weights or []

        if self.models and not self.weights:
            self.weights = [1.0 / len(self.models)] * len(self.models)

    def add_model(self, model: SignalModel, weight: float = 1.0):
        """Add a model to the ensemble"""
        self.models.append(model)
        self.weights.append(weight)

        # Normalize weights
        total = sum(self.weights)
        self.weights = [w / total for w in self.weights]

    def predict(self, df: pd.DataFrame) -> pd.Series:
        """
        Predict using ensemble

        Args:
            df: DataFrame with factor columns

        Returns:
            Series: Weighted average of predictions
        """
        if not self.models:
            raise ValueError("No models in ensemble")

        predictions = []

        for model in self.models:
            pred = model.predict(df)
            predictions.append(pred)

        # Weighted average
        ensemble_pred = sum(p * w for p, w in zip(predictions, self.weights))

        return ensemble_pred
