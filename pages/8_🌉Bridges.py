import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timedelta

# ============================================================
# --- Page Config ---
# ============================================================
st.set_page_config(
    page_title="Ink Chain - Bridges",
    page_icon="https://explorer.inkonchain.com/assets/configs/network_icon.svg",
    layout="wide"
)

CHAIN_NAME = "Ink"          # exact chain key as used by DefiLlama
ACCENT = "#4A90E2"
BOX_BG = "#E5F2FF"

# ============================================================
# --- Title with Logo ---
# ============================================================
st.markdown(
    """
<div style="display: flex; align-items: center; gap: 15px;">
<img src="https://img.cryptorank.io/coins/ink1729850762329.png" alt="ink" style="width:60px; height:60px;">
<h1 style="margin: 0;">Ink Chain — Bridges & Liquidity Flow</h1>
</div>
""",
    unsafe_allow_html=True
)

st.markdown(
    f"""
<div style="
background-color: {BOX_BG};
border-left: 6px solid {ACCENT};
padding: 15px;
border-radius: 10px;
margin-top: 10px;
color: #1a1a1a;
font-size: 16px;
line-height: 1.6;
">
This page tracks <b>bridge deposit/withdrawal volume</b> into and out of the <b>Ink</b> chain,
the resulting net liquidity flow, and which bridges are active on Ink.
Data is sourced live from the <b>DefiLlama</b> free public bridges API.
</div>
""",
    unsafe_allow_html=True
)

st.markdown("")

