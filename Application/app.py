import datetime
import html
import json
import sys
import uuid
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import crop_model as cm  # noqa: E402
import live  # noqa: E402
from data_prep import CROPS, PROCESSED_DIR  # noqa: E402

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Agri Forecast",
    layout="wide",
    initial_sidebar_state="collapsed"
)

PLANS_PATH = ROOT / "data" / "plans.json"

GREEN = "#2E5A31"
NAVY = "#000080"
# Cluster map: first three categorical slots (validated for all-pairs use in a scatter), plus ink colors
CLUSTER_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"]
# Same three hues as faint tints, for the cluster regions behind the dots
CLUSTER_TINTS = ["rgba(42,120,214,0.13)", "rgba(235,104,52,0.13)", "rgba(27,175,122,0.13)"]
INK, INK_SECONDARY, GRID = "#0b0b0b", "#52514e", "#ececec"

# Inline SVG line icons (24x24, drawn with currentColor). Paths follow the open-source Lucide set (ISC licence).
ICON_PATHS = {
    "pin": '<path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/><circle cx="12" cy="10" r="3"/>',
    "alert": '<path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"/>'
             '<path d="M12 9v4"/><path d="M12 17h.01"/>',
    "frost": '<path d="M2 12h20"/><path d="M12 2v20"/><path d="m20 16-4-4 4-4"/><path d="m4 8 4 4-4 4"/>'
             '<path d="m16 4-4 4-4-4"/><path d="m8 20 4-4 4 4"/>',
    "rain": '<path d="M4 14.9A7 7 0 1 1 15.7 8h1.8a4.5 4.5 0 0 1 2.5 8.2"/><path d="M16 14v6"/><path d="M8 14v6"/>'
            '<path d="M12 16v6"/>',
    "drizzle": '<path d="M4 14.9A7 7 0 1 1 15.7 8h1.8a4.5 4.5 0 0 1 2.5 8.2"/><path d="M8 19v1"/><path d="M8 14v1"/>'
               '<path d="M16 19v1"/><path d="M16 14v1"/><path d="M12 21v1"/><path d="M12 16v1"/>',
    "sun": '<circle cx="12" cy="12" r="4"/><path d="M12 2v2"/><path d="M12 20v2"/><path d="m4.93 4.93 1.41 1.41"/>'
           '<path d="m17.66 17.66 1.41 1.41"/><path d="M2 12h2"/><path d="M20 12h2"/><path d="m6.34 17.66-1.41 1.41"/>'
           '<path d="m19.07 4.93-1.41 1.41"/>',
    "heat": '<path d="M14 4v10.54a4 4 0 1 1-4 0V4a2 2 0 0 1 4 0Z"/>',
    "harvest": '<path d="m7.5 4.27 9 5.15"/><path d="M21 8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 '
               '0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16Z"/><path d="m3.3 7 8.7 5 8.7-5"/><path d="M12 22V12"/>',
    "check": '<path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><path d="m9 11 3 3L22 4"/>',
    "weather": '<path d="M12 2v2"/><path d="m4.93 4.93 1.41 1.41"/><path d="M20 12h2"/><path d="m19.07 4.93-1.41 1.41"/>'
               '<path d="M15.95 12.65a4 4 0 0 0-5.93-4.13"/><path d="M13 22H7a5 5 0 1 1 4.9-6H13a3 3 0 0 1 0 6Z"/>',
    "crop": '<path d="M2 22 16 8"/><path d="M3.47 12.53 5 11l1.53 1.53a3.5 3.5 0 0 1 0 4.94L5 19l-1.53-1.53a3.5 3.5 0 0 1 0-4.94Z"/>'
            '<path d="M7.47 8.53 9 7l1.53 1.53a3.5 3.5 0 0 1 0 4.94L9 15l-1.53-1.53a3.5 3.5 0 0 1 0-4.94Z"/>'
            '<path d="M11.47 4.53 13 3l1.53 1.53a3.5 3.5 0 0 1 0 4.94L13 11l-1.53-1.53a3.5 3.5 0 0 1 0-4.94Z"/>'
            '<path d="M20 2h2v2a4 4 0 0 1-4 4h-2V6a4 4 0 0 1 4-4Z"/>'
            '<path d="M11.47 17.47 13 19l-1.53 1.53a3.5 3.5 0 0 1-4.94 0L5 19l1.53-1.53a3.5 3.5 0 0 1 4.94 0Z"/>'
            '<path d="M15.47 13.47 17 15l-1.53 1.53a3.5 3.5 0 0 1-4.94 0L9 15l1.53-1.53a3.5 3.5 0 0 1 4.94 0Z"/>'
            '<path d="M19.47 9.47 21 11l-1.53 1.53a3.5 3.5 0 0 1-4.94 0L13 11l1.53-1.53a3.5 3.5 0 0 1 4.94 0Z"/>',
    "warehouse": '<path d="M22 8.35V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V8.35A2 2 0 0 1 3.26 6.5l8-3.2a2 2 0 0 1 1.48 0l8 3.2A2 '
                 '2 0 0 1 22 8.35Z"/><path d="M6 18h12"/><path d="M6 14h12"/><rect width="12" height="12" x="6" y="10"/>',
    "analyze": '<path d="M3 3v18h18"/><path d="m19 9-5 5-4-4-3 3"/>',
}
# Icon colors: blue for cold and wet, orange for sun and heat, red for alerts, brand green otherwise
ICON_COLORS = {"frost": "#2a78d6", "rain": "#2a78d6", "drizzle": "#2a78d6", "sun": "#eb6834", "heat": "#eb6834",
               "alert": "#d03b3b"}


def icon(name, size="1.05em", color=None):
    color = color or ICON_COLORS.get(name, "#2E5A31")
    return (f'<svg class="ico" viewBox="0 0 24 24" width="{size}" height="{size}" fill="none" stroke="{color}" '
            f'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
            f'{ICON_PATHS[name]}</svg>')


# Weather alert types grouped by the kind of damage they do to crops
HAZARDS = {
    "Freeze / frost": ("Freeze", "Frost"),
    "Flooding / heavy rain": ("Flood",),
    "Heat": ("Heat",),
    "Wind / storms": ("Wind", "Thunderstorm", "Tornado", "Hurricane", "Tropical", "Dust"),
    "Winter storm / ice": ("Winter", "Blizzard", "Ice"),
    "Fire weather": ("Red Flag", "Fire"),
}
EFFECTS = {
    ("Freeze / frost", "growing"): "freeze damage to young plants",
    ("Freeze / frost", "harvest"): "frost damage to the unharvested crop",
    ("Flooding / heavy rain", "growing"): "waterlogged fields",
    ("Flooding / heavy rain", "harvest"): "harvest delays and quality loss",
    ("Heat", "growing"): "heat stress during growth",
    ("Heat", "harvest"): "heat stress on the ripening crop",
    ("Wind / storms", "growing"): "lodging and plant damage",
    ("Wind / storms", "harvest"): "lodging and fruit drop",
    ("Winter storm / ice", "growing"): "cold injury",
    ("Winter storm / ice", "harvest"): "blocked field access and transport",
    ("Fire weather", "growing"): "field fire risk",
    ("Fire weather", "harvest"): "field fire risk",
}

# --- STATE MANAGEMENT ---
if 'page' not in st.session_state: st.session_state.page = "home"
if 'loc' not in st.session_state: st.session_state.loc = None
if 'loaded_for' not in st.session_state: st.session_state.loaded_for = None
if 'result' not in st.session_state: st.session_state.result = None
if 'plan_crop' not in st.session_state: st.session_state.plan_crop = None
if 'track_id' not in st.session_state: st.session_state.track_id = None

