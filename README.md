# Agri-Forecast: Weather-Based Crop Yield Forecasting

Forecasts crop yield from historical weather data using regression-based time-series modeling. The aim is to measure how temperature, rainfall, and seasonal patterns affect yield, and to produce yield forecasts that are easy to interpret.

---

## Overview

Crop yield depends heavily on weather. This project builds a regression model that learns the relationship between weather variables and recorded yield, then forecasts yield for unseen periods. The focus is on interpretability, so the model shows which weather factors matter most rather than acting as a black box.

## Problem Statement

Given historical weather (temperature, rainfall, humidity, and so on) and matching crop-yield records, predict yield for a target season or region and identify the weather factors that drive it.

## Dataset

- **Weather data:** [source, e.g. NOAA / IMD / Kaggle dataset name + link]
- **Yield data:** [source, e.g. government agriculture records]
- **Granularity:** [e.g. monthly weather aggregated to seasonal, per region/crop]
- Raw files live in `data/raw/` (not committed due to size; download links above).

## Approach

1. **Data preparation** (`src/data_prep.py`): clean and merge weather and yield data on region/time keys, handle missing values.
2. **Feature engineering** (`src/features.py`): seasonal aggregates, rolling averages, lag features, and derived indices such as growing-degree days.
3. **Modeling** (`src/train.py`): regression-based forecasting [Linear Regression / Random Forest Regressor / Gradient Boosting, state what you used].
4. **Evaluation** (`src/evaluate.py`): performance on a held-out time period, plus feature-importance analysis.

## Results

> Fill in once finalized. Do not leave blank on a linked repo.

- **Model:** [e.g. Random Forest Regressor]
- **Evaluation metric:** [e.g. RMSE / MAE / R2] on held-out data: [value]
- **Baseline comparison:** [e.g. vs. mean predictor / linear baseline]
- **Top yield drivers:** [e.g. rainfall in growing season, mean temperature]
- Key plots: predicted vs. actual yield, feature importance (see `notebooks/`).

## Project Structure

```
data/            raw and processed data
notebooks/       exploratory analysis
src/             data prep, features, training, evaluation
Application/     [describe: Streamlit app / demo]
models/          saved models
```

## Setup

```bash
git clone https://github.com/PVRPratyusha/Agri-forecast.git
cd Agri-forecast
pip install -r requirements.txt
```

## Usage

```bash
python src/data_prep.py      # prepare data
python src/features.py       # build features
python src/train.py          # train and save model
python src/evaluate.py       # evaluate on held-out data
```

## Future Work

- Compare against classical time-series models like ARIMA or SARIMA.
- Add cross-validation across multiple seasons for robustness.
- Extend to multi-crop or multi-region forecasting.

## Tech Stack

Python, Pandas, NumPy, scikit-learn, Matplotlib/Seaborn
[+ Streamlit if the Application is a demo app]
