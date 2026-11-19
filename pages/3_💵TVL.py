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

# Purple spectrum built around #7132f5 (dark → light), used for the TVL-by-Category chart.
PURPLE_SPECTRUM = [
    "#4a0fb8", "#5a1ed1", "#7132f5", "#8a54f7", "#a377f9",
    "#bc9afb", "#d5bdfd", "#e2cffe", "#ede1fe", "#f5eefe",
]

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
protocol-level breakdown. Data is sourced live from a free public on-chain analytics API.
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
insights_box = st.container()      # filled further down, once the data is loaded
# ============================================================
# --- Data Fetchers (free public on-chain analytics API) ---
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
    with st.spinner("Loading TVL data..."):
        hist_df = get_historical_chain_tvl(CHAIN_NAME)
        chains_df = get_all_chains_tvl()
        protocols_df = get_protocols_on_chain(CHAIN_NAME)
except Exception as e:
    st.error(f"Failed to fetch TVL data: {e}")
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
# --- Key Insights (auto-generated headlines, shown at the top of the page) ---
# ============================================================
LARGE_MOVE_PCT = 50.0
TONE_STYLE = {
    "up":      ("▲", "#16a34a"),
    "down":    ("▼", "#dc2626"),
    "neutral": ("●", "#6b7280"),
}


def _tone(ch, flat=0.5):
    if ch is None or pd.isna(ch) or abs(ch) < flat:
        return "neutral"
    return "up" if ch > 0 else "down"


def _past_tvl(days):
    past = hist_df[hist_df["date"] <= current_date - timedelta(days=days)]
    return past.iloc[-1]["tvl"] if not past.empty else None


def _drivers(col, delta):
    """Protocols (counted in chain TVL) ranked by the USD change implied by their own % change."""
    if col not in counted_df or counted_df.empty or not delta:
        return None
    d = counted_df[counted_df[col].notna() & (counted_df[col] > -100)].copy()
    if d.empty:
        return None
    d["contrib"] = d["TVL"] - d["TVL"] / (1 + d[col] / 100)
    d = d[d["contrib"] * delta > 0]               # only protocols moving in the chain's direction
    if d.empty:
        return None
    return d.loc[d["contrib"].abs().idxmax()]


def _chain_why(days, ch):
    """Explain a big chain-level TVL move using only the data."""
    past = _past_tvl(days)
    if not past:
        return None
    delta = current_tvl - past
    parts = []

    base = hist_df[(hist_df["date"] < current_date - timedelta(days=days)) &
                   (hist_df["date"] >= current_date - timedelta(days=days + 90))]["tvl"]
    if len(base) >= 14 and base.mean() > 0:
        vs = (current_tvl / base.mean() - 1) * 100
        if abs(vs) >= 30:
            parts.append(f"against the 90 days before the window the level is still {abs(vs):.0f}% "
                         f"{'above' if vs > 0 else 'below'} normal, so it is {'a real surge' if vs > 0 else 'a real drop'}")
        else:
            parts.append(f"base effect: the starting level was unusually {'low' if ch > 0 else 'high'}; "
                         f"versus the 90-day average the current TVL is only {vs:+.0f}%")

    if days > 1:
        win = hist_df[hist_df["date"] > current_date - timedelta(days=days)]
        steps = hist_df.set_index("date")["tvl"].diff().reindex(win["date"]).dropna()
        if len(steps) >= 2 and delta:
            big = steps.abs().idxmax()
            if steps[big] * delta > 0 and steps[big] / delta >= 0.5:
                parts.append(f"a single day ({big.strftime('%b %d')}) accounts for {steps[big] / delta * 100:.0f}% of the move")

    col = {1: "Change 1d (%)", 7: "Change 7d (%)"}.get(days)
    top = _drivers(col, delta) if col else None
    if top is not None:
        parts.append(f"largest driver: {top['Protocol']} ({'+' if top['contrib'] > 0 else '−'}{fmt_usd(abs(top['contrib']))}, "
                     f"{abs(top['contrib'] / delta) * 100:.0f}% of the chain's change)")
    return "; ".join(parts) if parts else None


