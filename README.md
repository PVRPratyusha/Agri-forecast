# Agri Forecast: Weather-Based Crop Yield Analysis and Planning

Agri Forecast uses US government data to answer these questions:
- Which crop suits my farm's soil and climate?
- How does weather move that crop's yield?
- How is my crop growing this season?
- Which weather is hurting crops and storage today?

It combines 46 years of USDA crop yields with NOAA weather, USDA crop insurance losses, USDA warehouse lists and live National Weather Service forecasts. All of this is in one Streamlit app written for beginners.

---

## Contents

1. [What the app does](#what-the-app-does)
2. [Data sources](#data-sources)
3. [Crops](#crops)
4. [Data cleaning](#data-cleaning)
5. [Methods](#methods)
6. [Results](#results)
7. [Application guide](#application-guide)
8. [Project structure](#project-structure)
9. [Setup and usage](#setup-and-usage)
10. [Limitations](#limitations)
11. [Future work](#future-work)
12. [Tech stack](#tech-stack)

---

## What the app does

| Page | What you get |
|---|---|
| **Home** | Weather news for your location, which crops today's weather affects (near you and across the US), and nearby USDA warehouses with the latest grain and cold storage stocks |
| **Analyze crop** | Enter soil (N, P, K, pH, irrigation) and weather (real-time or manual) to get a recommended crop with its match score and a climate cluster map built with one of four clustering models |
| **Crop plan** | Fix a plan with crop, area and start date: expected yield, production, harvest date and where to store the harvest. You can make several plans, one per crop or field |
| **Track my crops** | Growth progress from daily weather (heat units), estimated harvest date, this week's advice, how weather has moved yield this season, and tips to reduce losses based on past insurance payouts |

Every number shown is either computed from government data or clearly marked as a guide value (see [What is computed vs guide values](#what-is-computed-from-data-vs-guide-values)).

## Data sources

All data comes from US federal government sources. None of it is committed to the repo; the scripts in `src/` download it.

| Data | Source | Access | Coverage | Used for |
|---|---|---|---|---|
| Crop yield | [USDA NASS Quick Stats API](https://quickstats.nass.usda.gov/api) (survey program) | Free API key, JSON | County, state and national yield; 1866 to present depending on crop | Recommendation, clusters, expected yield, weather effects |
| Monthly weather | [NOAA NCEI nClimDiv](https://www.ncei.noaa.gov/pub/data/cirs/climdiv/) ([county format](https://www.ncei.noaa.gov/pub/data/cirs/climdiv/county-readme.txt), [state format](https://www.ncei.noaa.gov/pub/data/cirs/climdiv/divisional-readme.txt)) | Public fixed-width text files, no key | Monthly average, max and min temperature and precipitation per county and state, 1895 to present | Merged with yield; real-time climate of the user's county |
| Daily weather | [NOAA Regional Climate Centers ACIS](https://www.rcc-acis.org/docs_webservices.html), PRISM grid | Public JSON API, no key | Daily high, low and precipitation for any US point, through yesterday | Growth tracking (heat units) |
| Forecasts and alerts | [National Weather Service API](https://www.weather.gov/documentation/services-web-api) | Public JSON API, no key (User-Agent required) | Current conditions, 7-day forecast, hourly grid data, active alerts with county codes | Weather news, crops affected, weekly advice |
| Storage warehouses | [USDA AMS approved storage warehouses](https://www.ams.usda.gov/services/warehouse/approved-storage-warehouses) ([dashboard](https://publicdashboards.dl.usda.gov/t/MRP_PUB/views/WCMDDashboard/WCMDDashboard), "Detailed Report" tab) | Public CSV export, no key | Every US Warehouse Act licensed and CCC-approved warehouse location: name, city, county, commodity, capacity; current list only | Warehouses card, storage options in crop plans |
| Grain and cold storage stocks | [NASS Grain Stocks](https://esmis.nal.usda.gov/publication/grain-stocks) and [Cold Storage](https://esmis.nal.usda.gov/publication/cold-storage) reports (ESMIS) | Public report text, no key | Latest quarterly grain stocks by state; monthly US frozen fruit and vegetable stocks | Stocks on the home page |
| Crop insurance losses | [USDA RMA Cause of Loss](https://www.rma.usda.gov/tools-reports/summary-of-business/cause-loss), Summary of Business with month of loss | Public zip files, no key | Payouts by county, crop, year, month and cause (drought, excess rain, hail, freeze, ...), 1989 to present; 2015–2024 used | Loss causes, peak months, tips to reduce losses |
| County codes | [US Census Bureau 2020 county FIPS codes](https://www2.census.gov/geo/docs/reference/codes2020/national_county2020.txt) | Public text file | All US counties | Joining warehouses to yield data |
| ZIP and city lookup | [US Census Bureau Gazetteer files](https://www.census.gov/geographies/reference-files/time-series/geo/gazetteer-files.html) (ZCTA and places) | Public zip files | Coordinates of every ZIP code and city | Manual location entry |

## Crops

`src/data_prep.py` covers 12 crops. Only field crops have county-level yield. Fruit, vegetable and sugar yields are published per state, and only for the major producing states. Each crop is merged with weather at its own level and over its own growing season.

| Crop | NASS series (fallback for older years) | Level | Growing season used | Rows* | Locations* | Years* |
|---|---|---|---|---|---|---|
| Corn | `CORN, GRAIN - YIELD, MEASURED IN BU / ACRE` | County | Apr–Sep | 87,298 | 2,668 counties | 1980–2025 |
| Wheat | `WHEAT, WINTER - YIELD, MEASURED IN BU / ACRE` | County | Oct (prev. year)–Jun | 74,065 | 2,692 counties | 1980–2025 |
| Sugarbeets | `SUGARBEETS - YIELD, MEASURED IN TONS / ACRE` | State | Apr–Oct | 553 | 17 states | 1980–2026 |
| Sugarcane | `SUGARCANE, SUGAR - YIELD, MEASURED IN TONS / ACRE` | State | Mar–Nov | 162 | 4 states | 1980–2025 |
| Carrots | `CARROTS - YIELD, MEASURED IN CWT / ACRE` | State | Jan–Dec | 30 | 5 states | 2016–2025 |
| Lettuce | `LETTUCE, HEAD - YIELD, MEASURED IN CWT / ACRE` (`LETTUCE, HEAD, FRESH MARKET - …` before 2016) | State | Jan–Dec | 72 | 7 states | 1998–2025 |
| Apples | `APPLES - YIELD, MEASURED IN LB / ACRE` | State | Mar–Sep | 361 | 32 states | 2007–2025 |
| Oranges | `ORANGES - YIELD, MEASURED IN BOXES / ACRE` | State | Feb (prev. year)–Jan | 169 | 4 states | 1980–2026 |
| Peaches | `PEACHES - YIELD, MEASURED IN TONS / ACRE` | State | Feb–Aug | 318 | 28 states | 2007–2025 |
| Strawberries | `STRAWBERRIES - YIELD, MEASURED IN CWT / ACRE` | State | Jan–Dec | 222 | 14 states | 1998–2025 |
| Blueberries | `BLUEBERRIES, TAME - YIELD, MEASURED IN LB / ACRE` (`BLUEBERRIES, TAME, UTILIZED - …` before 2018) | State | Mar–Aug | 201 | 13 states | 2007–2025 |
| Raspberries | `RASPBERRIES - YIELD, MEASURED IN LB / ACRE` (`RASPBERRIES, UTILIZED - …` before 2018) | State | Mar–Sep | 41 | 3 states | 2007–2025 |

\* Merged yield and weather rows for all states, 1980 to present, with `--include-forecasts`, using NASS data as of 2026-10-31. The counts change as NASS publishes new data.

Notes:
- **Units differ by crop** (bushels, tons, hundredweight, boxes or pounds per acre), so yields are only compared within the same crop. Each row has a `unit` column.
- **NASS series names change over time.** All-wheat county yield ends in 2007, so winter wheat is used instead. Lettuce, blueberries and raspberries were renamed in 2016–2018. The older name is used only for years the current one doesn't cover, and each row records its source in the `series` column.
- **Carrots** have no comparable series before 2016. Earlier data is split into fresh market (cwt/acre) and processing (tons/acre), so carrots start in 2016.
- **Citrus years** are labelled by the end of the season. For example, oranges 2026 is the October 2025–July 2026 harvest, and its weather runs from the previous February (bloom) to January.
- **Growing seasons** are approximate windows for the main US producing regions. Crops grown year-round in California (carrots, lettuce, strawberries) use the whole calendar year. Edit `CROPS` in `src/data_prep.py` to change them.
- **Fruit and vegetable series are short**, about 30–550 rows per crop, which limits how much a model can learn from them. Corn and wheat have the most data.

### Data freshness

Yield is an annual statistic. The pipeline queries the NASS API every time it runs, so it picks up new numbers on the day NASS publishes them. `--end` defaults to the current year. The app's live data (forecasts, alerts, observations, stock reports and daily weather) is fetched when the page loads and cached for a short time.

| Data | Release schedule |
|---|---|
| Corn, wheat, sugar | Monthly NASS forecasts August–November; annual summary in January (winter wheat final in September) |
| Oranges and other citrus | Monthly forecasts October–July; season summary in August |
| Apples, peaches, berries | Noncitrus Fruits and Nuts summary, May |
| Carrots, lettuce | Vegetables annual summary, February |
| Weather (nClimDiv) | Monthly; the last two years are revised as late data arrives |
| Grain Stocks / Cold Storage | Quarterly / monthly |
| NWS forecasts and alerts | Continuously |

By default only final estimates are kept. `--include-forecasts` adds the latest in-season NASS forecast for years that don't have a final value yet (for example 2026 sugarbeets as of November 2026), labelled `estimate = forecast`. The pipeline always downloads the newest nClimDiv files by reading the NOAA directory listing.

### Outputs

| File | Contents |
|---|---|
| `data/raw/` | NOAA files, Census files and `nass_yield_all_crops.csv` (all crops' yield in one long table) |
| `data/processed/<crop>_yield_weather.csv` | One row per location-year: `crop`, `level`, `fips`, `county`, `state`, `year`, `yield`, `unit`, `estimate` (`final` or `forecast`), `series`, and monthly growing-season weather `tavg_*`, `tmax_*`, `tmin_*` (°C) and `pcpn_*` (mm). `m07` is July of the harvest year; `p10` is October of the previous year (for seasons that wrap past January, like winter wheat) |
| `data/processed/warehouses.csv` | One row per warehouse location: `warehouse_name`, `business`, `commodity`, `capacity`, `unit`, `city`, `county`, `state`, `fips`, `license_type`, `license_number`, `license_status`, `ccc_code`, `ccc_status`, `functional_unit` |
| `data/processed/warehouses_by_county.csv` | Number of warehouses and total capacity per county and commodity; joins to corn and wheat on `fips` |
| `data/processed/insured_losses.csv` | 289,133 records: payouts and policies paid per year, county, crop, cause and month |
| `data/plans.json` | Crop plans saved in the app |

## Data cleaning

Cleaning happens in `src/data_prep.py` (yield and weather), `src/warehouses.py` and `src/losses.py`. The table lists each problem found in the raw government data and how it is handled. The sections after it give the details in pipeline order.

### Summary

| # | Problem in the raw data | Source | How it's handled | Effect seen in the validation run |
|---|---|---|---|---|
| 1 | Suppressed values `(D)`, `(Z)`, `(NA)` instead of numbers | NASS | Converted to NaN and dropped | Rows removed per crop |
| 2 | Numbers stored as text with commas (`"1,234"`) | NASS | Commas removed, converted to numbers | — |
| 3 | "OTHER (COMBINED) COUNTIES" catch-all (county code `998`) | NASS | Dropped; it matches no real county | — |
| 4 | County code differs from Census FIPS (Ste. Genevieve, MO: `29193` vs `29186`) | NASS | Code corrected before joining | 45 corn and 45 wheat rows recovered |
| 5 | Current-season `YEAR` value is a copy of the latest forecast, not a final number | NASS | Labelled `forecast`; dropped unless `--include-forecasts` | 10 sugarbeet rows for 2026 |
| 6 | Series renamed over time (lettuce 2016, blueberries and raspberries 2018) | NASS | Older name used only for years the current name doesn't cover; source kept in `series` column | Lettuce back to 1998, berries back to 2007 |
| 7 | More than 50,000 rows in one request (API limit) | NASS API | Row count checked first; year range split until under the limit | Corn and wheat split into several requests |
| 8 | State codes numbered alphabetically (Iowa = 13), not FIPS (Iowa = 19) | NOAA | Mapped to USPS and FIPS codes before joining | Prevents joining the wrong states |
| 9 | Missing months coded as `-9.99` (rain) and `-99.90` (temperature) | NOAA | Exact codes replaced with NaN | Real cold readings below -9.99 °F are kept (an earlier threshold version wrongly erased 392 values in northern states) |
| 10 | Units in °F and inches | NOAA | Converted to °C and mm | — |
| 11 | Regional and national aggregates mixed in with states (codes above 50) | NOAA | Dropped | — |
| 12 | No weather for some locations (Hawaii statewide data starts in 1991) | NOAA | Location-years with no weather at all are dropped | 11 Hawaii sugarcane rows (1980–1990) |
| 13 | Months not yet observed in the current season | NOAA | Row kept with NaN for those months; count reported | 10 sugarbeet 2026 rows lack October |
| 14 | Stray NUL bytes (`\0`) and uppercase headers in the bulk download | NASS bulk file | Not used by the pipeline (the API returns clean JSON); see note below | — |
| 15 | Every field exported twice, plus dashboard filler symbols (`▼`, `►`, `║`) | USDA warehouses | Only the 13 real columns kept | 14 columns dropped (13 copies and `Measure Names`, which is the same on every row) |
| 16 | Grand-total row with every field set to `All` | USDA warehouses | Dropped | 1 row |
| 17 | IDs in brackets; `[]` for warehouses with no federal license | USDA warehouses | Brackets removed; `[]` → missing | 2,649 locations have no federal license number |
| 18 | Capacity as text with commas; `0` when not reported | USDA warehouses | Converted to numbers; `0` → missing | 402 locations (383 grain, 19 EFAC) |
| 19 | Commodity and unit in one field (`Grain (BU)`) | USDA warehouses | Split into `commodity` and `unit` | — |
| 20 | Mixed case (`BENKELMAN` vs `Imperial`) and double spaces in names | USDA warehouses | City title-cased; whitespace collapsed | — |
| 21 | County given by name only, spelled differently from Census (`St. John Baptist`, `Dona Ana`, `Suffolk`) | USDA warehouses | Matched to Census county FIPS codes by normalized name | All 5,529 locations with a county matched; 34 have no county in the source |
| 22 | Pipe-delimited files with no header, padded text and Latin-1 characters | USDA RMA | Column names from the RMA record layout; text stripped; read as Latin-1 | — |
| 23 | Payouts not caused by field conditions (price decline, area-based programs) | USDA RMA | Dropped | Only weather, pest and disease losses remain |
| 24 | County code `999` ("all other counties") | USDA RMA | Dropped | — |
| 25 | Over 30 detailed cause names | USDA RMA | Grouped into 6 plain-language groups (too much rain, drought/heat, hail, wind/storms, freeze, pests/disease) | — |

### Yield (NASS)

1. Request only `source_desc=SURVEY`, which excludes the 5-yearly Census of Agriculture, and `domain_desc=TOTAL`, which excludes breakdowns such as by farm size. Use each crop's exact series names.
2. Check the row count first with the API's `get_counts` endpoint. Split the year range in half until each request is under the 50,000-row limit. Queries that match nothing (NASS answers HTTP 400 "no data") are treated as empty, not as errors.
3. Keep annual values (`reference_period_desc` `YEAR`) and monthly forecasts (`YEAR - <MON> FORECAST`). Drop other periods, such as marketing years.
4. Remove thousands separators from `Value` (for example `"1,234"`) and convert to numbers.
5. Drop suppressed or unavailable values:
   - `(D)`: withheld to protect individual farms.
   - `(Z)`: less than half the unit shown.
   - `(NA)`: not available.
6. Drop county code `998` ("OTHER (COMBINED) COUNTIES"), a catch-all for small counties that matches no real county.
7. Build a 5-digit county FIPS key from `state_fips_code` and `county_code`. Correct NASS codes that differ from Census FIPS (Ste. Genevieve, MO: NASS `29193` → FIPS `29186`).
8. Label each value `final` or `forecast`. During the season, NASS copies the latest forecast into the `YEAR` row until the final estimate is released. So a `YEAR` row from this year or last that is not newer than the latest forecast is treated as a forecast.
9. Keep one value per location-year. The current series name wins over the older fallback, and the final estimate wins over the latest forecast. Forecasts are dropped unless `--include-forecasts` is set.

### Weather (NOAA nClimDiv)

1. Parse the fixed-width layout:
   - County files have an 11-character ID: 2-digit state code, 3-digit county FIPS, element and year.
   - Statewide files have a 10-character ID: 3-digit state code, division `0`, element and year.
   - Both are followed by 12 monthly values.
2. Map NOAA state codes to USPS and FIPS codes. nClimDiv numbers states alphabetically (Iowa = 13, Missouri = 23), while FIPS has Iowa = 19 and Missouri = 29. Joining without this mapping would match the wrong states. Statewide codes above 50 are regional and national aggregates and are dropped.
3. Replace NOAA's exact missing-value markers with NaN: `-9.99` for precipitation and `-99.90` for temperature. These markers appear for months that haven't happened yet. A simple `<= -9.99` threshold would also erase real winter temperatures below -9.99 °F in the northern Plains.
4. Convert units: °F to °C and inches to mm.
5. Keep each crop's growing-season months and pivot to one row per location and season year. Previous-year months are shifted forward for seasons that wrap past January.

### Merge

1. Inner join yield and weather on `fips` + `state` + `year` (county crops) or on `state` + `year` (state crops).
2. Drop location-years with no weather at all. NOAA statewide data for Hawaii starts in 1991, which removes Hawaii sugarcane for 1980–1990.
3. Keep rows that are only missing months not yet observed (an in-season forecast for the current year), and report how many there are.

### Warehouses (USDA AMS)

1. Download the dashboard's "Detailed Report" tab as CSV. Tableau serves any tab as CSV when `.csv` is added to its URL.
2. Keep the 13 real columns and rename them to snake_case. The export repeats every field with a trailing `*` and fills the copies with layout symbols (`▼`, `►`, `║`).
3. Drop the grand-total row (`State == "All"`).
4. Remove brackets from `license_number` and `ccc_code` (`[1-0265]` → `1-0265`). `[]` means no federal license and becomes missing.
5. Split `Commodity (Unit)` into `commodity` and `unit`.
6. Convert `capacity` to numbers and treat `0` as missing (not reported), so it isn't averaged in as an empty warehouse.
7. Collapse repeated whitespace in names and title-case city names.
8. Match each county name to a Census FIPS code within its state.
   - Names are normalized first: accents are removed (`Doña Ana` → `Dona Ana`), `Saint` becomes `St`, `the` is dropped (`St. John the Baptist Parish` → `St. John Baptist`), and suffixes such as `County` or `Parish` are removed.
   - The exact name is tried first, so `St. Louis City` maps to St. Louis city (29510), not St. Louis County (29189).
   - Only if that fails is a trailing `city` ignored. This matches Virginia independent cities, such as `Suffolk` → Suffolk city (51800).
9. Sum warehouses and capacity per county and commodity into `warehouses_by_county.csv`.

Checks: every location with a county got a FIPS code, and every code's state matches the warehouse's state.

### Insured losses (USDA RMA)

1. Download `colsom_YYYY.zip` for each year (2015–2024 by default) and read the pipe-delimited file with the column layout from RMA's record description.
2. Keep the commodities that match our crops:
   - "Processing Cling Peaches" and "Fresh Freestone Peaches" both count as peaches.
   - Carrots, lettuce and raspberries have no federal policies.
3. Drop non-field payouts: price decline and area-based programs (ARPI/SCO/ECO/STAX/MP/PACE).
4. Drop county code `999` and build a 5-digit FIPS key.
5. Map each cause to a plain-language group (`CAUSE_GROUPS`) and sum payouts per year, county, crop, cause and month.

### Validation

This run used all 12 crops, all states and 1980 to the present. NASS data as of 2026-10-31 was served through a mocked API, together with real NOAA files.
- Every yield row matched weather except the 11 Hawaii sugarcane years above.
- Corn and wheat have no missing weather values.
- The only incomplete rows are the ten 2026 sugarbeet forecasts, which lack October weather.

### Note: NUL bytes in the NASS bulk files

The bulk download at [nass.usda.gov/datasets](https://www.nass.usda.gov/datasets) (`qs.crops_YYYYMMDD.txt.gz`, about 1.1 GB) has uppercase column names and contains stray NUL bytes (`\0`). These make Python's `csv` module fail with `line contains NUL`. The pipeline doesn't use these files; it uses the API, which returns clean JSON. If you use the bulk file instead, strip `\0` from each line and split on tabs:

```python
for line in gzip.open(path, "rt"):
    row = line.replace("\0", "").rstrip("\n").split("\t")
```

## Methods

All models are in `src/crop_model.py`.

### 1. Crop recommendation

1. **Good seasons.** For each crop, the location-years with yield at or above that year's median are its "good" seasons. Each one is described by mean growing-season temperature, mean monthly rainfall and the coldest monthly low.
2. **The user's climate.**
   - *Real-time mode* measures the user's county over each crop's own season months, averaged over the last 10 complete seasons in the NOAA county files.
   - *Manual mode* applies the entered values to every crop.
3. **Climate match** is a Gaussian score of how far the user's climate is from the crop's good seasons.
   - Winters colder than usual for the crop are penalized; milder ones are not.
   - With irrigation, low rainfall is not penalized.
4. **Soil fit** is 1 inside the crop's preferred pH range (`PH_RANGE`, from university extension guidance) and falls off outside it.
5. **Score** = climate match × soil fit. The crop with the highest score is recommended, and the others are ranked below it.

### 2. Climate clustering (four models)

The good seasons (up to 1,500 sampled per crop, 4,125 in total) are grouped into 3 climate clusters on standardized temperature and rainfall. Clusters are always numbered from coolest to warmest, so their colors keep the same meaning under every model.

| Model | Silhouette score* | How the user's farm is placed | Notes |
|---|---|---|---|
| K-means (default) | 0.437 | `predict` | Clearest separation on this data |
| Gaussian mixture | 0.407 | `predict`, plus a probability for each cluster | Allows oval, overlapping clusters |
| Agglomerative (Ward) | 0.405 | Majority of the 15 nearest seasons (Ward has no predict step) | Builds clusters bottom-up from the most similar points |
| BIRCH | 0.248 | `predict` | Built for very large data; splits this data unevenly |
| DBSCAN | — | — | Not offered: the climate data is one continuous cloud, so it finds a single cluster |

\* Scores range from -1 to 1; higher means better-separated clusters. Compared with K-means, 13% of seasons change cluster under Gaussian mixture and Ward, and 38% change under BIRCH.

Changing the model redraws the map. Shaded regions behind the dots show which cluster every possible climate belongs to under that model, so each model's boundaries are visible: straight lines for K-means, curves for Gaussian mixture and irregular edges for Ward. The recommended crop does not depend on the clustering choice.

**Which clustering model to use when** (also shown in the app):

| Model | Use it when | Avoid it when |
|---|---|---|
| **K-means** | You want a quick, clear split and the groups are roughly round and similar in size. Best default here. | Groups have very different sizes or shapes, or overlap a lot. |
| **Gaussian mixture** | Groups overlap or have different shapes and spreads, or you need a probability of belonging (useful for a farm near a boundary). | You need a hard, simple rule, or the data has many outliers. |
| **Agglomerative (Ward)** | You want groups built bottom-up from the most similar seasons, with boundaries that follow the data. | The dataset is large (it compares every pair of points) or new points must be assigned often. |
| **BIRCH** | The data is very large or arrives as a stream and memory is limited. | The data is small, as here: it summarizes too coarsely and splits unevenly. |
| **DBSCAN** (not offered) | Clusters have odd shapes and are separated by empty space, and you want outliers flagged. | The data is one continuous cloud, as here: it finds a single cluster. |

### 3. How weather moves yield (`weather_drivers`)

1. **Yield anomaly.** Each location's yield is expressed as the % it lies above or below that location's own linear trend (only locations with at least 8 years). This removes technology gains and fixed differences between places.
2. **Weather anomaly.** Each month's temperature and rainfall minus that location's average for the month.
3. **Monthly effects.** For every month of the season, a least-squares slope (scipy `linregress`) gives the % yield change per +1 °C or per +1 inch of rain, with its correlation and p-value. The app shows only effects with p < 0.01.
4. **Explained share.** A ridge regression on all months (`RidgeCV`), cross-validated with whole years held out (`GroupKFold`), measures how much of the year-to-year yield swing the weather explains.
5. **This season so far** (`season_effects`). For each strong month that has passed since planting, the county's weather is compared with its previous 10 years and turned into an expected yield effect. Differences larger than the 5–95% range seen in the data are capped and flagged.

### 4. Growth tracking (`growth_progress`)

1. **Heat units.** Growing degree days (GDD) are computed from daily highs and lows since the start date (NOAA ACIS), using a base temperature per crop (`GROWTH`) and highs capped at 30 °C.
2. **Heat needed.** The heat needed for harvest is what last year's weather at the same place delivered over the crop's typical season length.
3. **Progress.** GDD so far divided by the heat needed. The stage follows from progress: just planted, establishment, vegetative growth, flowering, ripening, ready for harvest.
4. **Harvest date.** The remaining heat is projected using last year's daily pace. Comparing heat with last year shows whether the season is running ahead or behind.

### 5. Expected yield and production

Expected yield is the last-5-year NASS average for the county, falling back to the state and then to all US locations. Expected production is yield × area.

### 6. Insured losses (`src/losses.py`)

Payouts are summed per crop and cause for the plan's county, falling back to the state and then the US. The app shows each cause's share of payouts and its peak month, with one standard way to reduce that kind of loss (`CAUSE_ACTIONS` in the app).

## Results

**Recommendation checks.** These known growing areas were run in real-time mode with pH 6.5. Each one returns the crop the area is known for:

| Location | Recommended crop |
|---|---|
| Story County, IA | Corn |
| Sedgwick County, KS | Wheat |
| Cass County, ND | Sugarbeets |
| Iberia Parish, LA | Sugarcane |
| Berrien County, MI | Apples |

**Weather effects on yield** (significant at p < 0.01):

| Crop | Records | Strongest effects (per +1 °C or +1 inch) | Weather explains (cross-validated R²) |
|---|---|---|---|
| Corn | 86,252 county-years | August heat −5.2%, July heat −5.2%, July rain +2.8% | 9% |
| Wheat (winter) | 72,724 county-years | May heat −1.7%, June heat −1.7%, May rain −0.9% | 2% |
| Apples | 355 state-years | March warmth −3.2%, August heat −5.2%, June rain +2.6% | not predictive (< 0) |
| Peaches | 309 state-years | August heat −6.8%, March rain +4.2%, March warmth −2.2% | not predictive (< 0) |

What the results mean:
- **Summer heat hurts corn.** A July or August that is 1 °C hotter than normal cuts corn yield by about 5%. Extra July rain helps.
- **Monthly weather explains only part of the yield swing.** For corn it explains 9% of year-to-year changes on unseen years. Most of the rest comes from things monthly averages don't capture, such as single storms, pests, prices and management.
- **State-level crops have too few records** for the weather model to predict unseen years. The individual effects above still pass the significance test, and the app tells users when a model is not predictive.

**Insured losses.** The RMA file has 289,133 county-crop-cause-month records for 2015–2024, covering the 9 of our crops with federal policies.
- In Story County, IA, 75% of the $28.0 million paid for corn losses was for wind and storms, almost all of it in August (the 2020 derecho).
- In Florida, 59% of orange payouts were for hurricanes and 21% for freezes.

**Warehouses.** The list has 5,563 locations in 41 states, downloaded 2026-11-02. Illinois (721), Iowa (637), Kansas (609) and Nebraska (364) have the most.

| Commodity | Locations | Total capacity | Unit |
|---|---|---|---|
| Grain | 4,810 | 9.68 billion | bushels |
| Cotton | 317 | 16.9 million | bales |
| Peanuts | 300 | 4.30 million | tons |
| Sugar | 84 | 14.4 billion | listed as cwt (see limitations) |
| Dry edible beans | 32 | 12.0 million | cwt |
| EFAC | 19 | not reported | — |
| Cottonseed | 1 | 6,000 | tons |

Of the counties with 2025 yield, 676 of 1,211 corn counties and 460 of 712 winter wheat counties have at least one listed grain warehouse.

## Application guide

Run with `streamlit run Application/app.py`. The app needs the outputs of the three data scripts. Everything else is fetched live from government services, with no API key.

**Design**
- **Header:** shows only "Agri Forecast".
- **Theme:** green, set in `.streamlit/config.toml`.
- **Icons:** inline SVG line icons based on the open-source Lucide set, colored by meaning: blue for frost and rain, orange for sun and heat, red for alerts, green otherwise. No emoji are used.
- **Charts:** at most three colors and no dual axes.
- **Loading:** a centered "Loading..." screen with a green progress bar appears while the crop history and live data load, and again whenever the location changes. Streamlit's running animation is replaced with "Loading..." text.

**For beginners**
- The home page explains what the app does and gives four "how to use it" steps.
- Each result starts with an **In simple words** sentence.
- The analysis and tracking pages have a **What do these words mean?** glossary covering match %, good-yield season, climate cluster, cluster quality, heat units, progress to harvest, yield effect and insurance payouts.

### Location

Pick one of two options:
- **Use my current location.** The browser asks for permission and sends its coordinates. This requires `localhost` or HTTPS.
- **Enter location manually.** Type a 5-digit ZIP code or "City, ST". It is looked up in the Census Bureau gazetteer files.

The NWS `/points` endpoint then gives the city, state and county FIPS code for that location.

### Home page

| Card | What it shows | Source |
|---|---|---|
| Weather News | Current conditions, today's and tonight's forecast, 7-day low/high and rainfall, active alerts for the location, and a one-line summary of crop-relevant alerts nationwide | NWS API (observations, forecast, gridpoint data, alerts) |
| Crops Affected | *Near you:* each crop grown in the user's state, whether it is growing or being harvested this month, and risks from local alerts and the 7-day forecast (freeze ≤ 0 °C, heavy rain ≥ 50 mm, heat ≥ 35 °C). *Across the US:* active alerts grouped by hazard and matched to the counties (corn, wheat) or states (other crops) where each crop is grown | NWS alerts (county codes) and crop regions from NASS data |
| Warehouses & Stocks | USDA warehouses in the user's county (or state) with capacity per commodity, license and CCC status; state corn and wheat stocks vs a year ago; US frozen stocks of crops grown in the state | `warehouses.csv`, NASS Grain Stocks and Cold Storage reports |

The **Analyze crop** button opens the analysis page. **Track my crops** appears once a plan exists.

### Analyze crop page

- **Left: soil.** N, P, K, pH and irrigation.
- **Right: weather.** Either **real-time** for the chosen location or **entered manually**: temperature, humidity, monthly rainfall and an optional coldest winter low.
- **Results, left:** the recommended crop with its match score, the reasons for it, its climate zone, and the next two best crops ("Also suitable").
- **Results, right:** the climate cluster map. A dropdown picks the clustering model, with a "Which clustering model should I use?" guide. Under the map are:
  - the model's silhouette score;
  - the cluster sizes;
  - how many seasons changed cluster compared with K-means;
  - for Gaussian mixture, the farm's probability of belonging to each cluster.

### Crop plan page

Open it with **Create crop plan** under the result. Pick the crop (it defaults to the recommendation), the area in acres and the start date (the planting date, or green-up / bloom for fruit crops), then press **Fix plan** to save it. The summary shows:
- expected yield and expected production;
- expected harvest date (start date + typical season length);
- a warning when the start month is outside the crop's usual season;
- the pH range to keep;
- where the harvest can be stored: USDA warehouses for grain and sugar crops, cold storage for perishables.

**Multiple plans.** Farmers growing several crops can add as many plans as they need.
- The plan page lists the crops already planned.
- **+ Plan another crop** opens a new plan preset to the best-ranked crop from the last analysis that has no plan yet.
- A second plan for the same crop (another field) is allowed.

Plans are saved to `data/plans.json`.

### Track my crops page

- **Your crop plans.** One card per plan shows the crop, acres, location, start date, a progress bar, the stage and the estimated harvest date, plus the total area. **View details** opens that plan; each crop is tracked and analyzed separately.
- **Growth from weather.** Heat units, progress, stage, the estimated harvest date and heat compared with last year.
- **Charts.** Two separate charts:
  - cumulative heat units: this season, last year's pace, the projection and the amount needed;
  - daily rain.
- **This week's advice.** Based on the NWS 7-day forecast and alerts:
  - Frost: use row covers and water beforehand.
  - Heavy rain (≥ 50 mm): clear drains and hold off on fertilizer and spraying. Harvest first if the crop is at least 90% of the way to harvest.
  - Light rain: skip irrigation, or harvest between showers if the crop is ready.
  - Dry and warm weather: irrigate.
  - Heat ≥ 35 °C: irrigate early in the day.
- **How weather moves this crop's yield.** The strongest measured effects and how this season's weather has moved yield so far.
- **Tips to reduce losses.** What has caused insurance payouts for this crop here, with the peak month and a way to reduce each loss. Then answers to common questions, with links to USDA RMA, FSA and farmers.gov:
  - A storm is coming and my crop is almost ready. Should I harvest early?
  - Can I store grain that is still wet?
  - My field flooded. What should I do? (This includes reporting damage to the crop insurance agent within 72 hours.)
  - Frost is forecast tonight. What can I do?
  - How do I protect my income if weather destroys the crop? (Federal crop insurance through USDA RMA, or FSA's NAP program for uninsured crops.)
  - Where can I store my harvest safely?
  - Can I store the plant in a freezer to protect it from rain? (No. Freezing kills living plant cells; only harvested produce can be frozen.)

### What is computed from data vs guide values

| Content | Where it comes from |
|---|---|
| Crop recommendation, match %, climate clusters | Computed from USDA NASS yields and NOAA weather, 1980–2025 |
| Weather effects on yield, "this season so far" | Computed: regression on NASS and NOAA data |
| Loss causes, peak months, past losses | Computed from USDA RMA insurance payouts, 2015–2024 |
| Expected yield and production | Computed: last-5-year NASS average |
| Growth progress, heat units, estimated harvest | Computed from NOAA ACIS daily weather |
| Weather news, alerts, crops affected, warehouses, stocks | Live from NWS, USDA AMS and NASS reports |
| pH ranges, harvest windows, season lengths, GDD base temperatures | Guide values from general university extension guidance |
| Ways to reduce each loss, answers to common questions | Standard practice written for the app; links point to USDA sources |

## Project structure

```
Agri-forecast/
├── Application/
│   └── app.py            Streamlit app: home, analyze, plan and track pages
├── src/
│   ├── data_prep.py      NASS yield and NOAA weather download, cleaning and merge
│   ├── warehouses.py     USDA AMS warehouse list download, cleaning and county matching
│   ├── losses.py         USDA RMA crop insurance payouts by cause of loss
│   ├── live.py           Location lookup, NWS weather and alerts, ACIS daily weather, USDA stock reports
│   └── crop_model.py     Recommendation, clustering models, weather effects, crop plans, growth tracking
├── data/                 Downloaded and processed data, saved plans (not committed)
│   ├── raw/
│   ├── processed/
│   └── plans.json
├── .streamlit/config.toml  App theme
├── requirements.txt
└── README.md
```

## Setup and usage

```bash
git clone https://github.com/PVRPratyusha/Agri-forecast.git
cd Agri-forecast
pip install -r requirements.txt
```

1. Get a free NASS API key at https://quickstats.nass.usda.gov/api.
2. Build the data. This is needed once, and again whenever you want newer data:

```bash
export NASS_API_KEY=your_key
python src/data_prep.py                       # all 12 crops, all states, 1980 to this year
python src/data_prep.py --crops corn apples --states IA WA --start 1990   # a subset
python src/data_prep.py --include-forecasts   # also keep current-season NASS forecasts
python src/warehouses.py                      # USDA storage warehouses (no key needed)
python src/losses.py                          # USDA crop insurance losses, 2015-2024 (no key needed)
python src/losses.py --start 2010 --end 2024  # a different year range
```

3. Run the app:

```bash
streamlit run Application/app.py              # opens at http://localhost:8501
```

The first load takes a little longer because the Census gazetteer files are downloaded and the clustering models are fitted. After that, results are cached.

## Limitations

- **N, P, K and humidity are collected but not scored.** There is no public government dataset linking soil-test values or humidity to these crops' yields. Only pH is used, through guide ranges.
- **State-level crops use statewide weather,** which can differ from the actual growing areas. For example, California's statewide average is cooler than the Central Valley.
- **Monthly weather explains only part of the yield swing:** 9% for corn and 2% for wheat, and the model is not predictive for the state-level fruit crops.
- **Guide values.** Harvest windows (`HARVEST`), season lengths and GDD base temperatures (`GROWTH`) and pH ranges (`PH_RANGE`) are approximate values from general extension guidance.
- **Growth tracking compares against last year only,** not a long-term normal, so an unusual previous year shifts the estimate.
- **Warehouse data is a current snapshot** with city and county only (no coordinates and no history), and it covers storable commodities only. USDA publishes fruit and vegetable cold storage only as state and regional totals.
- **Sugar warehouse capacity looks like pounds, not cwt.** For example, Michigan Sugar's Bay City site is listed at 420 million cwt (about 21 million tons), which is only plausible as pounds (4.2 million cwt). Values are kept as published.
- **No insurance data for carrots, lettuce and raspberries,** because they have no federal policies.
- **Saved plans are local.** On a hosted deployment such as Streamlit Community Cloud, `data/plans.json` is lost when the app restarts.
- **Current location needs HTTPS or localhost,** because browsers block geolocation elsewhere.

## Future work

- Weight county weather by planted area for state-level crops, instead of using statewide averages.
- Add daily extremes (heat days above 30 °C, heavy-rain days) to the yield model; monthly means miss short events.
- Compare growth against a 10-year normal, not only last year.
- Use soil data from USDA NRCS SSURGO to fill in soil properties automatically.
- Store plans in a database so they persist on a hosted deployment.

## Tech stack

Python, pandas, NumPy, SciPy, scikit-learn (KMeans, GaussianMixture, AgglomerativeClustering, Birch, RidgeCV), Requests, Streamlit, Plotly
