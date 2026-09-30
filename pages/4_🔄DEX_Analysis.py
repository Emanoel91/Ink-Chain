```python
import pandas as pd
import numpy as np

# Mock chart data
dates = pd.date_range("2024-01-01", "2024-06-30", freq="D")
vols = np.random.randint(1000, 50000, size=len(dates))
df = pd.DataFrame({"date": dates, "volume": vols})

monthly = df.set_index("date")["volume"].resample("MS").sum().reset_index()
max_row = monthly.loc[monthly["volume"].idxmax()]
min_row = monthly.loc[monthly["volume"].idxmin()]
avg_vol = monthly["volume"].mean()
median_vol = monthly["volume"].median()

print("Monthly max:", max_row["volume"], max_row["date"].strftime("%B %Y"))
print("Monthly min:", min_row["volume"], min_row["date"].strftime("%B %Y"))
print("Monthly avg:", avg_vol)
print("Monthly median:", median_vol)


```

```text
Monthly max: 885076 January 2024
Monthly min: 709039 June 2024
Monthly avg: 779025.1666666666
Monthly median: 744838.0


```

```python
import plotly.graph_objects as go
import pandas as pd

# Mock protocols data
protocols_df = pd.DataFrame({
    "Protocol": ["Uniswap", "Velodrome", "Aerodrome", "Sushiswap", "Curve"],
    "Change 1d (%)": [12.5, -5.2, 0.0, 3.1, -15.0],
    "Change 7d (%)": [-8.0, 22.1, 0.0, -1.2, 5.5]
})

df_1d = protocols_df[
    (protocols_df["Change 1d (%)"].notnull()) & (protocols_df["Change 1d (%)"] != 0)
].sort_values("Change 1d (%)")

colors_1d = ["#28a745" if val > 0 else "#dc3545" for val in df_1d["Change 1d (%)"]]

fig_1d = go.Figure(go.Bar(
    x=df_1d["Change 1d (%)"],
    y=df_1d["Protocol"],
    orientation="h",
    marker_color=colors_1d,
    text=[f"{v:+.2f}%" for v in df_1d["Change 1d (%)"]],
    textposition="outside"
))
fig_1d.update_layout(
    title="DEX Volume Change 1d (%)",
    xaxis_title="Change 1d (%)",
    height=350,
    margin=dict(l=10, r=10, t=50, b=10)
)
print("Figure 1d created successfully!")


```

```text
Figure 1d created successfully!


```

تغییرات مورد نظر شما روی کد اعمال شد. کد به‌روزرسانی‌شده کامل به شرح زیر است:

```python
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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
BOX_BG = "#E5F2FF"

# ============================================================
# --- Title with Logo ---
# ============================================================
st.markdown(
    """

```

# Ink Chain — DEX Volume

""",
unsafe_allow_html=True
)

st.markdown(
f"""

This page tracks **spot DEX trading volume** on the **Ink** chain — swap activity over
time, protocol-level rankings, and market share across all decentralized exchanges live on
Ink. Different versions of the same exchange (e.g. Uniswap V3 / V4) are combined into one
entry. Data is sourced live from the **DefiLlama** free public API.

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
cleaned = re.sub(r"\s*$?[Vv]\d+(\.\d+)?$?\s*$", "", name).strip()
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
"Chains": "max",
"Logo": "first",
}).rename(columns={"Base Protocol": "Protocol"})

```
grouped["Change 1d (%)"] = grouped.apply(
    lambda r: (r["Volume 24h"] - r["Volume 48h-24h"]) / r["Volume 48h-24h"] * 100
    if r["Volume 48h-24h"] else None, axis=1
)
grouped["Change 7d (%)"] = grouped.apply(
    lambda r: (r["Volume 7d"] - r["Volume 14d-7d"]) / r["Volume 14d-7d"] * 100
    if r["Volume 14d-7d"] else None, axis=1
)
protocols_df = grouped.sort_values("Volume 24h", ascending=False).reset_index(drop=True)

```

else:
protocols_df = raw_df

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

# --- DEX Volume Over Time (timeframe + range selector) ---

# ============================================================

if not chart_df.empty:
timeframe = st.radio(
"Timeframe", ["Daily", "Weekly", "Monthly", "Quarterly"], horizontal=True, index=0
)

