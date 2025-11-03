import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Page Config ------------------------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Inkonchain Dashboard",
    page_icon="https://explorer.inkonchain.com/favicon.ico",
    layout="wide"
)

# --- Title ------------------------------------------------------------------------------------------------------------
st.title("📊 Inkonchain Network Stats")

st.info("📊Charts initially display data for the past 30 days. Select or hover for detailed values.")
st.info("⏳On-chain data retrieval may take a few moments. Please wait while results load.")

# --- Fetch Data -------------------------------------------------------------------------------------------------------
api_url = "https://explorer.inkonchain.com/stats-service/api/v1/pages/main"

try:
    response = requests.get(api_url)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    st.error(f"⚠️ Failed to fetch data from API: {e}")
    st.stop()

# --- Extract Key Data -------------------------------------------------------------------------------------------------
average_block_time = data.get("average_block_time", {}).get("value", "N/A")
total_addresses = data.get("total_addresses", {}).get("value", "N/A")
total_blocks = data.get("total_blocks", {}).get("value", "N/A")
total_transactions = data.get("total_transactions", {}).get("value", "N/A")
yesterday_transactions = data.get("yesterday_transactions", {}).get("value", "N/A")

# --- Custom KPI Card Style --------------------------------------------------------------------------------------------
kpi_style = """
<style>
.kpi-card {
    background-color: #ffffff;
    border-radius: 15px;
    padding: 20px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    text-align: center;
    transition: all 0.3s ease;
}
.kpi-card:hover {
    box-shadow: 0 6px 16px rgba(0,0,0,0.15);
    transform: translateY(-3px);
}
.kpi-title {
    font-size: 16px;
    font-weight: 600;
    color: #444444;
}
.kpi-value {
    font-size: 28px;
    font-weight: 800;
    color: #7132f5;
    margin-top: 10px;
}
.kpi-desc {
    font-size: 12px;
    color: #777777;
    margin-top: 4px;
}
</style>
"""
st.markdown(kpi_style, unsafe_allow_html=True)

# --- KPI Layout -------------------------------------------------------------------------------------------------------
st.markdown("---")
st.subheader("📈 Network Overview")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Average Block Time</div>
        <div class="kpi-value">{average_block_time} s</div>
        <div class="kpi-desc">Average time per block</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Total Addresses</div>
        <div class="kpi-value">{int(total_addresses):,}</div>
        <div class="kpi-desc">Addresses that participated</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Total Blocks</div>
        <div class="kpi-value">{int(total_blocks):,}</div>
        <div class="kpi-desc">All blocks produced</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Total Transactions</div>
        <div class="kpi-value">{int(total_transactions):,}</div>
        <div class="kpi-desc">Total number of transactions</div>
    </div>
    """, unsafe_allow_html=True)

with col5:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Yesterday Transactions</div>
        <div class="kpi-value">{int(yesterday_transactions):,}</div>
        <div class="kpi-desc">Transactions (last 24h)</div>
    </div>
    """, unsafe_allow_html=True)

# --- Daily Transactions Chart -----------------------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 Daily Transactions (Last 30 Days)")

chart_data = data.get("daily_new_transactions", {}).get("chart", [])
if chart_data:
    df = pd.DataFrame(chart_data)
    df["date"] = pd.to_datetime(df["date"])
    df["value"] = df["value"].astype(int)

    fig = px.bar(
        df,
        x="date",
        y="value",
        title="Daily Transactions (30 Days)",
        labels={"date": "Date", "value": "Transactions"},
        template="plotly_white",
    )
    fig.update_traces(marker_color="#7132f5", hovertemplate="Date: %{x}<br>Txns: %{y:,}")
    fig.update_layout(
        title_x=0.5,
        title_font=dict(size=18, color="#444"),
        yaxis_title=None,
        xaxis_title=None,
        margin=dict(l=20, r=20, t=60, b=40),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No daily transaction data available.")
