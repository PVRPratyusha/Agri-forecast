"""Live, key-free government data for the app: location lookup, weather, alerts and stock reports.

Location: US Census Bureau gazetteer (ZIP code and place centroids)
Weather:  National Weather Service API  https://www.weather.gov/documentation/services-web-api
Stocks:   USDA NASS Grain Stocks and Cold Storage reports, latest release text from ESMIS
          https://esmis.nal.usda.gov
Recent observed weather: NOAA nClimDiv county files (same files as data_prep.py)
Daily weather since planting: NOAA Regional Climate Centers ACIS, PRISM grid  https://www.rcc-acis.org/docs_webservices.html
"""
import datetime
import io
import re
import zipfile

import pandas as pd
import requests

from data_prep import NOAA_MISSING, NOAA_STATE_TO_USPS, RAW_DIR, download_noaa

NWS_URL = "https://api.weather.gov"
# NWS asks every client to identify itself in the User-Agent
HEADERS = {"User-Agent": "AgriForecast/0.1 (academic project)", "Accept": "application/geo+json"}
# Seconds to wait for a live service; a slow service then costs one card, not the whole page load
LIVE_TIMEOUT = 15

ACIS_URL = "https://data.rcc-acis.org/GridData"
GAZETTEER_URL ="https://www2.census.gov/geo/docs/maps-data/data/gazetteer/2025_Gazetteer/2025_Gaz_{kind}_national.zip"
ESMIS_URL = "https://esmis.nal.usda.gov"

# Alert types that matter for crops in the field, in storage or in transit
AG_ALERTS = {
    "Freeze Warning", "Freeze Watch", "Frost Advisory", "Hard Freeze Warning", "Hard Freeze Watch",
    "Flood Warning", "Flood Watch", "Flash Flood Warning", "Flash Flood Watch", "Flood Advisory",
    "Excessive Heat Warning", "Excessive Heat Watch", "Extreme Heat Warning", "Extreme Heat Watch", "Heat Advisory",
    "High Wind Warning", "High Wind Watch", "Wind Advisory", "Red Flag Warning", "Fire Weather Watch",
    "Winter Storm Warning", "Winter Storm Watch", "Blizzard Warning", "Ice Storm Warning",
    "Hurricane Warning", "Hurricane Watch", "Tropical Storm Warning", "Tropical Storm Watch",
    "Severe Thunderstorm Warning", "Tornado Warning", "Dust Storm Warning",
}

STATE_NAMES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas", "CA": "California", "CO": "Colorado",
    "CT": "Connecticut", "DE": "Delaware", "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas", "KY": "Kentucky", "LA": "Louisiana",
    "ME": "Maine", "MD": "Maryland", "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota",
    "MS": "Mississippi", "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York", "NC": "North Carolina",
    "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma", "OR": "Oregon", "PA": "Pennsylvania",
    "RI": "Rhode Island", "SC": "South Carolina", "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas",
    "UT": "Utah", "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming",
}
NAME_TO_STATE = {v.upper(): k for k, v in STATE_NAMES.items()}


def get_json(url, params=None):
    resp = requests.get(url, params=params, headers=HEADERS, timeout=LIVE_TIMEOUT)
    resp.raise_for_status()
    return resp.json()


# ----------------------------- location -----------------------------

def load_gazetteer(kind):
    """Census ZIP ("zcta") or place centroids, cached in data/raw."""
    path = RAW_DIR / f"census_gazetteer_{kind}.txt"
    if not path.exists():
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        resp = requests.get(GAZETTEER_URL.format(kind=kind), timeout=120)
        resp.raise_for_status()
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            path.write_bytes(zf.read(zf.namelist()[0]))
    df = pd.read_csv(path, sep="|", dtype=str)
    df.columns = df.columns.str.strip()
    df["lat"] = df["INTPTLAT"].astype(float)
    df["lon"] = df["INTPTLONG"].astype(float)
    return df


def geocode(text, zips, places):
    """Resolve '50010', 'Ames, IA' or 'Ames, Iowa' to (lat, lon, label). Returns None if not found."""
    text = text.strip()
    if re.fullmatch(r"\d{5}", text):
        row = zips[zips["GEOID"] == text]
        return None if row.empty else (row["lat"].iloc[0], row["lon"].iloc[0], f"ZIP {text}")

    match = re.fullmatch(r"(.+?),\s*([A-Za-z .]+)", text)
    if not match:
        return None
    city, state = match.group(1).strip().lower(), match.group(2).strip().upper()
    state = NAME_TO_STATE.get(state, state)
    # Place names carry a type suffix: "Ames city", "Story City city", "Hanover CDP"
    suffix = r"\s+(city|town|village|cdp|borough|municipality)$"
    names = places["NAME"].str.lower().str.replace(suffix, "", regex=True)
    row = places[(places["USPS"] == state) & (names == city)]
    if row.empty:
        return None
    name = re.sub(suffix, "", row["NAME"].iloc[0], flags=re.I)
    return row["lat"].iloc[0], row["lon"].iloc[0], f"{name}, {state}"


