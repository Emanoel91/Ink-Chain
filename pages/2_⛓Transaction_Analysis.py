# inkonchain_main_with_transactions.py
import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime
from typing import Optional

# --- Page Config ------------------------------------------------------------------------------------------------------
st.set_page_config(
    page_title="Inkonchain Dashboard",
    page_icon="https://explorer.inkonchain.com/favicon.ico",
    layout="wide"
)

# --- Title & Info ----------------------------------------------------------------------------------------------------
st.title("📊 Inkonchain Stats")

# --- Sidebar Footer Slightly Left-Aligned (same style as before) ----------------------------------------------------
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

# --- API endpoints ---------------------------------------------------------------------------------------------------
API_MAIN = "https://explorer.inkonchain.com/stats-service/api/v1/pages/main"
API_TRANSACTIONS = "https://explorer.inkonchain.com/stats-service/api/v1/pages/transactions"

# --- Fetch Data helper -----------------------------------------------------------------------------------------------
def fetch_json(url: str) -> Optional[dict]:
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.error(f"⚠️ Failed to fetch {url}: {e}")
        return None

# Fetch both APIs
data_main = fetch_json(API_MAIN)
data_tx = fetch_json(API_TRANSACTIONS)

if data_main is None:
    st.stop()

# --- Extract Key Data from main API ----------------------------------------------------------------------------------
average_block_time = data_main.get("average_block_time", {}).get("value", "N/A")
total_addresses = data_main.get("total_addresses", {}).get("value", "N/A")
total_blocks = data_main.get("total_blocks", {}).get("value", "N/A")
total_transactions = data_main.get("total_transactions", {}).get("value", "N/A")
yesterday_transactions = data_main.get("yesterday_transactions", {}).get("value", "N/A")

# Extract daily chart data (assume there is at least some data)
daily_chart = data_main.get("daily_new_transactions", {}).get("chart", []) or []

# Build DataFrame for the chart (guard against missing/invalid)
if daily_chart:
    df_daily = pd.DataFrame(daily_chart)
    # parse date column might be 'date' or similar; ensure conversion
    if "date" in df_daily.columns:
        df_daily["date"] = pd.to_datetime(df_daily["date"])
    elif "date_from" in df_daily.columns:
        df_daily["date"] = pd.to_datetime(df_daily["date_from"])
    else:
        # fallback: try first column as date
        df_daily["date"] = pd.to_datetime(df_daily.iloc[:, 0])
    # value -> int
    if "value" in df_daily.columns:
        df_daily["value"] = df_daily["value"].astype(int)
    else:
        df_daily["value"] = pd.to_numeric(df_daily.iloc[:, 1], errors="coerce").fillna(0).astype(int)

    # ensure sorted by date
    df_daily = df_daily.sort_values("date").reset_index(drop=True)
    # if more than 30 rows, take last 30
    if len(df_daily) > 30:
        df_daily = df_daily.iloc[-30:].reset_index(drop=True)
else:
    df_daily = pd.DataFrame(columns=["date", "value"])

# --- Extract Key Data from transactions API --------------------------------------------------------------------------
# data_tx could be None if failed; handle gracefully
txn_fee_24h_raw = None
avg_txn_fee_24h_raw = None
transactions_24h = None
pending_txns_30m = None

if data_tx:
    txn_fee_24h_raw = data_tx.get("transactions_fee_24h", {}).get("value")
    avg_txn_fee_24h_raw = data_tx.get("average_transactions_fee_24h", {}).get("value")
    transactions_24h = data_tx.get("transactions_24h", {}).get("value")
    pending_txns_30m = data_tx.get("pending_transactions_30m", {}).get("value")

# --- Utility formatting functions ------------------------------------------------------------------------------------
def fmt_int(x):
    try:
        return f"{int(x):,}"
    except Exception:
        return x

def fmt_float_fixed(x, decimals):
    try:
        return format(float(x), f".{decimals}f")
    except Exception:
        return x

def pct_change(new, old):
    try:
        new_f = float(new)
        old_f = float(old)
        if old_f == 0:
            return None
        return (new_f - old_f) / old_f * 100.0
    except Exception:
        return None

# --- Compute derived KPIs from df_daily --------------------------------------------------------------------------------
# Defaults
max_tx_value = None
max_tx_date = None
min_tx_value = None
min_tx_date = None
mean_tx_30 = None
pct_1d = None
pct_7d = None

if not df_daily.empty:
    max_row = df_daily.loc[df_daily["value"].idxmax()]
    min_row = df_daily.loc[df_daily["value"].idxmin()]
    max_tx_value = int(max_row["value"])
    max_tx_date = pd.to_datetime(max_row["date"]).date().isoformat()
    min_tx_value = int(min_row["value"])
    min_tx_date = pd.to_datetime(min_row["date"]).date().isoformat()
    mean_tx_30 = df_daily["value"].mean()

    # percent change 1 day: compare last day vs previous day
    if len(df_daily) >= 2:
        last = df_daily["value"].iloc[-1]
        prev1 = df_daily["value"].iloc[-2]
        pct_1d = pct_change(last, prev1)
    else:
        pct_1d = None

    # percent change 7 day: compare last day vs 7-days-ago (if available)
    if len(df_daily) >= 8:
        last = df_daily["value"].iloc[-1]
        prev7 = df_daily["value"].iloc[-8]
        pct_7d = pct_change(last, prev7)
    else:
        pct_7d = None