def _ath_why():
    parts = []
    since = (current_date - ath_date).days
    parts.append(f"the peak of {fmt_usd(ath_tvl)} was set on {ath_date.strftime('%b %d, %Y')} ({since} days ago)")
    around = hist_df[(hist_df["date"] >= ath_date - timedelta(days=15)) & (hist_df["date"] <= ath_date + timedelta(days=15))]["tvl"]
    if len(around) >= 10 and around.median() > 0 and ath_tvl / around.median() >= 1.5:
        parts.append(f"the peak looks like a short spike ({(ath_tvl / around.median() - 1) * 100:.0f}% above the surrounding "
                     f"30-day median), so the drawdown is partly inflated by that spike")
    p30 = _past_tvl(30)
    total_fall = ath_tvl - current_tvl
    if p30 and total_fall > 0:
        recent = max(p30 - current_tvl, 0) / total_fall * 100
        parts.append(f"{recent:.0f}% of the decline happened in the last 30 days")
    return "; ".join(parts)


def _protocol_why(row, col, label):
    ch = row[col]
    share = row["TVL"] / protocols_tvl_sum * 100 if protocols_tvl_sum else None
    delta = row["TVL"] - row["TVL"] / (1 + ch / 100) if ch > -100 else None
    parts = []
    if share is not None and delta is not None:
        if share < 1:
            parts.append(f"small base: only {share:.2f}% of Ink's counted TVL, so a {fmt_usd(abs(delta))} change is large in % terms "
                         f"but minor for the chain")
        else:
            parts.append(f"material: {share:.1f}% of Ink's counted TVL, a {fmt_usd(abs(delta))} change")
    c1 = row.get("Change 1d (%)")
    if col == "Change 7d (%)" and pd.notnull(c1) and c1 > -100 and ch > -100:
        f1 = 1 - 1 / (1 + c1 / 100)
        f7 = 1 - 1 / (1 + ch / 100)
        if f7 and f1 / f7 >= 0.6:
            parts.append("most of the 7-day move happened in the last day")
    return "; ".join(parts) if parts else None


def build_insights():
    """Headline sentences computed from the data."""
    out = []                                              # (tone, html)

    # 1) TVL level and momentum
    bits = [f"{lab} {v:+.1f}%" for lab, v in (("1d", change_1d), ("7d", change_7d), ("30d", change_30d)) if v is not None]
    out.append((_tone(change_7d if change_7d is not None else change_1d),
                f"<b>{fmt_usd(current_tvl)}</b> is locked in DeFi on Ink"
                + (f" — change: {', '.join(bits)}." if bits else ".")))

    # 2) All-time high / drawdown
    if (current_date - ath_date).days <= 7:
        out.append(("up", f"🏆 <b>TVL is at or near its all-time high</b> ({fmt_usd(ath_tvl)} on {ath_date.strftime('%b %d, %Y')})."))
    elif drawdown_from_ath is not None:
        out.append(("down" if drawdown_from_ath <= -5 else "neutral",
                    f"TVL is <b>{abs(drawdown_from_ath):.1f}% below</b> its all-time high of {fmt_usd(ath_tvl)} "
                    f"({ath_date.strftime('%b %d, %Y')})."))

    # 3) Rank and dominance
    if chain_rank:
        out.append(("neutral", f"Ink ranks <b>#{chain_rank}</b> of {len(chains_df)} chains by TVL"
                               + (f", with {dominance:.2f}% of all DeFi TVL." if dominance is not None else ".")))

    # 4) Concentration
    if not counted_df.empty and protocols_tvl_sum:
        t1 = counted_df.iloc[0]
        s1 = t1["TVL"] / protocols_tvl_sum * 100
        s3 = counted_df.head(3)["TVL"].sum() / protocols_tvl_sum * 100
        level = "highly concentrated" if s1 >= 50 else "concentrated" if s3 >= 70 else "fairly diversified"
        out.append(("neutral", f"<b>{t1['Protocol']}</b> is the largest protocol with {fmt_usd(t1['TVL'])} ({s1:.1f}% of counted TVL); "
                               f"the top 3 hold {s3:.1f}% — TVL is {level}."))

    # 5) Categories
    if not counted_df.empty and protocols_tvl_sum:
        cats = counted_df.groupby("Category")["TVL"].sum().sort_values(ascending=False)
        txt = f"<b>{cats.index[0]}</b> is the leading category with {cats.iloc[0] / protocols_tvl_sum * 100:.1f}% of counted TVL"
        if len(cats) > 1:
            txt += f", followed by {cats.index[1]} ({cats.iloc[1] / protocols_tvl_sum * 100:.1f}%)"
        out.append(("neutral", txt + f" — {len(cats)} categories in total."))

    # 6) Biggest 7d movers among meaningfully sized protocols
    if not counted_df.empty and protocols_tvl_sum:
        floor = max(0.005 * protocols_tvl_sum, 100_000)
        m = counted_df[(counted_df["TVL"] >= floor) & counted_df["Change 7d (%)"].notna()]
        if not m.empty:
            up, dn = m.loc[m["Change 7d (%)"].idxmax()], m.loc[m["Change 7d (%)"].idxmin()]
            if up["Change 7d (%)"] > 0:
                out.append(("up", f"Biggest 7-day gainer: <b>{up['Protocol']}</b> ({up['Change 7d (%)']:+.1f}%, {fmt_usd(up['TVL'])} TVL)."))
            if dn["Change 7d (%)"] < 0:
                out.append(("down", f"Biggest 7-day loser: <b>{dn['Protocol']}</b> ({dn['Change 7d (%)']:+.1f}%, {fmt_usd(dn['TVL'])} TVL)."))
            out_note = f"Movers consider protocols with at least {fmt_usd(floor)} TVL."
            out.append(("neutral", f'<span style="color:#6b7280; font-size:13px;">{out_note}</span>'))

    # 7) Excluded protocols
    if num_excluded > 0:
        ex = protocols_df[~protocols_df["Counted in Chain TVL"]]
        out.append(("neutral", f"{num_excluded} protocol(s) in excluded categories (e.g. {', '.join(ex.head(3)['Protocol'])}) are "
                               f"<b>not counted</b> in Ink's headline TVL; every figure on this page uses counted protocols only."))
    return out