def nws_point(lat, lon):
    """City, state, county FIPS and forecast endpoints for a point. Raises for points outside the US."""
    p = get_json(f"{NWS_URL}/points/{lat:.4f},{lon:.4f}")["properties"]
    rel = p["relativeLocation"]["properties"]
    county_zone = p["county"].rsplit("/", 1)[-1]  # e.g. IAC169 -> state IA, county FIPS 19169
    state = county_zone[:2]
    return {
        "lat": lat, "lon": lon,
        "city": rel["city"], "state": state,
        "fips": USPS_TO_FIPS2[state] + county_zone[3:],
        "forecast": p["forecast"], "grid": p["forecastGridData"], "stations": p["observationStations"],
    }


# ----------------------------- weather -----------------------------

def forecast_periods(url):
    return get_json(url)["properties"]["periods"]


def _series(prop, days):
    """Values from an NWS grid series whose start time falls within the next `days` days."""
    end = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(days=days)
    out = []
    for v in prop["values"]:
        start = datetime.datetime.fromisoformat(v["validTime"].split("/")[0])
        if start <= end and v["value"] is not None:
            out.append(v["value"])
    return out


def week_outlook(grid_url, days=7):
    """Min/max temperature (deg C) and total precipitation (mm) over the next week."""
    p = get_json(grid_url)["properties"]
    lows, highs, rain = _series(p["minTemperature"], days), _series(p["maxTemperature"], days), \
        _series(p["quantitativePrecipitation"], days)
    return {"min_c": min(lows) if lows else None, "max_c": max(highs) if highs else None,
            "rain_mm": sum(rain)}


def latest_observation(stations_url):
    """Most recent observation from the nearest station that reports one."""
    stations = get_json(stations_url, params={"limit": 5})["features"]
    for st in stations:
        sid = st["properties"]["stationIdentifier"]
        try:
            p = get_json(f"{NWS_URL}/stations/{sid}/observations/latest")["properties"]
        except requests.HTTPError:
            continue
        if p["temperature"]["value"] is None:
            continue
        return {"station": st["properties"]["name"], "time": p["timestamp"], "text": p["textDescription"],
                "temp_c": p["temperature"]["value"], "humidity": p["relativeHumidity"]["value"]}
    return None


def alerts_at(lat, lon):
    feats = get_json(f"{NWS_URL}/alerts/active", params={"point": f"{lat:.4f},{lon:.4f}"})["features"]
    return [f["properties"] for f in feats]


def ag_alerts_national():
    """Active crop-relevant alerts as one row per alert x county (county FIPS from the SAME codes)."""
    feats = get_json(f"{NWS_URL}/alerts/active", params={"status": "actual"})["features"]
    rows = []
    for f in feats:
        p = f["properties"]
        if p["event"] not in AG_ALERTS:
            continue
        for same in (p.get("geocode") or {}).get("SAME", []):
            fips = same[-5:]
            state = NOAA_FIPS_TO_USPS.get(fips[:2])
            if state:
                rows.append({"event": p["event"], "severity": p["severity"], "state": state, "fips": fips,
                             "headline": p["headline"], "expires": p["expires"]})
    return pd.DataFrame(rows, columns=["event", "severity", "state", "fips", "headline", "expires"])


# USPS by 2-digit state FIPS, for alert county codes
NOAA_FIPS_TO_USPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE", "12": "FL",
    "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA", "20": "KS", "21": "KY", "22": "LA",
    "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN", "28": "MS", "29": "MO", "30": "MT", "31": "NE",
    "32": "NV", "33": "NH", "34": "NJ", "35": "NM", "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK",
    "41": "OR", "42": "PA", "44": "RI", "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT",
    "51": "VA", "53": "WA", "54": "WV", "55": "WI", "56": "WY",
}
USPS_TO_FIPS2 = {v: k for k, v in NOAA_FIPS_TO_USPS.items()}


def county_monthly(fips, since=2015):
    """Observed monthly mean and minimum temperature (deg C) and rainfall (mm) for one county from the NOAA nClimDiv
    county files. Scans only that county's lines, so it is fast even though the files are large."""
    state = NOAA_FIPS_TO_USPS.get(fips[:2])
    noaa_state = {v: k for k, v in NOAA_STATE_TO_USPS.items()}.get(state)
    if noaa_state is None:
        return pd.DataFrame()
    prefix = f"{noaa_state:02d}{fips[2:]}"
    frames = []
    for var, element in (("temp", "tmpc"), ("cold", "tmin"), ("rain", "pcpn")):
        missing = NOAA_MISSING["pcpn" if var == "rain" else "tavg"]
        rows = []
        with open(download_noaa(element, "COUNTY")) as fh:
            for line in fh:
                if line.startswith(prefix) and int(line[7:11]) >= since:
                    for month, v in enumerate(map(float, line[11:].split()), start=1):
                        if round(v, 2) != missing:
                            rows.append((int(line[7:11]), month, v))
        df = pd.DataFrame(rows, columns=["year", "month", var])
        df[var] = df[var] * 25.4 if var == "rain" else (df[var] - 32) * 5 / 9
        frames.append(df.set_index(["year", "month"]))
    return frames[0].join(frames[1:], how="inner").reset_index()