# --- KPI Card CSS (same as before, values color #7132f5) ---------------------------------------------------------------
kpi_style = """
<style>
.kpi-card {
    background-color: #ffffff;
    border-radius: 15px;
    padding: 18px 16px;
    box-shadow: 0 4px 10px rgba(0,0,0,0.05);
    text-align: center;
    transition: all 0.22s ease;
    min-height: 94px;
}
.kpi-card:hover {
    box-shadow: 0 6px 16px rgba(0,0,0,0.12);
    transform: translateY(-3px);
}
.kpi-title {
    font-size: 14px;
    font-weight: 600;
    color: #444444;
}
.kpi-value {
    font-size: 26px;
    font-weight: 800;
    color: #7132f5;
    margin-top: 8px;
}
.kpi-desc {
    font-size: 12px;
    color: #777777;
    margin-top: 6px;
}
.kpi-small {
    font-size: 13px;
    color: #555555;
}
</style>
"""
st.markdown(kpi_style, unsafe_allow_html=True)

# --- Build KPI Grid (12 KPIs in 4 rows x 3 columns) -------------------------------------------------------------------
st.markdown("---")
st.subheader("📈 Network & Transaction KPIs")

# Prepare KPI content list in order (12 items)
# 1-5: from main API (as before)
# 6-7: from transactions API (two requested)
# 8-12: derived from 30-day chart (max, min, mean, pct 1d, pct 7d)

kpis = [
    {
        "title": "Average Block Time",
        "value": f"{average_block_time} s",
        "desc": "Average time per block"
    },
    {
        "title": "Total Addresses",
        "value": fmt_int(total_addresses),
        "desc": "Addresses that participated"
    },
    {
        "title": "Total Blocks",
        "value": fmt_int(total_blocks),
        "desc": "All blocks produced"
    },
    {
        "title": "Total Transactions",
        "value": fmt_int(total_transactions),
        "desc": "Total number of transactions (all-time)"
    },
    {
        "title": "Yesterday Transactions",
        "value": fmt_int(yesterday_transactions),
        "desc": "Transactions (last 24h)"
    },
    # Transactions API KPIs (formatting as requested)
    {
        "title": "Transactions fees (24h)",
        "value": fmt_float_fixed(txn_fee_24h_raw if txn_fee_24h_raw is not None else "N/A", 4) + (f" ETH" if txn_fee_24h_raw is not None else ""),
        "desc": "Sum of ETH spent on gas fees (24h)"
    },
    {
        "title": "Avg. transaction fee (24h)",
        "value": fmt_float_fixed(avg_txn_fee_24h_raw if avg_txn_fee_24h_raw is not None else "N/A", 10) + (f" ETH" if avg_txn_fee_24h_raw is not None else ""),
        "desc": "Average gas fee per txn (24h)"
    },
    # Derived KPIs from 30-day chart
    {
        "title": "Max daily txns (30d)",
        "value": fmt_int(max_tx_value) if max_tx_value is not None else "N/A",
        "desc": f"Date: {max_tx_date}" if max_tx_date else "—"
    },
    {
        "title": "Min daily txns (30d)",
        "value": fmt_int(min_tx_value) if min_tx_value is not None else "N/A",
        "desc": f"Date: {min_tx_date}" if min_tx_date else "—"
    },
    {
        "title": "Average daily txns",
        "value": fmt_int(round(mean_tx_30)) if mean_tx_30 is not None else "N/A",
        "desc": f"Mean over last {len(df_daily)} days" if len(df_daily) > 0 else "—"
    },
    {
        "title": "Change vs 1d",
        "value": (f"{pct_1d:+.2f}%" if pct_1d is not None else "N/A"),
        "desc": "Percent change vs previous day"
    },
    {
        "title": "Change vs 7d",
        "value": (f"{pct_7d:+.2f}%" if pct_7d is not None else "N/A"),
        "desc": "Percent change vs 7 days ago"
    },
]

# Render as 4 rows of 3 columns
idx = 0
rows = 4
cols_per_row = 3
for r in range(rows):
    cols = st.columns(cols_per_row)
    for c in range(cols_per_row):
        if idx >= len(kpis):
            break
        k = kpis[idx]
        with cols[c]:
            st.markdown(
                f"""
                <div class="kpi-card">
                    <div class="kpi-title">{k['title']}</div>
                    <div class="kpi-value">{k['value']}</div>
                    <div class="kpi-desc">{k['desc']}</div>
                </div>
                """,
                unsafe_allow_html=True
            )
        idx += 1

# --- Daily Transactions Chart (30 days) --------------------------------------------------------------------------------
st.markdown("---")
st.subheader("📊 Daily Transactions (Last 30 Days)")

if not df_daily.empty:
    fig = px.bar(
        df_daily,
        x="date",
        y="value",
        labels={"date": "Date", "value": "Transactions"},
        title="Daily Transactions (last 30 days)",
        template="plotly_white"
    )
    # apply purple color and hover formatting
    fig.update_traces(marker_color="#7132f5", hovertemplate="Date: %{x|%Y-%m-%d}<br>Txns: %{y:,}")
    fig.update_layout(
        title_x=0.5,
        margin=dict(l=20, r=20, t=60, b=40),
        xaxis=dict(tickformat="%b %d"),
        yaxis=dict(tickformat=",")
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning("No daily transaction data available to draw chart.")

# --- Optional: Show raw JSON (collapsed) for debugging ----------------------------------------------------------------
with st.expander("🔎 Raw API responses (for debugging)", expanded=False):
    st.write("Main API JSON:")
    st.json(data_main)
    st.write("Transactions API JSON:")
    st.json(data_tx)
