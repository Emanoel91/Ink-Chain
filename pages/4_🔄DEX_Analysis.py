import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
import requests
import re
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
ACCENT = "#7132f5"
LINE_COLOR = "#f59e0b"      # cumulative (Total Volume) line
POS_COLOR = "#16a34a"       # green for positive change
NEG_COLOR = "#dc2626"       # red for negative change
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
This page tracks <b>spot DEX trading volume</b> on the <b>Ink</b> chain — swap activity over
time, protocol-level rankings, and market share across all decentralized exchanges live on
Ink. Different versions of the same exchange (e.g. Uniswap V3 / V4) are combined into one
entry.
</div>
""",
    unsafe_allow_html=True
)

st.markdown("")
st.markdown(
    """
    <!-- Support / Tips Box -->
    <div style="
        background-color: #F5F5F5;
        border-left: 5px solid #888;
        padding: 12px;
        border-radius: 10px;
        margin-top: 10px;
        font-size: 15px;
        color: #333;
    ">
        🎁 <b>Support / Tips:</b><br>
        <code>0x621bd661e3d57da1c8237209824827f1027abf62</code>
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
# --- Build Daily Volume Chart DataFrame ---
# ============================================================
chart_df = pd.DataFrame(chart_raw, columns=["timestamp", "volume"])
if not chart_df.empty:
    chart_df["date"] = pd.to_datetime(chart_df["timestamp"], unit="s")
    chart_df = chart_df.sort_values("date").reset_index(drop=True)


def base_dex_name(name: str) -> str:
    """Strip a trailing version tag (V2, V3, v4.1, (V3) ...) so different versions of the
    same exchange (e.g. 'Uniswap V3' and 'Uniswap V4') collapse into one entry ('Uniswap')."""
    if not name:
        return name
    cleaned = re.sub(r"\s*\(?[Vv]\d+(\.\d+)?\)?\s*$", "", name).strip()
    return cleaned if cleaned else name


# ============================================================
# --- Build & Consolidate Protocol-Level DataFrame ---
# ============================================================
raw_rows = []
for p in protocols:
    raw_rows.append({
        "Protocol": p.get("displayName") or p.get("name"),
        "Category": p.get("category") or "Dexs",
        "Volume 24h": p.get("total24h") or 0,
        "Volume 48h-24h": p.get("total48hto24h") or 0,
        "Volume 7d": p.get("total7d") or 0,
        "Volume 14d-7d": p.get("total7dto14d") or p.get("total14dto7d") or 0,
        "Volume 30d": p.get("total30d") or 0,
        "Total All Time": p.get("totalAllTime") or 0,
        "Chains": len(p.get("chains", []) or []),
        "Logo": p.get("logo"),
    })
raw_df = pd.DataFrame(raw_rows)

if not raw_df.empty:
    raw_df["Base Protocol"] = raw_df["Protocol"].apply(base_dex_name)
    grouped = raw_df.groupby("Base Protocol", as_index=False).agg({
        "Category": "first",
        "Volume 24h": "sum",
        "Volume 48h-24h": "sum",
        "Volume 7d": "sum",
        "Volume 14d-7d": "sum",
        "Volume 30d": "sum",
        "Total All Time": "sum",
        "Chains": "max",
        "Logo": "first",
    }).rename(columns={"Base Protocol": "Protocol"})

    grouped["Change 1d (%)"] = grouped.apply(
        lambda r: (r["Volume 24h"] - r["Volume 48h-24h"]) / r["Volume 48h-24h"] * 100
        if r["Volume 48h-24h"] else None, axis=1
    )
    grouped["Change 7d (%)"] = grouped.apply(
        lambda r: (r["Volume 7d"] - r["Volume 14d-7d"]) / r["Volume 14d-7d"] * 100
        if r["Volume 14d-7d"] else None, axis=1
    )
    protocols_df = grouped.sort_values("Volume 24h", ascending=False).reset_index(drop=True)
else:
    protocols_df = raw_df

# ============================================================
# --- KPI Calculations ---
# ============================================================
total_24h = data.get("total24h") or 0
total_7d = data.get("total7d") or 0
total_30d = data.get("total30d") or 0

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


def period_change(df: pd.DataFrame, n: int):
    """% change between the sum of the last n daily candles and the sum of the n candles before them."""
    if df.empty:
        return None
    vols = df["volume"].to_numpy()
    if len(vols) < 2 * n:
        return None
    cur = vols[-n:].sum()
    prev = vols[-2 * n:-n].sum()
    return (cur - prev) / prev * 100 if prev else None


def donut_chart(df: pd.DataFrame, col: str, title: str):
    d = df[df[col] > 0][["Protocol", col]]
    if d.empty:
        return None
    fig = px.pie(d, names="Protocol", values=col, hole=0.5, title=title)
    fig.update_traces(textposition="inside", textinfo="percent+label")
    fig.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), showlegend=False)
    return fig


