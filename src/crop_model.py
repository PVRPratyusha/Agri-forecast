"""Crop regions, field calendar and climate-based crop recommendation.

Built from the merged NASS yield + NOAA weather files that data_prep.py writes to data/processed/.
For every crop, the location-years with good yields (at or above that crop's median for the year)
define the climate the crop does well in: mean growing-season temperature and mean monthly rainfall.
Also holds the crop plan and growth-tracking helpers (expected yield, growing degree days).
"""
import datetime

import numpy as np
import pandas as pd
from sklearn.cluster import AgglomerativeClustering, Birch, KMeans
from sklearn.metrics import silhouette_score
from sklearn.mixture import GaussianMixture
from sklearn.neighbors import KNeighborsClassifier

from data_prep import CROPS, PROCESSED_DIR

# Approximate harvest windows for the main US producing regions (start_month, end_month; wraps if start > end)
HARVEST = {
    "corn": (9, 11), "wheat": (6, 8), "sugarbeets": (9, 11), "sugarcane": (10, 3), "carrots": (1, 12),
    "lettuce": (1, 12), "apples": (8, 11), "oranges": (10, 6), "peaches": (6, 9), "strawberries": (1, 12),
    "blueberries": (5, 8), "raspberries": (6, 9),
}

# Preferred soil pH ranges, from general university extension guidance
PH_RANGE = {
    "corn": (5.8, 7.0), "wheat": (6.0, 7.0), "sugarbeets": (6.5, 8.0), "sugarcane": (5.5, 7.5),
    "carrots": (6.0, 6.8), "lettuce": (6.0, 7.0), "apples": (6.0, 7.0), "oranges": (6.0, 7.5),
    "peaches": (6.0, 7.0), "strawberries": (5.5, 6.8), "blueberries": (4.5, 5.5), "raspberries": (5.6, 6.5),
}

# Approximate days from planting (perennials: spring green-up or bloom) to harvest, and the base
# temperature (deg C) for growing degree days, from university extension guidance
GROWTH = {
    "corn": (120, 10.0), "wheat": (270, 0.0), "sugarbeets": (170, 1.0), "sugarcane": (365, 12.0),
    "carrots": (75, 4.0), "lettuce": (65, 4.0), "apples": (150, 4.5), "oranges": (300, 12.5),
    "peaches": (120, 7.0), "strawberries": (120, 5.0), "blueberries": (100, 7.0), "raspberries": (100, 5.0),
}
GDD_CAP = 30.0  # deg C; growth does not speed up above this
PERISHABLE = {"carrots", "lettuce", "apples", "oranges", "peaches", "strawberries", "blueberries", "raspberries"}
# Commodity names in the USDA warehouse list for crops it covers
WAREHOUSE_COMMODITY = {"corn": "Grain", "wheat": "Grain", "sugarbeets": "Sugar", "sugarcane": "Sugar"}

N_CLUSTERS = 3  # a scatter stays readable for color-blind viewers with at most three colors
SAMPLE_PER_CROP = 1500  # balances corn/wheat (tens of thousands of rows) against the fruit crops

# When each clustering model is the better choice, shown in the app next to the dropdown.
# DBSCAN is left out: our climate data is one continuous cloud, so it finds a single cluster.
CLUSTER_GUIDE = {
    "K-means": "Best general choice and the default. Works well when groups are roughly round and similar in "
               "size, is fast, and gives the clearest split on this data (highest silhouette score).",
    "Gaussian mixture": "Use when groups overlap or have different shapes and spreads. It gives a probability "
                        "of belonging to each cluster, which helps when a farm sits near a boundary.",
    "Agglomerative (Ward)": "Use when you want groups built bottom-up from the most similar seasons, giving "
                            "irregular, data-shaped boundaries. Slower on large data and has no rule for new "
                            "points, so your farm is placed by its 15 nearest seasons.",
    "BIRCH": "Use for very large or streaming datasets, where it summarizes the data to save memory. On a "
             "few thousand points like these it is the least accurate and splits the data unevenly.",
}
CLUSTER_METHODS = {
    "K-means": lambda seed: KMeans(N_CLUSTERS, n_init=10, random_state=seed),
    "Gaussian mixture": lambda seed: GaussianMixture(N_CLUSTERS, random_state=seed),
    "Agglomerative (Ward)": lambda seed: AgglomerativeClustering(N_CLUSTERS),
    "BIRCH": lambda seed: Birch(n_clusters=N_CLUSTERS),
}


