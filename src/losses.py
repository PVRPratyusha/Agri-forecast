"""Download and summarize USDA crop insurance payouts by cause of loss.

Source: USDA Risk Management Agency (RMA), Summary of Business - Cause of Loss with month of loss
        https://www.rma.usda.gov/tools-reports/summary-of-business/cause-loss

Each record is an insured crop in a county, with the cause and month of loss and the indemnity
(payout) for that cause. This shows which weather events actually cost farmers money, where and when.
No API key is needed.

Usage:
    python src/losses.py                 # 2015-2024
    python src/losses.py --start 2010 --end 2024
"""
import argparse
import io
import zipfile
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = ROOT / "data" / "processed"
RMA_URL = "https://pubfs-rma.fpac.usda.gov/pub/Web_Data_Files/Summary_of_Business/cause_of_loss/colsom_{year}.zip"

# Column layout of the pipe-delimited colsom files (RMA record description)
COLUMNS = [
    "commodity_year", "state_code", "state", "county_code", "county", "commodity_code", "commodity",
    "plan_code", "plan", "coverage_category", "stage_code", "cause_code", "cause", "month_code", "month_name",
    "loss_year", "policies_earning", "policies_indemnified", "net_planted_qty", "net_endorsed_acres",
    "liability", "total_premium", "producer_premium", "subsidy", "state_subsidy", "additional_subsidy",
    "efa_discount", "net_determined_qty", "indemnity", "loss_ratio",
]

# RMA commodity names for our crops. Carrots, lettuce and raspberries have no federal policies.
COMMODITIES = {
    "Corn": "corn", "Wheat": "wheat", "Sugar Beets": "sugarbeets", "Sugarcane": "sugarcane",
    "Apples": "apples", "Oranges": "oranges", "Peaches": "peaches", "Processing Cling Peaches": "peaches",
    "Fresh Freestone Peaches": "peaches", "Strawberries": "strawberries", "Blueberries": "blueberries",
}

# Payouts that are not caused by weather or pests in the field
NON_WEATHER = {"Decline in Price", "ARPI/SCO/ECO/STAX/MP/PACE Crops Only",
               "ARPI/SCO/ECO/STAX/MP/HIP-WI/PACE Crops Only"}

# Plain-language groups of RMA causes
CAUSE_GROUPS = {
    "Too much rain / flooding": ["Excess Moisture/Precipitation/Rain", "Flood", "Cold Wet Weather",
                                 "Low Salinity Caused by Excessive Rainfall"],
    "Drought / heat": ["Drought", "Heat", "Hot Wind", "Excess Sun", "Failure of Irrigation Supply"],
    "Hail": ["Hail"],
    "Wind / storms": ["Wind/Excess Wind", "Hurricane", "Tropical Depression", "Tropical Storm", "Tornado",
                      "Cyclone", "Hurricane/Tropical Depression"],
    "Freeze / frost / cold": ["Freeze", "Frost", "Cold Winter", "Insufficient Chilling Hours"],
    "Pests / disease / quality": ["Insects", "Plant Disease", "Mycotoxin", "Falling Numbers", "Wildlife",
                                  "Asian Soybean Rust"],
}
GROUP_OF = {cause: group for group, causes in CAUSE_GROUPS.items() for cause in causes}


def load_year(year):
    resp = requests.get(RMA_URL.format(year=year), timeout=300)
    resp.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
        raw = zf.read(zf.namelist()[0])
    df = pd.read_csv(io.BytesIO(raw), sep="|", header=None, names=COLUMNS, dtype=str, encoding="latin-1")
    for col in ("commodity", "cause", "county", "state"):
        df[col] = df[col].str.strip()

    df = df[df["commodity"].isin(COMMODITIES) & ~df["cause"].isin(NON_WEATHER)].copy()
    df["crop"] = df["commodity"].map(COMMODITIES)
    df["group"] = df["cause"].map(GROUP_OF).fillna("Other")
    df["fips"] = df["state_code"].str.zfill(2) + df["county_code"].str.zfill(3)
    df["month"] = pd.to_numeric(df["month_code"], errors="coerce")
    df["indemnity"] = pd.to_numeric(df["indemnity"], errors="coerce").fillna(0)
    df["policies_indemnified"] = pd.to_numeric(df["policies_indemnified"], errors="coerce").fillna(0)
    df["year"] = int(year)
    # County code 999 is RMA's "all other counties" bucket
    df = df[df["county_code"] != "999"]
    keys = ["year", "state", "fips", "county", "crop", "group", "cause", "month"]
    return df.groupby(keys, as_index=False, dropna=False)[["indemnity", "policies_indemnified"]].sum()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start", type=int, default=2015)
    parser.add_argument("--end", type=int, default=2024)
    args = parser.parse_args()

    frames = []
    for year in range(args.start, args.end + 1):
        df = load_year(year)
        print(f"RMA {year}: {len(df)} crop-county-cause records, ${df['indemnity'].sum() / 1e9:.2f}B paid")
        frames.append(df)
    losses = pd.concat(frames, ignore_index=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    out = PROCESSED_DIR / "insured_losses.csv"
    losses.to_csv(out, index=False)
    print(f"Saved {len(losses)} records to {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