# ============================================================
# --- Data Fetchers (DefiLlama free API) ---
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_bridge_volume_history(chain: str) -> pd.DataFrame:
    """Daily aggregated deposit/withdrawal volume for a single chain, across all bridges."""
    url = f"https://bridges.llama.fi/bridgevolume/{chain}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json() or []
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"].astype(int), unit="s")
    df["depositUSD"] = df.get("depositUSD", 0).fillna(0)
    df["withdrawUSD"] = df.get("withdrawUSD", 0).fillna(0)
    df["netFlow"] = df["depositUSD"] - df["withdrawUSD"]
    df = df.sort_values("date").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_bridges_on_chain(chain: str) -> pd.DataFrame:
    """List of bridges connected to a chain, with their (all-chain) volume stats."""
    url = "https://bridges.llama.fi/bridges?includeChains=true"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    bridges = r.json().get("bridges", []) or []

    rows = []
    for b in bridges:
        chains = b.get("chains", []) or []
        if chain in chains:
            rows.append({
                "Bridge": b.get("displayName") or b.get("name"),
                "Chains Connected": len(chains),
                "Volume (24h, all chains)": b.get("lastDailyVolume") or b.get("volumePrevDay") or 0,
                "Weekly Volume (all chains)": b.get("weeklyVolume") or 0,
                "Monthly Volume (all chains)": b.get("monthlyVolume") or 0,
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("Volume (24h, all chains)", ascending=False).reset_index(drop=True)
    return df


try:
    with st.spinner("Loading bridge data from DefiLlama..."):
        flow_df = get_bridge_volume_history(CHAIN_NAME)
        bridges_df = get_bridges_on_chain(CHAIN_NAME)
except Exception as e:
    st.error(f"Failed to fetch data from DefiLlama API: {e}")
    st.stop()

if flow_df.empty and bridges_df.empty:
    st.warning("No bridge data returned for Ink.")
    st.stop()

# ============================================================
# --- KPI Calculations ---
# ============================================================


def fmt_usd(x):
    if x is None:
        return "N/A"
    if abs(x) >= 1e9:
        return f"${x/1e9:,.2f}B"
    if abs(x) >= 1e6:
        return f"${x/1e6:,.2f}M"
    if abs(x) >= 1e3:
        return f"${x/1e3:,.2f}K"
    return f"${x:,.2f}"


last_row = flow_df.iloc[-1] if not flow_df.empty else None
deposit_24h = last_row["depositUSD"] if last_row is not None else 0
withdraw_24h = last_row["withdrawUSD"] if last_row is not None else 0
net_flow_24h = last_row["netFlow"] if last_row is not None else 0

net_flow_7d = flow_df.tail(7)["netFlow"].sum() if not flow_df.empty else 0
net_flow_30d = flow_df.tail(30)["netFlow"].sum() if not flow_df.empty else 0
cumulative_net_flow = flow_df["netFlow"].sum() if not flow_df.empty else 0

num_bridges = bridges_df.shape[0]
top_bridge = bridges_df.iloc[0]["Bridge"] if not bridges_df.empty else "N/A"

# ============================================================
# --- KPI Row 1 ---
# ============================================================
as_of = last_row["date"].strftime("%Y-%m-%d") if last_row is not None else datetime.utcnow().strftime("%Y-%m-%d")
st.markdown(f"##### As of {as_of}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Deposits (24h)", fmt_usd(deposit_24h))
c2.metric("Withdrawals (24h)", fmt_usd(withdraw_24h))
c3.metric("Net Flow (24h)", fmt_usd(net_flow_24h))
c4.metric("Active Bridges", f"{num_bridges}")

# ============================================================
# --- KPI Row 2 ---
# ============================================================
c5, c6, c7 = st.columns(3)
c5.metric("Net Flow (7d)", fmt_usd(net_flow_7d))
c6.metric("Net Flow (30d)", fmt_usd(net_flow_30d))
c7.metric("Cumulative Net Flow (all-time)", fmt_usd(cumulative_net_flow))

st.markdown(
    f"""
<div style="font-size:14px; color:#555; margin-top:-5px;">
Most active bridge (by all-chain volume): <b>{top_bridge}</b>
</div>
""",
    unsafe_allow_html=True
)

st.markdown("---")

# ============================================================
# --- Historical Deposit vs Withdrawal Chart (with range selector) ---
# ============================================================
st.subheader("Daily Deposits vs Withdrawals")

if not flow_df.empty:
    range_map = {"7D": 7, "30D": 30, "90D": 90, "180D": 180, "1Y": 365, "All": None}
    range_choice = st.radio("Range", list(range_map.keys()), horizontal=True, index=5, label_visibility="collapsed")

    days = range_map[range_choice]
    latest_date = flow_df["date"].max()
    plot_df = flow_df if days is None else flow_df[flow_df["date"] >= (latest_date - timedelta(days=days))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=plot_df["date"], y=plot_df["depositUSD"],
        marker_color=ACCENT, name="Deposits"
    ))
    fig.add_trace(go.Bar(
        x=plot_df["date"], y=-plot_df["withdrawUSD"],
        marker_color="#F5A623", name="Withdrawals"
    ))
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="USD (Deposits positive / Withdrawals negative)",
        xaxis_title=None,
        barmode="relative",
        hovermode="x unified",
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No historical bridge volume chart available for Ink.")

st.markdown("---")

# ============================================================
# --- Cumulative Net Flow Chart ---
# ============================================================
st.subheader("Cumulative Net Flow (Deposits − Withdrawals)")

if not flow_df.empty:
    cum_df = flow_df.copy()
    cum_df["cumulativeNetFlow"] = cum_df["netFlow"].cumsum()
    fig_cum = go.Figure()
    fig_cum.add_trace(go.Scatter(
        x=cum_df["date"], y=cum_df["cumulativeNetFlow"],
        mode="lines", fill="tozeroy",
        line=dict(color=ACCENT, width=2),
        fillcolor="rgba(74,144,226,0.15)",
        name="Cumulative Net Flow"
    ))
    fig_cum.update_layout(
        height=380,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Cumulative USD",
        xaxis_title=None,
        hovermode="x unified",
        plot_bgcolor="white"
    )
    st.plotly_chart(fig_cum, use_container_width=True)
else:
    st.info("No historical bridge volume chart available for Ink.")

st.markdown("---")

# ============================================================
# --- Bridges Table ---
# ============================================================
st.subheader("Bridges Connected to Ink")

if not bridges_df.empty:
    display_df = bridges_df.copy()
    for col in ["Volume (24h, all chains)", "Weekly Volume (all chains)", "Monthly Volume (all chains)"]:
        display_df[col] = display_df[col].apply(fmt_usd)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption(
        f"{len(display_df)} bridges shown. Volume figures are each bridge's total across all chains "
        "it services, not Ink-specific — DefiLlama does not expose a fully per-bridge, per-chain "
        "volume split via the free API. The chain-level deposit/withdrawal chart above is Ink-specific."
    )
else:
    st.info("No bridge data available for Ink at this time.")

# ============================================================
# --- Footer ---
# ============================================================
st.markdown(
    f"""
<div style="margin-top:25px; font-size:13px; color:gray;">
Data source: <a href="https://defillama.com/bridges" target="_blank">DefiLlama</a> (free public API, bridges.llama.fi) ·
Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} (cached hourly)
</div>
""",
    unsafe_allow_html=True
)
