import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np

# --- CONFIGURATION ---
st.set_page_config(
    page_title="Agri-Forecast",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- MOCK DATA ---
MOCK_CLUSTERS = {
    0: {"name": "Tropical / High Nitrogen Zone", "crop": "Rice", "avg_n": 90, "avg_p": 40, "avg_k": 40, "match": "92%"},
    1: {"name": "Arid / Sandy Soil Zone", "crop": "Chickpea", "avg_n": 20, "avg_p": 60, "avg_k": 20, "match": "88%"},
    2: {"name": "Temperate / Loam Zone", "crop": "Maize", "avg_n": 70, "avg_p": 50, "avg_k": 50, "match": "95%"},
}

MOCK_RULES = {
    "Rice": [
        {"item": "Urea Fertilizer (High N)", "type": "soil", "conf": "92%", "lift": 3.4,
         "desc": "Essential for leafy growth in wet conditions."},
        {"item": "Flooding Irrigation (Weekly)", "type": "water", "conf": "88%", "lift": 2.1,
         "desc": "Maintains anaerobic soil conditions."}
    ],
    "Maize": [
        {"item": "DAP Fertilizer (NP Mix)", "type": "soil", "conf": "85%", "lift": 2.8,
         "desc": "Crucial for root development and stalk strength."},
        {"item": "Sprinkler Irrigation", "type": "water", "conf": "79%", "lift": 1.9,
         "desc": "Ensures even coverage during tasseling."}
    ],
    "Chickpea": [
        {"item": "Bio-Compost Application", "type": "soil", "conf": "95%", "lift": 4.1,
         "desc": "Improves soil structure in sandy textures."},
        {"item": "Drip Irrigation", "type": "water", "conf": "81%", "lift": 2.5,
         "desc": "Prevents root rot by delivering water directly."}
    ]
}


def get_tracking_data(period):
    if period == 'Monthly':
        periods = pd.date_range(start='2024-01-01', periods=12, freq='M').strftime('%Y-%m')
        forecast = np.random.randint(80, 120, 12)
        actual = np.random.randint(70, 110, 12)
    elif period == 'Quarterly':
        periods = pd.date_range(start='2023-01-01', periods=4, freq='Q').strftime('Q%q %Y')
        forecast = np.random.randint(250, 350, 4)
        actual = np.random.randint(240, 340, 4)
    else:  # Annual
        periods = pd.date_range(start='2020-01-01', periods=5, freq='Y').strftime('%Y')
        forecast = np.random.randint(1000, 1400, 5)
        actual = np.random.randint(950, 1350, 5)

    return pd.DataFrame({
        'Period': periods,
        'Forecasted Yield (kg)': forecast,
        'Actual Yield (kg)': actual
    }).set_index('Period')


# --- STATE MANAGEMENT ---
if 'step' not in st.session_state: st.session_state.step = 1
if 'user_data' not in st.session_state: st.session_state.user_data = {}
if 'result_cluster' not in st.session_state: st.session_state.result_cluster = None

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

    /* --- TABS STYLING --- */
    /* Base Tab: Green Background, White Text */
    button[data-testid="stBaseButton-header"] {
        background-color: #2E5A31 !important;
        color: white !important;
        font-weight: 600 !important;
        border: 1px solid #2E5A31;
        border-radius: 5px;
        margin-right: 5px;
    }

    /* Hover State */
    button[data-testid="stBaseButton-header"]:hover {
        background-color: #4CAF50 !important;
        color: white !important;
    }

    /* Active Tab: Darker Green */
    button[data-testid="stBaseButton-header"][aria-selected="true"] {
        background-color: #1B381D !important; 
        color: white !important;
        border: 1px solid #1B381D;
    }

    /* --- 4. SIDEBAR --- */
    [data-testid="stSidebar"] {
        background-color: #2E5A31;
    }
    [data-testid="stSidebar"] * {
        color: #ffffff !important;
    }

    /* --- 5. BANNER --- */
    .header-banner {
        background-color: #2E5A31;
        padding: 2rem;
        border-radius: 0px 0px 15px 15px;
        color: white;
        text-align: center;
        margin-bottom: 2rem;
        margin-top: -50px;
    }
    .header-banner h1 {
        color: white !important;
        margin: 0;
        font-weight: 700;
        font-size: 2.5rem;
    }

    /* --- 6. CARDS & BUTTONS --- */
    .agri-card {
        background-color: #FFFFFF;
        padding: 2rem;
        border-radius: 15px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.05);
        margin-bottom: 1.5rem;
        border: 1px solid #E0E0E0;
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

    p { margin-bottom: 0px; }

    </style>
""", unsafe_allow_html=True)


# --- HELPER FUNCTIONS ---
def render_header():
    st.markdown("""
        <div class="header-banner">
            <h1>Agri-Forecast: Proactive Crop and Resource Planning</h1>
        </div>
    """, unsafe_allow_html=True)


def reset_app():
    st.session_state.step = 1
    st.session_state.user_data = {}
    st.rerun()


def analyze_data_quick():
    n_val = st.session_state.user_data.get('N', 50)
    if n_val > 80:
        st.session_state.result_cluster = 0
    elif n_val < 40:
        st.session_state.result_cluster = 1
    else:
        st.session_state.result_cluster = 2
    st.session_state.step = 2
    st.rerun()


# --- STYLING HELPERS ---
def label_soil(text):
    return f'<p style="color: #2E5A31; font-weight: 600; font-size: 1rem; margin-bottom: -10px;">{text}</p>'


def label_weather(text):
    return f'<p style="color: #000080; font-weight: 600; font-size: 1rem; margin-bottom: -10px;">{text}</p>'


def info_box_soil(text):
    return f"""
    <div style="background-color: #E8F5E9; padding: 15px; border-radius: 8px; border-left: 5px solid #2E5A31; margin-bottom: 20px;">
        <p style="color: #2E5A31; margin: 0;">{text}</p>
    </div>
    """


def info_box_weather(text):
    return f"""
    <div style="background-color: #E3F2FD; padding: 15px; border-radius: 8px; border-left: 5px solid #000080; margin-bottom: 20px;">
        <p style="color: #000080; margin: 0;">{text}</p>
    </div>
    """


# =================VIEWS=================

# --- VIEW 1: FARMER PROFILE INPUT ---
def render_profile_view():
    render_header()

    st.markdown('<div class="agri-card">', unsafe_allow_html=True)
    st.markdown("<h2 style='color: #2E5A31;'>Farmer Profile Input</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color: #333333;'>Enter your pre-season soil test results and environmental forecasts to begin the unsupervised analysis.</p><br>",
        unsafe_allow_html=True)

    col1, col2 = st.columns(2, gap="large")

    with col1:
        st.markdown("<h3 style='color: #2E5A31;'>Soil Conditions</h3>", unsafe_allow_html=True)
        st.markdown(info_box_soil("Input values from your recent soil lab report."), unsafe_allow_html=True)

        st.markdown(label_soil("Nitrogen (N) - mg/kg"), unsafe_allow_html=True)
        n = st.slider("n", 0, 140, 50, label_visibility="collapsed")

        st.markdown(label_soil("Phosphorus (P) - mg/kg"), unsafe_allow_html=True)
        p = st.slider("p", 5, 145, 50, label_visibility="collapsed")

        st.markdown(label_soil("Potassium (K) - mg/kg"), unsafe_allow_html=True)
        k = st.slider("k", 5, 205, 50, label_visibility="collapsed")

        st.markdown(label_soil("Soil pH Level"), unsafe_allow_html=True)
        ph = st.number_input("ph", 0.0, 14.0, 6.5, step=0.1, label_visibility="collapsed")

    with col2:
        st.markdown("<h3 style='color: #000080;'>Climatic Factors</h3>", unsafe_allow_html=True)
        st.markdown(info_box_weather("Seasonal forecast data."), unsafe_allow_html=True)

        st.markdown(label_weather("Avg Season Temp (°C)"), unsafe_allow_html=True)
        temp = st.number_input("temp", 10.0, 50.0, 25.0, label_visibility="collapsed")

        st.markdown(label_weather("Avg Humidity (%)"), unsafe_allow_html=True)
        humidity = st.slider("hum", 10, 100, 70, label_visibility="collapsed")

        st.markdown(label_weather("Expected Rainfall (mm)"), unsafe_allow_html=True)
        rain = st.number_input("rain", 0, 500, 150, label_visibility="collapsed")

        st.markdown(label_weather("Irrigation Availability"), unsafe_allow_html=True)
        irrigation = st.radio("irr", ["Yes", "No"], horizontal=True, label_visibility="collapsed")

    st.markdown("<br><hr>", unsafe_allow_html=True)

    st.session_state.user_data = {'N': n, 'P': p, 'K': k, 'ph': ph, 'temp': temp, 'irrigation': irrigation}

    col_center = st.columns([1, 2, 1])
    with col_center[1]:
        if st.button("Analyze Soil & Generate Plan", use_container_width=True):
            analyze_data_quick()

    st.markdown('</div>', unsafe_allow_html=True)


# --- VIEW 2: ZONE REVEAL ---
def render_zone_view():
    render_header()

    cluster_id = st.session_state.result_cluster
    cluster_info = MOCK_CLUSTERS[cluster_id]
    user_vals = st.session_state.user_data

    st.markdown('<div class="agri-card">', unsafe_allow_html=True)
    st.markdown(f"<h2 style='color: #2E5A31;'>Phase A Result: Cluster Identification</h2>", unsafe_allow_html=True)
    st.success(
        f"The unsupervised model has identified your farm's micro-climate archetype as: **Cluster {cluster_id + 1}**")

    m1, m2, m3 = st.columns(3)
    m1.metric("Cluster Zone Type", cluster_info['name'])
    m2.metric("Recommended Crop", cluster_info['crop'], delta="Highest Historical Yield")
    m3.metric("Cluster Match Score", cluster_info['match'])
    st.markdown('</div>', unsafe_allow_html=True)

    st.markdown('<div class="agri-card">', unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1], gap="large")

    with c1:
        st.markdown("<h3 style='color: #333333;'>Cluster Compatibility Scan (Radar View)</h3>", unsafe_allow_html=True)
        categories = [
            '<span style="color:#2E5A31"><b>Nitrogen</b></span>',
            '<span style="color:#2E5A31"><b>Phosphorus</b></span>',
            '<span style="color:#2E5A31"><b>Potassium</b></span>',
            '<span style="color:#2E5A31"><b>pH</b></span>',
            '<span style="color:#000080"><b>Temp</b></span>'
        ]

        fig = go.Figure()
        fig.add_trace(go.Scatterpolar(
            r=[cluster_info['avg_n'], cluster_info['avg_p'], cluster_info['avg_k'], 65, 50],
            theta=categories, fill='toself', name='Ideal Cluster Average',
            line_color='#4CAF50', fillcolor='rgba(76, 175, 80, 0.4)'
        ))
        fig.add_trace(go.Scatterpolar(
            r=[user_vals['N'], user_vals['P'], user_vals['K'], user_vals['ph'] * 10, user_vals['temp'] * 2],
            theta=categories, fill='toself', name='Your Farm Profile',
            line_color='#1E88E5', fillcolor='rgba(30, 136, 229, 0.2)'
        ))

        fig.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 150], gridcolor='#E0E0E0')),
            showlegend=True,
            margin=dict(l=40, r=40, t=20, b=20),
            height=350,
            paper_bgcolor='white',
            plot_bgcolor='white',
            font=dict(color="#333333")
        )
        st.plotly_chart(fig, use_container_width=True)

    with c2:
        st.markdown("<h3 style='color: #2E5A31;'>Interpretative Insight</h3>", unsafe_allow_html=True)
        st.markdown(f"""
        <p style="color: #333333;">
        <b>Why {cluster_info['crop']}?</b><br>
        Your input parameters (blue shape) heavily overlap with the historical success zone of Cluster {cluster_id + 1} (green shape).
        </p>
        """, unsafe_allow_html=True)

        st.button("View Proactive Resource Plan", on_click=lambda: st.session_state.update(step=3),
                  use_container_width=True)

    st.markdown('</div>', unsafe_allow_html=True)


# --- VIEW 3: RESOURCE PLANNER ---
def render_planner_view():
    render_header()
    cluster_id = st.session_state.result_cluster
    crop = MOCK_CLUSTERS[cluster_id]['crop']
    rules = MOCK_RULES[crop]

    st.markdown('<div class="agri-card">', unsafe_allow_html=True)
    st.markdown(f"<h2 style='color: #2E5A31;'>Phase B: Proactive Resource Plan for {crop}</h2>", unsafe_allow_html=True)
    st.markdown(
        "<p style='color: #333333;'>Based on Association Rule Mining (Apriori) of the top 25% highest yielding farms historically found in your cluster.</p>",
        unsafe_allow_html=True)
    st.markdown("---")

    col_rules, col_summary = st.columns([2, 1], gap="large")

    with col_rules:
        st.markdown("<h3 style='color: #2E5A31;'>Recommended Resource Basket</h3>", unsafe_allow_html=True)

        for i, rule in enumerate(rules):
            # Resource Cards -> Navy Blue Background, White Text
            border_color = "#000080"
            bg_color = "#000080"
            text_color = "#FFFFFF"

            with st.container():
                st.markdown(f"""
                    <div style="background-color: {bg_color}; padding: 15px; border-radius: 10px; border-left: 6px solid {border_color}; margin-bottom: 10px;">
                        <h4 style="margin:0; color: {text_color} !important;">{i + 1}. {rule['item']}</h4>
                        <p style="color: {text_color} !important; font-size: 0.9rem; margin-top: 5px;"><em>{rule['desc']}</em></p>
                    </div>
                """, unsafe_allow_html=True)
                c1, c2 = st.columns(2)
                c1.metric("Confidence", rule['conf'])
                c2.metric("Lift Score", f"{rule['lift']}x")
                st.markdown("---")

    with col_summary:
        st.markdown('<div style="background-color: #E8F5E9; padding: 20px; border-radius: 10px;">',
                    unsafe_allow_html=True)
        st.markdown("<h3 style='color: #2E5A31;'>Executive Summary</h3>", unsafe_allow_html=True)
        st.markdown("<h4 style='color: #2E5A31;'>Key Actions</h4>", unsafe_allow_html=True)

        st.markdown(f"""
        <ul style="color: #333333;">
            <li>Secure <b>{rules[0]['item']}</b>.</li>
            <li>Prepare for <b>{rules[1]['item']}</b>.</li>
        </ul>
        """, unsafe_allow_html=True)

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<br>", unsafe_allow_html=True)

        if st.button("View Forecast Tracking", use_container_width=True):
            st.session_state.step = 4
            st.rerun()

        if st.button("Start New Analysis", use_container_width=True):
            reset_app()

    st.markdown('</div>', unsafe_allow_html=True)


# --- VIEW 4: TRACKING ---
def render_tracking_view():
    render_header()

    st.markdown('<div class="agri-card">', unsafe_allow_html=True)
    st.markdown("<h2 style='color: #2E5A31;'>Forecast & Yield Tracking</h2>", unsafe_allow_html=True)
    st.markdown("<p style='color: #2E5A31;'>Monitor your farm's performance against forecasts over time.</p>",
                unsafe_allow_html=True)
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["Monthly", "Quarterly", "Annual"])

    # Common Styling for all Tracking Charts
    def style_chart(fig):
        fig.update_layout(
            paper_bgcolor='white',  # Force White Background (Outside)
            plot_bgcolor='white',  # Force White Background (Inside)
            font=dict(color='black'),  # Force All Text to Black
            xaxis=dict(
                showgrid=True,
                gridcolor='#f0f0f0',
                linecolor='black',
                tickfont=dict(color='black')
            ),
            yaxis=dict(
                showgrid=True,
                gridcolor='#f0f0f0',
                linecolor='black',
                tickfont=dict(color='black')
            ),
            legend=dict(
                font=dict(color='black'),
                bgcolor='rgba(255,255,255,0.5)'
            ),
            margin=dict(l=40, r=40, t=20, b=20)
        )
        return fig

    with tab1:
        st.markdown("<h4 style='color: #2E5A31;'>Monthly Performance</h4>", unsafe_allow_html=True)
        df_monthly = get_tracking_data('Monthly')

        fig_m = go.Figure()
        fig_m.add_trace(go.Scatter(
            x=df_monthly.index, y=df_monthly['Forecasted Yield (kg)'],
            mode='lines+markers', name='Forecast', line=dict(color='#4CAF50', width=3)
        ))
        fig_m.add_trace(go.Scatter(
            x=df_monthly.index, y=df_monthly['Actual Yield (kg)'],
            mode='lines+markers', name='Actual', line=dict(color='#1E88E5', width=3)
        ))
        st.plotly_chart(style_chart(fig_m), use_container_width=True)

    with tab2:
        st.markdown("<h4 style='color: #2E5A31;'>Quarterly Performance</h4>", unsafe_allow_html=True)
        df_quarterly = get_tracking_data('Quarterly')

        fig_q = go.Figure()
        fig_q.add_trace(go.Bar(
            x=df_quarterly.index, y=df_quarterly['Forecasted Yield (kg)'],
            name='Forecast', marker_color='#4CAF50'
        ))
        fig_q.add_trace(go.Bar(
            x=df_quarterly.index, y=df_quarterly['Actual Yield (kg)'],
            name='Actual', marker_color='#1E88E5'
        ))
        fig_q.update_layout(barmode='group')
        st.plotly_chart(style_chart(fig_q), use_container_width=True)

    with tab3:
        st.markdown("<h4 style='color: #2E5A31;'>Annual Performance</h4>", unsafe_allow_html=True)
        df_annual = get_tracking_data('Annual')

        fig_a = go.Figure()
        fig_a.add_trace(go.Bar(
            x=df_annual.index, y=df_annual['Forecasted Yield (kg)'],
            name='Forecast', marker_color='#4CAF50'
        ))
        fig_a.add_trace(go.Bar(
            x=df_annual.index, y=df_annual['Actual Yield (kg)'],
            name='Actual', marker_color='#1E88E5'
        ))
        fig_a.update_layout(barmode='group')
        st.plotly_chart(style_chart(fig_a), use_container_width=True)

    st.markdown("---")
    if st.button("Back to Resource Plan"):
        st.session_state.step = 3
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


# =================MAIN APP ROUTING=================
# Sidebar
st.sidebar.markdown("# Agri-Forecast")
st.sidebar.markdown("### Proactive Crop & Resource Planning")
st.sidebar.info("This tool uses unsupervised machine learning (K-Means Clustering & Apriori Association Mining).")
st.sidebar.markdown("---")
st.sidebar.write(f"**Project Phase:** Step {st.session_state.step} of 4")
progress_map = {1: 25, 2: 50, 3: 75, 4: 100}
st.sidebar.progress(progress_map[st.session_state.step])

# Routing
if st.session_state.step == 1:
    render_profile_view()
elif st.session_state.step == 2:
    render_zone_view()
elif st.session_state.step == 3:
    render_planner_view()
elif st.session_state.step == 4:
    render_tracking_view()