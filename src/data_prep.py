"""Download and merge crop yield (USDA NASS) and weather (NOAA nClimDiv) for multiple crops.

Yield:   USDA NASS Quick Stats API  https://quickstats.nass.usda.gov/api
Weather: NOAA NCEI nClimDiv         https://www.ncei.noaa.gov/pub/data/cirs/climdiv/

Field crops (corn, wheat) are published per county; sugar, fruit and vegetable yields only
per state. Each crop is merged with weather at its own level and growing season.

Requires a free NASS API key in the NASS_API_KEY environment variable.

Usage:
    export NASS_API_KEY=your_key
    python src/data_prep.py                                  # all crops, all states
    python src/data_prep.py --crops corn apples --states IA WA --start 1990
    python src/data_prep.py --include-forecasts              # add current-season NASS forecasts
"""
import argparse
import datetime
import os
import re
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

NASS_URL = "https://quickstats.nass.usda.gov/api/"
NASS_ROW_LIMIT = 50000
NOAA_URL = "https://www.ncei.noaa.gov/pub/data/cirs/climdiv/"

# series: exact NASS short_desc names, in order of preference. Later entries are older names
#   of the same series and only fill years the first one doesn't cover.
# level: finest level NASS publishes the series at.
# season: (start_month, end_month) of the main US growing window; start > end wraps
#   into the previous calendar year (e.g. winter wheat is planted in autumn).
CROPS = {
    "corn": {"series": ["CORN, GRAIN - YIELD, MEASURED IN BU / ACRE"], "level": "COUNTY", "season": (4, 9)},
    # County-level all-wheat yield stops in 2007; winter wheat runs to the present
    "wheat": {"series": ["WHEAT, WINTER - YIELD, MEASURED IN BU / ACRE"], "level": "COUNTY", "season": (10, 6)},
    "sugarbeets": {"series": ["SUGARBEETS - YIELD, MEASURED IN TONS / ACRE"], "level": "STATE", "season": (4, 10)},
    "sugarcane": {"series": ["SUGARCANE, SUGAR - YIELD, MEASURED IN TONS / ACRE"], "level": "STATE", "season": (3, 11)},
    "carrots": {"series": ["CARROTS - YIELD, MEASURED IN CWT / ACRE"], "level": "STATE", "season": (1, 12)},
    "lettuce": {"series": ["LETTUCE, HEAD - YIELD, MEASURED IN CWT / ACRE",
                           "LETTUCE, HEAD, FRESH MARKET - YIELD, MEASURED IN CWT / ACRE"],
                "level": "STATE", "season": (1, 12)},
    "apples": {"series": ["APPLES - YIELD, MEASURED IN LB / ACRE"], "level": "STATE", "season": (3, 9)},
    # Citrus years are labelled by the season's end: 2026 = Oct 2025 - Jul 2026 harvest
    "oranges": {"series": ["ORANGES - YIELD, MEASURED IN BOXES / ACRE"], "level": "STATE", "season": (2, 1)},
    "peaches": {"series": ["PEACHES - YIELD, MEASURED IN TONS / ACRE"], "level": "STATE", "season": (2, 8)},
    "strawberries": {"series": ["STRAWBERRIES - YIELD, MEASURED IN CWT / ACRE"], "level": "STATE", "season": (1, 12)},
    "blueberries": {"series": ["BLUEBERRIES, TAME - YIELD, MEASURED IN LB / ACRE",
                               "BLUEBERRIES, TAME, UTILIZED - YIELD, MEASURED IN LB / ACRE"],
                    "level": "STATE", "season": (3, 8)},
    "raspberries": {"series": ["RASPBERRIES - YIELD, MEASURED IN LB / ACRE",
                               "RASPBERRIES, UTILIZED - YIELD, MEASURED IN LB / ACRE"],
                    "level": "STATE", "season": (3, 9)},
}

# NASS county codes that differ from the Census FIPS code NOAA uses
NASS_FIPS_FIXES = {"29193": "29186"}  # Ste. Genevieve, MO

