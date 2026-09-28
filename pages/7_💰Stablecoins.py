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
    page_title="Ink Chain - Stablecoins",
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
<h1 style="margin: 0;">Ink Chain — Stablecoins</h1>
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
This page tracks the <b>circulating supply of stablecoins</b> bridged to / minted on the
<b>Ink</b> chain — total supply trend, per-token breakdown, peg mechanism, and price
(depeg) monitoring. Data is sourced live from the <b>DefiLlama</b> free public stablecoins API.
</div>
""",
    unsafe_allow_html=True
)

st.markdown("")

# ============================================================
# --- Data Fetchers (DefiLlama free API) ---
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_stablecoins_on_chain(chain: str) -> pd.DataFrame:
    """Per-stablecoin breakdown for a single chain, with current/prev-day/week/month supply."""
    url = "https://stablecoins.llama.fi/stablecoins?includePrices=true"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    assets = r.json().get("peggedAssets", []) or []

    rows = []
    for a in assets:
        chain_circ = (a.get("chainCirculating") or {}).get(chain)
        if not chain_circ:
            continue
        current = (chain_circ.get("current") or {}).get("peggedUSD")
        prev_day = (chain_circ.get("circulatingPrevDay") or {}).get("peggedUSD")
        prev_week = (chain_circ.get("circulatingPrevWeek") or {}).get("peggedUSD")
        prev_month = (chain_circ.get("circulatingPrevMonth") or {}).get("peggedUSD")
        if not current:
            continue
        rows.append({
            "Name": a.get("name"),
            "Symbol": a.get("symbol"),
            "Peg Type": a.get("pegType"),
            "Peg Mechanism": a.get("pegMechanism") or "unknown",
            "Supply": current,
            "Supply Prev Day": prev_day,
            "Supply Prev Week": prev_week,
            "Supply Prev Month": prev_month,
            "Price": a.get("price"),
        })
    return pd.DataFrame(rows)


@st.cache_data(ttl=3600, show_spinner=False)
def get_stablecoin_chart(chain: str) -> pd.DataFrame:
    """Historical total stablecoin circulating supply on a single chain."""
    url = f"https://stablecoins.llama.fi/stablecoincharts/{chain}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json() or []
    rows = []
    for d in data:
        total = (d.get("totalCirculatingUSD") or {}).get("peggedUSD")
        if total is None:
            continue
        rows.append({"date": pd.to_datetime(int(d.get("date")), unit="s"), "supply": total})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date").reset_index(drop=True)
    return df


try:
    with st.spinner("Loading stablecoin data from DefiLlama..."):
        stable_df = get_stablecoins_on_chain(CHAIN_NAME)
        chart_df = get_stablecoin_chart(CHAIN_NAME)
except Exception as e:
    st.error(f"Failed to fetch data from DefiLlama API: {e}")
    st.stop()

if stable_df.empty and chart_df.empty:
    st.warning("No stablecoin data returned for Ink.")
    st.stop()

# ============================================================
# --- Per-token % Changes ---
# ============================================================
if not stable_df.empty:
    stable_df["Change 1d (%)"] = stable_df.apply(
        lambda r: (r["Supply"] - r["Supply Prev Day"]) / r["Supply Prev Day"] * 100
        if r["Supply Prev Day"] else None, axis=1
    )
    stable_df["Change 7d (%)"] = stable_df.apply(
        lambda r: (r["Supply"] - r["Supply Prev Week"]) / r["Supply Prev Week"] * 100
        if r["Supply Prev Week"] else None, axis=1
    )
    stable_df["Change 30d (%)"] = stable_df.apply(
        lambda r: (r["Supply"] - r["Supply Prev Month"]) / r["Supply Prev Month"] * 100
        if r["Supply Prev Month"] else None, axis=1
    )
    stable_df = stable_df.sort_values("Supply", ascending=False).reset_index(drop=True)

# ============================================================
# --- KPI Calculations ---
# ============================================================
total_supply = stable_df["Supply"].sum() if not stable_df.empty else 0
num_stablecoins = stable_df.shape[0] if not stable_df.empty else 0

chart_change_7d = None
chart_change_30d = None
if not chart_df.empty:
    latest_date = chart_df["date"].max()
    latest_val = chart_df.loc[chart_df["date"] == latest_date, "supply"].values[0]

    def _pct_change(days):
        target = latest_date - timedelta(days=days)
        past = chart_df[chart_df["date"] <= target]
        if past.empty:
            return None
        past_val = past.iloc[-1]["supply"]
        return (latest_val - past_val) / past_val * 100 if past_val else None

    chart_change_7d = _pct_change(7)
    chart_change_30d = _pct_change(30)

top_stable = stable_df.iloc[0] if not stable_df.empty else None
top_stable_share = (top_stable["Supply"] / total_supply * 100) if (top_stable is not None and total_supply) else None

depegged = stable_df[(stable_df["Price"].notna()) & ((stable_df["Price"] < 0.98) | (stable_df["Price"] > 1.02))] if not stable_df.empty else pd.DataFrame()


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
    return "N/A" if x is None or pd.isna(x) else f"{x:+.2f}%"


# ============================================================
# --- KPI Row 1 ---
# ============================================================
as_of = chart_df["date"].max().strftime("%Y-%m-%d") if not chart_df.empty else datetime.utcnow().strftime("%Y-%m-%d")
st.markdown(f"##### As of {as_of}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Stablecoin Supply", fmt_usd(total_supply), fmt_pct(chart_change_7d))
c2.metric("Change (30d)", fmt_pct(chart_change_30d))
c3.metric("Distinct Stablecoins", f"{num_stablecoins}")
c4.metric(
    "Dominant Stablecoin",
    top_stable["Symbol"] if top_stable is not None else "N/A",
    fmt_pct(top_stable_share) if top_stable_share is not None else None
)

if not depegged.empty:
    names = ", ".join(f"{r['Symbol']} (${r['Price']:.3f})" for _, r in depegged.iterrows())
    st.warning(f"⚠️ Potential depeg detected: {names}")

st.markdown("---")

# ============================================================
# --- Historical Total Supply Chart (with range selector) ---
# ============================================================
st.subheader("Historical Total Stablecoin Supply")

if not chart_df.empty:
    range_map = {"7D": 7, "30D": 30, "90D": 90, "180D": 180, "1Y": 365, "All": None}
    range_choice = st.radio("Range", list(range_map.keys()), horizontal=True, index=5, label_visibility="collapsed")

    days = range_map[range_choice]
    latest_date = chart_df["date"].max()
    plot_df = chart_df if days is None else chart_df[chart_df["date"] >= (latest_date - timedelta(days=days))]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df["date"], y=plot_df["supply"],
        mode="lines", fill="tozeroy",
        line=dict(color=ACCENT, width=2),
        fillcolor="rgba(74,144,226,0.15)",
        name="Stablecoin Supply"
    ))
    fig.update_layout(
        height=420,
        margin=dict(l=10, r=10, t=10, b=10),
        yaxis_title="Supply (USD)",
        xaxis_title=None,
        hovermode="x unified",
        plot_bgcolor="white"
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No historical stablecoin supply chart available for Ink.")

st.markdown("---")

# ============================================================
# --- Supply Share & Peg Mechanism ---
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("Supply Share by Stablecoin")
    if not stable_df.empty:
        fig_share = px.pie(stable_df, names="Symbol", values="Supply", hole=0.5)
        fig_share.update_traces(textposition="inside", textinfo="percent+label")
        fig_share.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
        st.plotly_chart(fig_share, use_container_width=True)
    else:
        st.info("No per-token data available.")

with col_right:
    st.subheader("Supply by Peg Mechanism")
    if not stable_df.empty:
        mech_df = stable_df.groupby("Peg Mechanism", as_index=False)["Supply"].sum()
        mech_df = mech_df.sort_values("Supply", ascending=False)
        fig_mech = go.Figure(go.Bar(
            x=mech_df["Supply"], y=mech_df["Peg Mechanism"],
            orientation="h",
            marker_color=ACCENT,
            text=[fmt_usd(v) for v in mech_df["Supply"]],
            textposition="outside"
        ))
        fig_mech.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="Supply (USD)",
            yaxis_title=None
        )
        st.plotly_chart(fig_mech, use_container_width=True)
    else:
        st.info("No per-token data available.")

st.markdown("---")

# ============================================================
# --- Full Stablecoins Table ---
# ============================================================
st.subheader("Stablecoins on Ink — Full List")

if not stable_df.empty:
    display_df = stable_df[[
        "Name", "Symbol", "Peg Type", "Peg Mechanism", "Supply",
        "Change 1d (%)", "Change 7d (%)", "Change 30d (%)", "Price"
    ]].copy()
    display_df["Supply"] = display_df["Supply"].apply(fmt_usd)
    for col in ["Change 1d (%)", "Change 7d (%)", "Change 30d (%)"]:
        display_df[col] = display_df[col].apply(fmt_pct)
    display_df["Price"] = display_df["Price"].apply(lambda x: f"${x:.4f}" if pd.notnull(x) else "N/A")

    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption(f"{len(display_df)} stablecoins shown.")
else:
    st.info("No stablecoin data available for Ink at this time.")

# ============================================================
# --- Footer ---
# ============================================================
st.markdown(
    f"""
<div style="margin-top:25px; font-size:13px; color:gray;">
Data source: <a href="https://defillama.com/stablecoins/chains/Ink" target="_blank">DefiLlama</a> (free public API, stablecoins.llama.fi) ·
Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} (cached hourly)
</div>
""",
    unsafe_allow_html=True
)
