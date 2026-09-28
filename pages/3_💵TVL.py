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
    page_title="Ink Chain - TVL",
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

# Categories DefiLlama tracks but explicitly does NOT count toward a chain's headline TVL
# (stated on the category/protocol pages themselves, e.g. "Onchain Capital Allocator protocols
# are not counted into Chain TVL", "Risk Curators protocols are not counted into Chain TVL"),
# plus the two categories documented in DefiLlama's public methodology (Liquid Staking, Bridge).
# This list may not be fully exhaustive of every future category DefiLlama excludes.
EXCLUDED_FROM_CHAIN_TVL = {
    "Liquid Staking",
    "Bridge",
    "Onchain Capital Allocator",
    "Risk Curators",
}

# ============================================================
# --- Title with Logo ---
# ============================================================
st.markdown(
    """
<div style="display: flex; align-items: center; gap: 15px;">
<img src="https://img.cryptorank.io/coins/ink1729850762329.png" alt="ink" style="width:60px; height:60px;">
<h1 style="margin: 0;">Ink Chain — TVL Overview</h1>
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
This page tracks <b>Total Value Locked (TVL)</b> on the <b>Ink</b> chain — the aggregate capital
deposited in DeFi protocols on Ink — including historical trend, TVL by category, and a
protocol-level breakdown. Data is sourced live from the <b>DefiLlama</b> free public API.
</div>
""",
    unsafe_allow_html=True
)

st.markdown("")

# ============================================================
# --- Data Fetchers (DefiLlama free API) ---
# ============================================================

@st.cache_data(ttl=3600, show_spinner=False)
def get_historical_chain_tvl(chain: str) -> pd.DataFrame:
    """Historical total TVL for a single chain."""
    url = f"https://api.llama.fi/v2/historicalChainTvl/{chain}"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    data = r.json()
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["date"], unit="s")
    df = df.sort_values("date").reset_index(drop=True)
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_all_chains_tvl() -> pd.DataFrame:
    """Current TVL snapshot across every chain DefiLlama tracks (for rank/dominance)."""
    url = "https://api.llama.fi/v2/chains"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.DataFrame(r.json())
    df = df.sort_values("tvl", ascending=False).reset_index(drop=True)
    df["rank"] = df.index + 1
    return df


