import streamlit as st
import pandas as pd
import requests
import snowflake.connector
import plotly.express as px
import plotly.graph_objects as go
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.backends import default_backend
import networkx as nx

# --- Page Config ------------------------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Ink Chain",
    page_icon="https://explorer.inkonchain.com/assets/configs/network_icon.svg",
    layout="wide"
)

# --- Title -----------------------------------------------------------------------------------------------------
st.title("📑 Smart Contracts")

# --- Sidebar Footer Slightly Left-Aligned ---------------------------------------------------------------------
st.sidebar.markdown(
    """
    <style>
    .sidebar-footer {
        position: fixed;
        bottom: 20px;
        width: 250px;
        font-size: 13px;
        color: gray;
        margin-left: 5px; 
        text-align: left;  
    }
    .sidebar-footer img {
        width: 16px;
        height: 16px;
        vertical-align: middle;
        border-radius: 50%;
        margin-right: 5px;
    }
    .sidebar-footer a {
        color: gray;
        text-decoration: none;
    }
    </style>

    <div class="sidebar-footer">
        <div>
            <a href="https://x.com/inkonchain" target="_blank">
                <img src="https://explorer.inkonchain.com/assets/configs/network_icon.svg" alt="Ink Logo">
                Powered by Ink
            </a>
        </div>
        <div style="margin-top: 5px;">
            <a href="https://x.com/0xeman_raz" target="_blank">
                <img src="https://pbs.twimg.com/profile_images/1841479747332608000/bindDGZQ_400x400.jpg" alt="Eman Raz">
                Built by Eman Raz
            </a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Snowflake Connection ----------------------------------------------------------------------------------------
snowflake_secrets = st.secrets["snowflake"]
user = snowflake_secrets["user"]
account = snowflake_secrets["account"]
private_key_str = snowflake_secrets["private_key"]
warehouse = snowflake_secrets.get("warehouse", "")
database = snowflake_secrets.get("database", "")
schema = snowflake_secrets.get("schema", "")

private_key_pem = f"-----BEGIN PRIVATE KEY-----\n{private_key_str}\n-----END PRIVATE KEY-----".encode("utf-8")
private_key = serialization.load_pem_private_key(
    private_key_pem,
    password=None,
    backend=default_backend()
)
private_key_bytes = private_key.private_bytes(
    encoding=serialization.Encoding.DER,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption()
)

conn = snowflake.connector.connect(
    user=user,
    account=account,
    private_key=private_key_bytes,
    warehouse=warehouse,
    database=database,
    schema=schema
)

# --- Contracts KPIs Section ------------------------------------------------------------------------------------------
st.markdown("---")

# API Endpoint
api_url = "https://explorer.inkonchain.com/stats-service/api/v1/pages/contracts"

# Fetch Data
try:
    response = requests.get(api_url)
    response.raise_for_status()
    data = response.json()
except Exception as e:
    st.error(f"⚠️ Failed to fetch data from API: {e}")
    st.stop()

# Extract Data
total_contracts = data.get("total_contracts", {}).get("value", "N/A")
new_contracts_24h = data.get("new_contracts_24h", {}).get("value", "N/A")
total_verified_contracts = data.get("total_verified_contracts", {}).get("value", "N/A")
new_verified_contracts_24h = data.get("new_verified_contracts_24h", {}).get("value", "N/A")

# --- Custom KPI Card Style -------------------------------------------------------------------------------------------
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

# --- KPI Layout (4 columns) ------------------------------------------------------------------------------------------
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Total Contracts</div>
        <div class="kpi-value">{int(total_contracts):,}</div>
        <div class="kpi-desc">Number of all deployed contracts</div>
    </div>
    """, unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Contracts (24h)</div>
        <div class="kpi-value">{int(new_contracts_24h):,}</div>
        <div class="kpi-desc">New contracts deployed in last 24h</div>
    </div>
    """, unsafe_allow_html=True)

with col3:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Verified Contracts</div>
        <div class="kpi-value">{int(total_verified_contracts):,}</div>
        <div class="kpi-desc">Number of all verified contracts</div>
    </div>
    """, unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="kpi-card">
        <div class="kpi-title">Verified (24h)</div>
        <div class="kpi-value">{int(new_verified_contracts_24h):,}</div>
        <div class="kpi-desc">Contracts verified in last 24h</div>
    </div>
    """, unsafe_allow_html=True)

# -------------------------------------------------------------------------------------------------------
# --- Dune API Section ----------------------------------------------------------------------------------
st.markdown("---")
st.subheader("💻 Contracts Analysis")

dune_api_url = "https://api.dune.com/api/v1/query/6178301/results?api_key=kmCBMTxWKBxn6CVgCXhwDvcFL1fBp6rO"

try:
    dune_response = requests.get(dune_api_url)
    dune_response.raise_for_status()
    dune_data = dune_response.json()
    rows = dune_data["result"]["rows"]
    df = pd.DataFrame(rows)
except Exception as e:
    st.error(f"⚠️ Failed to fetch Dune data: {e}")
    st.stop()

# Clean and Prepare Data
df["Date"] = pd.to_datetime(df["Date"])
numeric_cols = ["Existing Contracts", "New Contract", "Total Contracts", "Transaction per Contract", "User per Contract", "New Contracts Ratio"]
for col in numeric_cols:
    df[col] = pd.to_numeric(df[col], errors="coerce")

df = df.sort_values("Date")

# --- Row 1: Contracts Over Time + Tx/User per Contract -------------------------------------------------------------
col1, col2 = st.columns(2)

# Chart 1: Stacked Bar + Line (Contracts)
with col1:
    fig1 = go.Figure()

    # Stacked Bars
    fig1.add_trace(go.Bar(
        x=df["Date"], y=df["Existing Contracts"], name="Existing Contracts", marker_color="#9b9bff"
    ))
    fig1.add_trace(go.Bar(
        x=df["Date"], y=df["New Contract"], name="New Contracts", marker_color="#7132f5"
    ))

    # Total Contracts Line
    fig1.add_trace(go.Scatter(
        x=df["Date"], y=df["Total Contracts"], name="Total Contracts", mode="lines",
        line=dict(color="#222", width=2)
    ))

    fig1.update_layout(
        barmode="stack",
        title="Number of Contracts Over Time",
        xaxis_title="Date",
        yaxis_title="Count",
        legend_title="Legend",
        template="plotly_white"
    )
    st.plotly_chart(fig1, use_container_width=True)

# Chart 2: Line Chart (Tx/User per Contract)
with col2:
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=df["Date"], y=df["Transaction per Contract"], name="Transaction per Contract",
        mode="lines", line=dict(width=2)
    ))
    fig2.add_trace(go.Scatter(
        x=df["Date"], y=df["User per Contract"], name="User per Contract",
        mode="lines", line=dict(width=2, dash="dot")
    ))

    fig2.update_layout(
        title="Transactions and Users per Contract Over Time",
        xaxis_title="Date",
        yaxis_title="Value",
        legend_title="Metric",
        template="plotly_white"
    )
    st.plotly_chart(fig2, use_container_width=True)

# --- Row 2: Normalized + New Contracts Ratio ------------------------------------------------------------------------
col3, col4 = st.columns(2)

# Chart 3: Normalized Stacked Bar (without Total Contracts)
with col3:
    norm_df = df.copy()
    norm_df["Existing Contracts"] = norm_df["Existing Contracts"].fillna(0)
    norm_df["New Contract"] = norm_df["New Contract"].fillna(0)
    norm_df["Total"] = norm_df["Existing Contracts"] + norm_df["New Contract"]
    norm_df["Existing (%)"] = norm_df["Existing Contracts"] / norm_df["Total"]
    norm_df["New (%)"] = norm_df["New Contract"] / norm_df["Total"]

    fig3 = go.Figure()
    fig3.add_trace(go.Bar(
        x=norm_df["Date"], y=norm_df["Existing (%)"], name="Existing Contracts (%)"
    ))
    fig3.add_trace(go.Bar(
        x=norm_df["Date"], y=norm_df["New (%)"], name="New Contracts (%)"
    ))

    fig3.update_layout(
        barmode="stack",
        title="Normalized Contracts Over Time",
        xaxis_title="Date",
        yaxis_title="Percentage",
        legend_title="Type",
        template="plotly_white"
    )
    st.plotly_chart(fig3, use_container_width=True)

# Chart 4: New Contracts Ratio Over Time
with col4:
    fig4 = px.line(
        df, x="Date", y="New Contracts Ratio", title="New Contracts Ratio Over Time"
    )
    fig4.update_traces(mode="lines")
    fig4.update_layout(template="plotly_white")
    st.plotly_chart(fig4, use_container_width=True)