def in_window(month, window):
    start, end = window
    return start <= month <= end if start <= end else month >= start or month <= end


def field_stage(crop, month=None):
    """'harvest', 'growing' or None for a crop in a given month (default: this month)."""
    month = month or datetime.date.today().month
    if in_window(month, HARVEST[crop]):
        return "harvest"
    if in_window(month, CROPS[crop]["season"]):
        return "growing"
    return None


def season_climate(monthly, season, n_seasons=10):
    """Mean temperature, mean monthly rain and mean coldest monthly low over the last `n_seasons`
    complete growing seasons. Ten seasons keep one unusually wet or dry year from deciding the result.

    `monthly` has columns year, month, temp, cold, rain. Seasons that wrap (start > end) are labelled
    by the year they end in, matching how data_prep.py builds the training data.
    """
    start, end = season
    df = monthly[monthly["month"].map(lambda m: in_window(m, season))].copy()
    if start > end:
        df.loc[df["month"] >= start, "year"] += 1
    length = len([m for m in range(1, 13) if in_window(m, season)])
    complete = df.groupby("year").filter(lambda g: len(g) == length)
    years = sorted(complete["year"].unique())[-n_seasons:]
    if not years:
        return None
    recent = complete[complete["year"].isin(years)]
    return {"temp": recent["temp"].mean(), "rain": recent["rain"].mean(),
            "cold": recent.groupby("year")["cold"].min().mean(), "years": (years[0], years[-1])}


def load_crop_data():
    """One row per location-year and crop with yield, season temperature (deg C) and monthly rain (mm)."""
    frames = []
    for crop in CROPS:
        path = PROCESSED_DIR / f"{crop}_yield_weather.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path, dtype={"fips": str})
        tavg = [c for c in df.columns if c.startswith("tavg_")]
        tmin = [c for c in df.columns if c.startswith("tmin_")]
        pcpn = [c for c in df.columns if c.startswith("pcpn_")]
        out = df[["crop", "state", "year", "yield", "unit"]].copy()
        out["fips"] = df["fips"] if "fips" in df.columns else None
        out["temp"] = df[tavg].mean(axis=1)
        out["rain"] = df[pcpn].mean(axis=1)
        out["cold"] = df[tmin].min(axis=1)  # coldest monthly low in the season
        frames.append(out.dropna(subset=["temp", "rain"]))
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True)


def crop_regions(data, recent_years=3):
    """States (and counties for county-level crops) that reported each crop in its last few years."""
    regions = {}
    for crop, df in data.groupby("crop"):
        recent = df[df["year"] > df["year"].max() - recent_years]
        regions[crop] = {"states": set(recent["state"]), "counties": set(recent["fips"].dropna())}
    return regions


class CropModel:
    def __init__(self, data, seed=0):
        # Good years: yield at or above the crop's median across locations in the same year
        median = data.groupby(["crop", "year"])["yield"].transform("median")
        good = data[data["yield"] >= median]

        self.stats = good.groupby("crop").agg(temp_mean=("temp", "mean"), temp_std=("temp", "std"),
                                              rain_mean=("rain", "mean"), rain_std=("rain", "std"),
                                              cold_mean=("cold", "mean"), cold_std=("cold", "std"),
                                              records=("temp", "size"))
        self.sample = pd.concat(g.sample(min(len(g), SAMPLE_PER_CROP), random_state=seed)
                                for _, g in good.groupby("crop")).reset_index(drop=True)

        x = self.sample[["temp", "rain"]].to_numpy()
        self.center, self.scale = x.mean(axis=0), x.std(axis=0)
        self.seed = seed

    def _z(self, x):
        return (np.asarray(x, dtype=float) - self.center) / self.scale

    def clustering(self, method="K-means"):
        return Clustering(self, method)

    def recommend(self, climate_by_crop, ph, irrigated):
        """Rank crops by climate match x soil pH fit. Returns a DataFrame sorted best first.

        `climate_by_crop` maps crop -> {"temp", "rain", optional "cold"}. Real-time mode measures each
        crop over its own season months; manual entry passes the same values for every crop.
        """
        rows = []
        for crop, s in self.stats.iterrows():
            if crop not in climate_by_crop:
                continue
            c = climate_by_crop[crop]
            temp, rain, cold = c["temp"], c["rain"], c.get("cold")
            # With irrigation, rainfall below what the crop usually gets is not held against it
            r = max(rain, s["rain_mean"]) if irrigated else rain
            z = ((temp - s["temp_mean"]) / s["temp_std"]) ** 2 + ((r - s["rain_mean"]) / s["rain_std"]) ** 2
            # Winters colder than the crop's good years are penalized; milder ones are not
            if cold is not None and not np.isnan(cold) and cold < s["cold_mean"]:
                z += ((cold - s["cold_mean"]) / s["cold_std"]) ** 2
            climate = float(np.exp(-0.5 * z))
            lo, hi = PH_RANGE[crop]
            ph_gap = max(lo - ph, ph - hi, 0)
            ph_fit = float(np.exp(-(ph_gap / 0.5) ** 2))
            rows.append({"crop": crop, "climate_match": climate, "ph_fit": ph_fit, "ph_range": (lo, hi),
                         "score": climate * ph_fit, "temp": temp, "rain": rain,
                         "temp_mean": s["temp_mean"], "rain_mean": s["rain_mean"]})
        return pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)


