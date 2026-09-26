import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from datetime import datetime

# ============================================================
# --- Page Config ---
# ============================================================
st.set_page_config(
    page_title="Ink Chain - Yields",
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
<h1 style="margin: 0;">Ink Chain — Yields / APY</h1>
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
This page tracks <b>yield-bearing pools</b> (lending, LPs, staking, vaults) live on the
<b>Ink</b> chain — APY breakdown, TVL per pool, and stablecoin/IL-risk classification.
Data is sourced live from the <b>DefiLlama</b> free public yields API.
</div>
""",
    unsafe_allow_html=True
)

st.markdown("")

# ============================================================
# --- Data Fetcher (DefiLlama free API) ---
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_pools(chain: str) -> pd.DataFrame:
    """All yield pools tracked by DefiLlama, filtered to a single chain."""
    url = "https://yields.llama.fi/pools"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    payload = r.json()
    data = payload.get("data", []) or []
    df = pd.DataFrame(data)
    if df.empty:
        return df
    df = df[df["chain"] == chain].copy()
    return df.reset_index(drop=True)


try:
    with st.spinner("Loading yield pool data from DefiLlama..."):
        pools_df = get_pools(CHAIN_NAME)
except Exception as e:
    st.error(f"Failed to fetch data from DefiLlama API: {e}")
    st.stop()

if pools_df.empty:
    st.warning("No yield pool data returned for Ink.")
    st.stop()

# ============================================================
# --- Clean / Prepare Columns ---
# ============================================================
pools_df["project"] = pools_df["project"].fillna("Unknown")
pools_df["symbol"] = pools_df["symbol"].fillna("N/A")
pools_df["tvlUsd"] = pools_df["tvlUsd"].fillna(0)
pools_df["apy"] = pools_df["apy"].fillna(0)
pools_df["apyBase"] = pools_df.get("apyBase", pd.Series(dtype=float)).fillna(0)
pools_df["apyReward"] = pools_df.get("apyReward", pd.Series(dtype=float)).fillna(0)
pools_df["stablecoin"] = pools_df.get("stablecoin", False).fillna(False)
pools_df["ilRisk"] = pools_df.get("ilRisk", "unknown").fillna("unknown")
pools_df["exposure"] = pools_df.get("exposure", "N/A").fillna("N/A")

pools_df = pools_df.sort_values("tvlUsd", ascending=False).reset_index(drop=True)

# ============================================================
# --- KPI Calculations ---
# ============================================================
num_pools = pools_df.shape[0]
total_yield_tvl = pools_df["tvlUsd"].sum()
avg_apy = pools_df["apy"].mean()
max_apy_row = pools_df.loc[pools_df["apy"].idxmax()]
num_stable_pools = int(pools_df["stablecoin"].sum())
num_projects = pools_df["project"].nunique()
no_il_pools = int((pools_df["ilRisk"].str.lower() == "no").sum())


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


def fmt_pct(x):
    return "N/A" if x is None or pd.isna(x) else f"{x:.2f}%"


# ============================================================
# --- KPI Row 1 ---
# ============================================================
st.markdown(f"##### As of {datetime.utcnow().strftime('%Y-%m-%d')}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Active Yield Pools", f"{num_pools}")
c2.metric("Total TVL in Pools", fmt_usd(total_yield_tvl))
c3.metric("Average APY", fmt_pct(avg_apy))
c4.metric("Highest APY", fmt_pct(max_apy_row["apy"]), max_apy_row["project"])

# ============================================================
# --- KPI Row 2 ---
# ============================================================
c5, c6, c7 = st.columns(3)
c5.metric("Stablecoin Pools", f"{num_stable_pools}")
c6.metric("No-IL-Risk Pools", f"{no_il_pools}")
c7.metric("Distinct Protocols", f"{num_projects}")

st.markdown("---")

# ============================================================
# --- Filters ---
# ============================================================
st.subheader("Filters")
f1, f2, f3 = st.columns(3)
with f1:
    stable_only = st.checkbox("Stablecoin pools only", value=False)
with f2:
    no_il_only = st.checkbox("No IL risk only", value=False)
with f3:
    min_tvl = st.number_input("Minimum pool TVL (USD)", min_value=0, value=0, step=1000)

filtered_df = pools_df.copy()
if stable_only:
    filtered_df = filtered_df[filtered_df["stablecoin"] == True]  # noqa: E712
if no_il_only:
    filtered_df = filtered_df[filtered_df["ilRisk"].str.lower() == "no"]
if min_tvl > 0:
    filtered_df = filtered_df[filtered_df["tvlUsd"] >= min_tvl]

st.markdown("---")

# ============================================================
# --- Risk/Return Scatter & Top APY Pools ---
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("TVL vs APY (Risk/Return)")
    if not filtered_df.empty:
        scatter_df = filtered_df.copy()
        scatter_df["label"] = scatter_df["project"] + " · " + scatter_df["symbol"]
        fig_scatter = px.scatter(
            scatter_df, x="tvlUsd", y="apy",
            color="stablecoin", hover_name="label",
            labels={"tvlUsd": "Pool TVL (USD)", "apy": "APY (%)", "stablecoin": "Stablecoin"},
            log_x=True,
            color_discrete_map={True: ACCENT, False: "#F5A623"}
        )
        fig_scatter.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("No pools match the selected filters.")

with col_right:
    st.subheader("Top 10 Pools by APY")
    if not filtered_df.empty:
        top10 = filtered_df.sort_values("apy", ascending=False).head(10).copy()
        top10["label"] = top10["project"] + " · " + top10["symbol"]
        top10 = top10.sort_values("apy")
        fig_top = go.Figure(go.Bar(
            x=top10["apy"], y=top10["label"],
            orientation="h",
            marker_color=ACCENT,
            text=[f"{v:.2f}%" for v in top10["apy"]],
            textposition="outside"
        ))
        fig_top.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="APY (%)",
            yaxis_title=None
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No pools match the selected filters.")

st.markdown("---")

# ============================================================
# --- TVL by Protocol ---
# ============================================================
st.subheader("Yield TVL by Protocol")
if not filtered_df.empty:
    proj_df = filtered_df.groupby("project", as_index=False)["tvlUsd"].sum()
    proj_df = proj_df.sort_values("tvlUsd", ascending=False)
    fig_proj = px.pie(proj_df, names="project", values="tvlUsd", hole=0.5)
    fig_proj.update_traces(textposition="inside", textinfo="percent+label")
    fig_proj.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
    st.plotly_chart(fig_proj, use_container_width=True)
else:
    st.info("No pools match the selected filters.")

st.markdown("---")

# ============================================================
# --- Full Pools Table ---
# ============================================================
st.subheader("Yield Pools on Ink — Full List")

if not filtered_df.empty:
    search = st.text_input("Search project or symbol", "")
    table_df = filtered_df.copy()
    if search:
        mask = (
            table_df["project"].str.contains(search, case=False, na=False) |
            table_df["symbol"].str.contains(search, case=False, na=False)
        )
        table_df = table_df[mask]

    display_df = table_df[[
        "project", "symbol", "tvlUsd", "apyBase", "apyReward", "apy",
        "stablecoin", "ilRisk", "exposure"
    ]].rename(columns={
        "project": "Protocol",
        "symbol": "Pool / Tokens",
        "tvlUsd": "TVL",
        "apyBase": "APY Base (%)",
        "apyReward": "APY Reward (%)",
        "apy": "APY Total (%)",
        "stablecoin": "Stablecoin",
        "ilRisk": "IL Risk",
        "exposure": "Exposure"
    })
    display_df["TVL"] = display_df["TVL"].apply(fmt_usd)
    display_df["APY Base (%)"] = display_df["APY Base (%)"].apply(lambda x: f"{x:.2f}%")
    display_df["APY Reward (%)"] = display_df["APY Reward (%)"].apply(lambda x: f"{x:.2f}%")
    display_df["APY Total (%)"] = display_df["APY Total (%)"].apply(lambda x: f"{x:.2f}%")

    display_df = display_df.sort_values("TVL", ascending=False)
    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption(f"{len(display_df)} pools shown.")
else:
    st.info("No pools match the selected filters.")

# ============================================================
# --- Footer ---
# ============================================================
st.markdown(
    f"""
<div style="margin-top:25px; font-size:13px; color:gray;">
Data source: <a href="https://defillama.com/yields?chain=Ink" target="_blank">DefiLlama</a> (free public API, yields.llama.fi) ·
Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} (cached hourly)
</div>
""",
    unsafe_allow_html=True
)
