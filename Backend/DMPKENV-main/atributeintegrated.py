"""
atributeintegrated.py

Utilities to work with pre-trained Prophet models for emotions, clothing and head attributes.
This module provides functions to list available models, load a model by label, and produce
forecasts for a given label. Models are expected to be pickle files in the `models/` folder
named like `model_prophet_<label>.pkl`.

Example usage:
  from atributeintegrated import list_models, forecast_label
  print(list_models('cloth'))
  df_forecast = forecast_label('kaos', periods=14)

The module is intentionally dependency-light: it uses `pickle` to load models and assumes the
models follow Prophet's API (have `make_future_dataframe` and `predict`).
"""
import os
import glob
import pickle
from typing import List, Dict, Optional
from pathlib import Path
import pandas as pd
from datetime import datetime


MODELS_DIR = Path(__file__).parent / 'models'
MODEL_PREFIX = 'model_prophet_'


def _discover_models() -> Dict[str, Path]:
    files = glob.glob(str(MODELS_DIR / (MODEL_PREFIX + '*.pkl')))
    mapping = {}
    for f in files:
        name = os.path.basename(f)
        if name.startswith(MODEL_PREFIX) and name.endswith('.pkl'):
            label = name[len(MODEL_PREFIX):-4]  # strip prefix and .pkl
            mapping[label] = Path(f)
    return mapping


_MODEL_INDEX = _discover_models()


def list_models(category: Optional[str] = None) -> List[str]:
    """Return available model labels. If `category` provided it filters by a simple heuristic:
    - 'emotion' : labels that are common emotion names (happy, sad, angry, etc.)
    - 'cloth'   : labels that match clothing-related words (shirt, kaos, sweater, etc.)
    - 'head'    : labels that match head-related words (hat, hijab, hair, etc.)
    If category is None, return all discovered labels.
    """
    labels = sorted(_MODEL_INDEX.keys())
    if not category:
        return labels

    cat = category.lower()
    if cat == 'emotion':
        keywords = {'happy', 'sad', 'angry', 'surprised', 'fear', 'neutral'}
    elif cat in ('cloth', 'clothing', 'baju'):
        keywords = {'t-shirt', 'shirt', 'kaos', 'sweater', 'outer', 'blouse', 'rok', 'shorts', 'long_pants', 'skirt', 'pants'}
    elif cat in ('head', 'kepala'):
        keywords = {'hat', 'hijab', 'hair', 'topi'}
    else:
        keywords = set()

    return [l for l in labels if any(k in l for k in keywords)]


def load_model(label: str):
    """Load and return the model object for given label. Raises KeyError if not found."""
    label = label.replace(' ', '_')
    if label not in _MODEL_INDEX:
        raise KeyError(f"Model for label '{label}' not found. Available: {sorted(_MODEL_INDEX.keys())[:30]}")
    path = _MODEL_INDEX[label]
    with open(path, 'rb') as f:
        model = pickle.load(f)
    return model


def forecast_label(label: str, periods: int = 30, freq: str = 'D') -> pd.DataFrame:
    """Produce a forecast DataFrame for a single label using its Prophet model.

    Returns a DataFrame containing the forecast (the model's predict output).
    The function assumes the loaded model follows Prophet API (has `make_future_dataframe` and `predict`).
    """
    model = load_model(label)

    # Create future dataframe and predict
    if hasattr(model, 'make_future_dataframe'):
        future = model.make_future_dataframe(periods=periods, freq=freq)
    else:
        # Some models may expect manual future df
        last = pd.to_datetime(datetime.now())
        future = pd.date_range(end=last, periods=periods, freq=freq).to_frame(index=False, name='ds')

    if hasattr(model, 'predict'):
        forecast = model.predict(future)
    else:
        raise RuntimeError(f"Loaded model for '{label}' does not support `predict` method")

    return forecast


def forecast_bulk(labels: List[str], periods: int = 30, freq: str = 'D') -> Dict[str, pd.DataFrame]:
    """Forecast multiple labels and return a dict label -> forecast DataFrame."""
    results = {}
    for lab in labels:
        try:
            results[lab] = forecast_label(lab, periods=periods, freq=freq)
        except Exception as e:
            results[lab] = pd.DataFrame({'error': [str(e)]})
    return results


def summary_for_label(label: str, periods: int = 30) -> Dict:
    """Helper that returns a small dict summary: last historical date, forecast totals, etc."""
    fc = forecast_label(label, periods=periods)
    # Prophet output commonly has 'ds' and 'yhat' columns
    if 'ds' in fc.columns:
        ds_col = 'ds'
    else:
        ds_col = fc.columns[0]

    result = {
        'label': label,
        'forecast_start': fc[ds_col].min() if not fc.empty else None,
        'forecast_end': fc[ds_col].max() if not fc.empty else None,
    }
    # include simple aggregates if yhat present
    if 'yhat' in fc.columns:
        result['yhat_mean'] = float(fc['yhat'].mean())
        result['yhat_sum'] = float(fc['yhat'].sum())
    return result


if __name__ == '__main__':
    # quick CLI: show available models and demo forecast for a sample label if provided
    import argparse

    parser = argparse.ArgumentParser(description='Atribute integrated utilities for Prophet models')
    parser.add_argument('--list', action='store_true', help='List available models')
    parser.add_argument('--category', type=str, default=None, help='Filter list by category: emotion, cloth, head')
    parser.add_argument('--label', type=str, default=None, help='Label to forecast')
    parser.add_argument('--periods', type=int, default=14, help='Forecast periods')
    args = parser.parse_args()

    if args.list:
        print('Available models:', list_models(args.category))
    if args.label:
        print('Forecasting', args.label)
        df = forecast_label(args.label, periods=args.periods)
        print(df[['ds'] + [c for c in df.columns if c.startswith('yhat')][:2]].head())