def build_large_moves():
    """(tone, headline_html, why) for every headline indicator with |change| >= LARGE_MOVE_PCT."""
    out = []

    def add(ch, headline, why):
        if ch is None or pd.isna(ch) or abs(ch) < LARGE_MOVE_PCT:
            return
        out.append(("up" if ch > 0 else "down", f"{headline} — <b>{ch:+.0f}%</b>", why))

    for days, ch in ((1, change_1d), (7, change_7d), (30, change_30d)):
        add(ch, f"Ink total TVL, {days}d ({fmt_usd(current_tvl)})", _chain_why(days, ch))
    add(drawdown_from_ath, "TVL vs all-time high", _ath_why())

    # Protocols (counted in chain TVL), largest first, max 6
    if not counted_df.empty:
        cand = []
        for col, lab in (("Change 1d (%)", "1d"), ("Change 7d (%)", "7d")):
            for _, r in counted_df[counted_df[col].abs() >= LARGE_MOVE_PCT].iterrows():
                cand.append((r["TVL"], r, col, lab))
        cand.sort(key=lambda x: -x[0])
        for _, r, col, lab in cand[:6]:
            add(r[col], f"{r['Protocol']} TVL, {lab} ({fmt_usd(r['TVL'])})", _protocol_why(r, col, lab))
        if len(cand) > 6:
            out.append(("neutral", f"…and {len(cand) - 6} more protocol move(s) of ±{LARGE_MOVE_PCT:.0f}% or more "
                                   f"(smaller protocols); see the gainers/losers charts below.", None))
    return out