# nClimDiv element codes: tavg/tmax/tmin in deg F, pcpn in inches
NOAA_ELEMENTS = {"tavg": "tmpc", "tmax": "tmax", "tmin": "tmin", "pcpn": "pcpn"}
# Exact missing-value markers; a plain threshold would erase real sub -9.99 F winter temperatures
NOAA_MISSING = {"tavg": -99.90, "tmax": -99.90, "tmin": -99.90, "pcpn": -9.99}
# File suffix and fixed-width ID length: county IDs are SS CCC EE YYYY, state IDs SSS D EE YYYY
NOAA_LEVELS = {"COUNTY": ("cy", 11), "STATE": ("st", 10)}

# nClimDiv uses its own alphabetical state codes, not FIPS
NOAA_STATE_TO_USPS = {
    1: "AL", 2: "AZ", 3: "AR", 4: "CA", 5: "CO", 6: "CT", 7: "DE", 8: "FL", 9: "GA", 10: "ID",
    11: "IL", 12: "IN", 13: "IA", 14: "KS", 15: "KY", 16: "LA", 17: "ME", 18: "MD", 19: "MA",
    20: "MI", 21: "MN", 22: "MS", 23: "MO", 24: "MT", 25: "NE", 26: "NV", 27: "NH", 28: "NJ",
    29: "NM", 30: "NY", 31: "NC", 32: "ND", 33: "OH", 34: "OK", 35: "OR", 36: "PA", 37: "RI",
    38: "SC", 39: "SD", 40: "TN", 41: "TX", 42: "UT", 43: "VT", 44: "VA", 45: "WA", 46: "WV",
    47: "WI", 48: "WY", 49: "HI", 50: "AK",
}
USPS_TO_FIPS = {
    "AL": 1, "AK": 2, "AZ": 4, "AR": 5, "CA": 6, "CO": 8, "CT": 9, "DE": 10, "FL": 12, "GA": 13,
    "HI": 15, "ID": 16, "IL": 17, "IN": 18, "IA": 19, "KS": 20, "KY": 21, "LA": 22, "ME": 23,
    "MD": 24, "MA": 25, "MI": 26, "MN": 27, "MS": 28, "MO": 29, "MT": 30, "NE": 31, "NV": 32,
    "NH": 33, "NJ": 34, "NM": 35, "NY": 36, "NC": 37, "ND": 38, "OH": 39, "OK": 40, "OR": 41,
    "PA": 42, "RI": 44, "SC": 45, "SD": 46, "TN": 47, "TX": 48, "UT": 49, "VT": 50, "VA": 51,
    "WA": 53, "WV": 54, "WI": 55, "WY": 56,
}


# ----------------------------- NASS yield -----------------------------

def nass_get(endpoint, params):
    resp = requests.get(NASS_URL + endpoint, params=params, timeout=300)
    # NASS answers 400 {"error": ["no data"]} when a query matches nothing
    if resp.status_code == 400 and "no data" in resp.text.lower():
        return None
    resp.raise_for_status()
    return resp.json()


def nass_query(params, start, end):
    """Fetch rows for [start, end], splitting the year range while it exceeds the API row limit."""
    params = {**params, "year__GE": start, "year__LE": end}
    count = int((nass_get("get_counts/", params) or {}).get("count", 0))
    if count == 0:
        return []
    if count > NASS_ROW_LIMIT and start < end:
        mid = (start + end) // 2
        return nass_query(params, start, mid) + nass_query(params, mid + 1, end)
    return nass_get("api_GET/", {**params, "format": "JSON"})["data"]


def forecast_month(period):
    """Order NASS forecast periods like 'YEAR - AUG FORECAST' by month (Oct-Dec come before Jan-Jul for citrus)."""
    months = ["OCT", "NOV", "DEC", "JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP"]
    match = re.search(r"YEAR - (\w{3}) FORECAST", period)
    return months.index(match.group(1)) if match else -1


