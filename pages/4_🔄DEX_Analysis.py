import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
from datetime import datetime, timedelta

# ============================================================
# --- Page Config ---
# ============================================================
st.set_page_config(
    page_title="Ink Chain - DEX Volume",
    page_icon="https://explorer.inkonchain.com/assets/configs/network_icon.svg",
    layout="wide"
)

CHAIN_NAME = "Ink"          # exact chain key as used by DefiLlama
ACCENT = "#4A90E2"
BOX_BG = "#E5F2FF"

# --- Sidebar Footer Slightly Left-Aligned ---
st.sidebar.markdown(
    """
    <style>
    .sidebar-footer {
        position: fixed;
        bottom: 20px;
        width: 250px;
        font-size: 13px;
        color: gray;
        margin-left: 5px; /* Move slightly left */
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
                <img src="https://img.cryptorank.io/coins/ink1729850762329.png" alt="Ink Logo">
                Powered by Ink
            </a>
        </div>
        <div style="margin-top: 5px;">
            <a href="https://x.com/0xeman_raz" target="_blank">
                <img src="https://pbs.twimg.com/profile_images/2060406047391559681/sA9zPNKM_400x400.jpg" alt="Eman Raz">
                Built by Eman Raz
            </a>
        </div>
    </div>
    """,
    unsafe_allow_html=True
)

# ============================================================
# --- Title with Logo ---
# ============================================================
st.markdown(
    """
<div style="display: flex; align-items: center; gap: 15px;">
<img src="https://img.cryptorank.io/coins/ink1729850762329.png" alt="ink" style="width:60px; height:60px;">
<h1 style="margin: 0;">Ink Chain — DEX Volume</h1>
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
This page tracks <b>spot DEX trading volume</b> on the <b>Ink</b> chain — daily swap activity,
protocol-level rankings, and market share across all decentralized exchanges live on Ink.
Data is sourced live from the <b>DefiLlama</b> free public API.
</div>
""",
    unsafe_allow_html=True
)

st.markdown("")