def daily_weather(lat, lon, start, end):
    """Daily high/low (deg C) and rain (mm) for a point from the ACIS PRISM grid (data through yesterday)."""
    params = {"loc": f"{lon:.4f},{lat:.4f}", "sdate": start.isoformat(), "edate": end.isoformat(),
              "grid": "21", "elems": "maxt,mint,pcpn"}
    resp = requests.post(ACIS_URL, json=params, headers={"User-Agent": HEADERS["User-Agent"]}, timeout=LIVE_TIMEOUT * 2)
    resp.raise_for_status()
    df = pd.DataFrame(resp.json().get("data", []), columns=["date", "tmax", "tmin", "rain"])
    df[["tmax", "tmin", "rain"]] = df[["tmax", "tmin", "rain"]].apply(pd.to_numeric, errors="coerce")
    df = df[(df["tmax"] > -999) & (df["tmin"] > -999)]  # -999 marks missing days
    df["tmax"] = (df["tmax"] - 32) * 5 / 9
    df["tmin"] = (df["tmin"] - 32) * 5 / 9
    df["rain"] = df["rain"].clip(lower=0) * 25.4
    df["date"] = pd.to_datetime(df["date"]).dt.date
    return df.reset_index(drop=True)


# ----------------------------- USDA stock reports -----------------------------

def latest_report_text(publication):
    """Text of the newest release of an ESMIS publication, e.g. 'grain-stocks'."""
    page = requests.get(f"{ESMIS_URL}/publication/{publication}", timeout=LIVE_TIMEOUT).text
    links = re.findall(r'(?:https://esmis\.nal\.usda\.gov/sites/default/)?(release-files/[^"\s]+?\.txt)', page)
    if not links:
        raise RuntimeError(f"No text release found for {publication}")
    resp = requests.get(f"{ESMIS_URL}/sites/default/{links[0]}", timeout=LIVE_TIMEOUT)
    resp.raise_for_status()
    return resp.text


def _number(text):
    text = text.strip().replace(",", "")
    return float(text) if re.fullmatch(r"-?\d+(\.\d+)?", text) else None  # (D), (NA), (X) -> None


def grain_stocks(text):
    """State on-farm / off-farm / total stocks (1,000 bu) for corn and all wheat, latest two years."""
    rows = []
    for crop, title in (("corn", "Corn"), ("wheat", "All Wheat")):
        match = re.search(rf"^{title} Stocks by Position - States and United States: (.+? \d{{4}}) and (\d{{4}})\s*$",
                          text, re.M)
        if not match:
            continue
        date, prev_year, year = match.group(1), int(match.group(1)[-4:]), int(match.group(2))
        body = text[match.end():].split("\n")
        started = False
        for line in body:
            if line.startswith("---"):
                if started:
                    break
                continue
            if ":" not in line:
                continue
            name, _, nums = line.partition(":")
            name = name.strip(" .")
            cells = nums.split()
            if not name or len(cells) != 6:
                continue
            started = True
            state = "US" if name == "United States" else NAME_TO_STATE.get(name.upper())
            if state is None:
                continue
            vals = [_number(c) for c in cells]
            rows.append({"crop": crop, "state": state, "as_of": date.rsplit(" ", 1)[0] + f" {year}",
                         "on_farm": vals[3], "off_farm": vals[4], "total": vals[5],
                         "total_prev": vals[2], "off_farm_prev": vals[1], "prev_year": prev_year})
    return pd.DataFrame(rows)


COLD_STORAGE_ITEMS = {
    "Apples": "apples", "Blueberries": "blueberries", "Peaches": "peaches",
    "Total red raspberries": "raspberries", "Total strawberries": "strawberries",
    "Orange": "oranges", "Carrots, diced": "carrots", "Carrots, other": "carrots",
}


def cold_storage(text):
    """US frozen stocks (1,000 lb) of our crops and % of a year ago, from the Cold Storage report."""
    date = re.search(r"Cold Storage - United States: (\w+ \d+, \d{4})", text)
    rows = []
    for line in text.split("\n"):
        name, _, nums = line.partition(":")
        name = name.strip(" .")
        if name in COLD_STORAGE_ITEMS:
            cells = nums.split()
            if len(cells) >= 5 and _number(cells[2]) is not None:
                rows.append({"crop": COLD_STORAGE_ITEMS[name], "item": name, "stocks": _number(cells[2]),
                             "pct_year_ago": _number(cells[3])})
    df = pd.DataFrame(rows).drop_duplicates("item")  # regional tables repeat item names
    df["as_of"] = date.group(1) if date else ""
    return df