def fetch_yield(crop, states, start, end, api_key, include_forecasts):
    spec = CROPS[crop]
    params = {
        "key": api_key,
        "source_desc": "SURVEY",
        "domain_desc": "TOTAL",
        "short_desc": spec["series"],  # repeated parameter = OR filter
        "agg_level_desc": spec["level"],
    }
    if states:
        params["state_alpha"] = states

    df = pd.DataFrame(nass_query(params, start, end))
    print(f"NASS {crop}: {len(df)} rows")
    if df.empty:
        return df

    # Annual estimate is "YEAR"; current-season forecasts are "YEAR - <MON> FORECAST"
    period = df["reference_period_desc"]
    df = df[(period == "YEAR") | period.str.contains("FORECAST")]

    # Suppressed values "(D)", "(Z)", "(NA)" become NaN; remove thousands separators first
    df["yield"] = pd.to_numeric(df["Value"].str.replace(",", "").str.strip(), errors="coerce")
    df = df.dropna(subset=["yield"])

    df["state"] = df["state_alpha"]
    df["year"] = df["year"].astype(int)
    keys = ["state", "year"]
    if spec["level"] == "COUNTY":
        # "OTHER (COMBINED) COUNTIES" is a catch-all that matches no real county
        df = df[df["county_code"] != "998"]
        df["fips"] = df["state_fips_code"].str.zfill(2) + df["county_code"].str.zfill(3)
        df["fips"] = df["fips"].replace(NASS_FIPS_FIXES)
        df["county"] = df["county_name"]
        keys = ["fips", "county"] + keys

    # During the season NASS copies the latest forecast into the "YEAR" row until the final
    # estimate is released, so a recent YEAR row not newer than the last forecast is still a forecast
    df["load_time"] = pd.to_datetime(df["load_time"])
    is_forecast = df["reference_period_desc"] != "YEAR"
    last_forecast = df[is_forecast].groupby(keys + ["short_desc"])["load_time"].max().rename("last_forecast")
    df = df.join(last_forecast, on=keys + ["short_desc"])
    provisional = (df["load_time"] <= df["last_forecast"]) & (df["year"] >= datetime.date.today().year - 1)
    df["estimate"] = "final"
    df.loc[is_forecast | provisional, "estimate"] = "forecast"

    # Per location-year keep one value: preferred series first, then final over the latest forecast
    if not include_forecasts:
        df = df[df["estimate"] == "final"]
    df["priority"] = df["short_desc"].map({s: -i for i, s in enumerate(spec["series"])})
    df["rank"] = df["reference_period_desc"].map(lambda p: 99 if p == "YEAR" else forecast_month(p))
    df = df.sort_values(["priority", "rank"]).groupby(keys, as_index=False).last()

    df["crop"] = crop
    df["series"] = df["short_desc"]
    df["unit"] = df["short_desc"].str.split("MEASURED IN ").str[-1]
    df["level"] = spec["level"].lower()
    return df[["crop", "level"] + keys + ["yield", "unit", "estimate", "series"]].sort_values(keys)


# ----------------------------- NOAA weather -----------------------------

def latest_noaa_file(element, level):
    listing = requests.get(NOAA_URL, timeout=60).text
    suffix = NOAA_LEVELS[level][0]
    names = sorted(set(re.findall(rf"climdiv-{element}{suffix}-v[\d.]+-\d{{8}}", listing)))
    if not names:
        raise RuntimeError(f"No nClimDiv file found for {element}{suffix}")
    return names[-1]


def download_noaa(element, level):
    name = latest_noaa_file(element, level)
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    path = RAW_DIR / name
    if not path.exists():
        print(f"Downloading {name}")
        resp = requests.get(NOAA_URL + name, timeout=300)
        resp.raise_for_status()
        path.write_bytes(resp.content)
    return path


def parse_noaa(path, var, level, start, end):
    """Parse a fixed-width nClimDiv file into long format (state[, fips], year, month, value)."""
    id_len = NOAA_LEVELS[level][1]
    cols = ["id"] + list(range(1, 13))
    df = pd.read_fwf(path, widths=[id_len] + [7] * 12, names=cols, dtype={"id": str})

    if level == "COUNTY":
        df["state"] = df["id"].str[:2].astype(int).map(NOAA_STATE_TO_USPS)
        df["fips"] = df["state"].map(USPS_TO_FIPS).astype("Int64").astype(str).str.zfill(2) + df["id"].str[2:5]
        keys = ["state", "fips"]
    else:
        # Codes above 50 are regional and national aggregates, not states
        df["state"] = df["id"].str[:3].astype(int).map(NOAA_STATE_TO_USPS)
        keys = ["state"]
    df["year"] = df["id"].str[-4:].astype(int)
    df = df[df["state"].notna() & df["year"].between(start, end)]

    long = df.melt(id_vars=keys + ["year"], value_vars=list(range(1, 13)), var_name="month", value_name=var)
    long[var] = long[var].astype(float)
    long.loc[long[var].round(2) == NOAA_MISSING[var], var] = float("nan")  # months not yet observed

    # Convert to metric: deg F -> deg C, inches -> mm
    if var == "pcpn":
        long[var] = long[var] * 25.4
    else:
        long[var] = (long[var] - 32) * 5 / 9
    return long