```
if timeframe == "Weekly":
    agg_df = (
        chart_df.set_index("date")["volume"]
        .resample("W-MON").sum()
        .reset_index()
    )
elif timeframe == "Monthly":
    agg_df = (
        chart_df.set_index("date")["volume"]
        .resample("MS").sum()
        .reset_index()
    )
elif timeframe == "Quarterly":
    agg_df = (
        chart_df.set_index("date")["volume"]
        .resample("QS").sum()
        .reset_index()
    )
else:
    agg_df = chart_df[["date", "volume"]].copy()

range_map = {"7D": 7, "30D": 30, "Quarter": 90, "90D": 90, "180D": 180, "1Y": 365, "All": None}
range_choice = st.radio("Range", list(range_map.keys()), horizontal=True, index=6, label_visibility="collapsed")

days = range_map[range_choice]
plot_df = agg_df if days is None else agg_df[agg_df["date"] >= (last_date - timedelta(days=days))].copy()

# Calculate cumulative total volume for the line trace
plot_df["total_volume"] = plot_df["volume"].cumsum()

fig_vol = go.Figure()

# Volume Bar Trace (Left Y-Axis)
fig_vol.add_trace(go.Bar(
    x=plot_df["date"],
    y=plot_df["volume"],
    marker_color=ACCENT,
    name="Volume",
    yaxis="y"
))

# Cumulative Total Volume Line Trace (Right Y-Axis)
fig_vol.add_trace(go.Scatter(
    x=plot_df["date"],
    y=plot_df["total_volume"],
    mode="lines",
    line=dict(color="#FF8C00", width=2.5),
    name="Total Volume",
    yaxis="y2"
))

fig_vol.update_layout(
    title="DEX Volume Over Time",
    height=450,
    margin=dict(l=10, r=10, t=60, b=10),
    hovermode="x unified",
    plot_bgcolor="white",
    yaxis=dict(
        title="Volume (USD)",
        showgrid=True
    ),
    yaxis2=dict(
        title="Total Volume (USD)",
        overlaying="y",
        side="right",
        showgrid=False
    ),
    xaxis_title=None,
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="center",
        x=0.5
    )
)
st.plotly_chart(fig_vol, use_container_width=True)

# ============================================================
# --- Monthly KPIs under DEX Volume Over Time ---
# ============================================================
monthly_df = (
    chart_df.set_index("date")["volume"]
    .resample("MS").sum()
    .reset_index()
)

if not monthly_df.empty:
    max_idx = monthly_df["volume"].idxmax()
    min_idx = monthly_df["volume"].idxmin()

    max_vol = monthly_df.loc[max_idx, "volume"]
    max_month = monthly_df.loc[max_idx, "date"].strftime("%B %Y")

    min_vol = monthly_df.loc[min_idx, "volume"]
    min_month = monthly_df.loc[min_idx, "date"].strftime("%B %Y")

    avg_monthly_vol = monthly_df["volume"].mean()
    med_monthly_vol = monthly_df["volume"].median()

    m_kpi1, m_kpi2, m_kpi3, m_kpi4 = st.columns(4)
    
    m_kpi1.metric("Max Monthly Volume", fmt_usd(max_vol))
    m_kpi1.caption(f"Peak Month: **{max_month}**")

    m_kpi2.metric("Avg Monthly Volume", fmt_usd(avg_monthly_vol))

    m_kpi3.metric("Min Monthly Volume", fmt_usd(min_vol))
    m_kpi3.caption(f"Lowest Month: **{min_month}**")

    m_kpi4.metric("Median Monthly Volume", fmt_usd(med_monthly_vol))

```

else:
st.info("No historical volume chart available for Ink.")

st.markdown("---")

# ============================================================

# --- Row: DEX Volume Changes (1d & 7d Horizontal Bar Charts) ---

# ============================================================

if not protocols_df.empty:
ch_col1, ch_col2 = st.columns(2)

```
with ch_col1:
    df_1d = protocols_df[
        protocols_df["Change 1d (%)"].notnull() & (protocols_df["Change 1d (%)"] != 0)
    ].sort_values("Change 1d (%)", ascending=True)

    if not df_1d.empty:
        colors_1d = ["#28a745" if v > 0 else "#dc3545" for v in df_1d["Change 1d (%)"]]
        fig_1d = go.Figure(go.Bar(
            x=df_1d["Change 1d (%)"],
            y=df_1d["Protocol"],
            orientation="h",
            marker_color=colors_1d,
            text=[f"{v:+.2f}%" for v in df_1d["Change 1d (%)"]],
            textposition="outside"
        ))
        fig_1d.update_layout(
            title="DEX Volume Change 1d (%)",
            height=400,
            margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="Change (%)",
            yaxis_title=None,
            plot_bgcolor="white"
        )
        st.plotly_chart(fig_1d, use_container_width=True)
    else:
        st.info("No non-zero 1d volume change data available.")

with ch_col2:
    df_7d = protocols_df[
        protocols_df["Change 7d (%)"].notnull() & (protocols_df["Change 7d (%)"] != 0)
    ].sort_values("Change 7d (%)", ascending=True)

    if not df_7d.empty:
        colors_7d = ["#28a745" if v > 0 else "#dc3545" for v in df_7d["Change 7d (%)"]]
        fig_7d = go.Figure(go.Bar(
            x=df_7d["Change 7d (%)"],
            y=df_7d["Protocol"],
            orientation="h",
            marker_color=colors_7d,
            text=[f"{v:+.2f}%" for v in df_7d["Change 7d (%)"]],
            textposition="outside"
        ))
        fig_7d.update_layout(
            title="DEX Volume Change 7d (%)",
            height=400,
            margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="Change (%)",
            yaxis_title=None,
            plot_bgcolor="white"
        )
        st.plotly_chart(fig_7d, use_container_width=True)
    else:
        st.info("No non-zero 7d volume change data available.")

st.markdown("---")

```

# ============================================================

# --- Market Share & Top Protocols ---

# ============================================================

col_left, col_right = st.columns(2)

with col_left:
if not protocols_df.empty:
share_df = protocols_df[protocols_df["Volume 7d"] > 0][["Protocol", "Volume 7d"]]
if not share_df.empty:
fig_share = px.pie(
share_df, names="Protocol", values="Volume 7d", hole=0.5,
title="Market Share (7d Volume)"
)
fig_share.update_traces(textposition="inside", textinfo="percent+label")
fig_share.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), showlegend=True)
st.plotly_chart(fig_share, use_container_width=True)
else:
st.info("No 7d volume data to compute market share.")
else:
st.info("No protocol-level data available.")

with col_right:
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
title="Top 10 DEXs by 24h Volume",
height=420,
margin=dict(l=10, r=10, t=50, b=10),
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

```
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

```

else:
st.info("No protocol-level data available for Ink at this time.")

# ============================================================

# --- Footer ---

# ============================================================

st.markdown(
f"""

Data source: [DefiLlama](https://defillama.com/dexs/chain/ink) (free public API, api.llama.fi) ·
Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} (cached hourly)

""",
unsafe_allow_html=True
)

```

```
