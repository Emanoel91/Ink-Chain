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
    page_title="Ink Chain - Fees & Revenue",
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
<h1 style="margin: 0;">Ink Chain — Fees & Revenue</h1>
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
This page tracks <b>protocol fees</b> (total amount paid by users) and <b>revenue</b>
(the portion kept by the protocol/token holders) generated on the <b>Ink</b> chain,
along with a protocol-level breakdown. Data is sourced live from the <b>DefiLlama</b> free public API.
</div>
""",
    unsafe_allow_html=True
)

st.markdown("")

# ============================================================
# --- Data Fetchers (DefiLlama free API) ---
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_overview(chain: str, data_type: str) -> dict:
    """Fees or Revenue overview for a chain: totals, daily chart, per-protocol breakdown."""
    url = (
        f"https://api.llama.fi/overview/fees/{chain}"
        f"?excludeTotalDataChart=false&excludeTotalDataChartBreakdown=true&dataType={data_type}"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()


try:
    with st.spinner("Loading fees & revenue data from DefiLlama..."):
        fees_data = get_overview(CHAIN_NAME, "dailyFees")
        rev_data = get_overview(CHAIN_NAME, "dailyRevenue")
except Exception as e:
    st.error(f"Failed to fetch data from DefiLlama API: {e}")
    st.stop()

fees_protocols = fees_data.get("protocols", []) or []
rev_protocols = rev_data.get("protocols", []) or []
fees_chart_raw = fees_data.get("totalDataChart", []) or []
rev_chart_raw = rev_data.get("totalDataChart", []) or []

if not fees_chart_raw and not fees_protocols:
    st.warning("No fees/revenue data returned for Ink.")
    st.stop()

# ============================================================
# --- Build Chart DataFrames ---
# ============================================================
fees_chart_df = pd.DataFrame(fees_chart_raw, columns=["timestamp", "fees"])
rev_chart_df = pd.DataFrame(rev_chart_raw, columns=["timestamp", "revenue"])

if not fees_chart_df.empty:
    fees_chart_df["date"] = pd.to_datetime(fees_chart_df["timestamp"], unit="s")
if not rev_chart_df.empty:
    rev_chart_df["date"] = pd.to_datetime(rev_chart_df["timestamp"], unit="s")

if not fees_chart_df.empty and not rev_chart_df.empty:
    chart_df = pd.merge(
        fees_chart_df[["date", "fees"]],
        rev_chart_df[["date", "revenue"]],
        on="date", how="outer"
    ).sort_values("date").reset_index(drop=True)
else:
    chart_df = fees_chart_df.rename(columns={}).assign(revenue=None) if not fees_chart_df.empty else pd.DataFrame()

# ============================================================
# --- Build Protocol-Level DataFrame (merge fees + revenue) ---
# ============================================================
fees_rows = {
    p.get("displayName") or p.get("name"): {
        "Category": p.get("category") or "N/A",
        "Fees 24h": p.get("total24h") or 0,
        "Fees 7d": p.get("total7d") or 0,
        "Fees 30d": p.get("total30d") or 0,
        "Fees Change 1d (%)": p.get("change_1d"),
        "Fees Change 7d (%)": p.get("change_7d"),
    }
    for p in fees_protocols
}
rev_rows = {
    p.get("displayName") or p.get("name"): {
        "Revenue 24h": p.get("total24h") or 0,
        "Revenue 7d": p.get("total7d") or 0,
        "Revenue 30d": p.get("total30d") or 0,
    }
    for p in rev_protocols
}

all_names = set(fees_rows.keys()) | set(rev_rows.keys())
merged_rows = []
for name in all_names:
    f = fees_rows.get(name, {})
    r = rev_rows.get(name, {})
    merged_rows.append({
        "Protocol": name,
        "Category": f.get("Category", "N/A"),
        "Fees 24h": f.get("Fees 24h", 0),
        "Fees 7d": f.get("Fees 7d", 0),
        "Fees 30d": f.get("Fees 30d", 0),
        "Fees Change 1d (%)": f.get("Fees Change 1d (%)"),
        "Fees Change 7d (%)": f.get("Fees Change 7d (%)"),
        "Revenue 24h": r.get("Revenue 24h", 0),
        "Revenue 7d": r.get("Revenue 7d", 0),
        "Revenue 30d": r.get("Revenue 30d", 0),
    })

protocols_df = pd.DataFrame(merged_rows)
if not protocols_df.empty:
    protocols_df["Revenue/Fees (7d)"] = protocols_df.apply(
        lambda r: round(r["Revenue 7d"] / r["Fees 7d"] * 100, 1) if r["Fees 7d"] else None,
        axis=1
    )
    protocols_df = protocols_df.sort_values("Fees 24h", ascending=False).reset_index(drop=True)

# ============================================================
# --- KPI Calculations ---
# ============================================================
fees_24h = fees_data.get("total24h") or 0
fees_7d = fees_data.get("total7d") or 0
fees_30d = fees_data.get("total30d") or 0
fees_change_1d = fees_data.get("change_1d")
fees_change_7d = fees_data.get("change_7d")

rev_24h = rev_data.get("total24h") or 0
rev_7d = rev_data.get("total7d") or 0
rev_30d = rev_data.get("total30d") or 0
rev_change_1d = rev_data.get("change_1d")
rev_change_7d = rev_data.get("change_7d")

rev_share_24h = (rev_24h / fees_24h * 100) if fees_24h else None
num_protocols = protocols_df.shape[0]
top_fee_protocol = protocols_df.iloc[0]["Protocol"] if not protocols_df.empty else "N/A"
top_fee_protocol_val = protocols_df.iloc[0]["Fees 24h"] if not protocols_df.empty else 0


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
# --- KPI Row 1: Fees ---
# ============================================================
last_date = chart_df["date"].max() if not chart_df.empty else datetime.utcnow()
st.markdown(f"##### As of {last_date.strftime('%Y-%m-%d')}")

st.markdown("###### Fees")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Fees (24h)", fmt_usd(fees_24h), fmt_pct(fees_change_1d))
c2.metric("Fees (7d)", fmt_usd(fees_7d), fmt_pct(fees_change_7d))
c3.metric("Fees (30d)", fmt_usd(fees_30d))
c4.metric("Top Protocol by Fees", top_fee_protocol)

# ============================================================
# --- KPI Row 2: Revenue ---
# ============================================================
st.markdown("###### Revenue")
c5, c6, c7, c8 = st.columns(4)
c5.metric("Revenue (24h)", fmt_usd(rev_24h), fmt_pct(rev_change_1d))
c6.metric("Revenue (7d)", fmt_usd(rev_7d), fmt_pct(rev_change_7d))
c7.metric("Revenue (30d)", fmt_usd(rev_30d))
c8.metric("Revenue/Fees Ratio (24h)", fmt_pct(rev_share_24h))

st.markdown("---")

# ============================================================
# --- Historical Fees vs Revenue Chart (with range selector) ---
# ============================================================
st.subheader("Daily Fees vs Revenue")

if not chart_df.empty:
    range_map = {"7D": 7, "30D": 30, "90D": 90, "180D": 180, "1Y": 365, "All": None}
    range_choice = st.radio("Range", list(range_map.keys()), horizontal=True, index=5, label_visibility="collapsed")

    days = range_map[range_choice]
    plot_df = chart_df if days is None else chart_df[chart_df["date"] >= (last_date - timedelta(days=days))]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=plot_df["date"], y=plot_df["fees"],
        marker_color=ACCENT, name="Fees"
    ))
    if "revenue" in plot_df.columns:
        fig.add_trace(go.Bar(
            x=plot_df["date"], y=plot_df["revenue"],
            marker_color="#7ED6DF", name="Revenue"
        ))
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="USD",
        xaxis_title=None,
        barmode="overlay",
        hovermode="x unified",
        plot_bgcolor="white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No historical daily fees/revenue chart available for Ink.")

st.markdown("---")

# ============================================================
# --- Top Protocols & Category Breakdown ---
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Top 10 Protocols by Fees (24h)")
    if not protocols_df.empty:
        top10 = protocols_df[protocols_df["Fees 24h"] > 0].head(10).sort_values("Fees 24h")
        if not top10.empty:
            fig_top = go.Figure(go.Bar(
                x=top10["Fees 24h"], y=top10["Protocol"],
                orientation="h",
                marker_color=ACCENT,
                text=[fmt_usd(v) for v in top10["Fees 24h"]],
                textposition="outside"
            ))
            fig_top.update_layout(
                height=420,
                margin=dict(l=10, r=10, t=10, b=10),
                xaxis_title="Fees 24h (USD)",
                yaxis_title=None
            )
            st.plotly_chart(fig_top, use_container_width=True)
        else:
            st.info("No 24h fees data available.")
    else:
        st.info("No protocol-level data available.")

with col_right:
    st.subheader("Fees by Category (7d)")
    if not protocols_df.empty:
        cat_df = protocols_df.groupby("Category", as_index=False)["Fees 7d"].sum()
        cat_df = cat_df[cat_df["Fees 7d"] > 0].sort_values("Fees 7d", ascending=False)
        if not cat_df.empty:
            fig_cat = px.pie(cat_df, names="Category", values="Fees 7d", hole=0.5)
            fig_cat.update_traces(textposition="inside", textinfo="percent+label")
            fig_cat.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
            st.plotly_chart(fig_cat, use_container_width=True)
        else:
            st.info("No 7d fees data available.")
    else:
        st.info("No protocol-level data available.")

st.markdown("---")

# ============================================================
# --- Full Fees & Revenue Table ---
# ============================================================
st.subheader("Protocols on Ink — Fees & Revenue")

if not protocols_df.empty:
    search = st.text_input("Search protocol", "")
    table_df = protocols_df.copy()
    if search:
        table_df = table_df[table_df["Protocol"].str.contains(search, case=False, na=False)]

    display_df = table_df[[
        "Protocol", "Category", "Fees 24h", "Fees 7d", "Fees 30d",
        "Revenue 24h", "Revenue 7d", "Revenue/Fees (7d)", "Fees Change 7d (%)"
    ]].copy()
    for col in ["Fees 24h", "Fees 7d", "Fees 30d", "Revenue 24h", "Revenue 7d"]:
        display_df[col] = display_df[col].apply(fmt_usd)
    display_df["Revenue/Fees (7d)"] = display_df["Revenue/Fees (7d)"].apply(
        lambda x: f"{x:.1f}%" if pd.notnull(x) else "N/A"
    )
    display_df["Fees Change 7d (%)"] = display_df["Fees Change 7d (%)"].apply(
        lambda x: f"{x:+.2f}%" if pd.notnull(x) else "N/A"
    )

    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption(f"{len(display_df)} protocols shown.")
else:
    st.info("No protocol-level data available for Ink at this time.")

# ============================================================
# --- Footer ---
# ============================================================
st.markdown(
    f"""
<div style="margin-top:25px; font-size:13px; color:gray;">
Data source: <a href="https://defillama.com/fees/ink" target="_blank">DefiLlama</a> (free public API, api.llama.fi) ·
Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} (cached hourly)
</div>
""",
    unsafe_allow_html=True
)