class Clustering:
    """Climate clusters of the good-yield seasons from one of CLUSTER_METHODS.

    Clusters are renumbered from coolest to warmest so a cluster keeps its color across methods.
    New points are assigned with each method's own rule: K-means, Gaussian mixture and BIRCH use
    their fitted predict step; agglomerative clustering has none, so its new points take the
    majority cluster of their 15 nearest seasons.
    """

    def __init__(self, model, method):
        self.model, self.method = model, method
        z = model._z(model.sample[["temp", "rain"]].to_numpy())
        self.estimator = CLUSTER_METHODS[method](model.seed)
        raw = self.estimator.fit_predict(z)
        order = np.argsort([model.sample["temp"].to_numpy()[raw == c].mean() for c in range(N_CLUSTERS)])
        self.relabel = np.argsort(order)  # raw cluster id -> cool-to-warm id
        self.labels = self.relabel[raw]
        self.centers = np.array([z[self.labels == c].mean(axis=0) for c in range(N_CLUSTERS)])
        self.silhouette = float(silhouette_score(z, self.labels))
        if not hasattr(self.estimator, "predict"):
            self.neighbors = KNeighborsClassifier(n_neighbors=15).fit(z, self.labels)
        self.names = self._name_clusters()

    def _predict_z(self, z):
        z = np.atleast_2d(z)
        if hasattr(self.estimator, "predict"):
            return self.relabel[self.estimator.predict(z)]
        return self.neighbors.predict(z)

    def membership(self, temp, rain):
        """Probability of belonging to each cluster; only the Gaussian mixture gives soft membership."""
        if not hasattr(self.estimator, "predict_proba"):
            return None
        raw = self.estimator.predict_proba(self.model._z([[temp, rain]]))[0]
        out = np.zeros(N_CLUSTERS)
        out[self.relabel] = raw
        return out

    def regions(self, temp_range, rain_range, steps=120):
        """Cluster assigned to every point of a temperature x rainfall grid, for shading the map."""
        temps = np.linspace(*temp_range, steps)
        rains = np.linspace(*rain_range, steps)
        tt, rr = np.meshgrid(temps, rains)
        grid = self.model._z(np.column_stack([tt.ravel(), rr.ravel()]))
        return temps, rains, self._predict_z(grid).reshape(tt.shape)

    def _name_clusters(self):
        """Name clusters by their centre relative to the others, e.g. 'Warm & wet'."""
        sample = self.model.sample.assign(cluster=self.labels)
        centers = sample.groupby("cluster")[["temp", "rain"]].mean()
        temp_word = {0: "Cool", 1: "Mild", 2: "Warm"}
        rain_mid = centers["rain"].median()
        names = {}
        for c, row in centers.iterrows():
            rain_word = "wet" if row["rain"] > rain_mid else "dry" if row["rain"] < rain_mid else "moderate rain"
            # Share of each crop's records that fall in this cluster
            share = (sample[sample["cluster"] == c].groupby("crop").size()
                     / sample.groupby("crop").size()).dropna().sort_values(ascending=False)
            names[c] = {"label": f"{temp_word[c]} & {rain_word}", "temp": row["temp"], "rain": row["rain"],
                        "top_crops": list(share.index[:3]), "size": int((self.labels == c).sum())}
        return names

    def cluster_of(self, temp, rain):
        return int(self._predict_z(self.model._z([temp, rain]))[0])


# ----------------------------- crop plan and growth tracking -----------------------------

