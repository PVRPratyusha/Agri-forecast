"""Download and clean the USDA list of approved and licensed agricultural storage warehouses.

Warehouses: USDA AMS Warehouse and Commodity Management Division (WCMD) public dashboard,
            "Detailed Report" tab, which lists US Warehouse Act (USWA) licensed and CCC approved
            warehouses.  https://www.ams.usda.gov/services/warehouse/approved-storage-warehouses
Counties:   US Census Bureau 2020 county FIPS codes, used to join warehouses to the yield data.

No API key is needed.

Usage:
    python src/warehouses.py
"""
import io
import re
import unicodedata
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"

# Tableau serves any dashboard tab as CSV by adding .csv to the view URL
WAREHOUSE_URL = "https://publicdashboards.dl.usda.gov/t/MRP_PUB/views/WCMDDashboard/DetailedReport.csv"
COUNTY_URL = "https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt"

# Dashboard columns to keep, renamed. The export also repeats every field with a trailing "*"
# and filler symbols (▼, ►, ║) from the dashboard layout; those columns are dropped.
COLUMNS = {
    "Warehouse Name": "warehouse_name",
    "Business Entity": "business",
    "[License Number]": "license_number",
    "License Type": "license_type",
    "License Status*": "license_status",
    "CCC Code": "ccc_code",
    "CCC Status": "ccc_status",
    "Functional Unit": "functional_unit",
    "Commodity (Unit)": "commodity_unit",
    "Capacity*": "capacity",
    "City": "city",
    "County*": "county",
    "State": "state",
}

# Census county-equivalent suffixes stripped before matching on name
COUNTY_SUFFIXES = r"\s+(county|parish|borough|census area|city and borough|municipality|municipio)$"


def download(url, name):
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {name}")
    resp = requests.get(url, timeout=300)
    resp.raise_for_status()
    path = RAW_DIR / name
    path.write_bytes(resp.content)
    return resp.content


def clean_text(series):
    """Collapse repeated whitespace and strip; empty strings become NaN."""
    return series.str.replace(r"\s+", " ", regex=True).str.strip().replace("", pd.NA)


def county_key(name, drop_city=False):
    """Normalize a county name so 'St. John the Baptist Parish' and 'St. John Baptist',
    or 'Doña Ana County' and 'Dona Ana', match."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode().lower()
    name = name.replace("saint ", "st ").replace("sainte ", "ste ").replace(" the ", " ")
    name = re.sub(COUNTY_SUFFIXES, "", name)
    if drop_city:
        name = re.sub(r"\s+city$", "", name)
    return re.sub(r"[^a-z]", "", name)


def load_counties():
    raw = download(COUNTY_URL, "census_counties_2020.txt")
    counties = pd.read_csv(io.BytesIO(raw), sep="|", dtype=str)
    counties["fips"] = counties["STATEFP"] + counties["COUNTYFP"]
    counties = counties.rename(columns={"STATE": "state"})
    counties["key"] = counties["COUNTYNAME"].map(county_key)
    counties["short_key"] = counties["COUNTYNAME"].map(lambda n: county_key(n, drop_city=True))
    # Independent cities (VA, MD, MO, NV) can share a name with a county, e.g. "St. Louis city"
    # and "St. Louis County"; on the short key the county wins
    counties["is_city"] = counties["COUNTYNAME"].str.endswith(" city")
    return counties.sort_values("is_city")


def clean_warehouses(raw):
    df = pd.read_csv(io.BytesIO(raw), dtype=str)
    df = df[list(COLUMNS)].rename(columns=COLUMNS)

    # The export ends with a grand-total row whose fields are all "All"
    df = df[df["state"] != "All"]

    for col in ["warehouse_name", "business", "city", "county", "license_status", "ccc_status"]:
        df[col] = clean_text(df[col])
    # City spelling mixes "BENKELMAN" and "Imperial"
    df["city"] = df["city"].str.title()

    # Identifiers are wrapped in brackets, and "[]" means no federal license
    for col in ["license_number", "ccc_code"]:
        df[col] = df[col].str.strip("[]").replace("", pd.NA)

    # "Grain (BU)" -> commodity "Grain", unit "BU"
    parts = df["commodity_unit"].str.extract(r"^(.*) \((\w+)\)$")
    df["commodity"], df["unit"] = parts[0], parts[1]
    df = df.drop(columns="commodity_unit")

    # Capacity is text with thousands separators; 0 means no capacity reported
    df["capacity"] = pd.to_numeric(df["capacity"].str.replace(",", ""), errors="coerce")
    df.loc[df["capacity"] == 0, "capacity"] = pd.NA
    df["functional_unit"] = pd.to_numeric(df["functional_unit"], errors="coerce").astype("Int64")
    return df


def add_fips(df, counties):
    """Match on the full name first ("St. Louis City" -> St. Louis city), then without a
    trailing "city" ("Suffolk" -> Suffolk city, VA, which has no county of that name)."""
    names = df["county"].fillna("")
    full = counties.drop_duplicates(["state", "key"]).set_index(["state", "key"])["fips"]
    short = counties.drop_duplicates(["state", "short_key"]).set_index(["state", "short_key"])["fips"]
    df["fips"] = pd.MultiIndex.from_arrays([df["state"], names.map(county_key)]).map(full)
    fallback = pd.MultiIndex.from_arrays([df["state"], names.map(lambda n: county_key(n, drop_city=True))]).map(short)
    df["fips"] = df["fips"].fillna(pd.Series(fallback, index=df.index))
    return df


def main():
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    warehouses = clean_warehouses(download(WAREHOUSE_URL, "usda_warehouses.csv"))
    warehouses = add_fips(warehouses, load_counties())

    cols = ["warehouse_name", "business", "commodity", "capacity", "unit", "city", "county", "state",
            "fips", "license_type", "license_number", "license_status", "ccc_code", "ccc_status",
            "functional_unit"]
    warehouses = warehouses[cols].sort_values(["state", "county", "warehouse_name", "functional_unit"])
    out = PROCESSED_DIR / "warehouses.csv"
    warehouses.to_csv(out, index=False)

    unmatched = warehouses[warehouses["fips"].isna()]
    print(f"Saved {len(warehouses)} warehouse locations in {warehouses['state'].nunique()} states "
          f"to {out.relative_to(ROOT)}")
    print(f"  {len(unmatched)} without a county FIPS match "
          f"({unmatched['county'].isna().sum()} have no county in the source)")

    # Capacity per county and commodity, ready to join to the county-level yield files on fips
    by_county = (warehouses.dropna(subset=["fips"])
                 .groupby(["fips", "state", "county", "commodity", "unit"], as_index=False)
                 .agg(warehouses=("warehouse_name", "size"), capacity=("capacity", "sum")))
    out = PROCESSED_DIR / "warehouses_by_county.csv"
    by_county.to_csv(out, index=False)
    print(f"Saved {len(by_county)} county-commodity totals to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