# --- CUSTOM CSS STYLING ---
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap');

    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* --- 1. MAIN BACKGROUND --- */
    .stApp {
        background-color: #F0F4F0;
    }

    /* --- 2. GLOBAL TEXT COLORS --- */
    /* Default Body Text -> Dark Grey */
    .stApp .main .block-container p,
    .stApp .main .block-container span,
    .stApp .main .block-container div {
        color: #333333;
    }

    /* Headers -> Dark Green */
    .stApp .main .block-container h1,
    .stApp .main .block-container h2,
    .stApp .main .block-container h3,
    .stApp .main .block-container h4 {
        color: #2E5A31 !important;
    }

    /* --- 3. COMPONENT STYLING --- */

    /* Metrics Labels -> Green */
    [data-testid="stMetricLabel"] {
        color: #2E5A31 !important;
        font-weight: bold;
    }
    /* Metric Values -> Dark Grey */
    [data-testid="stMetricValue"] {
        color: #333333 !important;
    }

    /* Radio Button Options -> Navy Blue */
    div[data-testid="stRadio"] label p {
        color: #000080 !important;
        font-weight: 600;
    }

    /* --- 4. SIDEBAR (not used) --- */
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
        display: none;
    }

    /* --- 5. BANNER --- */
    .header-banner {
        background-color: #2E5A31;
        padding: 1.25rem 2rem;
        border-radius: 0px 0px 15px 15px;
        color: white;
        text-align: center;
        margin-bottom: 1.5rem;
        margin-top: -50px;
    }
    .header-banner h1 {
        color: white !important;
        margin: 0;
        padding: 0;
        font-weight: 700;
        font-size: clamp(1.6rem, 4vw, 2.5rem);
        letter-spacing: 0.02em;
    }

    /* --- 6. CARDS & BUTTONS --- */
    .agri-card {
        background-color: #FFFFFF;
        padding: 1.25rem 1.5rem;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 1.5rem;
        border: 1px solid #E0E0E0;
        border-top: 5px solid #2E5A31;
    }
    .agri-card.weather { border-top-color: #000080; }
    .agri-card h3 {
        margin: 0 0 0.25rem 0;
        padding: 0;
        font-size: 1.2rem;
    }
    .agri-card .card-sub {
        color: #52514e !important;
        font-size: 0.85rem;
        margin-bottom: 0.75rem;
    }
    .agri-card ul {
        margin: 0;
        padding-left: 1.2rem;
    }
    .agri-card li {
        margin-bottom: 0.45rem;
        line-height: 1.45;
        color: #333333;
    }
    .agri-card .section {
        font-weight: 700;
        color: #2E5A31;
        margin: 0.75rem 0 0.35rem 0;
    }
    .agri-card .muted { color: #52514e; font-size: 0.85rem; }

    [data-testid="stVerticalBlockBorderWrapper"] {
        background-color: #FFFFFF;
        border-radius: 15px;
    }

    .stButton > button {
        background-color: #4CAF50;
        color: white !important;
        border-radius: 8px;
        border: none;
        padding: 0.75rem 1.5rem;
        font-weight: 600;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        transition: all 0.3s ease;
    }
    .stButton > button:hover {
        background-color: #45a049;
    }
    .stButton > button p { color: white !important; }
    [data-testid="stFormSubmitButton"] > button {
        background-color: #4CAF50;
        color: white !important;
        border-radius: 8px;
        border: none;
        font-weight: 600;
    }
    [data-testid="stFormSubmitButton"] > button p { color: white !important; }

    .result-crop {
        font-size: 2rem !important;
        font-weight: 700;
        color: #2E5A31 !important;
        line-height: 1.2;
        margin: 0;
    }
    .result-match {
        display: inline-block;
        background: #E8F5E9;
        color: #2E5A31;
        font-weight: 700;
        border-radius: 999px;
        padding: 0.15rem 0.75rem;
        margin: 0.25rem 0 0.75rem 0;
    }

    .stat-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.75rem 1.5rem;
        margin: 0.5rem 0;
    }
    .stat-label {
        color: #2E5A31 !important;
        font-weight: 600;
        font-size: 0.85rem;
    }
    .stat-value {
        color: #333333 !important;
        font-size: 1.5rem;
        font-weight: 600;
    }

    .muted { color: #52514e !important; font-size: 0.85rem; }
    svg.ico { vertical-align: -0.17em; margin-right: 0.3em; flex-shrink: 0; }
    .intro-tile .t-icon svg.ico { margin: 0; }

    /* --- INTRO --- */
    .intro {
        background: #FFFFFF;
        border-radius: 15px;
        border: 1px solid #E0E0E0;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        padding: 1.25rem 1.5rem;
        margin-bottom: 1.25rem;
    }
    .intro-lead {
        font-size: 1.05rem;
        line-height: 1.5;
        color: #333333 !important;
        margin-bottom: 1rem;
    }
    .intro-steps {
        background: #E8F5E9;
        border-radius: 10px;
        padding: 0.6rem 0.9rem;
        margin-bottom: 1rem;
        font-size: 0.92rem;
        color: #333333 !important;
    }
    .intro-grid {
        display: grid;
        grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 0.75rem;
    }
    .intro-tile {
        background: #F5F9F5;
        border-radius: 12px;
        padding: 0.85rem 1rem;
        border-left: 4px solid #2E5A31;
    }
    .intro-tile .t-icon { font-size: 1.4rem; }
    .intro-tile .t-title { font-weight: 700; color: #2E5A31 !important; margin: 0.2rem 0; }
    .intro-tile .t-text { font-size: 0.88rem; color: #333333 !important; line-height: 1.4; }
    .intro-sources { margin-top: 0.85rem; font-size: 0.8rem; color: #52514e !important; }

    /* --- PLAN OVERVIEW CARDS --- */
    .plan-card {
        background: #FFFFFF;
        border-radius: 12px;
        border: 1px solid #E0E0E0;
        border-top: 4px solid #2E5A31;
        padding: 0.9rem 1rem;
        margin-bottom: 0.75rem;
    }
    .plan-card .p-name { font-weight: 700; color: #2E5A31 !important; font-size: 1.05rem; }
    .plan-card .p-meta { font-size: 0.82rem; color: #52514e !important; margin-bottom: 0.5rem; }
    .plan-card .p-track { height: 8px; background: #DDE7DD; border-radius: 999px; overflow: hidden; margin: 0.35rem 0; }
    .plan-card .p-fill { height: 100%; background: #2E5A31; border-radius: 999px; }
    .plan-card .p-line { font-size: 0.88rem; color: #333333 !important; }

    /* Hide the link icon Streamlit adds next to headings */
    [data-testid="stHeaderActionElements"] { display: none; }

    p { margin-bottom: 0px; }

    /* --- 7. RUNNING INDICATOR --- */
    /* Replace Streamlit's animated running icons (swimmer, cyclist, ...) with plain "Loading..." text */
    [data-testid="stStatusWidgetRunningIcon"] {
        width: auto !important;
        height: auto !important;
    }
    [data-testid="stStatusWidgetRunningIcon"] > * {
        display: none !important;
    }
    [data-testid="stStatusWidgetRunningIcon"]::after {
        content: "Loading...";
        color: #2E5A31;
        font-weight: 600;
        font-size: 0.9rem;
        white-space: nowrap;
    }

    /* --- 8. FULL-SCREEN LOADER --- */
    .loader-overlay {
        position: fixed;
        inset: 0;
        z-index: 999990;
        background-color: #F0F4F0;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .loader-box {
        width: min(420px, 85vw);
        text-align: center;
    }
    .loader-title {
        color: #2E5A31;
        font-weight: 700;
        font-size: 1.6rem;
        margin-bottom: 0.5rem;
    }
    .loader-text {
        color: #333333;
        font-weight: 600;
        margin-bottom: 0.9rem;
    }
    .loader-track {
        height: 12px;
        background-color: #DDE7DD;
        border-radius: 999px;
        overflow: hidden;
    }
    .loader-fill {
        height: 100%;
        background-color: #2E5A31;
        border-radius: 999px;
        transition: width 0.4s ease;
    }
    .loader-step {
        color: #52514e;
        font-size: 0.85rem;
        margin-top: 0.6rem;
    }

    </style>
""", unsafe_allow_html=True)


# --- BROWSER LOCATION ---
# Asks the browser for the visitor's position once and hands it to Python as component state
GEO_JS = """
export default function(component) {
    const { data, setStateValue, parentElement } = component;
    if (data && data.have) return;
    let note = parentElement.querySelector('.geo-note');
    if (!note) {
        note = document.createElement('div');
        note.className = 'geo-note';
        note.style.cssText = 'font: 600 0.9rem Inter, sans-serif; color: #2E5A31; padding: 2px 0;';
        parentElement.appendChild(note);
    }
    if (!navigator.geolocation) {
        setStateValue('location', {error: 'This browser does not support location access.'});
        return;
    }
    note.textContent = 'Requesting your location...';
    navigator.geolocation.getCurrentPosition(
        (pos) => {
            note.textContent = '';
            setStateValue('location', {
                lat: Math.round(pos.coords.latitude * 1000) / 1000,
                lon: Math.round(pos.coords.longitude * 1000) / 1000,
            });
        },
        (err) => {
            note.textContent = '';
            setStateValue('location', {error: err.message});
        },
        {timeout: 15000, maximumAge: 600000}
    );
}
"""
geolocation = st.components.v2.component("browser_geolocation", js=GEO_JS)


# --- DATA (cached) ---
@st.cache_data(show_spinner=False)
def load_gazetteers():
    return live.load_gazetteer("zcta"), live.load_gazetteer("place")


@st.cache_resource(show_spinner=False)
def load_model():
    data = cm.load_crop_data()
    if data.empty:
        return None, {}, data
    return cm.CropModel(data), cm.crop_regions(data), data


@st.cache_resource(show_spinner=False)
def load_clustering(method):
    model, _, _ = load_model()
    return model.clustering(method)


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def daily_weather(lat, lon, start, end):
    return live.daily_weather(lat, lon, start, end)


@st.cache_data(show_spinner=False)
def load_losses():
    path = PROCESSED_DIR / "insured_losses.csv"
    return pd.read_csv(path, dtype={"fips": str}) if path.exists() else None


@st.cache_data(show_spinner=False)
def crop_drivers(crop):
    return cm.weather_drivers(crop)


@st.cache_data(show_spinner=False)
def load_warehouses():
    path = PROCESSED_DIR / "warehouses.csv"
    return pd.read_csv(path, dtype={"fips": str}) if path.exists() else None


@st.cache_data(ttl=900, show_spinner=False)
def national_alerts():
    return live.ag_alerts_national()


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def stock_reports():
    """Latest Grain Stocks and Cold Storage reports; None for a report that can't be fetched."""
    out = {}
    for name, parse in (("grain-stocks", live.grain_stocks), ("cold-storage", live.cold_storage)):
        try:
            out[name] = parse(live.latest_report_text(name))
        except Exception:
            out[name] = None
    return out


@st.cache_data(ttl=900, show_spinner=False)
def local_weather(loc_key, forecast_url, grid_url, stations_url, lat, lon):
    return {
        "periods": live.forecast_periods(forecast_url),
        "week": live.week_outlook(grid_url),
        "now": live.latest_observation(stations_url),
        "alerts": live.alerts_at(lat, lon),
    }


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def county_monthly(fips):
    return live.county_monthly(fips)


@st.cache_data(ttl=900, show_spinner=False)
def nws_point(lat, lon):
    return live.nws_point(lat, lon)


# --- HELPER FUNCTIONS ---
def esc(text):
    return html.escape(str(text))


def f_from_c(c):
    return c * 9 / 5 + 32


def temp_text(c):
    return f"{f_from_c(c):.0f}°F ({c:.0f}°C)"


def big_number(value, unit=""):
    if value >= 1e9:
        return f"{value / 1e9:.2f} billion {unit}".strip()
    if value >= 1e6:
        return f"{value / 1e6:.1f} million {unit}".strip()
    return f"{value:,.0f} {unit}".strip()


def pct_change(new, old):
    if not new or not old:
        return ""
    change = (new / old - 1) * 100
    return f"{change:+.0f}% vs a year ago"


def render_header():
    st.markdown("""
        <div class="header-banner">
            <h1>Agri Forecast</h1>
        </div>
    """, unsafe_allow_html=True)


def loader_html(pct, step):
    return f"""
        <div class="loader-overlay"><div class="loader-box">
            <div class="loader-title">Agri Forecast</div>
            <div class="loader-text">Loading...</div>
            <div class="loader-track"><div class="loader-fill" style="width: {pct}%"></div></div>
            <div class="loader-step">{esc(step)} · {pct}%</div>
        </div></div>
    """


def card(title, subtitle, body, kind=""):
    st.markdown(f"""
        <div class="agri-card {kind}">
            <h3>{esc(title)}</h3>
            <div class="card-sub">{subtitle}</div>
            {body}
        </div>
    """, unsafe_allow_html=True)


def bullets(items):
    return "<ul>" + "".join(f"<li>{i}</li>" for i in items) + "</ul>"


def go_to(page):
    st.session_state.page = page


def load_plans():
    try:
        return json.loads(PLANS_PATH.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_plans(plans):
    PLANS_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLANS_PATH.write_text(json.dumps(plans, indent=2))


def set_location(lat, lon, label):
    try:
        point = nws_point(float(lat), float(lon))
    except Exception:
        st.session_state.loc_error = "The National Weather Service has no data for that location (US locations only)."
        return
    point["label"] = label or f"{point['city']}, {point['state']}"
    st.session_state.loc = point
    st.session_state.loc_error = None
    st.session_state.result = None


def location_picker(prefix):
    """Two ways to set the weather location: the browser's position or a typed ZIP / city."""
    loc = st.session_state.loc
    mode = st.radio("Weather location", ["Use my current location", "Enter location manually"],
                    index=1 if loc and loc.get("source") == "manual" else 0, horizontal=True, key=f"{prefix}_mode")

    if mode == "Use my current location":
        result = geolocation(key=f"{prefix}_geo", data={"have": loc is not None and loc.get("source") == "browser"},
                             on_location_change=lambda: None)
        found = getattr(result, "location", None)
        if found and "lat" in found:
            if loc is None or loc.get("source") != "browser" or (loc["lat"], loc["lon"]) != (found["lat"], found["lon"]):
                set_location(found["lat"], found["lon"], None)
                if st.session_state.loc:
                    st.session_state.loc["source"] = "browser"
                st.rerun()
        elif found and "error" in found:
            st.warning(f"Couldn't get your location ({found['error']}). Allow location access in your browser "
                       "or enter it manually.")
    else:
        with st.form(f"{prefix}_form", border=False):
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            text = c1.text_input("ZIP code or City, State", placeholder="e.g. 50010 or Ames, IA")
            if c2.form_submit_button("Set location", use_container_width=True):
                found = live.geocode(text, *load_gazetteers()) if text.strip() else None
                if found:
                    set_location(found[0], found[1], found[2])
                    if st.session_state.loc:
                        st.session_state.loc["source"] = "manual"
                    st.rerun()
                else:
                    st.session_state.loc_error = "Location not found. Try a 5-digit ZIP code or 'City, ST'."

    if st.session_state.get("loc_error"):
        st.error(st.session_state.loc_error)
    elif loc:
        st.markdown(f"<p class='muted'>{icon('pin')}Showing weather for <b>{esc(loc['label'])}</b> "
                    f"({esc(loc['city'])}, {esc(loc['state'])})</p>", unsafe_allow_html=True)


def load_everything(placeholder):
    """Load all data behind the full-screen loader; it only shows when something new must be fetched."""
    loc = st.session_state.loc
    loc_key = (loc["lat"], loc["lon"]) if loc else None
    if st.session_state.loaded_for == ("done", loc_key):
        return

    steps = [
        ("Reading crop and weather history", load_model),
        ("Reading warehouse list", load_warehouses),
        ("Reading crop insurance loss records", load_losses),
        ("Checking national weather alerts", national_alerts),
        ("Fetching USDA stock reports", stock_reports),
    ]
    if loc:
        steps.append(("Fetching weather for your location",
                      lambda: local_weather(loc_key, loc["forecast"], loc["grid"], loc["stations"],
                                            loc["lat"], loc["lon"])))
    for i, (label, fn) in enumerate(steps):
        placeholder.markdown(loader_html(int(i / len(steps) * 100), label), unsafe_allow_html=True)
        try:
            fn()
        except Exception:
            pass  # each card reports its own missing data
    placeholder.markdown(loader_html(100, "Ready"), unsafe_allow_html=True)
    st.session_state.loaded_for = ("done", loc_key)


def hazard_of(event):
    for name, words in HAZARDS.items():
        if any(w in event for w in words):
            return name
    return None


# =================VIEWS=================

# --- HOME: WEATHER NEWS, CROPS AFFECTED, WAREHOUSES ---
def weather_news_card(loc, weather, alerts):
    items = []
    if loc and weather:
        now, week, periods = weather["now"], weather["week"], weather["periods"]
        if now:
            hum = f", humidity {now['humidity']:.0f}%" if now.get("humidity") is not None else ""
            items.append(f"<b>Now:</b> {esc(now['text'] or 'Conditions unavailable')}, {temp_text(now['temp_c'])}{hum} "
                         f"at {esc(now['station'])}.")
        for p in periods[:2]:
            items.append(f"<b>{esc(p['name'])}:</b> {esc(p['detailedForecast'])}")
        if week["min_c"] is not None:
            items.append(f"<b>Next 7 days:</b> lows down to {temp_text(week['min_c'])}, highs up to "
                         f"{temp_text(week['max_c'])}, about {week['rain_mm']:.0f} mm "
                         f"({week['rain_mm'] / 25.4:.1f} in) of rain.")
        local = {a["event"]: a for a in weather["alerts"]}
        if local:
            for a in local.values():
                items.append(f"{icon('alert')}<b>{esc(a['event'])}:</b> {esc(a['headline'])}")
        else:
            items.append("No active weather alerts for your area.")
    elif loc:
        items.append("Weather service is not responding right now. Try again in a few minutes.")
    else:
        items.append("Choose a location above to see today's local forecast and alerts.")

    if alerts is not None and not alerts.empty:
        alerts = alerts.assign(hazard=alerts["event"].map(hazard_of)).dropna(subset=["hazard"])
        summary = []
        for hazard, g in alerts.groupby("hazard"):
            states = sorted(g["state"].unique())
            more = f" +{len(states) - 6} more" if len(states) > 6 else ""
            summary.append((len(states), f"{hazard.lower()} in {', '.join(states[:6])}{more}"))
        top = "; ".join(s for _, s in sorted(summary, reverse=True)[:3])
        items.append(f"<b>Across the US:</b> active alerts for {esc(top)}.")

    where = f"{esc(loc['city'])}, {esc(loc['state'])} · " if loc else ""
    card("Weather News", f"{where}{datetime.date.today():%A, %B %d, %Y} · National Weather Service",
         bullets(items), kind="weather")


def crop_impact_card(loc, weather, alerts, regions):
    if not regions:
        card("Crops Affected", "Our analysis", bullets(["Crop data not found. Run <code>python src/data_prep.py</code>."]))
        return
    body = ""
    month = datetime.date.today().month

    if loc:
        state = loc["state"]
        grown = [c for c in CROPS if state in regions.get(c, {}).get("states", set())]
        local_hazards = {hazard_of(a["event"]) for a in (weather or {}).get("alerts", [])} - {None}
        week = (weather or {}).get("week") or {}
        if week.get("min_c") is not None and week["min_c"] <= 0:
            local_hazards.add("Freeze / frost")
        if week.get("rain_mm", 0) >= 50:
            local_hazards.add("Flooding / heavy rain")
        if week.get("max_c") is not None and week["max_c"] >= 35:
            local_hazards.add("Heat")

        items = []
        for crop in grown:
            stage = cm.field_stage(crop, month)
            if not stage:
                continue
            effects = [EFFECTS[(h, stage)] for h in sorted(local_hazards)]
            status = f"risk of {', '.join(effects)}" if effects else "no weather threats this week"
            items.append(f"<b>{crop.title()}</b> ({stage}): {status}")
        off = [c.title() for c in grown if not cm.field_stage(c, month)]
        if off:
            items.append(f"<span class='muted'>Off-season now: {', '.join(off)}</span>")
        if not grown:
            items.append(f"None of the 12 tracked crops is grown commercially in {esc(live.STATE_NAMES.get(state, state))}.")
        body += f"<div class='section'>Near you ({esc(live.STATE_NAMES.get(state, state))})</div>" + bullets(items)
        losses = load_losses()
        if losses is not None:
            here = losses[losses["fips"] == loc["fips"]]
            area = f"{here['county'].iloc[0]} County" if not here.empty else None
            if here.empty or here["indemnity"].sum() < 100_000:
                here, area = losses[losses["state"] == state], live.STATE_NAMES.get(state, state)
            if here["indemnity"].sum() >= 100_000:
                groups = here.groupby("group")["indemnity"].sum().sort_values(ascending=False)
                top, share = groups.index[0], groups.iloc[0] / groups.sum()
                month = here[here["group"] == top].groupby("month")["indemnity"].sum().idxmax()
                crops_hit = here[here["group"] == top].groupby("crop")["indemnity"].sum().sort_values(ascending=False)
                body += (f"<div class='section'>Past losses in {esc(area)}</div>"
                         + bullets([f"<b>{esc(top)}</b> caused {share:.0%} of the {big_number(groups.sum(), 'dollars')} "
                                    f"in crop insurance payouts here ({int(here['year'].min())}-{int(here['year'].max())}), "
                                    f"mostly in {cm.MONTH_NAMES[int(month) - 1]}, hitting "
                                    f"{esc(', '.join(crops_hit.index[:3]))} most."]))

    items = []
    if alerts is not None and not alerts.empty:
        alerts = alerts.assign(hazard=alerts["event"].map(hazard_of)).dropna(subset=["hazard"])
        for hazard, g in alerts.groupby("hazard"):
            hit = []
            for crop in CROPS:
                stage = cm.field_stage(crop, month)
                reg = regions.get(crop)
                if not stage or not reg:
                    continue
                # County-level crops match alert counties; the rest match by state
                if reg["counties"]:
                    states = sorted(g.loc[g["fips"].isin(reg["counties"]), "state"].unique())
                else:
                    states = sorted(set(g["state"]) & reg["states"])
                if states:
                    hit.append(f"{crop} ({', '.join(states[:4])}{'…' if len(states) > 4 else ''})")
            if hit:
                items.append(f"<b>{esc(hazard)}:</b> {esc('; '.join(hit))}")
    body += "<div class='section'>Across the US</div>" + bullets(items or ["No crop-relevant weather alerts right now."])

    card("Crops Affected", "Our analysis: active NWS alerts and the 7-day forecast, matched to where each crop "
         "is grown (USDA NASS) and whether it is growing or being harvested this month", body)


def warehouse_card(loc, warehouses, reports, regions):
    body = ""
    if warehouses is None:
        card("Warehouses & Stocks", "USDA", bullets(["Warehouse list not found. Run <code>python src/warehouses.py</code>."]))
        return
    if not loc:
        card("Warehouses & Stocks", "USDA AMS warehouse list · NASS Grain Stocks and Cold Storage",
             bullets(["Choose a location above to see warehouses and stocks near you."]))
        return

    state, state_name = loc["state"], live.STATE_NAMES.get(loc["state"], loc["state"])
    here = warehouses[warehouses["fips"] == loc["fips"]]
    area = f"{here['county'].iloc[0]} County" if not here.empty else state_name
    if here.empty:
        here = warehouses[warehouses["state"] == state]

    items = []
    if here.empty:
        items.append(f"No USDA-licensed or approved warehouses listed in {esc(state_name)}.")
    else:
        for (commodity, unit), g in here.groupby(["commodity", "unit"]):
            cap = g["capacity"].sum()
            cap_text = f", {big_number(cap, unit.lower())} capacity" if cap > 0 else ""
            items.append(f"<b>{esc(commodity)}:</b> {len(g)} warehouse{'s' if len(g) != 1 else ''}{cap_text}")
        federal = here[here["license_type"] == "Federal"]
        problems = federal[federal["license_status"].fillna("").ne("Issued")]
        condition = ("all federal licenses active" if problems.empty
                     else f"{len(problems)} federal license(s) {', '.join(sorted(problems['license_status'].dropna().str.lower().unique()))}")
        approved = (here["ccc_status"] == "Approved").sum()
        items.append(f"<b>Condition:</b> {condition}; {approved} of {len(here)} approved for USDA (CCC) storage.")
    body += f"<div class='section'>Warehouses in {esc(area)}</div>" + bullets(items)

    items = []
    grain = reports.get("grain-stocks")
    if grain is not None and not grain.empty:
        as_of = grain["as_of"].iloc[0]
        for crop in ("corn", "wheat"):
            row = grain[(grain["crop"] == crop) & (grain["state"] == state)]
            if row.empty:
                continue
            r = row.iloc[0]
            if pd.isna(r["total"]):
                items.append(f"<b>{crop.title()}:</b> withheld by USDA to protect individual operations.")
                continue
            # The share is only meaningful when neither position is withheld
            off = (f"; {r['off_farm'] / r['total']:.0%} in off-farm storage"
                   if pd.notna(r["off_farm"]) and pd.notna(r["on_farm"]) else "")
            items.append(f"<b>{crop.title()}:</b> {big_number(r['total'] * 1000, 'bu')} "
                         f"({pct_change(r['total'], r['total_prev'])}){off}")
        title = f"Grain in storage, {esc(state_name)} ({esc(as_of)})"
        body += f"<div class='section'>{title}</div>" + bullets(items or [f"No corn or wheat stocks reported for {esc(state_name)}."])

    cold = reports.get("cold-storage")
    if cold is not None and not cold.empty:
        grown = {c for c in CROPS if state in regions.get(c, {}).get("states", set())}
        rows = cold[cold["crop"].isin(grown)]
        if not rows.empty:
            items = [f"<b>{esc(r['item'])}:</b> {big_number(r['stocks'] * 1000, 'lb')} "
                     f"({r['pct_year_ago'] - 100:+.0f}% vs a year ago)" for _, r in rows.iterrows()]
            body += (f"<div class='section'>US frozen stocks of crops grown here ({esc(cold['as_of'].iloc[0])})</div>"
                     + bullets(items))

    card("Warehouses & Stocks", "USDA AMS warehouse list · NASS Grain Stocks and Cold Storage reports", body)


INTRO_TILES = [
    ("weather", "Live weather news", "Today's forecast, the week ahead and active alerts from the National Weather Service."),
    ("crop", "Crops at risk", "Which of 12 major US crops are affected by the weather, near you and across the country."),
    ("warehouse", "Storage & stocks", "USDA-licensed warehouses near you and how much grain and frozen produce is in storage."),
    ("analyze", "Analyze, plan, track", "Get a crop recommendation from your soil and climate, plan your fields, and track "
                                  "growth with real weather and weekly advice."),
]


def render_intro():
    tiles = "".join(f"<div class='intro-tile'><div class='t-icon'>{icon(name, size='1.6rem')}</div><div class='t-title'>{esc(title)}</div>"
                    f"<div class='t-text'>{esc(text)}</div></div>" for name, title, text in INTRO_TILES)
    st.markdown(f"""
        <div class="intro">
            <div class="intro-lead"><b>Agri Forecast</b> helps farmers decide what to grow and protect what they have
            planted. It combines 45 years of crop yields with weather records and today's forecasts to show how the
            weather affects crops, where to store the harvest, and what to do this week to reduce losses.</div>
            <div class="intro-steps"><b>How to use it:</b> 1. Choose your location below. 2. Read today's weather
            news and which crops are at risk. 3. Press <b>Analyze crop</b> to find the best crop for your soil and
            weather. 4. Save a crop plan and come back to <b>Track my crops</b> each week.</div>
            <div class="intro-grid">{tiles}</div>
            <div class="intro-sources">Data: USDA National Agricultural Statistics Service · USDA Agricultural Marketing
            Service · NOAA and the National Weather Service · US Census Bureau. Free public sources, updated as they
            publish.</div>
        </div>
    """, unsafe_allow_html=True)


def render_home():
    render_header()
    render_intro()

    left, right = st.columns([4, 1], vertical_alignment="center")
    with left:
        location_picker("home")
    with right:
        st.button("Analyze crop →", on_click=go_to, args=("analyze",), use_container_width=True, type="primary")
        if load_plans():
            st.button("Track my crops", on_click=go_to, args=("track",), use_container_width=True)

    loc = st.session_state.loc
    model, regions, _ = load_model()
    try:
        alerts = national_alerts()
    except Exception:
        alerts = None
    weather = None
    if loc:
        try:
            weather = local_weather((loc["lat"], loc["lon"]), loc["forecast"], loc["grid"], loc["stations"],
                                    loc["lat"], loc["lon"])
        except Exception:
            weather = None

    weather_news_card(loc, weather, alerts)
    c1, c2 = st.columns(2, gap="large")
    with c1:
        crop_impact_card(loc, weather, alerts, regions)
    with c2:
        warehouse_card(loc, load_warehouses(), stock_reports(), regions)


# --- ANALYZE CROP: INPUTS, RESULT AND CLUSTER MAP ---
def realtime_climate(loc):
    """Each crop's growing-season climate at the user's county over the last 10 seasons (NOAA)."""
    monthly = county_monthly(loc["fips"])
    if monthly.empty:
        return None
    climate = {}
    for crop, spec in CROPS.items():
        values = cm.season_climate(monthly, spec["season"])
        if values:
            climate[crop] = values
    return climate


def cluster_map(model, clustering, rec, user_temp, user_rain):
    fig = go.Figure()
    sample = model.sample
    # Shade the area each cluster claims, so the boundaries of the chosen model are visible
    t_lo, t_hi = min(sample["temp"].min(), user_temp) - 1, max(sample["temp"].max(), user_temp) + 1
    r_lo, r_hi = max(min(sample["rain"].min(), user_rain) - 10, 0), max(sample["rain"].max(), user_rain) + 10
    temps, rains, grid = clustering.regions((t_lo, t_hi), (r_lo, r_hi))
    steps = []
    for c, tint in enumerate(CLUSTER_TINTS):
        steps += [[c / len(CLUSTER_TINTS), tint], [(c + 1) / len(CLUSTER_TINTS), tint]]
    fig.add_trace(go.Heatmap(x=temps, y=rains, z=grid, zmin=-0.5, zmax=len(CLUSTER_TINTS) - 0.5,
                             colorscale=steps, showscale=False, hoverinfo="skip"))
    for c, info in sorted(clustering.names.items()):
        pts = sample[clustering.labels == c]
        fig.add_trace(go.Scatter(
            x=pts["temp"], y=pts["rain"], mode="markers",
            name=f"{info['label']} ({', '.join(info['top_crops'])})",
            marker=dict(size=6, color=CLUSTER_COLORS[c % 3], opacity=0.35, line=dict(width=0)),
            customdata=pts[["crop", "state", "year"]].to_numpy(),
            hovertemplate="%{customdata[0]} · %{customdata[1]} %{customdata[2]}<br>"
                          "%{x:.1f}°C · %{y:.0f} mm/month<extra></extra>",
        ))
    # Typical climate of the recommended crop's good years
    fig.add_trace(go.Scatter(
        x=[rec["temp_mean"]], y=[rec["rain_mean"]], mode="markers", name=f"Typical {rec['crop']} climate",
        marker=dict(symbol="diamond", size=14, color="white", line=dict(width=2, color=INK)),
        hovertemplate=f"Typical {rec['crop']} climate<br>%{{x:.1f}}°C · %{{y:.0f}} mm/month<extra></extra>",
    ))
    fig.add_trace(go.Scatter(
        x=[user_temp], y=[user_rain], mode="markers", name="Your farm",
        marker=dict(symbol="star", size=20, color=INK, line=dict(width=2, color="white")),
        hovertemplate="Your farm<br>%{x:.1f}°C · %{y:.0f} mm/month<extra></extra>",
    ))
    # Labels sit on short leader lines in opposite directions so they never overlap when the points are close
    label = dict(showarrow=True, arrowhead=0, arrowwidth=1, arrowcolor=INK_SECONDARY, bgcolor="white",
                 borderpad=3, font=dict(color=INK, size=12))
    fig.add_annotation(x=rec["temp_mean"], y=rec["rain_mean"], text=f"{rec['crop'].title()} (typical)",
                       ax=-60, ay=-40, **label)
    fig.add_annotation(x=user_temp, y=user_rain, text="Your farm", ax=60, ay=40, **label)
    fig.update_layout(
        height=430,
        paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", color=INK_SECONDARY, size=12),
        margin=dict(l=10, r=10, t=10, b=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=INK, size=11)),
        xaxis=dict(title="Average growing-season temperature (°C)", gridcolor=GRID, zeroline=False,
                   linecolor=GRID, tickfont=dict(color=INK_SECONDARY), range=[t_lo, t_hi]),
        yaxis=dict(title="Average monthly rainfall (mm)", gridcolor=GRID, zeroline=False,
                   linecolor=GRID, tickfont=dict(color=INK_SECONDARY), range=[r_lo, r_hi]),
        hoverlabel=dict(bgcolor="white", font=dict(color=INK)),
    )
    return fig


def render_analyze():
    render_header()
    st.button("← Back to home", on_click=go_to, args=("home",))

    model, _, _ = load_model()
    if model is None:
        st.error("Crop history not found. Run `python src/data_prep.py` first.")
        return

    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.markdown("<h3 style='color: #2E5A31;'>Soil Conditions</h3>", unsafe_allow_html=True)
            st.caption("Values from your recent soil lab report.")
            n = st.slider("Nitrogen (N) - mg/kg", 0, 140, 50)
            p = st.slider("Phosphorus (P) - mg/kg", 5, 145, 50)
            k = st.slider("Potassium (K) - mg/kg", 5, 205, 50)
            ph = st.number_input("Soil pH", 3.5, 9.5, 6.5, step=0.1)
            irrigation = st.radio("Irrigation available", ["Yes", "No"], index=1, horizontal=True)

    with right:
        with st.container(border=True):
            st.markdown("<h3 style='color: #000080;'>Weather Conditions</h3>", unsafe_allow_html=True)
            source = st.radio("Weather data", ["Real-time (my location)", "Enter manually"], horizontal=True)
            climate, humidity, user_point = None, None, None
            if source.startswith("Real-time"):
                loc = st.session_state.loc
                if loc:
                    st.markdown(f"<p class='muted'>{icon('pin')}Using <b>{esc(loc['label'])}</b>. "
                                "Change it on the home page.</p>", unsafe_allow_html=True)
                else:
                    location_picker("analyze")
                    loc = st.session_state.loc
                if loc:
                    with st.spinner("Loading..."):
                        climate = realtime_climate(loc)
                        try:
                            now = local_weather((loc["lat"], loc["lon"]), loc["forecast"], loc["grid"],
                                                loc["stations"], loc["lat"], loc["lon"])["now"]
                        except Exception:
                            now = None
                    if climate:
                        corn = climate.get("corn") or next(iter(climate.values()))
                        stats = [("Season temp (Apr-Sep)", f"{corn['temp']:.1f}°C"),
                                 ("Rainfall", f"{corn['rain']:.0f} mm/month")]
                        if now and now.get("humidity") is not None:
                            humidity = now["humidity"]
                            stats.append(("Humidity now", f"{humidity:.0f}%"))
                        st.markdown("<div class='stat-row'>" + "".join(
                            f"<div class='stat'><div class='stat-label'>{esc(k)}</div>"
                            f"<div class='stat-value'>{esc(v)}</div></div>" for k, v in stats) + "</div>",
                            unsafe_allow_html=True)
                        st.caption(f"NOAA county averages for {corn['years'][0]}-{corn['years'][1]} growing seasons. "
                                   "Each crop is checked against its own season months.")
                    else:
                        st.warning("No NOAA county weather found for this location.")
            else:
                temp = st.number_input("Avg growing-season temperature (°C)", -10.0, 40.0, 20.0, step=0.5)
                humidity = st.slider("Avg humidity (%)", 10, 100, 70)
                rain = st.number_input("Avg monthly rainfall (mm)", 0, 500, 90)
                cold = st.number_input("Coldest winter low (°C), optional", -40.0, 25.0, value=None, step=0.5)
                manual = {"temp": temp, "rain": rain}
                if cold is not None:
                    manual["cold"] = cold
                climate = {crop: manual for crop in CROPS}

    if st.button("Analyze", type="primary", use_container_width=True, disabled=not climate):
        ranked = model.recommend(climate, ph, irrigation == "Yes")
        st.session_state.result = {"ranked": ranked, "ph": ph, "irrigation": irrigation, "humidity": humidity,
                                   "npk": (n, p, k), "source": source}

    result = st.session_state.result
    if not result:
        return

    ranked, best = result["ranked"], result["ranked"].iloc[0]
    # The dropdown lives in the map card; read its value first so the left card uses the same clusters
    method = st.session_state.get("cluster_method", "K-means")
    clustering = load_clustering(method)
    cluster = clustering.names[clustering.cluster_of(best["temp"], best["rain"])]
    lo, hi = best["ph_range"]

    st.markdown("<br>", unsafe_allow_html=True)
    res_l, res_r = st.columns([1, 1.4], gap="large")
    with res_l:
        with st.container(border=True):
            st.markdown("<h3 style='color: #2E5A31;'>Recommended Crop</h3>", unsafe_allow_html=True)
            st.markdown(f"<div class='result-crop'>{esc(best['crop'].title())}</div>"
                        f"<span class='result-match'>{best['score']:.0%} match</span>", unsafe_allow_html=True)
            records = int(model.stats.loc[best["crop"], "records"])
            closeness = ("very close to" if best["climate_match"] >= 0.7 else "fairly close to"
                         if best["climate_match"] >= 0.4 else "somewhat different from")
            st.markdown(f"<p><b>In simple words:</b> your weather is {closeness} the weather in the "
                        f"{records:,} past seasons when {esc(best['crop'])} grew well, and your soil "
                        f"{'suits it' if best['ph_fit'] == 1 else 'needs adjusting for it'}. That makes it the best of the 12 crops "
                        f"for your farm.</p>", unsafe_allow_html=True)
            ph_note = (f"Soil pH {result['ph']:.1f} is within the preferred {lo}-{hi}." if best["ph_fit"] == 1
                       else f"Soil pH {result['ph']:.1f} is outside the preferred {lo}-{hi}; consider liming or acidifying.")
            others = ", ".join(f"{r['crop']} ({r['score']:.0%})" for _, r in ranked.iloc[1:3].iterrows())
            st.markdown(bullets([
                f"<b>Climate:</b> {best['temp']:.1f}°C and {best['rain']:.0f} mm/month in its season; "
                f"good {esc(best['crop'])} years average {best['temp_mean']:.1f}°C and {best['rain_mean']:.0f} mm.",
                f"<b>Soil:</b> {ph_note}",
                f"<b>Climate zone:</b> {esc(cluster['label'])}, where {esc(', '.join(cluster['top_crops']))} do best.",
                f"<b>Also suitable:</b> {esc(others)}.",
            ]), unsafe_allow_html=True)
            st.caption("Match = climate fit to the crop's good-yield seasons (USDA NASS + NOAA, 1980-2025) x soil pH fit."
                       + (" Irrigation removes the low-rainfall penalty." if result["irrigation"] == "Yes" else "")
                       + " N/P/K and humidity are recorded but not scored yet.")
            st.markdown(f"<div class='section'>What moves {esc(best['crop'])} yield</div>"
                        + drivers_html(best["crop"], crop_drivers(best["crop"])), unsafe_allow_html=True)
            glossary("Match %", "Good-yield season", "Yield effect")
            plan_crop = st.selectbox("Crop to plan", ranked["crop"].tolist(), format_func=str.title)
            if st.button("Create crop plan →", type="primary", use_container_width=True):
                st.session_state.plan_crop = plan_crop
                go_to("plan")
                st.rerun()
    with res_r:
        with st.container(border=True):
            st.markdown("<h3 style='color: #2E5A31;'>Climate Cluster Map</h3>", unsafe_allow_html=True)
            st.selectbox("Clustering model", list(cm.CLUSTER_METHODS), key="cluster_method",
                         help="Groups the good-yield seasons into 3 climate clusters. The recommended crop does not "
                              "change with this choice; the clusters, their boundaries and your farm's zone do.")
            st.markdown(f"<p class='muted' style='margin: 0 0 0.5rem 0;'><b>When to use it:</b> "
                        f"{esc(cm.CLUSTER_GUIDE[method])}</p>", unsafe_allow_html=True)
            st.plotly_chart(cluster_map(model, clustering, best, best["temp"], best["rain"]), use_container_width=True,
                            config={"displayModeBar": False})
            facts = [f"Cluster quality (silhouette score) <b>{clustering.silhouette:.2f}</b> "
                     f"({'clear split' if clustering.silhouette >= 0.4 else 'groups blur together'}; -1 to 1, higher is better)",
                     "Cluster sizes: " + ", ".join(f"{v['label']} {v['size']:,}" for v in clustering.names.values())]
            if method != "K-means":
                moved = (clustering.labels != load_clustering("K-means").labels).mean()
                facts.append(f"{moved:.0%} of seasons fall in a different cluster than with K-means")
            proba = clustering.membership(best["temp"], best["rain"])
            if proba is not None:
                facts.append("Your farm's membership: " + ", ".join(
                    f"{clustering.names[c]['label']} {p:.0%}" for c, p in sorted(enumerate(proba), key=lambda x: -x[1])))
            st.markdown(bullets(facts), unsafe_allow_html=True)
            st.caption("Shaded areas show which cluster each climate belongs to under this model. Each dot is a county "
                       "or state season with an above-median yield.")
            glossary("Climate cluster", "Clustering model", "Cluster quality (silhouette score)")
            with st.expander("Which clustering model should I use?"):
                st.markdown("\n".join(f"- **{name}**: {text}" for name, text in cm.CLUSTER_GUIDE.items())
                            + "\n- **DBSCAN** (not offered): finds clusters of any shape and flags outliers, but only "
                              "when groups are separated by empty space. Our climate data has no gaps, so it finds "
                              "a single cluster.")


# --- CROP PLAN: FIX CROP, AREA AND START DATE ---
def production_unit(unit):
    """'BU / ACRE' -> 'bu'."""
    return unit.split("/")[0].strip().lower()


def nearby_storage(crop, loc, warehouses):
    """Short note on where a harvested crop can be stored near the location."""
    commodity = cm.WAREHOUSE_COMMODITY.get(crop)
    if commodity and warehouses is not None:
        for area, rows in (("county", warehouses[warehouses["fips"] == loc["fips"]]),
                           (f"in {live.STATE_NAMES.get(loc['state'], loc['state'])}", warehouses[warehouses["state"] == loc["state"]])):
            rows = rows[rows["commodity"] == commodity]
            if not rows.empty:
                if area == "county":
                    area = f"in {rows['county'].iloc[0]} County"
                cap = rows["capacity"].sum()
                cap_text = f" ({big_number(cap, rows['unit'].iloc[0].lower())} capacity)" if cap > 0 else ""
                return f"{len(rows)} USDA-listed {commodity.lower()} warehouse{'s' if len(rows) != 1 else ''} {area}{cap_text}"
        return f"no USDA-listed {commodity.lower()} warehouses nearby"
    if crop in cm.PERISHABLE:
        return "cool it quickly after picking and keep it in cold storage"
    return None


def render_plan():
    render_header()
    st.button("← Back to analysis", on_click=go_to, args=("analyze",))
    model, _, data = load_model()
    loc = st.session_state.loc

    left, right = st.columns(2, gap="large")
    with left:
        with st.container(border=True):
            st.markdown("<h3 style='color: #2E5A31;'>Crop Plan</h3>", unsafe_allow_html=True)
            if not loc:
                location_picker("plan")
                loc = st.session_state.loc
            else:
                st.markdown(f"<p class='muted'>{icon('pin')}Field location: <b>{esc(loc['label'])}</b> "
                            f"({esc(loc['city'])}, {esc(loc['state'])}). Change it on the home page.</p>",
                            unsafe_allow_html=True)
            existing = load_plans()
            if existing:
                st.markdown("<p class='muted'><b>Already planned:</b> " + esc(", ".join(
                    f"{p['crop']} ({p['area']:,.0f} acres)" for p in existing)) + ". This adds a separate plan.</p>",
                    unsafe_allow_html=True)
            crops = list(CROPS)
            default = crops.index(st.session_state.plan_crop) if st.session_state.plan_crop in crops else 0
            crop = st.selectbox("Crop", crops, index=default, format_func=str.title)
            if any(p["crop"] == crop for p in existing):
                st.caption(f"You already have a {crop} plan; a second one is fine for another field.")
            area = st.number_input("Area (acres)", min_value=0.1, max_value=100000.0, value=10.0, step=1.0)
            days, _ = cm.GROWTH[crop]
            start = st.date_input("Start date (planting, or green-up / bloom for fruit crops)",
                                  value=datetime.date.today())
            name = st.text_input("Plan name (optional)", placeholder=f"{crop.title()} - north field")

    with right:
        with st.container(border=True):
            st.markdown("<h3 style='color: #2E5A31;'>Plan Summary</h3>", unsafe_allow_html=True)
            if not loc:
                st.info("Set the field location to see the plan summary.")
                return
            items = []
            exp = cm.expected_yield(data, crop, loc["fips"], loc["state"])
            if exp:
                unit = production_unit(exp["unit"])
                items.append(f"<b>Expected yield:</b> {exp['yield']:,.1f} {esc(exp['unit'].lower())} "
                             f"({esc(exp['basis'])} average, {exp['years'][0]}-{exp['years'][1]}, USDA NASS)")
                items.append(f"<b>Expected production:</b> {big_number(exp['yield'] * area, unit)} from {area:,.1f} acres")
            items.append(f"<b>Expected harvest:</b> around {start + datetime.timedelta(days=days):%b %d, %Y} "
                         f"(about {days} days; tracking refines this with real weather)")
            if not cm.in_window(start.month, CROPS[crop]["season"]):
                s0, s1 = CROPS[crop]["season"]
                items.append(f"{icon('alert')}{start:%B} is outside the usual {crop} season "
                             f"({datetime.date(2000, s0, 1):%B}-{datetime.date(2000, s1, 1):%B}) in the main US regions.")
            lo, hi = cm.PH_RANGE[crop]
            items.append(f"<b>Soil:</b> keep pH between {lo} and {hi}.")
            storage = nearby_storage(crop, loc, load_warehouses())
            if storage:
                items.append(f"<b>Storage after harvest:</b> {esc(storage)}.")
            st.markdown(bullets(items), unsafe_allow_html=True)

            if st.button("Fix plan", type="primary", use_container_width=True):
                plans = load_plans()
                plan = {
                    "id": uuid.uuid4().hex[:8], "name": name.strip() or f"{crop.title()} plan",
                    "crop": crop, "area": area, "start": start.isoformat(),
                    "lat": loc["lat"], "lon": loc["lon"], "label": loc["label"], "city": loc["city"],
                    "state": loc["state"], "fips": loc["fips"], "forecast": loc["forecast"], "grid": loc["grid"],
                    "stations": loc["stations"], "created": datetime.date.today().isoformat(),
                    "expected_yield": exp["yield"] if exp else None, "unit": exp["unit"] if exp else None,
                }
                plans.append(plan)
                save_plans(plans)
                st.session_state.track_id = plan["id"]
                st.session_state.track_select = plan["id"]
                go_to("track")
                st.rerun()


# --- TRACKING: GROWTH FROM REAL WEATHER, WEEKLY ADVICE ---
def growth_chart(g, start):
    """Cumulative heat (growing degree days) since planting against what the season needs."""
    fig = go.Figure()
    ly = g["last_year"]
    to_date = lambda days: [start + datetime.timedelta(days=int(d)) for d in days]  # noqa: E731
    fig.add_trace(go.Scatter(x=to_date(ly["day"]), y=ly["cum_gdd"], mode="lines", name="Last year's pace",
                             line=dict(color="#a3a29d", width=2),
                             hovertemplate="Last year: %{y:.0f} GDD by %{x|%b %d}<extra></extra>"))
    if not g["actual"].empty:
        fig.add_trace(go.Scatter(x=to_date(g["actual"]["day"]), y=g["actual"]["cum_gdd"], mode="lines",
                                 name="This season", line=dict(color=GREEN, width=2),
                                 hovertemplate="This season: %{y:.0f} GDD by %{x|%b %d}<extra></extra>"))
    if not g["projection"].empty and g["progress"] < 1:
        fig.add_trace(go.Scatter(x=to_date(g["projection"]["day"]), y=g["projection"]["cum_gdd"], mode="lines",
                                 name="Projection", line=dict(color=GREEN, width=2, dash="dash"),
                                 hovertemplate="Projected: %{y:.0f} GDD by %{x|%b %d}<extra></extra>"))
    fig.add_hline(y=g["target_gdd"], line=dict(color=INK_SECONDARY, width=1, dash="dot"),
                  annotation_text=f"Needed for harvest ≈ {g['target_gdd']:.0f}", annotation_position="top left",
                  annotation_font=dict(color=INK, size=11))
    fig.update_layout(
        height=330, paper_bgcolor="white", plot_bgcolor="white",
        font=dict(family="Inter, sans-serif", color=INK_SECONDARY, size=12),
        margin=dict(l=10, r=10, t=30, b=10), hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, font=dict(color=INK, size=11)),
        xaxis=dict(gridcolor=GRID, linecolor=GRID), yaxis=dict(title="Growing degree days (°C)", gridcolor=GRID,
                                                              zeroline=False, linecolor=GRID),
        hoverlabel=dict(bgcolor="white", font=dict(color=INK)),
    )
    return fig


def rain_chart(actual):
    fig = go.Figure(go.Bar(x=actual["date"], y=actual["rain"], marker=dict(color=CLUSTER_COLORS[0]),
                           hovertemplate="%{x|%b %d}: %{y:.1f} mm<extra></extra>", name="Daily rain"))
    fig.update_layout(
        height=200, paper_bgcolor="white", plot_bgcolor="white", bargap=0.3,
        font=dict(family="Inter, sans-serif", color=INK_SECONDARY, size=12), margin=dict(l=10, r=10, t=10, b=10),
        xaxis=dict(gridcolor=GRID, linecolor=GRID), yaxis=dict(title="Rain (mm/day)", gridcolor=GRID, zeroline=False),
        hoverlabel=dict(bgcolor="white", font=dict(color=INK)), showlegend=False,
    )
    return fig


def weekly_advice(plan, g, week, alerts, warehouses):
    """Plain-language actions for the coming week from the NWS forecast and the crop's growth stage."""
    crop, items = plan["crop"], []
    planted = g["progress"] > 0
    near_harvest = g["progress"] >= 0.9
    storage = nearby_storage(crop, plan, warehouses)
    if week.get("min_c") is not None and week["min_c"] <= 0:
        if not planted:
            items.append(f"{icon('frost')}<b>Frost expected</b> (low {temp_text(week['min_c'])}): hold planting until after it passes.")
        elif crop == "wheat":
            items.append(f"{icon('frost')}<b>Frost expected</b> (low {temp_text(week['min_c'])}): established winter wheat is frost-hardy; no action needed.")
        else:
            items.append(f"{icon('frost')}<b>Frost expected</b> (low {temp_text(week['min_c'])}): cover young or tender plants with "
                         "row covers overnight, water the soil the day before (moist soil holds heat), and pick ripe produce first.")
    rain = week.get("rain_mm", 0)
    if rain >= 50:
        items.append(f"{icon('rain')}<b>Heavy rain</b> (about {rain:.0f} mm this week): clear drains and furrows, hold fertilizer and "
                     "spraying until after (rain washes them off), and keep machinery off wet soil.")
        if near_harvest:
            items.append(f"{icon('harvest')}<b>Harvest before the rain:</b> the crop is {g['progress']:.0%} of the way to harvest. Bring in "
                         f"what is ready and store it{'; ' + esc(storage) if storage else ''}.")
    elif rain >= 10 and near_harvest:
        items.append(f"{icon('drizzle')}<b>Some rain</b> (about {rain:.0f} mm this week): harvest between showers and let the crop "
                     "dry before storing it.")
    elif rain >= 10:
        items.append(f"{icon('drizzle')}<b>Useful rain</b> (about {rain:.0f} mm this week): you can skip irrigation.")
    elif planted and not near_harvest and week.get("max_c") is not None and week["max_c"] >= 25:
        items.append(f"{icon('sun')}<b>Dry, warm week</b> (about {rain:.0f} mm of rain): plan irrigation.")
    if week.get("max_c") is not None and week["max_c"] >= 35:
        items.append(f"{icon('heat')}<b>Heat</b> (highs up to {temp_text(week['max_c'])}): irrigate early in the morning and avoid "
                     "field work in the afternoon.")
    for a in {a["event"]: a for a in alerts}.values():
        if hazard_of(a["event"]):
            items.append(f"{icon('alert')}<b>{esc(a['event'])}:</b> {esc(a['headline'])}")
    if g["progress"] >= 1:
        items.append(f"{icon('check')}<b>Ready for harvest</b> based on heat received. Storage: {esc(storage or 'see Warehouses on the home page')}.")
    if not items:
        items.append("No weather risks this week; keep normal care.")
    return items


# Short, standard ways to reduce each kind of loss. The ranking of causes comes from the USDA RMA payout data.
CAUSE_ACTIONS = {
    "Too much rain / flooding": "keep drains and ditches clear, stay off wet soil, and harvest ripe crops before long wet spells",
    "Drought / heat": "plan irrigation for the hottest, driest weeks and keep the soil covered to hold moisture",
    "Hail": "hail cannot be stopped in the field; insurance is the main protection (some orchards use hail nets)",
    "Wind / storms": "harvest mature or weak-stalked fields before forecast storms and choose varieties with strong stalks",
    "Freeze / frost / cold": "watch frost forecasts at planting and bloom; use row covers, or wind machines in orchards",
    "Pests / disease / quality": "scout fields after warm, wet spells and follow your extension office's spray thresholds",
    "Other": "keep field records and report damage to your insurance agent quickly",
}

# Plain-language meanings of the terms used in the app
GLOSSARY = {
    "Match %": "How close your weather and soil are to the conditions in years when the crop grew well. "
               "100% = the same as its good years; below 30% = quite different.",
    "Good-yield season": "A county (or state) and year where the crop's yield was at or above the middle value "
                         "for that year. These are the examples the app learns from.",
    "Climate cluster": "A group of places and years with similar weather (temperature and rainfall). The map "
                       "colors each group so you can see which group your farm is in.",
    "Clustering model": "The method used to form the groups. Different methods draw the group borders differently.",
    "Cluster quality (silhouette score)": "How clearly the groups are separated, from -1 to 1. Above 0.4 is a "
                                          "clear split; near 0 means the groups blur into each other.",
    "Heat units (growing degree days, GDD)": "A count of useful warmth. Each day adds the amount the average "
                                             "temperature is above the crop's minimum growing temperature. Crops "
                                             "need a certain total to be ready for harvest.",
    "Progress to harvest": "Heat units received since planting divided by the heat units the season needs.",
    "Yield effect": "From 45 years of records: how much yield usually changes, in %, when a month is 1°C warmer "
                    "or gets 1 inch more rain than normal for that place.",
    "Insurance payouts": "Money paid by federal crop insurance to farmers for losses, by cause. It shows which "
                         "weather events have actually cost farmers money in an area.",
}


def glossary(*terms):
    with st.expander("What do these words mean?"):
        st.markdown("\n".join(f"- **{t}**: {GLOSSARY[t]}" for t in terms))


def loss_profile(losses, crop, fips, state):
    """Where insured losses of a crop came from in the county (else the state, else the US), 2015-2024."""
    if losses is None:
        return None
    rows = losses[losses["crop"] == crop]
    for area, subset in (("county", rows[rows["fips"] == fips]), ("state", rows[rows["state"] == state]),
                         ("US", rows)):
        # Need a meaningful amount of payouts to say anything about an area
        if subset["indemnity"].sum() >= 100_000 and subset["year"].nunique() >= 3:
            groups = subset.groupby("group")["indemnity"].sum().sort_values(ascending=False)
            peak = subset.groupby(["group", "month"])["indemnity"].sum()
            out = []
            for group, amount in groups.items():
                if amount / groups.sum() < 0.03:
                    continue
                month = int(peak[group].idxmax()) if group in peak.index.get_level_values(0) else None
                out.append({"group": group, "share": amount / groups.sum(), "amount": amount,
                            "peak_month": cm.MONTH_NAMES[month - 1] if month and 1 <= month <= 12 else None})
            name = (f"{subset['county'].iloc[0]} County, {state}" if area == "county"
                    else live.STATE_NAMES.get(state, state) if area == "state" else "the US")
            return {"area": area, "name": name, "total": groups.sum(), "years": subset["year"].nunique(),
                    "span": (int(losses["year"].min()), int(losses["year"].max())), "causes": out}
    return None


def loss_section_html(crop, fips, state):
    profile = loss_profile(load_losses(), crop, fips, state)
    if profile is None:
        return (f"<p class='muted'>No federal crop insurance payout data for {esc(crop)} "
                "(it is not covered by a USDA insurance policy, or payouts are too small to rank).</p>")
    items = []
    for c in profile["causes"][:4]:
        when = f", mostly in {c['peak_month']}" if c["peak_month"] else ""
        items.append(f"<b>{esc(c['group'])}: {c['share']:.0%}</b> of payouts{esc(when)}. "
                     f"<span class='muted'>To reduce it: {esc(CAUSE_ACTIONS.get(c['group'], CAUSE_ACTIONS['Other']))}.</span>")
    lo, hi = profile["span"]
    return (f"<p class='muted'>Federal crop insurance paid {big_number(profile['total'], 'dollars')} for {esc(crop)} "
            f"losses in {esc(profile['name'])}, {lo}-{hi}. What caused them (USDA RMA):</p>" + bullets(items))


def driver_sentences(drivers, top=3, alpha=0.01):
    """Plain sentences for the strongest statistically significant weather effects on yield."""
    if drivers is None or drivers["drivers"].empty:
        return []
    out = []
    for d in drivers["drivers"][drivers["drivers"]["p"] < alpha].head(top).itertuples():
        if d.variable == "temperature":
            article = "An" if d.month[0] in "AEIOU" else "A"
            cause = f"{article} {d.month} 1°C warmer than normal"
        else:
            cause = f"1 inch (25 mm) more rain than normal in {d.month}"
        direction = "higher" if d.effect > 0 else "lower"
        out.append(f"{cause} goes with about <b>{abs(d.effect):.1f}% {direction}</b> yield.")
    return out


def drivers_html(crop, drivers):
    sentences = driver_sentences(drivers)
    if not sentences:
        rows = 0 if drivers is None else drivers["rows"]
        return (f"<p class='muted'>Not enough records to measure reliably how weather moves {esc(crop)} yield "
                f"({rows} location-years).</p>")
    lo, hi = drivers["years"]
    unit, where = ("county", "counties") if drivers["key"] == "fips" else ("state", "states")
    strength = ("weak: most year-to-year changes come from other things (pests, disease, farming practices)"
                if drivers["r2"] < 0.1 else "moderate")
    return (bullets(sentences) +
            f"<p class='muted'>Measured from {drivers['rows']:,} {unit}-years in {drivers['locations']:,} "
            f"{where}, {lo}-{hi} (USDA NASS yields + NOAA weather). Only effects that pass a significance test "
            f"(p &lt; 0.01) are shown. Weather explains about {max(drivers['r2'], 0):.0%} of the year-to-year "
            f"swings when tested on years the model did not see, so its pull is {strength}.</p>")


# Questions farmers ask when bad weather is coming, answered like the freezer question
LOSS_FAQ = {
    "A storm is coming and my crop is almost ready. Should I harvest early?": """
Usually **yes**, if the crop is close to maturity.
- **Grain (corn, wheat):** harvesting a few days early and drying the grain costs less than losing it to
  lodging, sprouting or mold after heavy rain.
- **Fruit and vegetables:** pick what is ripe before heavy rain or hail; ripe fruit splits and rots when wet.
- **Not close to maturity:** leave it. Instead, clear drains and keep machinery off wet soil.
""",
    "Can I store grain that is still wet?": """
**No.** Wet grain heats up and molds within days, and the damage spreads through the bin.
- Dry corn to about **15%** moisture for winter storage, **13%** to keep it into summer; wheat to about **13%**.
- Run aeration fans to cool grain after it goes into the bin, and check grain temperature every 2 weeks.
- Never put wet and dry grain in the same bin.
""",
    "My field flooded. What should I do?": """
- Most crops survive only **2-4 days under water**, less in warm weather. After the water drops, wait 3-5 days
  and check for new leaves or healthy white roots before deciding to replant.
- Scout for disease; wet, warm conditions favor root rots and leaf diseases.
- **Take dated photos and report the damage to your crop insurance agent within 72 hours** of finding it, and
  before you replant or destroy the crop.
""",
    "Frost is forecast tonight. What can I do?": """
- Cover tender plants in the evening with row covers or blankets; keep covers off the leaves where possible.
- Water the soil during the day: moist soil stores and releases more heat overnight.
- Pick ripe fruit and vegetables first.
- Do not use plastic touching the leaves; it can make frost damage worse.
""",
    "How do I protect my income if weather destroys the crop?": """
- **Federal crop insurance** (USDA Risk Management Agency, sold through private agents) covers yield or revenue
  losses from weather. Sign up before the sales closing date for your crop, which is **before planting**.
- If no insurance policy exists for your crop in your county, ask your local **USDA Farm Service Agency** office
  about the **Noninsured Crop Disaster Assistance Program (NAP)**.
- Keep records of planting dates, acres and yields; they are needed for any claim.

Sources: [USDA Risk Management Agency](https://www.rma.usda.gov/) ·
[FSA Noninsured Crop Disaster Assistance](https://www.fsa.usda.gov/resources/programs/noninsured-crop-disaster-assistance-related-information) ·
[farmers.gov disaster recovery](https://www.farmers.gov/protection-recovery)
""",
    "Where can I store my harvest safely?": """
- **Grain, cotton, peanuts, sugar, beans:** USDA-licensed (US Warehouse Act) warehouses are inspected and must
  meet financial requirements, which protects stored crops. The home page lists the ones near you.
- **Fruit and vegetables:** remove field heat within hours (pick in the cool morning, keep in shade) and move
  them to cold storage; each crop has its own best temperature and humidity.
""",
}

FREEZER_FAQ = """
**No. A living plant cannot be frozen and brought back.** Freezing forms ice crystals inside the plant's
cells that burst them, so the plant dies, and growth cannot be "paused" and restarted. Freezing only works
for **harvested produce** (berries, peaches, sweet corn, carrots), which is what the USDA Cold Storage report
tracks.

Rain is usually good for a growing crop. What to do instead:
- **Before heavy rain:** clear drains, hold fertilizer and spraying, keep machinery off wet soil.
- **If the crop is ready:** harvest before the rain and move it into storage (grain warehouses for corn and
  wheat, cold storage for fruit and vegetables).
- **Seedlings in pots or trays:** move them under cover or indoors, not into a freezer.
- **Frost (not rain) is the cold risk:** row covers overnight protect tender plants.
"""


def plan_growth(plan):
    """Growth progress of one plan from daily weather since its start date; None if the service is down."""
    crop, start = plan["crop"], datetime.date.fromisoformat(plan["start"])
    days, _ = cm.GROWTH[crop]
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    try:
        if start <= yesterday:
            actual = daily_weather(plan["lat"], plan["lon"], start, min(yesterday, start + datetime.timedelta(days=days)))
        else:
            actual = pd.DataFrame(columns=["date", "tmax", "tmin", "rain"])
        ly_start = start - datetime.timedelta(days=365)
        last_year = daily_weather(plan["lat"], plan["lon"], ly_start, min(yesterday, ly_start + datetime.timedelta(days=days)))
    except Exception:
        return None
    return cm.growth_progress(crop, start, actual, last_year)


def plan_label(p):
    return (f"{p['name']} · {p['crop'].title()} · {p['area']:,.1f} acres · "
            f"started {datetime.date.fromisoformat(p['start']):%b %d, %Y} · {p['label']}")


def select_plan(plan_id):
    st.session_state.track_id = plan_id
    st.session_state.track_select = plan_id


def plans_overview(plans):
    """One card per plan so several crops can be compared at a glance."""
    total = sum(p["area"] for p in plans)
    st.markdown(f"<h3 style='color: #2E5A31;'>Your Crop Plans</h3>"
                f"<p class='muted'>{len(plans)} plan{'s' if len(plans) != 1 else ''} · {total:,.1f} acres in total. "
                "Each crop is tracked and analyzed separately.</p>", unsafe_allow_html=True)
    per_row = 3
    for row in range(0, len(plans), per_row):
        cols = st.columns(per_row, gap="medium")
        for col, p in zip(cols, plans[row:row + per_row]):
            g = plan_growth(p)
            with col:
                if g is None:
                    status = "<div class='p-line'>Weather service not responding.</div>"
                    pct = 0
                else:
                    pct = g["progress"] * 100
                    status = (f"<div class='p-line'><b>{esc(g['stage'])}</b> · {g['progress']:.0%}</div>"
                              f"<div class='p-line'>Est. harvest {g['harvest']:%b %d, %Y}</div>")
                st.markdown(f"""
                    <div class="plan-card">
                        <div class="p-name">{esc(p['name'])}</div>
                        <div class="p-meta">{esc(p['crop'].title())} · {p['area']:,.1f} acres · {esc(p['label'])} ·
                            started {datetime.date.fromisoformat(p['start']):%b %d, %Y}</div>
                        <div class="p-track"><div class="p-fill" style="width: {pct:.0f}%"></div></div>
                        {status}
                    </div>
                """, unsafe_allow_html=True)
                st.button("View details", key=f"view_{p['id']}", on_click=select_plan, args=(p["id"],),
                          use_container_width=True)


def next_crop_to_plan():
    """Best-ranked crop from the last analysis that has no plan yet."""
    planned = {p["crop"] for p in load_plans()}
    result = st.session_state.result
    ranked = result["ranked"]["crop"].tolist() if result else list(CROPS)
    return next((c for c in ranked if c not in planned), ranked[0])


def plan_another():
    st.session_state.plan_crop = next_crop_to_plan()
    go_to("plan")


def render_track():
    render_header()
    nav_l, nav_r = st.columns([3, 1], vertical_alignment="center")
    nav_l.button("← Back to home", on_click=go_to, args=("home",))
    nav_r.button("+ Plan another crop", on_click=plan_another, type="primary", use_container_width=True)
    plans = load_plans()
    if not plans:
        st.info("No crop plans yet. Analyze a crop and choose **Create crop plan**.")
        return

    with st.spinner("Loading..."):
        plans_overview(plans)

    ids = [p["id"] for p in plans]
    if st.session_state.get("track_select") not in ids:
        st.session_state.track_select = st.session_state.track_id if st.session_state.track_id in ids else ids[-1]
    st.markdown("<h3 style='color: #2E5A31;'>Plan Details</h3>", unsafe_allow_html=True)
    plan_id = st.selectbox("Crop plan", ids, key="track_select",
                           format_func=lambda i: plan_label(next(p for p in plans if p["id"] == i)))
    plan = next(p for p in plans if p["id"] == plan_id)
    st.session_state.track_id = plan["id"]
    crop = plan["crop"]
    days, base = cm.GROWTH[crop]

    with st.spinner("Loading..."):
        g = plan_growth(plan)
        if g is None:
            st.error("Daily weather service (NOAA ACIS) is not responding. Try again in a few minutes.")
            return
        start = datetime.date.fromisoformat(plan["start"])
        try:
            week_data = local_weather((plan["lat"], plan["lon"]), plan["forecast"], plan["grid"], plan["stations"],
                                      plan["lat"], plan["lon"])
        except Exception:
            week_data = {"week": {}, "alerts": []}

    production = (f"{big_number(plan['expected_yield'] * plan['area'], production_unit(plan['unit']))}"
                  if plan.get("expected_yield") else "n/a")
    pace = "n/a" if g["pace"] is None else f"{g['pace']:+.0%}"
    stats = [("Stage (approx.)", g["stage"]), ("Progress to harvest", f"{g['progress']:.0%}"),
             ("Warmth vs last year", pace), ("Est. harvest", f"{g['harvest']:%b %d, %Y}"),
             ("Expected production", production)]
    with st.container(border=True):
        st.markdown(f"<h3 style='color: #2E5A31;'>{esc(plan['crop'].title())} · {esc(plan['label'])}</h3>",
                    unsafe_allow_html=True)
        st.markdown("<div class='stat-row'>" + "".join(
            f"<div class='stat'><div class='stat-label'>{esc(k)}</div><div class='stat-value'>{esc(v)}</div></div>"
            for k, v in stats) + "</div>", unsafe_allow_html=True)
        st.progress(g["progress"])
        st.markdown(f"<p class='muted'><b>In simple words:</b> the crop has received {g['progress']:.0%} of the warmth it "
                    f"needs to be ready, {('about the same as' if g['pace'] is None or abs(g['pace']) < 0.03 else ('more than' if g['pace'] > 0 else 'less than'))} "
                    f"last year by this point. {g['days']} days since start · {g['gdd']:.0f} heat units (base {base:g}°C) "
                    f"and {g['rain_mm']:.0f} mm of rain so far (NOAA ACIS). The total needed is what last year's weather "
                    f"here delivered over a typical {days}-day {crop} season.</p>", unsafe_allow_html=True)

    left, right = st.columns([1.4, 1], gap="large")
    with left:
        with st.container(border=True):
            st.markdown("<h3 style='color: #2E5A31;'>Growth From Weather</h3>", unsafe_allow_html=True)
            st.plotly_chart(growth_chart(g, start), use_container_width=True, config={"displayModeBar": False})
            if not g["actual"].empty:
                st.plotly_chart(rain_chart(g["actual"]), use_container_width=True, config={"displayModeBar": False})
        with st.container(border=True):
            st.markdown(f"<h3 style='color: #2E5A31;'>How Weather Moves {esc(crop.title())} Yield</h3>",
                        unsafe_allow_html=True)
            drivers = crop_drivers(crop)
            st.markdown(drivers_html(crop, drivers), unsafe_allow_html=True)
            planted = datetime.date.fromisoformat(plan["start"])
            effects = [e for e in cm.season_effects(drivers, county_monthly(plan["fips"]), g["harvest"].year, planted)
                       if e.get("observed")]
            if not effects and driver_sentences(drivers):
                st.markdown("<div class='section'>This season so far</div><p class='muted'>None of these key months "
                            "has passed since planting yet. Their effect will show here as NOAA publishes each "
                            "month's weather.</p>", unsafe_allow_html=True)
            if effects:
                items = []
                for e in effects:
                    if e["variable"] == "temperature":
                        what = f"{e['month']} {e['year']} was {abs(e['difference']):.1f}°C {'warmer' if e['difference'] > 0 else 'cooler'}"
                    else:
                        what = (f"{e['month']} {e['year']} had {abs(e['difference']):.0f} mm "
                                f"{'more' if e['difference'] > 0 else 'less'} rain")
                    cap = (" <span class='muted'>(unusually large; effect limited to the range seen in past "
                           "data)</span>" if e["capped"] else "")
                    items.append(f"{what} than the 10-year normal here → about <b>{e['expected_effect']:+.1f}%</b> yield.{cap}")
                st.markdown("<div class='section'>This season so far</div>" + bullets(items)
                            + "<p class='muted'>NOAA county weather; normal = the previous 10 years.</p>",
                            unsafe_allow_html=True)
            glossary("Heat units (growing degree days, GDD)", "Progress to harvest", "Yield effect", "Insurance payouts")
    with right:
        with st.container(border=True):
            st.markdown("<h3 style='color: #000080;'>This Week's Advice</h3>", unsafe_allow_html=True)
            week = week_data.get("week") or {}
            if week.get("min_c") is not None:
                st.caption(f"NWS 7-day forecast: lows {temp_text(week['min_c'])}, highs {temp_text(week['max_c'])}, "
                           f"about {week['rain_mm']:.0f} mm of rain.")
            st.markdown(bullets(weekly_advice(plan, g, week, week_data.get("alerts", []), load_warehouses())),
                        unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown("<h3 style='color: #2E5A31;'>Tips to Reduce Losses</h3>"
                        "<div class='section'>What has caused losses here</div>", unsafe_allow_html=True)
            st.markdown(loss_section_html(crop, plan["fips"], plan["state"]), unsafe_allow_html=True)
            st.markdown("<div class='section'>Common questions</div>", unsafe_allow_html=True)
            for question, answer in LOSS_FAQ.items():
                with st.expander(question):
                    st.markdown(answer)
            with st.expander("Can I store the plant in a freezer to protect it from rain?"):
                st.markdown(FREEZER_FAQ)
        if st.button("Delete this plan", use_container_width=True):
            save_plans([p for p in plans if p["id"] != plan["id"]])
            st.session_state.track_id = None
            st.session_state.pop("track_select", None)
            st.rerun()


# =================MAIN APP ROUTING=================
loader = st.empty()
load_everything(loader)
loader.empty()

if st.session_state.page == "analyze":
    render_analyze()
elif st.session_state.page == "plan":
    render_plan()
elif st.session_state.page == "track":
    render_track()
else:
    render_home()