def expected_yield(data, crop, fips, state, years=5):
    """Average yield over the last few years for the county, else the state, else all US locations."""
    df = data[data["crop"] == crop]
    for label, subset in ((f"your county", df[df["fips"] == fips]), (f"{state}", df[df["state"] == state]),
                          ("US locations", df)):
        if not subset.empty:
            recent = subset[subset["year"] > subset["year"].max() - years]
            return {"yield": recent["yield"].mean(), "unit": recent["unit"].iloc[0], "basis": label,
                    "years": (int(recent["year"].min()), int(recent["year"].max()))}
    return None


def daily_gdd(tmax, tmin, base):
    """Growing degree days per day (deg C), modified method: highs capped at GDD_CAP, lows floored at base."""
    hi = np.minimum(tmax, GDD_CAP)
    lo = np.clip(tmin, base, GDD_CAP)
    return np.maximum((hi + lo) / 2 - base, 0)


def growth_progress(crop, start, actual, last_year, today=None):
    """Track a planting against last year's weather at the same place.

    `actual` holds daily weather since `start` (date, tmax, tmin, rain); `last_year` holds the same
    calendar days one year earlier, covering the whole season. The heat a crop needs to reach harvest
    is taken as what last year's season delivered, so progress = heat so far / that total.
    """
    today = today or datetime.date.today()
    days, base = GROWTH[crop]
    ly = last_year.assign(gdd=daily_gdd(last_year["tmax"], last_year["tmin"], base))
    ly["day"] = (pd.to_datetime(ly["date"]) - pd.Timestamp(start - datetime.timedelta(days=365))).dt.days
    ly = ly[(ly["day"] >= 0) & (ly["day"] < days)]
    target = float(ly["gdd"].sum())

    act = actual.assign(gdd=daily_gdd(actual["tmax"], actual["tmin"], base))
    act["day"] = (pd.to_datetime(act["date"]) - pd.Timestamp(start)).dt.days
    act["cum_gdd"] = act["gdd"].cumsum()
    so_far = float(act["gdd"].sum())

    # Project forward with last year's daily heat for the remaining days
    done = int(act["day"].max()) + 1 if not act.empty else 0
    future = ly[ly["day"] >= done].copy()
    future["cum_gdd"] = so_far + future["gdd"].cumsum()
    reached = future[future["cum_gdd"] >= target]
    # With no heat on record for last year's window (no data yet, or a cold window), fall back to season length
    if target > 0 and so_far >= target:
        harvest = start + datetime.timedelta(days=int(act.loc[act["cum_gdd"] >= target, "day"].iloc[0]))
    elif target > 0 and not reached.empty:
        harvest = start + datetime.timedelta(days=int(reached["day"].iloc[0]))
    else:
        harvest = start + datetime.timedelta(days=days)

    # Pace vs last year over the same number of days
    ly_same = float(ly[ly["day"] < done]["gdd"].sum())
    progress = so_far / target if target else 0.0
    stage = growth_stage(progress) if progress > 0 or start > today else "Just planted"
    return {
        "target_gdd": target, "gdd": so_far, "progress": min(progress, 1.0), "stage": stage,
        "pace": (so_far / ly_same - 1) if ly_same else None, "harvest": harvest,
        "actual": act, "last_year": ly.assign(cum_gdd=ly["gdd"].cumsum()), "projection": future,
        "rain_mm": float(actual["rain"].sum()), "days": done,
    }


def growth_stage(progress):
    """Approximate growth stage from the share of season heat received."""
    if progress <= 0:
        return "Not planted yet"
    if progress < 0.10:
        return "Establishment"
    if progress < 0.45:
        return "Vegetative growth"
    if progress < 0.75:
        return "Flowering"
    if progress < 1.0:
        return "Ripening"
    return "Ready for harvest"


# ----------------------------- weather -> yield analysis -----------------------------

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
               "October", "November", "December"]
RAIN_STEP = 25.4  # report rain effects per inch (25.4 mm)


def _month_label(period):
    """'m07' -> 'July', 'p10' -> 'October (previous year)'."""
    name = MONTH_NAMES[int(period[1:]) - 1]
    return f"{name} (previous year)" if period[0] == "p" else name


