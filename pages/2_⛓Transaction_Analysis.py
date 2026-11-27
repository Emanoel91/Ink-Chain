import numpy as np
import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

from common import (
    ACCENT, ACCENT_FILL, MA_COLOR,
    safe_call, empty_ts, show_chart, page_header, sidebar_controls,
    fmt_num, fmt_pct,
)

# --- Page Config: Tab Title & Icon ---
st.set_page_config(
    page_title="Ink Chain — Transaction Analysis",
    page_icon="https://explorer.inkonchain.com/assets/configs/network_icon.svg",
    layout="wide"
)

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
# --- Title with Logo ---
st.markdown(
    """
    <div style="display: flex; align-items: center; gap: 15px;">
        <img src="https://img.cryptorank.io/coins/ink1729850762329.png" alt="Ink" style="width:60px; height:60px;">
        <h1 style="margin: 0;">Ink Chain — Transaction Analysis</h1>
    </div>
    """,
    unsafe_allow_html=True
)

# --- Builder Info ------------------------------------------------------------------------
st.markdown(
    """
    <div style="margin-top: 25px; font-size: 16px;">
        <div style="display: flex; align-items: center; gap: 10px;">
            <img src="https://pbs.twimg.com/profile_images/2060406047391559681/sA9zPNKM_400x400.jpg" alt="Eman Raz" style="width:25px; height:25px; border-radius: 50%;">
            <span>Built by: <a href="https://x.com/0xeman_raz" target="_blank">Eman Raz</a></span>
        </div>
    </div>

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

insights_box = st.container()      # filled further down, once the data is loaded

errors = []


def sc(fn, *args, **kwargs):
    return safe_call(errors, fn, *args, **kwargs)

## -- sidebar_controls()

GTP_API = "https://api.growthepie.com/v1"
CHAIN = "ink"

# Metrics used (growthepie: /v1/metrics/chains/ink/{metric}.json)
#   agg  = how daily rows are combined into weekly / monthly buckets
#   kind = chart style
CHARTS = {
    "txcount":      dict(title="Number of Transactions Over Time",                    agg="sum",  kind="bar",  ma=True,  units="transactions"),
    "txnsGrowth":   dict(title="Cumulative Transactions Over Time",         agg="last", kind="area", ma=False, units="transactions"),  # derived
    "daa":          dict(title="Active Addresses Over Time",                agg="mean", kind="bar",  ma=True,  units="addresses",
                         title_agg="Active Addresses (daily avg)"),
    "txsPerActive": dict(title="Transactions per Active Address", agg="mean", kind="line", ma=False, units="txs / address"),  # derived
}
GROUPS = [
    ("Transactions Analysis", ["txcount", "txnsGrowth"]),
    ("Addresses Analysis", ["daa", "txsPerActive"]),
]


# ============================================================
# --- Data fetchers ---
# ============================================================
def _find_timeseries(o):
    """Fallback: locate any {'types': [...], 'data': [[...], ...]} block in the JSON."""
    if isinstance(o, dict):
        if isinstance(o.get("types"), list) and isinstance(o.get("data"), list):
            return o
        for v in o.values():
            r = _find_timeseries(v)
            if r is not None:
                return r
    elif isinstance(o, list):
        for v in o:
            r = _find_timeseries(v)
            if r is not None:
                return r
    return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_metric_raw(metric: str) -> pd.DataFrame:
    """Full daily history of one growthepie metric for Ink -> DataFrame[date, <value columns>]."""
    r = requests.get(
        f"{GTP_API}/metrics/chains/{CHAIN}/{metric}.json",
        timeout=30, headers={"User-Agent": "ink-dashboard/1.0"},
    )
    r.raise_for_status()
    j = r.json()
    # Each file holds several resolutions under details.timeseries (daily, weekly, monthly, hourly...)
    tsd = (j.get("details") or {}).get("timeseries") if isinstance(j, dict) else None
    ts = tsd.get("daily") if isinstance(tsd, dict) else None
    if not (isinstance(ts, dict) and ts.get("data")):
        ts = _find_timeseries(j)
    if ts is None or not ts["data"]:
        return empty_ts()
    df = pd.DataFrame(ts["data"], columns=ts["types"])
    if "unix" not in df.columns:
        return empty_ts()
    unit = "ms" if df["unix"].astype("float64").abs().max() > 1e11 else "s"
    df["date"] = pd.to_datetime(df["unix"], unit=unit).dt.normalize()
    df = df.drop(columns=["unix"])
    for c in df.columns:
        if c != "date":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df["date"].dt.date < datetime.now(timezone.utc).date()]  # drop today's partial day
    return df.sort_values("date").reset_index(drop=True)


def col_series(raw, candidates):
    """Pick the first existing column among `candidates` -> DataFrame[date, value] (or None)."""
    if raw is None or raw.empty:
        return None
    for c in candidates:
        if c in raw.columns:
            d = raw[["date", c]].rename(columns={c: "value"}).dropna()
            return d.reset_index(drop=True) if not d.empty else None
    return None


# ============================================================
# --- Filters (each one a separate dropdown) ---
# ============================================================
RANGES = {"7D": 7, "30D": 30, "90D": 90, "Q (current quarter)": "Q", "180D": 180, "1Y": 365, "All": None}

f1, f2, f3, _ = st.columns([1, 1, 1, 3])
with f1:
    gran = st.selectbox("Time Frame", ["Daily", "Weekly", "Monthly"], index=0)
with f2:
    range_choice = st.selectbox("Range", list(RANGES.keys()), index=len(RANGES) - 1)
with f3:
    show_ma = st.selectbox("Moving Average", ["On", "Off"], index=0) == "On"
MA_WINDOW = {"Daily": 7, "Weekly": 4, "Monthly": 3}[gran]

st.markdown("---")


# ============================================================
# --- Load data ---
# ============================================================
with st.spinner("Loading Ink data from growthepie..."):
    tx_raw = sc(get_metric_raw, "txcount", default=None, label="growthepie txcount")
    daa_raw = sc(get_metric_raw, "daa", default=None, label="growthepie daa")
    fees_raw = sc(get_metric_raw, "fees", default=None, label="growthepie fees")

tx = col_series(tx_raw, ["value"])
daa = col_series(daa_raw, ["value"])
fees_usd = col_series(fees_raw, ["usd", "value_usd"])
fees_eth = col_series(fees_raw, ["eth", "value_eth"])

series = {}   # chart id -> (daily df[date, value], units)
if tx is not None:
    series["txcount"] = (tx, CHARTS["txcount"]["units"])
    cum = tx.copy()
    cum["value"] = cum["value"].cumsum()
    series["txnsGrowth"] = (cum, CHARTS["txnsGrowth"]["units"])
if daa is not None:
    series["daa"] = (daa, CHARTS["daa"]["units"])
if tx is not None and daa is not None:
    m = tx.merge(daa, on="date", suffixes=("_tx", "_act"))
    m = m[m["value_act"] > 0]
    if not m.empty:
        series["txsPerActive"] = (
            pd.DataFrame({"date": m["date"], "value": m["value_tx"] / m["value_act"]}),
            CHARTS["txsPerActive"]["units"])

if not series:
    st.warning("growthepie data could not be loaded right now. See the data warnings at the bottom.")


# ============================================================
# --- KPI helpers ---
# ============================================================
def pct(cur, prev):
    if cur is None or prev is None or pd.isna(cur) or pd.isna(prev) or prev == 0:
        return None
    return (cur - prev) / prev * 100


def dlt(ch):
    return fmt_pct(ch) if ch is not None else None


def window_sum(df, n):
    """Sum of the last n days vs the n days before."""
    if df is None or len(df) < 2 * n:
        return None, None
    v = df["value"]
    cur, prv = v.tail(n).sum(), v.iloc[-2 * n:-n].sum()
    return cur, pct(cur, prv)


def window_avg(df, n):
    """Average of the last n days vs the n days before."""
    if df is None or len(df) < 2 * n:
        return None, None
    v = df["value"]
    cur, prv = v.tail(n).mean(), v.iloc[-2 * n:-n].mean()
    return cur, pct(cur, prv)


def last_vs_prev(df):
    if df is None or len(df) < 2:
        return None, None
    last, prev = df.iloc[-1]["value"], df.iloc[-2]["value"]
    return last, pct(last, prev)


def ytd_sum(df):
    """Sum since Jan 1 of the latest year vs the same period of the previous year."""
    if df is None or df.empty:
        return None, None
    end = df["date"].max()
    start = pd.Timestamp(year=end.year, month=1, day=1)
    cur = df.loc[df["date"] >= start, "value"].sum()
    prev_start = pd.Timestamp(year=end.year - 1, month=1, day=1)
    prev_end = end - pd.DateOffset(years=1)
    if df["date"].min() > prev_start:        # no full previous-year comparison window
        return cur, None
    prv = df.loc[(df["date"] >= prev_start) & (df["date"] <= prev_end), "value"].sum()
    return cur, pct(cur, prv)


def usd_compact(v):
    if v is None or pd.isna(v):
        return "N/A"
    a = abs(v)
    if a >= 1e9:
        return f"${v / 1e9:,.2f}B"
    if a >= 1e6:
        return f"${v / 1e6:,.2f}M"
    if a >= 1e3:
        return f"${v / 1e3:,.1f}K"
    return f"${v:,.2f}"


def eth_fmt(v, decimals=2):
    if v is None or pd.isna(v):
        return "N/A"
    return f"{v:,.{decimals}f} ETH"


def usd_small(v):
    if v is None or pd.isna(v):
        return "N/A"
    return f"${v:.5f}" if abs(v) < 0.01 else f"${v:.4f}"


def fee_per_tx_last(fees_df):
    """Fees / transactions on the latest day present in both series."""
    if fees_df is None or tx is None:
        return None
    m = fees_df.merge(tx, on="date", suffixes=("_fee", "_tx"))
    m = m[m["value_tx"] > 0]
    if m.empty:
        return None
    r = m.iloc[-1]
    return r["value_fee"] / r["value_tx"]


# ============================================================
# --- KPI cards ---
# ============================================================
POS_COLOR = "#16a34a"       # green for positive change
NEG_COLOR = "#dc2626"       # red for negative change
CARD_COLOR = "#9d70ff"
NEUTRAL_SUB = "#5b3fa6"


def kpi_card(col, label: str, value: str, sub: str = None, sub_color: str = NEUTRAL_SUB):
    """Bold KPI card with a #9d70ff colour pattern; `sub` is the footnote under the value."""
    sub_html = (f'<div style="font-size:14px; font-weight:700; color:{sub_color}; margin-top:2px;">{sub}</div>'
                if sub else '<div style="font-size:14px; margin-top:2px;">&nbsp;</div>')
    col.markdown(
        f"""
<div style="background:linear-gradient(180deg,#f7f2ff 0%,#ece3ff 100%); border:1.5px solid {CARD_COLOR};
            border-left:6px solid {CARD_COLOR}; border-radius:14px; padding:14px 16px; margin-bottom:14px;
            box-shadow:0 2px 8px rgba(157,112,255,0.20); min-height:118px;">
  <div style="font-size:14px; font-weight:700; color:{NEUTRAL_SUB};">{label}</div>
  <div style="font-size:28px; font-weight:800; color:#1a1a1a; line-height:1.25; word-break:break-word;">{value}</div>
  {sub_html}
</div>
""",
        unsafe_allow_html=True,
    )


def change_sub(chg, label: str):
    """Footnote text + colour for a % change: green if positive, red if negative."""
    if chg is None or pd.isna(chg):
        return "N/A", "#6b7280"
    arrow = "▲" if chg > 0 else "▼" if chg < 0 else "●"
    color = POS_COLOR if chg > 0 else NEG_COLOR if chg < 0 else "#6b7280"
    return f"{arrow} {chg:+.2f}% vs {label}", color


def card_chg(col, label, value, ch, ref):
    txt, clr = change_sub(ch, ref)
    kpi_card(col, label, value, txt, clr)


# ============================================================
# --- Key Insights (auto-generated headlines, shown at the top of the page) ---
# ============================================================
LARGE_MOVE_PCT = 50.0
TONE_STYLE = {
    "up":      ("▲", "#16a34a"),
    "down":    ("▼", "#dc2626"),
    "neutral": ("●", "#6b7280"),
}
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
WEEKDAYS_FULL = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def change_phrase(ch, flat=1.0):
    """('up 5.2%' | 'down 3.1%' | 'flat', tone) for a % change; (None, 'neutral') if unavailable."""
    if ch is None or pd.isna(ch):
        return None, "neutral"
    if abs(ch) < flat:
        return "flat", "neutral"
    return (f"up {abs(ch):.1f}%" if ch > 0 else f"down {abs(ch):.1f}%"), ("up" if ch > 0 else "down")


def _why_last(df, ch):
    """Explain a big day-over-day move of a daily series using only the data."""
    if df is None or len(df) < 9:
        return None
    s_ = df["value"]
    last_v, prev_v = s_.iloc[-1], s_.iloc[-2]
    base = s_.iloc[-9:-2].mean()                     # 7 days before the previous day
    own = s_.iloc[-8:-1].mean()                      # 7 days before the latest day
    parts = []
    if base > 0 and abs(prev_v / base - 1) >= 0.30:
        parts.append(f"base effect: the previous day ({fmt_num(prev_v)}) was already "
                     f"{abs(prev_v / base - 1) * 100:.0f}% {'above' if prev_v > base else 'below'} its own trailing 7-day average ({fmt_num(base)})")
    if own > 0:
        vs = (last_v / own - 1) * 100
        if abs(vs) >= 30:
            parts.append(f"the latest day is {abs(vs):.0f}% {'above' if vs > 0 else 'below'} its trailing 7-day average ({fmt_num(own)}), "
                         f"so it is {'a genuine spike' if vs > 0 else 'a genuine drop'} and not only a rebound")
        elif not parts:
            parts.append(f"the latest day is close to its trailing 7-day average ({fmt_num(own)}), "
                         f"so the swing mostly reflects an unusual previous day")
    rec = df.tail(90)
    wd_mean = rec.assign(wd=rec["date"].dt.dayofweek).groupby("wd")["value"].mean()
    d_last, d_prev = df["date"].iloc[-1].dayofweek, df["date"].iloc[-2].dayofweek
    if d_last in wd_mean.index and d_prev in wd_mean.index and wd_mean[d_prev] > 0:
        wd = (wd_mean[d_last] / wd_mean[d_prev] - 1) * 100
        if abs(wd) >= 20:
            parts.append(f"weekday effect: {WEEKDAYS[d_last]} is typically {abs(wd):.0f}% {'higher' if wd > 0 else 'lower'} than {WEEKDAYS[d_prev]}")
    return "; ".join(parts) if parts else None


def _why_window(df, n, ch, mode):
    """Explain a big n-day window move: vs a longer baseline and whether one day drives it."""
    if df is None or len(df) < 2 * n + 30:
        return None
    v = df["value"]
    cur = v.tail(n)
    parts = []
    base = v.iloc[-(2 * n + 90):-n]                  # up to ~90 days before the current window
    if base.mean() > 0:
        vs = (cur.mean() / base.mean() - 1) * 100
        if abs(vs) >= 30:
            parts.append(f"against a longer baseline ({len(base)} days before) the window is still {abs(vs):.0f}% "
                         f"{'above' if vs > 0 else 'below'} normal, so it is {'a real surge' if vs > 0 else 'a real slowdown'}")
        else:
            parts.append(f"base effect: the comparison window was unusually {'weak' if ch > 0 else 'strong'}; "
                         f"versus the longer baseline the current level is only {vs:+.0f}%")
    if mode == "sum" and cur.sum() > 0 and cur.max() / cur.sum() >= 2.5 / n:
        d = df["date"].iloc[len(df) - n + int(np.argmax(cur.values))]
        parts.append(f"one day ({d.strftime('%b %d')}) contributes {cur.max() / cur.sum() * 100:.0f}% of the window, so the move is concentrated")
    return "; ".join(parts) if parts else None


def build_insights():
    out = []                                              # (tone, html)
    day = last_day.strftime("%b %d, %Y")

    # 1) Size of the activity base
    _, ch30 = window_sum(tx, 30)
    w, tone = change_phrase(ch30)
    out.append((tone, f"<b>{fmt_num(tx['value'].sum())}</b> transactions have been processed on Ink since {first_day.strftime('%b %d, %Y')}"
                      + (f" — the last 30 days are {w} vs the 30 days before." if w else ".")))

    # 2) Transactions, last 7 days
    t7, t7ch = window_sum(tx, 7)
    w, tone = change_phrase(t7ch)
    if t7 is not None:
        out.append((tone, f"<b>{fmt_num(t7)}</b> transactions in the last 7 days" + (f" ({w} vs the previous 7 days)." if w else ".")))

    # 3) Momentum (7-day vs 30-day average)
    a7, _ = window_avg(tx, 7)
    a30, _ = window_avg(tx, 30)
    if a7 is not None and a30:
        ratio = a7 / a30
        if ratio >= 1.10:
            out.append(("up", f"Transaction activity is <b>accelerating</b>: the 7-day average ({fmt_num(a7)}/day) is "
                              f"{abs(ratio - 1) * 100:.0f}% above the 30-day average ({fmt_num(a30)}/day)."))
        elif ratio <= 0.90:
            out.append(("down", f"Transaction activity is <b>cooling</b>: the 7-day average ({fmt_num(a7)}/day) is "
                                f"{abs(1 - ratio) * 100:.0f}% below the 30-day average ({fmt_num(a30)}/day)."))

    # 4) Active addresses
    if daa is not None:
        d_last, d_ch = last_vs_prev(daa)
        d7, d7ch = window_avg(daa, 7)
        w, tone = change_phrase(d_ch)
        txt = f"<b>{fmt_num(d_last)}</b> addresses were active on {day}" + (f" ({w} vs the day before)" if w else "")
        w7, _ = change_phrase(d7ch)
        txt += (f"; the 7-day average is {fmt_num(d7)}/day" + (f" ({w7} vs the prior week)." if w7 else ".")) if d7 is not None else "."
        out.append((tone, txt))

    # 5) Intensity: transactions per active address
    if "txsPerActive" in series and len(tx) >= 14 and daa is not None:
        m = tx.merge(daa, on="date", suffixes=("_tx", "_act")).tail(14)
        if len(m) == 14 and m["value_act"].iloc[:7].sum() > 0 and m["value_act"].iloc[7:].sum() > 0:
            cur = m["value_tx"].iloc[7:].sum() / m["value_act"].iloc[7:].sum()
            prv = m["value_tx"].iloc[:7].sum() / m["value_act"].iloc[:7].sum()
            w, tone = change_phrase(pct(cur, prv))
            out.append((tone, f"Each active address made <b>{cur:,.1f}</b> transactions per day on average over the last 7 days"
                              + (f" ({w} vs the previous week)." if w else ".")))

    # 6) Records
    for label, s_ in (("daily transactions", tx), ("daily active addresses", daa)):
        if s_ is None or s_.empty:
            continue
        top = s_.loc[s_["value"].idxmax()]
        if top["date"] >= last_day - pd.Timedelta(days=6):
            out.append(("up", f"🏆 <b>New all-time high</b> in {label}: <b>{fmt_num(top['value'])}</b> on {top['date'].strftime('%b %d, %Y')}."))
    top = tx.loc[tx["value"].idxmax()]
    t_last, _ = last_vs_prev(tx)
    if top["date"] < last_day - pd.Timedelta(days=6) and t_last is not None:
        out.append(("neutral", f"All-time peak of daily transactions: <b>{fmt_num(top['value'])}</b> on {top['date'].strftime('%b %d, %Y')}; "
                               f"the latest day is {t_last / top['value'] * 100:.0f}% of that level."))

    # 7) Fees
    if fees_usd is not None and not fees_usd.empty:
        f7, f7ch = window_sum(fees_usd, 7)
        if f7 is not None:
            w, tone = change_phrase(f7ch)
            out.append((tone, f"Users paid <b>{usd_compact(f7)}</b> in fees over the last 7 days"
                              + (f" ({w} vs the previous 7 days)" if w else "")
                              + (f"; the average fee on the latest day was <b>{usd_small(fee_per_tx_last(fees_usd))}</b> per transaction." if fee_per_tx_last(fees_usd) is not None else ".")))

    # 8) Weekday pattern (last 90 days)
    rec = tx.tail(90)
    if len(rec) >= 28:
        g = rec.assign(wd=rec["date"].dt.dayofweek).groupby("wd")["value"].mean()
        best, worst = g.idxmax(), g.idxmin()
        if g[worst] > 0:
            out.append(("neutral", f"Over the last 90 days, <b>{WEEKDAYS_FULL[best]}</b> is the busiest day "
                                   f"({fmt_num(g[best])} transactions on average) and <b>{WEEKDAYS_FULL[worst]}</b> the quietest "
                                   f"({fmt_num(g[worst])}) — a {((g[best] / g[worst]) - 1) * 100:.0f}% gap."))
    out.sort(key=lambda x: 0 if "🏆" in x[1] else 1)         # record-high news goes first
    return out


def build_large_moves():
    """(tone, headline_html, why) for every headline indicator with |change| >= LARGE_MOVE_PCT."""
    out = []

    def add(ch, headline, why):
        if ch is None or pd.isna(ch) or abs(ch) < LARGE_MOVE_PCT:
            return
        out.append(("up" if ch > 0 else "down", f"{headline} — <b>{ch:+.0f}%</b>", why))

    for n in (7, 30):
        v, ch = window_sum(tx, n)
        add(ch, f"Transactions, last {n} days ({fmt_num(v)})", _why_window(tx, n, ch, "sum"))
    v, ch = ytd_sum(tx)
    if v is not None and ch is not None and abs(ch) >= LARGE_MOVE_PCT and ch > -100:
        end = tx["date"].max()
        add(ch, f"Transactions, year to date ({fmt_num(v)})",
            f"compared with {fmt_num(v / (1 + ch / 100))} in the same period of {end.year - 1}"
            + ("; a much smaller comparison base amplifies the percentage." if ch > 0 else "."))
    for n in (7, 30):
        v, ch = window_avg(tx, n)
        add(ch, f"Transactions, {n}D average ({fmt_num(v)}/day)", _why_window(tx, n, ch, "avg"))
    v, ch = last_vs_prev(tx)
    add(ch, f"Transactions, latest day ({fmt_num(v)})", _why_last(tx, ch))

    if daa is not None:
        for n in (7, 30):
            v, ch = window_avg(daa, n)
            add(ch, f"Active addresses, {n}D average ({fmt_num(v)}/day)", _why_window(daa, n, ch, "avg"))
        v, ch = last_vs_prev(daa)
        add(ch, f"Active addresses, latest day ({fmt_num(v)})", _why_last(daa, ch))
    if "txsPerActive" in series:
        tpa_ = series["txsPerActive"][0]
        v, ch = last_vs_prev(tpa_)
        add(ch, f"Transactions per address, latest day ({v:,.2f})" if v is not None else "Transactions per address",
            _why_last(tpa_, ch))
    if fees_usd is not None:
        for n in (7, 30):
            v, ch = window_sum(fees_usd, n)
            add(ch, f"Fees paid, last {n} days ({usd_compact(v)})", _why_window(fees_usd, n, ch, "sum"))

    out.sort(key=lambda x: -abs(float(x[1].split("<b>")[-1].split("%")[0])))
    return out


def render_insights():
    insights = build_insights()
    large_moves = build_large_moves()
    items = "".join(
        f'<li style="margin:6px 0;"><span style="color:{TONE_STYLE[t][1]}; font-weight:700;">{TONE_STYLE[t][0]}</span> {txt}</li>'
        for t, txt in insights
    )
    if large_moves:
        lm_items = "".join(
            f'<li style="margin:8px 0;"><span style="color:{TONE_STYLE[t][1]}; font-weight:700;">{TONE_STYLE[t][0]}</span> {head}'
            + (f'<div style="font-size:13.5px; color:#4b5563; margin-left:18px;">Why: {why}.</div>' if why else
               '<div style="font-size:13.5px; color:#4b5563; margin-left:18px;">Why: no single driver stands out in the data.</div>')
            + "</li>"
            for t, head, why in large_moves
        )
        lm_block = (f'<div style="border-top:1px dashed #b99cf9; margin-top:10px; padding-top:8px;">'
                    f'<div style="font-weight:700; font-size:16px;">⚠️ Large moves (±{LARGE_MOVE_PCT:.0f}% or more) — what is behind them</div>'
                    f'<ul style="list-style:none; padding-left:0; margin:6px 0 4px 0;">{lm_items}</ul>'
                    f'<div style="font-size:12px; color:#6b7280;">Explanations show what moved in the data (base effect, outlier days, weekday pattern); '
                    f'they do not identify real-world causes such as campaigns or incentives.</div></div>')
    else:
        lm_block = ('<div style="border-top:1px dashed #b99cf9; margin-top:10px; padding-top:8px; font-size:13.5px; color:#6b7280;">'
                    f'No headline indicator moved by ±{LARGE_MOVE_PCT:.0f}% or more.</div>')
    with insights_box:
        st.markdown(
            f"""
        <div style="background:#F1EAFE; border:1px solid #d9c8fb; border-left:6px solid #7132f5;
                    border-radius:10px; padding:14px 20px; margin-top:12px; color:#1a1a1a; font-size:15.5px; line-height:1.55;">
            <div style="font-weight:700; font-size:18px; margin-bottom:4px;">📰 Key Insights — latest complete day: {last_day.strftime('%Y-%m-%d')} (UTC)</div>
            <ul style="list-style:none; padding-left:0; margin:6px 0 4px 0;">{items}</ul>
            {lm_block}
            <div style="font-size:12px; color:#6b7280; margin-top:8px;">Auto-generated from the daily data; independent of the Time Frame and Range filters below.</div>
        </div>
        """,
            unsafe_allow_html=True,
        )


# ============================================================
# --- KPIs ---
# ============================================================
if tx is not None:
    first_day, last_day = tx.iloc[0]["date"], tx.iloc[-1]["date"]
    st.markdown(f"##### Latest complete day: {last_day.strftime('%Y-%m-%d')} (UTC)")
    st.caption(f"Data available from {first_day.strftime('%Y-%m-%d')} to {last_day.strftime('%Y-%m-%d')} "
               f"({len(tx):,} days).")
    render_insights()

# Row 1 — transaction totals
r1 = st.columns(4)
kpi_card(r1[0], "Total Transactions", fmt_num(tx["value"].sum()) if tx is not None else "N/A", "Since first data day")
v, ch = window_sum(tx, 7)
card_chg(r1[1], "Transactions (7d)", fmt_num(v), ch, "previous 7d")
v, ch = window_sum(tx, 30)
card_chg(r1[2], "Transactions (30d)", fmt_num(v), ch, "previous 30d")
v, ch = ytd_sum(tx)
card_chg(r1[3], "Transactions (ytd)", fmt_num(v), ch, "same period last year")

# Row 2 — daily transaction levels
r2 = st.columns(4)
v, ch = last_vs_prev(tx)
card_chg(r2[0], "Transactions (last day)", fmt_num(v), ch, "previous day")
v, ch = window_avg(tx, 7)
card_chg(r2[1], "7D Avg / Day", fmt_num(v), ch, "previous 7d")
v, ch = window_avg(tx, 30)
card_chg(r2[2], "30D Avg / Day", fmt_num(v), ch, "previous 30d")
if tx is not None:
    peak = tx.loc[tx["value"].idxmax()]
    kpi_card(r2[3], "Peak Daily Transactions", fmt_num(peak["value"]), f"📅 {peak['date'].strftime('%b %d, %Y')}")
else:
    kpi_card(r2[3], "Peak Daily Transactions", "N/A")

# Row 3 — addresses
r3 = st.columns(4)
v, ch = last_vs_prev(daa)
card_chg(r3[0], "Active Addresses (last day)", fmt_num(v), ch, "previous day")
tpa = series["txsPerActive"][0] if "txsPerActive" in series else None
v, ch = last_vs_prev(tpa)
card_chg(r3[1], "Transaction per Address (last day)", f"{v:,.2f}" if v is not None else "N/A", ch, "previous day")
v, ch = window_avg(daa, 7)
card_chg(r3[2], "Avg Daily Active Address (7d)", fmt_num(v), ch, "previous 7d")
v, ch = window_avg(daa, 30)
card_chg(r3[3], "Avg Daily Active Address (30d)", fmt_num(v), ch, "previous 30d")

# Row 4 — fees
r4 = st.columns(4)
kpi_card(r4[0], "Total Fees Paid ($)", usd_compact(fees_usd["value"].sum()) if fees_usd is not None else "N/A", "Since first data day")
kpi_card(r4[1], "Total Fees Paid (ETH)", eth_fmt(fees_eth["value"].sum()) if fees_eth is not None else "N/A", "Since first data day")
kpi_card(r4[2], "Avg Fee per Transaction ($)", usd_small(fee_per_tx_last(fees_usd)), "Latest day")
kpi_card(r4[3], "Avg Fee per Transaction (ETH)", eth_fmt(fee_per_tx_last(fees_eth), 8), "Latest day")

st.markdown("---")


# ============================================================
# --- Chart helpers ---
# ============================================================
def aggregate(df: pd.DataFrame, agg: str) -> pd.DataFrame:
    """Combine daily rows into weekly / monthly buckets (incomplete last bucket is dropped)."""
    if gran == "Daily" or df.empty:
        return df
    s = df.set_index("date")["value"]
    if gran == "Weekly":
        rs = s.resample("W-MON", label="left", closed="left")
        span_end = lambda d: d + pd.Timedelta(days=6)
    else:
        rs = s.resample("MS")
        span_end = lambda d: d + pd.offsets.MonthEnd(0)
    out = getattr(rs, agg)().dropna().reset_index()
    out.columns = ["date", "value"]
    last_date = df["date"].max()
    out = out[out["date"].map(span_end) <= last_date]
    return out.reset_index(drop=True)


def in_range(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    sel = RANGES[range_choice]
    end = df["date"].max()
    if sel is None:
        return df
    if sel == "Q":                                   # current calendar quarter to date
        start = pd.Timestamp(year=end.year, month=3 * ((end.month - 1) // 3) + 1, day=1)
        return df[df["date"] >= start]
    return df[df["date"] > end - timedelta(days=sel)]


def style_layout(fig, title, units=None, legend=False):
    """Title top-left; legend (when shown) centred and pushed down, clear of the title."""
    fig.update_layout(
        title=dict(text=title, x=0.0, xanchor="left", y=0.97, yanchor="top"),
        height=380 if legend else 340,
        margin=dict(l=10, r=10, t=100 if legend else 60, b=10),
        yaxis_title=units, xaxis_title=None, hovermode="x unified", plot_bgcolor="white",
        showlegend=legend,
        legend=dict(orientation="h", x=0.5, xanchor="center", y=1.04, yanchor="bottom"),
    )
    return fig


def metric_chart(sid: str):
    cfg = CHARTS[sid]
    daily, units = series[sid]
    df = in_range(aggregate(daily, cfg["agg"]))
    base_title = cfg.get("title_agg", cfg["title"]) if gran != "Daily" else cfg["title"]
    title = base_title if gran == "Daily" else f"{base_title} — {gran}"
    fig = go.Figure()
    if cfg["kind"] == "bar":
        fig.add_trace(go.Bar(x=df["date"], y=df["value"], marker_color=ACCENT, name=cfg["title"]))
    elif cfg["kind"] == "area":
        fig.add_trace(go.Scatter(x=df["date"], y=df["value"], mode="lines", fill="tozeroy",
                                 line=dict(color=ACCENT, width=2), fillcolor=ACCENT_FILL, name=cfg["title"]))
    else:
        # pure "line" chart kind -> black line, per request
        fig.add_trace(go.Scatter(x=df["date"], y=df["value"], mode="lines",
                                 line=dict(color=MA_COLOR, width=2), name=cfg["title"]))
    legend = bool(show_ma and cfg["ma"])
    if legend and len(df) > MA_WINDOW:
        # moving-average overlay on bar charts -> black line, per request
        fig.add_trace(go.Scatter(x=df["date"], y=df["value"].rolling(MA_WINDOW).mean(), mode="lines",
                                 line=dict(color=MA_COLOR, width=2), name=f"{MA_WINDOW}-period MA"))
    return style_layout(fig, title, units, legend=legend)


WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def weekday_tx_chart():
    wd = in_range(series["txcount"][0]).copy()
    if wd.empty:
        return None
    wd["wd"] = wd["date"].dt.dayofweek
    g = wd.groupby("wd")["value"].mean().reindex(range(7))
    fig = go.Figure(go.Bar(x=WEEKDAYS, y=g.values, marker_color=ACCENT,
                           text=[fmt_num(x) if pd.notna(x) else "" for x in g.values], textposition="outside"))
    return style_layout(fig, "Average Transactions by Day of Week (Selected Range)", "Transactions")


def weekday_fee_chart():
    """Average fee per transaction (USD) by weekday = total fees / total transactions of that weekday."""
    if fees_usd is None or tx is None:
        return None
    m = in_range(fees_usd.merge(tx, on="date", suffixes=("_fee", "_tx")))
    if m.empty:
        return None
    m = m.assign(wd=m["date"].dt.dayofweek)
    g = m.groupby("wd")[["value_fee", "value_tx"]].sum().reindex(range(7))
    avg = g["value_fee"] / g["value_tx"].where(g["value_tx"] > 0)
    fig = go.Figure(go.Bar(x=WEEKDAYS, y=avg.values, marker_color=ACCENT,
                           text=[usd_small(x) if pd.notna(x) else "" for x in avg.values], textposition="outside"))
    return style_layout(fig, "Average Transaction Fees by Day of Week (Selected Range)", "USD per transaction")


# ============================================================
# --- Chart groups ---
# ============================================================
for header, ids in GROUPS:
    present = [i for i in ids if i in series]
    missing = [CHARTS[i]["title"] for i in ids if i not in series]
    if not present:
        continue
    st.subheader(header)
    for i in range(0, len(present), 2):
        cols = st.columns(2)
        for col, sid in zip(cols, present[i:i + 2]):
            with col:
                show_chart(metric_chart(sid))
    if header == "Transactions Analysis" and "txcount" in series:
        wc1, wc2 = st.columns(2)
        with wc1:
            fig = weekday_tx_chart()
            if fig is not None:
                show_chart(fig)
        with wc2:
            fig = weekday_fee_chart()
            if fig is not None:
                show_chart(fig)
    if missing:
        st.caption("Not available from this data source: " + ", ".join(missing))

st.markdown("---")

# ============================================================
# --- Sources ---
# ============================================================
st.subheader("Sources")
st.markdown(
    """
| Section | Data | Source |
|---|---|---|
| KPIs and charts | Transactions, active addresses | [growthepie](https://www.growthepie.com/chains/ink) · `https://api.growthepie.com/v1/metrics/chains/ink/txcount.json`, `.../daa.json` |
| Fee KPIs and fee-by-weekday chart | Fees paid by users (USD and ETH) | growthepie · `https://api.growthepie.com/v1/metrics/chains/ink/fees.json` |
| Derived metrics | Cumulative transactions, transactions per active address, average fee per transaction, weekday patterns, weekly/monthly aggregation, YTD and period-over-period changes | Calculated in this app from the daily growthepie series above |
"""
)
st.caption(
    "Notes: today's partial day is excluded; incomplete weeks/months are dropped for Weekly/Monthly time frames. "
    "'Active Addresses' is averaged per day when aggregated. 'Q' range = current calendar quarter to date. "
    "Period changes compare against the equal-length preceding period (YTD: same dates of the previous year). "
    "'Total ... since first data day' sums the daily values available in the API. "
    "Average fee per transaction = fees paid / transactions for the day."
)

if errors:
    with st.expander("⚠️ Data warnings"):
        for e in errors:
            st.write(f"- {e}")

st.markdown(
    f"""<div style="margin-top:25px; font-size:13px; color:gray;">
Last refreshed: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}</div>""",
    unsafe_allow_html=True,
)