def volume_bar_chart(df: pd.DataFrame, col: str, title: str, axis_title: str):
    d = df[df[col] > 0][["Protocol", col]].sort_values(col)   # largest at the top
    if d.empty:
        return None
    fig = go.Figure(go.Bar(
        x=d[col], y=d["Protocol"],
        orientation="h",
        marker_color=ACCENT,
        text=[fmt_usd(v) for v in d[col]],
        textposition="outside",
        cliponaxis=False,
    ))
    fig.update_layout(
        title=title,
        height=max(320, 30 * len(d) + 110),
        margin=dict(l=10, r=60, t=50, b=10),
        xaxis_title=axis_title,
        yaxis_title=None,
        plot_bgcolor="white",
    )
    return fig


# ============================================================
# --- KPI Row 1 ---
# ============================================================
last_date = chart_df.iloc[-1]["date"] if not chart_df.empty else datetime.utcnow()
st.markdown(f"##### As of {last_date.strftime('%Y-%m-%d')}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("DEX Volume (24h)", fmt_usd(total_24h))
c2.metric("DEX Volume (7d)", fmt_usd(total_7d))
c3.metric("DEX Volume (30d)", fmt_usd(total_30d))
c4.metric("Active DEXs", f"{num_dexs}")

# ============================================================
# --- KPI Row: Volume Change (computed from the daily chart) ---
# ============================================================
chg_24h = period_change(chart_df, 1)    # last candle vs previous candle
chg_7d = period_change(chart_df, 7)     # sum of last 7 candles vs the 7 before
chg_30d = period_change(chart_df, 30)   # sum of last 30 candles vs the 30 before

k1, k2, k3 = st.columns(3)
k1.metric("DEX Volume Change (24h)", fmt_pct(chg_24h))
k2.metric("DEX Volume Change (7d)", fmt_pct(chg_7d))
k3.metric("DEX Volume Change (30d)", fmt_pct(chg_30d))

# ============================================================
# --- KPI Row 2 ---
# ============================================================
c5, c6, c7 = st.columns(3)
c5.metric("Avg Daily Volume (30d)", fmt_usd(daily_avg_30d))
c6.metric("Top DEX", top_dex)
c7.metric("Top DEX Share (24h)", fmt_pct(top_dex_share))

st.markdown("---")

# ============================================================
# --- DEX Volume Over Time (bars + cumulative line) ---
# ============================================================
if not chart_df.empty:
    st.metric("Total DEX Volume (All Time)", fmt_usd(chart_df["volume"].sum()))

    timeframe = st.radio(
        "Timeframe", ["Daily", "Weekly", "Monthly", "Quarterly"], horizontal=True, index=0
    )

    series = chart_df.set_index("date")["volume"]
    if timeframe == "Weekly":
        agg_df = series.resample("W-MON").sum().reset_index()
    elif timeframe == "Monthly":
        agg_df = series.resample("MS").sum().reset_index()
    elif timeframe == "Quarterly":
        agg_df = series.resample("QS").sum().reset_index()
    else:
        agg_df = chart_df[["date", "volume"]].copy()

    # Cumulative volume is computed on the FULL history, then the range filter is applied,
    # so the line always shows the true running total (not a total restarted at range start).
    agg_df["cumulative"] = agg_df["volume"].cumsum()

    range_map = {"7D": 7, "30D": 30, "90D": 90, "180D": 180, "1Y": 365, "All": None}
    range_choice = st.radio("Range", list(range_map.keys()), horizontal=True, index=5, label_visibility="collapsed")

    days = range_map[range_choice]
    plot_df = agg_df if days is None else agg_df[agg_df["date"] >= (last_date - timedelta(days=days))]

    fig_vol = make_subplots(specs=[[{"secondary_y": True}]])
    fig_vol.add_trace(
        go.Bar(
            x=plot_df["date"], y=plot_df["volume"],
            marker_color=ACCENT,
            name="Volume"
        ),
        secondary_y=False,
    )
    fig_vol.add_trace(
        go.Scatter(
            x=plot_df["date"], y=plot_df["cumulative"],
            mode="lines",
            line=dict(color=LINE_COLOR, width=3),
            name="Total Volume"
        ),
        secondary_y=True,
    )
    fig_vol.update_layout(
        title=dict(text="DEX Volume Over Time", x=0, xanchor="left", y=0.97),
        height=460,
        margin=dict(l=10, r=10, t=90, b=10),
        xaxis_title=None,
        hovermode="x unified",
        plot_bgcolor="white",
        legend=dict(
            orientation="h",
            x=0.5, xanchor="center",
            y=1.02, yanchor="bottom",
        ),
    )
    fig_vol.update_yaxes(title_text="Volume (USD)", secondary_y=False)
    fig_vol.update_yaxes(title_text="Total Volume (USD)", secondary_y=True, showgrid=False)
    st.plotly_chart(fig_vol, use_container_width=True)

    # ========================================================
    # --- Monthly Volume KPIs (below the chart) ---
    # ========================================================
    monthly = series.resample("MS").sum()
    # Drop the current month if it is still in progress, so it doesn't distort Min/Avg/Median
    if not monthly.empty and last_date.day != last_date.days_in_month:
        monthly = monthly.iloc[:-1]
    monthly = monthly[monthly > 0]

    if not monthly.empty:
        max_month = monthly.idxmax()
        min_month = monthly.idxmin()

        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Max Monthly Volume", fmt_usd(monthly.max()))
        m1.caption(f"📅 {max_month.strftime('%B %Y')}")
        m2.metric("Avg Monthly Volume", fmt_usd(monthly.mean()))
        m2.caption(f"Based on {len(monthly)} complete months")
        m3.metric("Min Monthly Volume", fmt_usd(monthly.min()))
        m3.caption(f"📅 {min_month.strftime('%B %Y')}")
        m4.metric("Median Monthly Volume", fmt_usd(monthly.median()))
        m4.caption("Complete months only")
    else:
        st.info("Not enough complete months of data to compute monthly statistics.")

    # ========================================================
    # --- Total Volume by DEX / Total DEX Share (only if all-time data exists) ---
    # ========================================================
    if (not protocols_df.empty and "Total All Time" in protocols_df.columns
            and protocols_df["Total All Time"].sum() > 0):
        t_left, t_right = st.columns(2)
        with t_left:
            fig_tv = volume_bar_chart(protocols_df, "Total All Time", "Total Volume by DEX", "Total Volume (USD)")
            if fig_tv is not None:
                st.plotly_chart(fig_tv, use_container_width=True)
        with t_right:
            fig_ts = donut_chart(protocols_df, "Total All Time", "Total DEX Share")
            if fig_ts is not None:
                st.plotly_chart(fig_ts, use_container_width=True)
else:
    st.info("No historical volume chart available for Ink.")

st.markdown("---")

# ============================================================
# --- Market Share (24h / 7d / 30d) ---
# ============================================================
if not protocols_df.empty:
    ms1, ms2, ms3 = st.columns(3)
    for col_ui, col_name, ttl in [
        (ms1, "Volume 24h", "Market Share (24h Volume)"),
        (ms2, "Volume 7d", "Market Share (7d Volume)"),
        (ms3, "Volume 30d", "Market Share (30d Volume)"),
    ]:
        with col_ui:
            fig_ms = donut_chart(protocols_df, col_name, ttl)
            if fig_ms is not None:
                st.plotly_chart(fig_ms, use_container_width=True)
            else:
                st.info(f"No data for {ttl}.")
else:
    st.info("No protocol-level data available.")

st.markdown("---")

# ============================================================
# --- DEXs by Volume (24h / 7d / 30d) ---
# ============================================================
if not protocols_df.empty:
    bv1, bv2, bv3 = st.columns(3)
    for col_ui, col_name, ttl in [
        (bv1, "Volume 24h", "DEXs by 24h Volume"),
        (bv2, "Volume 7d", "DEXs by 7d Volume"),
        (bv3, "Volume 30d", "DEXs by 30d Volume"),
    ]:
        with col_ui:
            fig_bv = volume_bar_chart(protocols_df, col_name, ttl, f"{col_name} (USD)")
            if fig_bv is not None:
                st.plotly_chart(fig_bv, use_container_width=True)
            else:
                st.info(f"No data for {ttl}.")
else:
    st.info("No protocol-level data available.")

st.markdown("---")

# ============================================================
# --- DEX Volume Change (1d / 7d) — green positive, red negative ---
# ============================================================


def change_bar_chart(df: pd.DataFrame, col: str, title: str):
    """Horizontal bar chart of per-DEX % change. Zero / missing values are removed;
    positive bars are green, negative bars are red."""
    d = df[["Protocol", col]].dropna()
    d = d[d[col] != 0].sort_values(col)          # ascending -> largest at the top
    if d.empty:
        return None

    colors = [POS_COLOR if v > 0 else NEG_COLOR for v in d[col]]
    fig = go.Figure(go.Bar(
        x=d[col], y=d["Protocol"],
        orientation="h",
        marker_color=colors,
        text=[f"{v:+.2f}%" for v in d[col]],
        textposition="outside",
        cliponaxis=False,
    ))
    fig.update_layout(
        title=title,
        height=max(320, 32 * len(d) + 110),
        margin=dict(l=10, r=40, t=50, b=10),
        xaxis_title="Change (%)",
        yaxis_title=None,
        plot_bgcolor="white",
        showlegend=False,
    )
    fig.add_vline(x=0, line_width=1, line_color="gray")
    return fig


chg_left, chg_right = st.columns(2)

with chg_left:
    if not protocols_df.empty:
        fig_c1 = change_bar_chart(protocols_df, "Change 1d (%)", "DEX Volume Change 1d (%)")
        if fig_c1 is not None:
            st.plotly_chart(fig_c1, use_container_width=True)
        else:
            st.info("No 1d volume change data available.")
    else:
        st.info("No protocol-level data available.")

with chg_right:
    if not protocols_df.empty:
        fig_c7 = change_bar_chart(protocols_df, "Change 7d (%)", "DEX Volume Change 7d (%)")
        if fig_c7 is not None:
            st.plotly_chart(fig_c7, use_container_width=True)
        else:
            st.info("No 7d volume change data available.")
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
    st.caption(
        f"{len(display_df)} DEX protocols shown (versions of the same exchange, e.g. Uniswap "
        "V3/V4, are combined into a single row)."
    )
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