@st.cache_data(ttl=3600, show_spinner=False)
def get_protocols_on_chain(chain: str) -> pd.DataFrame:
    """All protocols with a nonzero TVL on the given chain."""
    url = "https://api.llama.fi/protocols"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    protocols = r.json()

    rows = []
    for p in protocols:
        chain_tvls = p.get("chainTvls", {}) or {}
        tvl_on_chain = chain_tvls.get(chain, 0) or 0
        if tvl_on_chain and tvl_on_chain > 0:
            rows.append({
                "Protocol": p.get("name"),
                "Category": p.get("category") or "Other",
                "TVL": tvl_on_chain,
                "Change 1d (%)": p.get("change_1d"),
                "Change 7d (%)": p.get("change_7d"),
                "Total TVL (all chains)": p.get("tvl"),
                "Mcap": p.get("mcap"),
                "Logo": p.get("logo"),
                "URL": p.get("url"),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df["Mcap/TVL"] = df.apply(
            lambda r: round(r["Mcap"] / r["TVL"], 2) if r["Mcap"] and r["TVL"] else None,
            axis=1
        )
        df["Counted in Chain TVL"] = ~df["Category"].isin(EXCLUDED_FROM_CHAIN_TVL)
        df = df.sort_values("TVL", ascending=False).reset_index(drop=True)
    return df


def pct_change(df: pd.DataFrame, days: int):
    """% change in TVL over the last `days` days, using the historical TVL dataframe."""
    if df.empty:
        return None
    latest_date = df["date"].max()
    latest_tvl = df.loc[df["date"] == latest_date, "tvl"].values[0]
    target_date = latest_date - timedelta(days=days)
    past = df[df["date"] <= target_date]
    if past.empty:
        return None
    past_tvl = past.iloc[-1]["tvl"]
    if not past_tvl:
        return None
    return (latest_tvl - past_tvl) / past_tvl * 100


# ============================================================
# --- Load Data ---
# ============================================================
try:
    with st.spinner("Loading TVL data from DefiLlama..."):
        hist_df = get_historical_chain_tvl(CHAIN_NAME)
        chains_df = get_all_chains_tvl()
        protocols_df = get_protocols_on_chain(CHAIN_NAME)
except Exception as e:
    st.error(f"Failed to fetch data from DefiLlama API: {e}")
    st.stop()

if hist_df.empty:
    st.warning("No historical TVL data returned for Ink.")
    st.stop()

# ============================================================
# --- KPI Calculations ---
# ============================================================
current_tvl = hist_df.iloc[-1]["tvl"]
current_date = hist_df.iloc[-1]["date"]

change_1d = pct_change(hist_df, 1)
change_7d = pct_change(hist_df, 7)
change_30d = pct_change(hist_df, 30)

ath_row = hist_df.loc[hist_df["tvl"].idxmax()]
ath_tvl = ath_row["tvl"]
ath_date = ath_row["date"]
drawdown_from_ath = (current_tvl - ath_tvl) / ath_tvl * 100 if ath_tvl else None

chain_row = chains_df[chains_df["name"] == CHAIN_NAME]
chain_rank = int(chain_row["rank"].values[0]) if not chain_row.empty else None
total_defi_tvl = chains_df["tvl"].sum()
dominance = (current_tvl / total_defi_tvl * 100) if total_defi_tvl else None

num_protocols = protocols_df.shape[0]
num_excluded = int((~protocols_df["Counted in Chain TVL"]).sum()) if not protocols_df.empty else 0

# Protocols DefiLlama actually counts toward the chain's headline TVL (excludes categories
# like Liquid Staking, Bridge, Onchain Capital Allocator, Risk Curators — see note above).
# Summing just these should reconcile closely with current_tvl from historicalChainTvl.
counted_df = protocols_df[protocols_df["Counted in Chain TVL"]] if not protocols_df.empty else protocols_df
protocols_tvl_sum = counted_df["TVL"].sum() if not counted_df.empty else 0

top_protocol = counted_df.iloc[0]["Protocol"] if not counted_df.empty else "N/A"
top_protocol_tvl = counted_df.iloc[0]["TVL"] if not counted_df.empty else 0
top_protocol_share = (top_protocol_tvl / protocols_tvl_sum * 100) if protocols_tvl_sum else None
reconciliation_ratio = (protocols_tvl_sum / current_tvl * 100) if current_tvl else None


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
st.markdown(f"##### As of {current_date.strftime('%Y-%m-%d')}")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Total TVL", fmt_usd(current_tvl), fmt_pct(change_1d))
c2.metric("TVL Change (7d)", fmt_pct(change_7d))
c3.metric("TVL Change (30d)", fmt_pct(change_30d))
c4.metric("Chain Rank by TVL", f"#{chain_rank}" if chain_rank else "N/A")

# ============================================================
# --- KPI Row 2 ---
# ============================================================
c5, c6, c7, c8 = st.columns(4)
c5.metric("All-Time High TVL", fmt_usd(ath_tvl), f"{ath_date.strftime('%Y-%m-%d')}")
c6.metric("Down From ATH", fmt_pct(drawdown_from_ath))
c7.metric("Protocols on Ink", f"{num_protocols}")
c8.metric("DeFi TVL Dominance", fmt_pct(dominance) if dominance is not None else "N/A")

st.markdown(
    f"""
<div style="font-size:14px; color:#555; margin-top:-5px;">
Top protocol counted toward Chain TVL: <b>{top_protocol}</b> — {fmt_usd(top_protocol_tvl)}
({fmt_pct(top_protocol_share)} of the {fmt_usd(protocols_tvl_sum)} summed across protocols
DefiLlama counts toward Ink's Chain TVL — {fmt_pct(reconciliation_ratio - 100 if reconciliation_ratio is not None else None)}
vs. the headline Total TVL KPI, a normal small gap)
</div>
""",
    unsafe_allow_html=True
)

if num_excluded > 0:
    st.info(
        f"ℹ️ {num_excluded} protocol(s) on Ink belong to categories DefiLlama tracks but "
        f"explicitly excludes from a chain's headline TVL — e.g. **Liquid Staking**, "
        f"**Bridge**, **Onchain Capital Allocator**, and **Risk Curators** protocols (this is "
        f"stated on each such protocol's own DefiLlama page, e.g. \"Onchain Capital Allocator "
        f"protocols are not counted into Chain TVL\"). All KPIs, charts, and the top-10 list "
        f"above use only the protocols DefiLlama does count. The full table below still lists "
        f"every protocol, with a **Counted in Chain TVL** column, so nothing is hidden."
    )

st.markdown("---")

# ============================================================
# --- Historical TVL Chart (with range selector) ---
# ============================================================
st.subheader("Historical TVL")

range_map = {"7D": 7, "30D": 30, "90D": 90, "180D": 180, "1Y": 365, "All": None}
range_choice = st.radio("Range", list(range_map.keys()), horizontal=True, index=5, label_visibility="collapsed")

days = range_map[range_choice]
plot_df = hist_df if days is None else hist_df[hist_df["date"] >= (current_date - timedelta(days=days))]

fig_tvl = go.Figure()
fig_tvl.add_trace(go.Scatter(
    x=plot_df["date"], y=plot_df["tvl"],
    mode="lines", fill="tozeroy",
    line=dict(color="#7132f5", width=2),
    fillcolor="rgba(113,50,245,0.15)",
    name="TVL"
))
fig_tvl.update_layout(
    height=420,
    margin=dict(l=10, r=10, t=10, b=10),
    yaxis_title="TVL (USD)",
    xaxis_title=None,
    hovermode="x unified",
    plot_bgcolor="white"
)
st.plotly_chart(fig_tvl, use_container_width=True)

st.markdown("---")

include_excluded = st.checkbox(
    "Also include categories DefiLlama excludes from headline Chain TVL "
    "(Liquid Staking, Bridge, Onchain Capital Allocator, Risk Curators)",
    value=False
)
chart_source_df = protocols_df if include_excluded else counted_df

st.caption(
    "By default, the charts and table below use only the protocols DefiLlama counts toward "
    "Ink's headline Chain TVL — matching the KPIs above and defillama.com/chain/Ink. "
    "Tick the box to also see vault/curator/liquid-staking protocols, which are real TVL but "
    "excluded from the chain total to avoid double-counting."
)

# ============================================================
# --- TVL by Category & Top Protocols ---
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
    st.subheader("TVL by Category")
    if not chart_source_df.empty:
        cat_df = chart_source_df.groupby("Category", as_index=False)["TVL"].sum().sort_values("TVL", ascending=False)
        fig_cat = px.pie(cat_df, names="Category", values="TVL", hole=0.5)
        fig_cat.update_traces(textposition="inside", textinfo="percent+label")
        fig_cat.update_layout(height=420, margin=dict(l=10, r=10, t=10, b=10), showlegend=True)
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("No protocol-level data available.")

with col_right:
    st.subheader("Top 10 Protocols by TVL")
    if not chart_source_df.empty:
        top10 = chart_source_df.sort_values("TVL", ascending=False).head(10).sort_values("TVL")
        fig_top = go.Figure(go.Bar(
            x=top10["TVL"], y=top10["Protocol"],
            orientation="h",
            marker_color=ACCENT,
            text=[fmt_usd(v) for v in top10["TVL"]],
            textposition="outside"
        ))
        fig_top.update_layout(
            height=420,
            margin=dict(l=10, r=10, t=10, b=10),
            xaxis_title="TVL (USD)",
            yaxis_title=None
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No protocol-level data available.")

st.markdown("---")

# ============================================================
# --- Full Protocols Table ---
# ============================================================
st.subheader("Protocols on Ink — Full List")

if not protocols_df.empty:
    search = st.text_input("Search protocol", "")
    table_df = chart_source_df.copy()
    if search:
        table_df = table_df[table_df["Protocol"].str.contains(search, case=False, na=False)]

    display_df = table_df[[
        "Protocol", "Category", "TVL", "Counted in Chain TVL",
        "Change 1d (%)", "Change 7d (%)", "Mcap/TVL"
    ]].rename(columns={"TVL": "TVL on Ink"}).copy()
    display_df["TVL on Ink"] = display_df["TVL on Ink"].apply(fmt_usd)
    display_df["Counted in Chain TVL"] = display_df["Counted in Chain TVL"].map({True: "Yes", False: "No"})
    display_df["Change 1d (%)"] = display_df["Change 1d (%)"].apply(
        lambda x: f"{x:+.2f}%" if pd.notnull(x) else "N/A"
    )
    display_df["Change 7d (%)"] = display_df["Change 7d (%)"].apply(
        lambda x: f"{x:+.2f}%" if pd.notnull(x) else "N/A"
    )
    display_df["Mcap/TVL"] = display_df["Mcap/TVL"].apply(lambda x: x if pd.notnull(x) else "N/A")

    st.dataframe(display_df, use_container_width=True, hide_index=True)
    st.caption(
        f"{len(display_df)} protocols shown. \"TVL on Ink\" is each protocol's own reported "
        "TVL on this chain (matches its DefiLlama protocol page). \"Counted in Chain TVL\" "
        "marks whether DefiLlama includes that protocol in Ink's headline Total TVL figure "
        "— protocols marked \"No\" (e.g. vaults, curators, liquid-staking) are real TVL that "
        "DefiLlama tracks separately to avoid double-counting with the protocols they deposit "
        "into."
    )
else:
    st.info("No protocol-level data available for Ink at this time.")

# ============================================================
# --- Footer ---
# ============================================================
st.markdown(
    f"""
<div style="margin-top:25px; font-size:13px; color:gray;">
Data source: <a href="https://defillama.com/chain/Ink" target="_blank">DefiLlama</a> (free public API, api.llama.fi) ·
Last refreshed: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')} (cached hourly)
</div>
""",
    unsafe_allow_html=True
)