insights = build_insights()
large_moves = build_large_moves()
with insights_box:
    items = "".join(
        f'<li style="margin:6px 0;"><span style="color:{TONE_STYLE[t][1]}; font-weight:700;">{TONE_STYLE[t][0]}</span> {txt}</li>'
        for t, txt in insights
    )
    if large_moves:
        lm_items = "".join(
            f'<li style="margin:8px 0;"><span style="color:{TONE_STYLE[t][1]}; font-weight:700;">{TONE_STYLE[t][0]}</span> {head}'
            + (f'<div style="font-size:13.5px; color:#4b5563; margin-left:18px;">Why: {why}.</div>' if why else
               ('' if head.startswith("…") else
                '<div style="font-size:13.5px; color:#4b5563; margin-left:18px;">Why: no single driver stands out in the data.</div>'))
            + "</li>"
            for t, head, why in large_moves
        )
        lm_block = (f'<div style="border-top:1px dashed #b99cf9; margin-top:10px; padding-top:8px;">'
                    f'<div style="font-weight:700; font-size:16px;">⚠️ Large moves (±{LARGE_MOVE_PCT:.0f}% or more) — what is behind them</div>'
                    f'<ul style="list-style:none; padding-left:0; margin:6px 0 4px 0;">{lm_items}</ul>'
                    f'<div style="font-size:12px; color:#6b7280;">Explanations show what moved in the data (base effect, one-day jumps, '
                    f'dominant protocols); TVL also moves with token prices, and the data cannot identify real-world causes.</div></div>')
    else:
        lm_block = ('<div style="border-top:1px dashed #b99cf9; margin-top:10px; padding-top:8px; font-size:13.5px; color:#6b7280;">'
                    f'No headline indicator moved by ±{LARGE_MOVE_PCT:.0f}% or more.</div>')
    st.markdown(
        f"""
        <div style="background:#F1EAFE; border:1px solid #d9c8fb; border-left:6px solid #7132f5;
                    border-radius:10px; padding:14px 20px; margin-top:12px; color:#1a1a1a; font-size:15.5px; line-height:1.55;">
            <div style="font-weight:700; font-size:18px; margin-bottom:4px;">📰 Key Insights — as of {current_date.strftime('%Y-%m-%d')} (UTC)</div>
            <ul style="list-style:none; padding-left:0; margin:6px 0 4px 0;">{items}</ul>
            {lm_block}
            <div style="font-size:12px; color:#6b7280; margin-top:8px;">Auto-generated from the live data; independent of the chart filters below.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


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

if num_excluded > 0:
    st.info(
        f"ℹ️ {num_excluded} protocol(s) on Ink belong to categories that are tracked but "
        f"explicitly excluded from a chain's headline TVL — e.g. **Liquid Staking**, "
        f"**Bridge**, **Onchain Capital Allocator**, and **Risk Curators** protocols (this is "
        f"stated on each such protocol's own page, e.g. \"Onchain Capital Allocator "
        f"protocols are not counted into Chain TVL\"). All KPIs, charts, and the top-10 list "
        f"above use only the protocols that are counted. The full table below still lists "
        f"every protocol, with a **Counted in Chain TVL** column, so nothing is hidden."
    )

st.markdown("---")

# ============================================================
# --- Historical TVL Chart (with range selector) ---
# ============================================================
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
    title="Ink TVL Over Time",
    height=420,
    margin=dict(l=10, r=10, t=50, b=10),
    yaxis_title="TVL (USD)",
    xaxis_title=None,
    hovermode="x unified",
    plot_bgcolor="white"
)
st.plotly_chart(fig_tvl, use_container_width=True)

st.markdown("---")

# ============================================================
# --- Top 20 Chains by TVL (Ink highlighted) ---
# ============================================================
def human_format(num):
    if num >= 1e9:
        return f"{num/1e9:.1f}B"
    if num >= 1e6:
        return f"{num/1e6:.1f}M"
    if num >= 1e3:
        return f"{num/1e3:.1f}K"
    return str(int(num))


top_chains = chains_df.head(20)[["name", "tvl", "rank"]].copy()
ink_in_top = CHAIN_NAME in set(top_chains["name"])
if not ink_in_top and chain_rank:
    # Ink is outside the top 20: append it (with its rank) so it is still visible and highlighted
    ink_row = chains_df[chains_df["name"] == CHAIN_NAME][["name", "tvl", "rank"]]
    top_chains = pd.concat([top_chains, ink_row], ignore_index=True)

is_ink = top_chains["name"] == CHAIN_NAME
top_chains["label"] = top_chains["name"].where(~is_ink | ink_in_top, top_chains["name"] + " (#" + top_chains["rank"].astype(str) + ")")

fig_chains = go.Figure(go.Bar(
    x=top_chains["label"], y=top_chains["tvl"],
    marker_color=["#7132f5" if v else "#d5bdfd" for v in is_ink],
    text=[human_format(v) for v in top_chains["tvl"]],
    textposition="outside",
    hovertemplate="%{x}<br>TVL: $%{y:,.0f}<extra></extra>"
))
fig_chains.update_layout(
    title=f"Top 20 Chains by TVL ($USD) — {CHAIN_NAME} highlighted"
          + (f" (#{chain_rank})" if chain_rank else ""),
    height=460,
    margin=dict(l=10, r=10, t=60, b=10),
    xaxis_title=None,
    yaxis_title="$USD",
    xaxis_tickangle=-35,
    showlegend=False,
    plot_bgcolor="white"
)
st.plotly_chart(fig_chains, use_container_width=True)

st.markdown("---")

include_excluded = st.checkbox(
    "Also include categories excluded from headline Chain TVL "
    "(Liquid Staking, Bridge, Onchain Capital Allocator, Risk Curators)",
    value=False
)
chart_source_df = protocols_df if include_excluded else counted_df

st.caption(
    "By default, the charts and table below use only the protocols counted toward "
    "Ink's headline Chain TVL, matching the KPIs above. Tick the box to also see "
    "vault/curator/liquid-staking protocols, which are real TVL but excluded from the "
    "chain total to avoid double-counting."
)

# ============================================================
# --- TVL by Category & Top Protocols ---
# ============================================================
col_left, col_right = st.columns(2)

with col_left:
    if not chart_source_df.empty:
        cat_df = chart_source_df.groupby("Category", as_index=False)["TVL"].sum().sort_values("TVL", ascending=False)
        fig_cat = px.pie(
            cat_df, names="Category", values="TVL", hole=0.5,
            color_discrete_sequence=PURPLE_SPECTRUM,
            title="TVL by Category"
        )
        fig_cat.update_traces(textposition="inside", textinfo="percent+label")
        fig_cat.update_layout(height=420, margin=dict(l=10, r=10, t=50, b=10), showlegend=True)
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("No protocol-level data available.")

with col_right:
    if not chart_source_df.empty:
        top10 = chart_source_df.sort_values("TVL", ascending=False).head(10).sort_values("TVL")
        fig_top = go.Figure(go.Bar(
            x=top10["TVL"], y=top10["Protocol"],
            orientation="h",
            marker_color="#7132f5",
            text=[fmt_usd(v) for v in top10["TVL"]],
            textposition="outside"
        ))
        fig_top.update_layout(
            title="Top 10 Protocols by TVL",
            height=420,
            margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="TVL (USD)",
            yaxis_title=None
        )
        st.plotly_chart(fig_top, use_container_width=True)
    else:
        st.info("No protocol-level data available.")

st.markdown("---")

# ============================================================
# --- Row: TVL by Category (bar chart + table) ---
# ============================================================
if not chart_source_df.empty:
    cat_bar_df = chart_source_df.groupby("Category", as_index=False)["TVL"].sum().sort_values("TVL", ascending=False)
    cat_total = cat_bar_df["TVL"].sum()
    cat_bar_df["Share (%)"] = cat_bar_df["TVL"] / cat_total * 100 if cat_total else 0
else:
    cat_bar_df = pd.DataFrame(columns=["Category", "TVL", "Share (%)"])

log_scale_cat = st.checkbox("Log scale (category chart)", value=False, key="cat_log_scale")

col_cat_chart, col_cat_table = st.columns(2)

with col_cat_chart:
    if not cat_bar_df.empty:
        fig_cat_bar = go.Figure(go.Bar(
            x=cat_bar_df["Category"], y=cat_bar_df["TVL"],
            marker_color="#7132f5",
            text=[fmt_usd(v) for v in cat_bar_df["TVL"]],
            textposition="outside"
        ))
        fig_cat_bar.update_layout(
            title="TVL by Category",
            height=420,
            margin=dict(l=10, r=10, t=50, b=10),
            yaxis_title="TVL (USD)",
            yaxis_type="log" if log_scale_cat else "linear",
            xaxis_title=None,
            xaxis_tickangle=-30
        )
        st.plotly_chart(fig_cat_bar, use_container_width=True)
    else:
        st.info("No protocol-level data available.")

with col_cat_table:
    if not cat_bar_df.empty:
        cat_table_display = cat_bar_df.copy()
        cat_table_display["TVL"] = cat_table_display["TVL"].apply(fmt_usd)
        cat_table_display["Share (%)"] = cat_table_display["Share (%)"].apply(lambda x: f"{x:.2f}%")
        row_height, header_height = 35, 38
        table_height = header_height + row_height * len(cat_table_display)
        st.dataframe(cat_table_display, use_container_width=True, hide_index=True, height=table_height)
    else:
        st.info("No protocol-level data available.")

st.markdown("---")

# ============================================================
# --- Row: Top Gainers (1d and 7d) — positive changes only, max 10 ---
# ============================================================
col_gain_1d, col_gain_7d = st.columns(2)

with col_gain_1d:
    gainers_1d = chart_source_df[chart_source_df["Change 1d (%)"] > 0].sort_values(
        "Change 1d (%)", ascending=False
    ).head(10).sort_values("Change 1d (%)")
    if not gainers_1d.empty:
        fig_g1 = go.Figure(go.Bar(
            x=gainers_1d["Change 1d (%)"], y=gainers_1d["Protocol"],
            orientation="h",
            marker_color="#22c55e",
            text=[f"{v:+.2f}%" for v in gainers_1d["Change 1d (%)"]],
            textposition="outside"
        ))
        fig_g1.update_layout(
            title="Top Gainers — 1-Day TVL Change",
            height=420, margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="Change 1d (%)", yaxis_title=None
        )
        st.plotly_chart(fig_g1, use_container_width=True)
    else:
        st.info("No protocols with a positive 1-day TVL change.")

with col_gain_7d:
    gainers_7d = chart_source_df[chart_source_df["Change 7d (%)"] > 0].sort_values(
        "Change 7d (%)", ascending=False
    ).head(10).sort_values("Change 7d (%)")
    if not gainers_7d.empty:
        fig_g7 = go.Figure(go.Bar(
            x=gainers_7d["Change 7d (%)"], y=gainers_7d["Protocol"],
            orientation="h",
            marker_color="#22c55e",
            text=[f"{v:+.2f}%" for v in gainers_7d["Change 7d (%)"]],
            textposition="outside"
        ))
        fig_g7.update_layout(
            title="Top Gainers — 7-Day TVL Change",
            height=420, margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="Change 7d (%)", yaxis_title=None
        )
        st.plotly_chart(fig_g7, use_container_width=True)
    else:
        st.info("No protocols with a positive 7-day TVL change.")

st.markdown("---")

# ============================================================
# --- Row: Top Losers (1d and 7d) — negative changes only, max 10 ---
# ============================================================
col_loss_1d, col_loss_7d = st.columns(2)

with col_loss_1d:
    losers_1d = chart_source_df[chart_source_df["Change 1d (%)"] < 0].sort_values(
        "Change 1d (%)", ascending=True
    ).head(10).sort_values("Change 1d (%)", ascending=False)
    if not losers_1d.empty:
        fig_l1 = go.Figure(go.Bar(
            x=losers_1d["Change 1d (%)"], y=losers_1d["Protocol"],
            orientation="h",
            marker_color="#ef4444",
            text=[f"{v:+.2f}%" for v in losers_1d["Change 1d (%)"]],
            textposition="outside"
        ))
        fig_l1.update_layout(
            title="Top Losers — 1-Day TVL Change",
            height=420, margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="Change 1d (%)", yaxis_title=None
        )
        st.plotly_chart(fig_l1, use_container_width=True)
    else:
        st.info("No protocols with a negative 1-day TVL change.")

with col_loss_7d:
    losers_7d = chart_source_df[chart_source_df["Change 7d (%)"] < 0].sort_values(
        "Change 7d (%)", ascending=True
    ).head(10).sort_values("Change 7d (%)", ascending=False)
    if not losers_7d.empty:
        fig_l7 = go.Figure(go.Bar(
            x=losers_7d["Change 7d (%)"], y=losers_7d["Protocol"],
            orientation="h",
            marker_color="#ef4444",
            text=[f"{v:+.2f}%" for v in losers_7d["Change 7d (%)"]],
            textposition="outside"
        ))
        fig_l7.update_layout(
            title="Top Losers — 7-Day TVL Change",
            height=420, margin=dict(l=10, r=10, t=50, b=10),
            xaxis_title="Change 7d (%)", yaxis_title=None
        )
        st.plotly_chart(fig_l7, use_container_width=True)
    else:
        st.info("No protocols with a negative 7-day TVL change.")

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
        "TVL on this chain. \"Counted in Chain TVL\" marks whether that protocol is included "
        "in Ink's headline Total TVL figure — protocols marked \"No\" (e.g. vaults, curators, "
        "liquid-staking) are real TVL that is tracked separately to avoid double-counting with "
        "the protocols they deposit into."
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