def load_weather(level, start, end):
    """Monthly weather in long format for every county or state; start - 1 covers seasons that wrap."""
    long = None
    for var, element in NOAA_ELEMENTS.items():
        part = parse_noaa(download_noaa(element, level), var, level, start - 1, end)
        long = part if long is None else long.merge(part, on=[c for c in part.columns if c != var])
    return long


def season_weather(long, season):
    """Pivot monthly weather to one row per location and season year.

    Months from the previous calendar year (wrapping seasons) are named p<MM>, others m<MM>.
    """
    first, last = season
    df = long.copy()
    if first <= last:
        df = df[df["month"].between(first, last)]
        df["prefix"] = "m"
    else:
        df = df[(df["month"] >= first) | (df["month"] <= last)]
        prev = df["month"] >= first
        df.loc[prev, "year"] += 1
        df["prefix"] = prev.map({True: "p", False: "m"})

    keys = [c for c in ("state", "fips") if c in df.columns]
    df["period"] = df["prefix"] + df["month"].astype(int).map("{:02d}".format)
    values = list(NOAA_ELEMENTS)
    wide = df.pivot_table(index=keys + ["year"], columns="period", values=values, dropna=False)

    # Order columns chronologically within the season (p before m)
    periods = sorted(df["period"].unique(), key=lambda p: (p[0] == "m", p[1:]))
    wide = wide.reindex(columns=pd.MultiIndex.from_product([values, periods]))
    wide.columns = [f"{var}_{period}" for var, period in wide.columns]
    return wide.reset_index()


# ----------------------------- main -----------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--crops", nargs="+", choices=list(CROPS), default=list(CROPS))
    parser.add_argument("--states", nargs="+", help="USPS codes, e.g. IA CA. Default: every state NASS reports")
    parser.add_argument("--start", type=int, default=1980)
    parser.add_argument("--end", type=int, default=datetime.date.today().year)
    parser.add_argument("--include-forecasts", action="store_true",
                        help="Use the latest NASS forecast for years without a final estimate yet")
    args = parser.parse_args()

    api_key = os.environ.get("NASS_API_KEY")
    if not api_key:
        raise SystemExit("Set NASS_API_KEY (free key: https://quickstats.nass.usda.gov/api)")

    states = [s.upper() for s in args.states] if args.states else None
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    weather = {}
    all_yield = []
    for crop in args.crops:
        spec = CROPS[crop]
        yld = fetch_yield(crop, states, args.start, args.end, api_key, args.include_forecasts)
        if yld.empty:
            print(f"  no {crop} yield data for the selected states/years, skipping")
            continue
        all_yield.append(yld)

        level = spec["level"]
        if level not in weather:
            weather[level] = load_weather(level, args.start, args.end)
        season = season_weather(weather[level], spec["season"])

        keys = ["fips", "state", "year"] if level == "COUNTY" else ["state", "year"]
        merged = yld.merge(season, on=keys, how="inner")
        # Drop location-years NOAA has no weather for at all (e.g. Hawaii before 1991);
        # partly empty rows are current seasons whose later months haven't happened yet
        weather_cols = [c for c in season.columns if c not in keys]
        merged = merged.dropna(subset=weather_cols, how="all")
        partial = merged[weather_cols].isna().any(axis=1).sum()
        if partial:
            print(f"  {partial} rows have months not yet observed (current season)")
        out = PROCESSED_DIR / f"{crop}_yield_weather.csv"
        merged.to_csv(out, index=False)
        loc = "counties" if level == "COUNTY" else "states"
        print(f"  saved {len(merged)} rows ({merged[keys[0]].nunique()} {loc}, "
              f"{merged['year'].min()}-{merged['year'].max()}) to {out.relative_to(ROOT)}")

    if all_yield:
        combined = pd.concat(all_yield, ignore_index=True)
        combined.to_csv(RAW_DIR / "nass_yield_all_crops.csv", index=False)
        print(f"Saved {len(combined)} yield rows for {combined['crop'].nunique()} crops to data/raw/nass_yield_all_crops.csv")


if __name__ == "__main__":
    main()