# ============================================================
# --- Data Fetcher (DefiLlama free API) ---
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_dex_overview(chain: str) -> dict:
    """DEX volume overview for a single chain: totals, daily chart, per-protocol breakdown."""
    url = (
        f"https://api.llama.fi/overview/dexs/{chain}"
        "?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType=dailyVolume"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


try:
    with st.spinner("Loading DEX volume data from DefiLlama..."):
        data = get_dex_overview(CHAIN_NAME)
except Exception as e:
    st.error(f"Failed to fetch data from DefiLlama API: {e}")
    st.stop()

protocols = data.get("protocols", []) or []
chart_raw = data.get("totalDataChart", []) or []

if not chart_raw and not protocols:
    st.warning("No DEX volume data returned for Ink.")
    st.stop()

# ============================================================
# --- Build DataFrames ---
# ============================================================
chart_df = pd.DataFrame(chart_raw, columns=["timestamp", "volume"])
if not chart_df.empty:
    chart_df["date"] = pd.to_datetime(chart_df["timestamp"], unit="s")
    chart_df = chart_df.sort_values("date").reset_index(drop=True)

rows = []
for p in protocols:
    rows.append({
        "Protocol": p.get("displayName") or p.get("name"),
        "Category": p.get("category") or "Dexs",
        "Volume 24h": p.get("total24h") or 0,
        "Volume 7d": p.get("total7d") or 0,
        "Volume 30d": p.get("total30d") or 0,
        "Change 1d (%)": p.get("change_1d"),
        "Change 7d (%)": p.get("change_7d"),
        "Change 1m (%)": p.get("change_1m"),
        "Chains": len(p.get("chains", []) or []),
        "Logo": p.get("logo"),
    })
protocols_df = pd.DataFrame(rows)
if not protocols_df.empty:
    protocols_df = protocols_df.sort_values("Volume 24h", ascending=False).reset_index(drop=True)

# ============================================================
# --- KPI Calculations ---
# ============================================================
total_24h = data.get("total24h") or 0
total_7d = data.get("total7d") or 0
total_30d = data.get("total30d") or 0
change_1d = data.get("change_1d")
change_7d = data.get("change_7d")
change_1m = data.get("change_1m")

num_dexs = protocols_df.shape[0]
top_dex = protocols_df.iloc[0]["Protocol"] if not protocols_df.empty else "N/A"
top_dex_vol = protocols_df.iloc[0]["Volume 24h"] if not protocols_df.empty else 0
top_dex_share = (top_dex_vol / total_24h * 100) if total_24h else None

daily_avg_30d = (total_30d / 30) if total_30d else None


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
    return "N/A" if x is None else f"{x:+.2f}%"


# ============================================================
# --- KPI Row 1 ---
# ============================================================
last_date = chart_df.iloc[-1]["date"] if not chart_df.empty else datetime.utcnow()
st.markdown(f"##### As of {last_date.strftime('%Y-%m-%d')}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("DEX Volume (24h)", fmt_usd(total_24h), fmt_pct(change_1d))
c2.metric("DEX Volume (7d)", fmt_usd(total_7d), fmt_pct(change_7d))
c3.metric("DEX Volume (30d)", fmt_usd(total_30d), fmt_pct(change_1m))
c4.metric("Active DEXs", f"{num_dexs}")

# ============================================================
# --- KPI Row 2 ---
# ============================================================
c5, c6, c7 = st.columns(3)
c5.metric("Avg Daily Volume (30d)", fmt_usd(daily_avg_30d))
c6.metric("Top DEX", top_dex)
c7.metric("Top DEX Share (24h)", fmt_pct(top_dex_share))

st.markdown("---")

# ============================================================
# --- Historical Daily Volume Chart (with range selector) ---
# ============================================================
st.subheader("Daily DEX Volume")

if not chart_df.empty:
    range_map = {"7D": 7, "30D": 30, "90D": 90, "180D": 180, "1Y": 365, "All": None}
    range_choice = st.radio("Range", list(range_map.keys()), horizontal=True, index=5, label_visibility="collapsed")

    days = range_map[range_choice]
    plot_df = chart_df if days is None else chart_df[chart_df["date"] >= (last_date - timedelta(days=days))]

    fig_vol = go.Figure()
    fig_vol.add_trace(go.Bar(
        x=plot_df["date"], y=plot_df["volume"],
        marker_color=ACCENT,
        name="Volume"
    ))
    fig_vol.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Volume (USD)",
        xaxis_title=None,
        hovermode="x unified",
        plot_bgcolor="white"
    )
    st.plotly_chart(fig_vol, use_container_width=True)
else:
    st.info("No historical daily volume chart available for Ink.")

st.markdown("---")

# ============================================================
# --- Market Share & Top Protocols ---
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Market Share (7d Volume)")
    if not protocols_df.empty:
        share_df = protocols_df[protocols_df["Volume 7d"] > 0][["Protocol", "Volume 7d"]]
        if not share_df.empty:
            fig_share = px.pie(share_df, names="Protocol", values="Volume 7d", hole=0.5)
            fig_share.update_traces(textposition="inside", textinfo="percent+label")
            fig_share.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
            st.plotly_chart(fig_share, use_container_width=True)
        else:
            st.info("No 7d volume data to compute market share.")
    else:
        st.info("No protocol-level data available.")

with col_right:
    st.subheader("Top 10 DEXs by 24h Volume")
    if not protocols_df.empty:
        top10 = protocols_df.head(10).sort_values("Volume 24h")
        fig_top = go.Figure(go.Bar(
            x=top10["Volume 24h"], y=top10["Protocol"],
            orientation="h",
            marker_color=ACCENT,
            text=[fmt_usd(v) for v in top10["Volume 24h"]],
            textposition="outside"
        ))
        fig_top.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Volume 24h (USD)",
            yaxis_title=None
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No protocol-level data available.")

st.markdown("---")

# ============================================================
# --- Full DEX Table ---
# ============================================================
st.subheader("DEX Protocols on Ink — Full List")

if not protocols_df.empty:
    search = st.text_input("Search protocol", "")
    table_df = protocols_df.copy()
    if search:
        table_df = table_df[table_df["Protocol"].str.contains(search, case=False, na=False)]

    display_df = table_df[[
        "Protocol", "Category", "Volume 24h", "Volume 7d", "Volume 30d",
        "Change 1d (%)", "Change 7d (%)", "Chains"
    ]].copy()
    display_df["Volume 24h"] = display_df["Volume 24h"].apply(fmt_usd)
    display_df["Volume 7d"] = display_df["Volume 7d"].apply(fmt_usd)
    display_df["Volume 30d"] = display_df["Volume 30d"].apply(fmt_usd)
    display_df["Change 1d (%)"] = display_df["Change 1d (%)"].apply(
        lambda x: f"{x:+.2f}%" if pd.notnull(x) else "N/A"
    )
    display_df["Change 7d (%)"] = display_df["Change 7d (%)"].apply(
        lambda x: f"{x:+.2f}%" if pd.notnull(x) else "N/A"
    )

    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption(f"{len(display_df)} DEX protocols shown.")
else:
    st.info("No protocol-level data available for Ink at this time.")

# ============================================================
# --- Footer ---
# ============================================================
st.markdown(
    f"""
<div style="margin-top:25px; font-size:13px; color:gray;">
Data source: <a href="https://defillama.com/dexs/chain/ink" target="_blank">DefiLlama</a> (free public API, api.llama.fi) ·
Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} (cached hourly)
</div>
""",
    unsafe_allow_html=True
)