def weather_drivers(crop, min_rows=40):
    """Which months' temperature and rainfall move this crop's yield, from the merged NASS + NOAA data.

    Yield is expressed as % above or below each location's own linear trend, which removes technology
    gains and fixed differences between places. Weather is expressed as the difference from that
    location's average for the month. For every month in the crop's season and both variables, a
    least-squares slope gives the % yield change per +1 deg C or per +1 inch of rain, with its
    correlation and p-value. A ridge regression on all months, cross-validated by holding out whole
    years, measures how much of the year-to-year swing in yield the weather explains.
    """
    from scipy import stats
    from sklearn.linear_model import RidgeCV
    from sklearn.model_selection import GroupKFold, cross_val_score

    path = PROCESSED_DIR / f"{crop}_yield_weather.csv"
    if not path.exists():
        return None
    df = pd.read_csv(path, dtype={"fips": str})
    df = df[df["estimate"] == "final"] if "estimate" in df.columns else df
    key = "fips" if "fips" in df.columns and df["fips"].notna().any() else "state"
    weather = [c for c in df.columns if c.startswith(("tavg_", "pcpn_"))]
    df = df.dropna(subset=weather + ["yield"])

    # Yield anomaly against each location's own trend (locations with at least 8 years)
    counts = df.groupby(key)["year"].transform("size")
    df = df[counts >= 8].copy()
    if len(df) < min_rows:
        return {"rows": len(df), "drivers": pd.DataFrame(), "r2": None, "key": key}
    year_c = df["year"] - df.groupby(key)["year"].transform("mean")
    yield_c = df["yield"] - df.groupby(key)["yield"].transform("mean")
    slope = (year_c * yield_c).groupby(df[key]).transform("sum") / (year_c ** 2).groupby(df[key]).transform("sum")
    fitted = df.groupby(key)["yield"].transform("mean") + slope * year_c
    df["anomaly"] = (df["yield"] / fitted - 1) * 100
    df = df[np.isfinite(df["anomaly"])]

    anomalies = df[weather] - df.groupby(key)[weather].transform("mean")
    rows = []
    for col in weather:
        var, period = col.split("_")
        x = anomalies[col] / (RAIN_STEP if var == "pcpn" else 1)
        fit = stats.linregress(x, df["anomaly"])
        rows.append({"variable": "rain" if var == "pcpn" else "temperature", "period": period,
                     "month": _month_label(period), "column": col,
                     "effect": fit.slope, "r": fit.rvalue, "p": fit.pvalue, "n": len(x),
                     # Middle 90% of the anomalies the slope was fitted on; outside it a straight line is unreliable
                     "low": float(x.quantile(0.05)), "high": float(x.quantile(0.95))})
    drivers = pd.DataFrame(rows)
    drivers = drivers.reindex(drivers["r"].abs().sort_values(ascending=False).index).reset_index(drop=True)

    # Out-of-sample share of yield swings explained by the weather (whole years held out)
    folds = min(5, df["year"].nunique())
    r2 = cross_val_score(RidgeCV(alphas=np.logspace(-2, 3, 12)), anomalies.to_numpy(), df["anomaly"].to_numpy(),
                         groups=df["year"].to_numpy(), cv=GroupKFold(n_splits=folds), scoring="r2")
    return {"rows": len(df), "locations": df[key].nunique(), "years": (int(df["year"].min()), int(df["year"].max())),
            "drivers": drivers, "r2": float(np.mean(r2)), "key": key}


def season_effects(drivers, monthly, season_year, planted, top=4, alpha=0.01):
    """Apply the strongest significant drivers to a planting's observed weather at a county.

    `monthly` is NOAA county data (year, month, temp, rain); `season_year` is the year the crop is
    harvested. Each driver month from planting onward that has been observed is compared with the
    county's average for that month over the previous 10 years; effect = driver slope x difference.
    """
    if drivers is None or drivers["drivers"].empty or monthly.empty:
        return []
    out = []
    for _, d in drivers["drivers"][drivers["drivers"]["p"] < alpha].head(top).iterrows():
        month = int(d["period"][1:])
        year = season_year - 1 if d["period"][0] == "p" else season_year
        if (year, month) < (planted.year, planted.month):
            continue  # weather before the crop was in the ground does not apply to it
        var = "rain" if d["variable"] == "rain" else "temp"
        this = monthly[(monthly["year"] == year) & (monthly["month"] == month)]
        past = monthly[(monthly["month"] == month) & monthly["year"].between(year - 10, year - 1)]
        if this.empty or past.empty:
            out.append({**d.to_dict(), "observed": False, "year": year})
            continue
        diff = this[var].iloc[0] - past[var].mean()
        step = diff / RAIN_STEP if var == "rain" else diff
        capped = float(np.clip(step, d["low"], d["high"]))
        out.append({**d.to_dict(), "observed": True, "year": year, "difference": diff,
                    "expected_effect": d["effect"] * capped, "capped": capped != step})
    return out
