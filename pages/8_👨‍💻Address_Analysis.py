import requests
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone

from common import (
    ACCENT, ACCENT_FILL, MA_COLOR,
    safe_call, empty_ts, show_chart,
    fmt_num, fmt_pct,
)

# --- Page Config: Tab Title & Icon ---
st.set_page_config(
    page_title="Ink Chain — Address Analysis",
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
        <h1 style="margin: 0;">Ink Chain — Address Analysis</h1>
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

st.markdown(
    """
    <div style="
        background-color: #F1EAFE;
        border-left: 6px solid #7132f5;
        padding: 15px;
        border-radius: 10px;
        margin-top: 15px;
        color: #1a1a1a;
        font-size: 16px;
        line-height: 1.6;
    ">
    This page analyses the <b>users (accounts / addresses)</b> of the <b>Ink</b> chain: how fast the
    account base is growing, how many accounts are active, and how many of those are
    <b>new</b> versus <b>returning</b>. <b>Returning accounts = Active accounts − New accounts.</b>
    Data comes live from the official Ink block explorer statistics service.
    </div>
    """,
    unsafe_allow_html=True
)

# Placeholder for the "Key Insights" headlines: it sits at the top of the page but is filled in
# further down, once the data has been loaded and the KPIs have been computed.
insights_box = st.container()

errors = []


def sc(fn, *args, **kwargs):
    return safe_call(errors, fn, *args, **kwargs)


# ============================================================
# --- Constants ---
# ============================================================
STATS_API = "https://explorer.inkonchain.com/stats-service/api/v1/lines"
START_DATE = "2024-11-01"          # before Ink mainnet launch; leading empty days are trimmed below
ACCENT_LIGHT = "#b99cf9"           # lighter tint of #7132f5, used where two series are stacked
WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


# ============================================================
# --- Data fetchers ---
# ============================================================
@st.cache_data(ttl=3600, show_spinner=False)
def get_line(line_id: str, resolution: str, end_date: str) -> pd.DataFrame:
    """One explorer stats line (accountsGrowth / activeAccounts / newAccounts) -> DataFrame[date, value].

    Buckets flagged `is_approximate` (the still-running day / week) and anything dated today or later
    are dropped, so only complete periods are analysed. `end_date` only keys the cache per day."""
    r = requests.get(
        f"{STATS_API}/{line_id}",
        params={"from": START_DATE, "to": end_date, "resolution": resolution},
        timeout=45, headers={"User-Agent": "ink-dashboard/1.0"},
    )
    r.raise_for_status()
    chart = (r.json() or {}).get("chart") or []
    if not chart:
        return empty_ts()
    df = pd.DataFrame(chart)
    if "date" not in df.columns or "value" not in df.columns:
        return empty_ts()
    if "is_approximate" not in df.columns:
        df["is_approximate"] = False
    df["is_approximate"] = df["is_approximate"].fillna(False).astype(bool)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[~df["is_approximate"]]
    df = df[df["date"].dt.date < datetime.now(timezone.utc).date()]
    return df[["date", "value"]].dropna().sort_values("date").reset_index(drop=True)


def build_frame(resolution: str, end_date: str):
    """Merge the three lines into one table: date, active, new, cum, returning, ret_share (%), growth (%)."""
    parts = {}
    for key, line_id in (("active", "activeAccounts"), ("new", "newAccounts"), ("cum", "accountsGrowth")):
        d = sc(get_line, line_id, resolution, end_date, default=None, label=f"explorer {line_id} ({resolution})")
        if d is None or d.empty:
            return None
        parts[key] = d.rename(columns={"value": key})
    df = parts["active"].merge(parts["new"], on="date").merge(parts["cum"], on="date")
    df = df[df["cum"] > 0].sort_values("date").reset_index(drop=True)      # trim days before the first account
    if df.empty:
        return None
    df["returning"] = (df["active"] - df["new"]).clip(lower=0)             # Returning = Active - New (never negative)
    df["ret_share"] = (df["returning"] / df["active"].where(df["active"] > 0)) * 100
    df["growth"] = df["cum"].pct_change() * 100                            # period-over-period growth of total accounts
    return df


# ============================================================
# --- Filters (each one a separate dropdown) ---
# ============================================================
RANGES = {"7D": 7, "30D": 30, "90D": 90, "Q (current quarter)": "Q", "180D": 180, "1Y": 365, "All": None}

f1, f2, f3, _ = st.columns([1, 1, 1, 3])
with f1:
    gran = st.selectbox("Time Frame", ["Daily", "Weekly"], index=0)
with f2:
    range_choice = st.selectbox("Range", list(RANGES.keys()), index=len(RANGES) - 1)
with f3:
    show_ma = st.selectbox("Moving Average", ["On", "Off"], index=0) == "On"

st.markdown("---")


# ============================================================
# --- Load data ---
# ============================================================
today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

with st.spinner("Loading Ink account data from the explorer..."):
    D = build_frame("DAY", today_str)                  # daily frame: always needed (KPIs, weekday patterns, monthly table)
    W = build_frame("WEEK", today_str) if gran == "Weekly" else None

if D is None:
    st.warning("Account data could not be loaded right now. See the data warnings below.")
    if errors:
        with st.expander("⚠️ Data warnings", expanded=True):
            for e in errors:
                st.write(f"- {e}")
    st.stop()

gran_used = gran
base = D
if gran == "Weekly":
    if W is not None:
        base = W
    else:
        gran_used = "Daily"
        st.warning("Weekly data could not be loaded, so the charts below fall back to the Daily time frame.")

MA_WINDOW = {"Daily": 7, "Weekly": 4}[gran_used]


# ============================================================
# --- KPI helpers (all on the daily frame D) ---
# ============================================================
def ser(col):
    return D[["date", col]].rename(columns={col: "value"})


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


def share_window(n):
    """Returning share (%) over the last n days, and its change in percentage points vs the n days before."""
    if len(D) < 2 * n:
        return None, None
    a_cur, a_prv = D["active"].tail(n).sum(), D["active"].iloc[-2 * n:-n].sum()
    if not a_cur or not a_prv:
        return None, None
    cur = D["returning"].tail(n).sum() / a_cur * 100
    prv = D["returning"].iloc[-2 * n:-n].sum() / a_prv * 100
    return cur, cur - prv


def pp(x):
    return f"{x:+.2f} pp" if x is not None and not pd.isna(x) else None


def pct_str(x):
    return f"{x:.2f}%" if x is not None and not pd.isna(x) else "N/A"


def peak(df):
    row = df.loc[df["value"].idxmax()]
    return fmt_num(row["value"]), row["date"].strftime("%Y-%m-%d")


# ============================================================
# --- KPIs ---
# ============================================================
first_day, last_day = D.iloc[0]["date"], D.iloc[-1]["date"]
st.markdown(f"##### Latest complete day: {last_day.strftime('%Y-%m-%d')} (UTC)")
st.caption(f"Data available from {first_day.strftime('%Y-%m-%d')} to {last_day.strftime('%Y-%m-%d')} "
           f"({len(D):,} days).")

new_s, act_s, ret_s = ser("new"), ser("active"), ser("returning")

# Row 1 — account base
r1 = st.columns(4)
cum_now = D["cum"].iloc[-1]
cum_30 = D["cum"].iloc[-31] if len(D) > 30 else None
r1[0].metric("Total Accounts", f"{cum_now:,.0f}", dlt(pct(cum_now, cum_30)),
             help="Cumulative number of accounts. The delta is the growth of the account base over the last 30 days.")
v, ch = window_sum(new_s, 7)
r1[1].metric("New Accounts (7d)", fmt_num(v), dlt(ch))
v, ch = window_sum(new_s, 30)
r1[2].metric("New Accounts (30d)", fmt_num(v), dlt(ch))
v, ch = ytd_sum(new_s)
r1[3].metric("New Accounts (ytd)", fmt_num(v), dlt(ch))

# Row 2 — new accounts
r2 = st.columns(4)
v, ch = last_vs_prev(new_s)
r2[0].metric("New Accounts (last day)", fmt_num(v), dlt(ch))
v, ch = window_avg(new_s, 7)
r2[1].metric("New Accounts — 7D Avg / Day", fmt_num(v), dlt(ch))
v, ch = window_avg(new_s, 30)
r2[2].metric("New Accounts — 30D Avg / Day", fmt_num(v), dlt(ch))
pv, pd_ = peak(new_s)
r2[3].metric("Peak Daily New Accounts", pv, pd_, delta_color="off")

# Row 3 — active accounts
r3 = st.columns(4)
v, ch = last_vs_prev(act_s)
r3[0].metric("Active Accounts (last day)", fmt_num(v), dlt(ch))
v, ch = window_avg(act_s, 7)
r3[1].metric("Active Accounts — 7D Avg / Day", fmt_num(v), dlt(ch))
v, ch = window_avg(act_s, 30)
r3[2].metric("Active Accounts — 30D Avg / Day", fmt_num(v), dlt(ch))
pv, pd_ = peak(act_s)
r3[3].metric("Peak Daily Active Accounts", pv, pd_, delta_color="off")

# Row 4 — returning accounts
r4 = st.columns(4)
v, ch = last_vs_prev(ret_s)
r4[0].metric("Returning Accounts (last day)", fmt_num(v), dlt(ch))
last_sh = D["ret_share"].iloc[-1]
prev_sh = D["ret_share"].iloc[-2] if len(D) > 1 else None
r4[1].metric("Returning Share (last day)", pct_str(last_sh),
             pp(last_sh - prev_sh) if prev_sh is not None and not pd.isna(last_sh) and not pd.isna(prev_sh) else None,
             help="Returning accounts as a share of active accounts. The delta is in percentage points vs the previous day.")
v, d = share_window(7)
r4[2].metric("Returning Share (7d)", pct_str(v), pp(d))
v, d = share_window(30)
r4[3].metric("Returning Share (30d)", pct_str(v), pp(d))


# ============================================================
# --- Key Insights (auto-generated headlines, shown at the top of the page) ---
# ============================================================
TONE_STYLE = {
    "up":      ("▲", "#16a34a"),
    "down":    ("▼", "#dc2626"),
    "neutral": ("●", "#6b7280"),
}


def change_phrase(ch, flat=1.0):
    """('up 5.2%' | 'down 3.1%' | 'flat', tone) for a % change; (None, 'neutral') if unavailable."""
    if ch is None or pd.isna(ch):
        return None, "neutral"
    if abs(ch) < flat:
        return "flat", "neutral"
    return (f"up {abs(ch):.1f}%" if ch > 0 else f"down {abs(ch):.1f}%"), ("up" if ch > 0 else "down")


def build_insights():
    """Headline sentences computed from the daily data. Independent of the Time Frame / Range filters."""
    out = []                                         # (tone, html)
    day = last_day.strftime("%b %d, %Y")

    # 1) Size of the account base
    g30 = pct(cum_now, cum_30)
    w, tone = change_phrase(g30, flat=0.05)
    out.append((tone, f"<b>{cum_now:,.0f}</b> accounts in total on Ink"
                      + (f" — the account base is {w} over the last 30 days." if w else ".")))

    # 2) New accounts, last 7 days
    n7, n7ch = window_sum(new_s, 7)
    w, tone = change_phrase(n7ch)
    if n7 is not None:
        out.append((tone, f"<b>{fmt_num(n7)}</b> new accounts joined in the last 7 days"
                          + (f" ({w} vs the previous 7 days)." if w else ".")))

    # 3) Momentum of new-account acquisition (7-day average vs 30-day average)
    a7n, _ = window_avg(new_s, 7)
    a30n, _ = window_avg(new_s, 30)
    if a7n is not None and a30n:
        ratio = a7n / a30n
        if ratio >= 1.10:
            out.append(("up", f"New-account growth is <b>accelerating</b>: the 7-day average "
                              f"({fmt_num(a7n)}/day) is {abs(ratio - 1) * 100:.0f}% above the 30-day average ({fmt_num(a30n)}/day)."))
        elif ratio <= 0.90:
            out.append(("down", f"New-account growth is <b>cooling</b>: the 7-day average "
                                f"({fmt_num(a7n)}/day) is {abs(1 - ratio) * 100:.0f}% below the 30-day average ({fmt_num(a30n)}/day)."))

    # 3b) Active accounts, latest day and weekly average
    a_last, a_ch = last_vs_prev(act_s)
    a7, a7ch = window_avg(act_s, 7)
    w, tone = change_phrase(a_ch)
    if a_last is not None:
        text = f"<b>{fmt_num(a_last)}</b> accounts were active on {day}"
        text += f" ({w} vs the day before)" if w else ""
        w7, _ = change_phrase(a7ch)
        if a7 is not None:
            text += f"; the 7-day average is {fmt_num(a7)}/day" + (f" ({w7} vs the prior week)." if w7 else ".")
        else:
            text += "."
        out.append((tone, text))

    # 4) Retention
    sh7, d7 = share_window(7)
    if sh7 is not None:
        tone = "up" if (d7 is not None and d7 >= 0.5) else "down" if (d7 is not None and d7 <= -0.5) else "neutral"
        who = "mostly returning users" if sh7 >= 50 else "mostly newcomers"
        out.append((tone, f"<b>{sh7:.1f}%</b> of active accounts over the last 7 days were returning users "
                          f"({d7:+.1f} pp vs the previous week) — the active base is {who}."))

    # 5) Records
    for label, s in (("daily active accounts", act_s), ("daily new accounts", new_s)):
        top = s.loc[s["value"].idxmax()]
        if top["date"] >= last_day - pd.Timedelta(days=6):
            out.append(("up", f"🏆 <b>New all-time high</b> in {label}: <b>{fmt_num(top['value'])}</b> "
                              f"on {top['date'].strftime('%b %d, %Y')}."))
    top = act_s.loc[act_s["value"].idxmax()]
    if top["date"] < last_day - pd.Timedelta(days=6) and a_last is not None:
        out.append(("neutral", f"All-time peak of daily active accounts: <b>{fmt_num(top['value'])}</b> on "
                               f"{top['date'].strftime('%b %d, %Y')}; the latest day is {a_last / top['value'] * 100:.0f}% of that level."))

    # 6) Weekday pattern (last 90 days)
    recent = D.tail(90)
    if len(recent) >= 28:
        g = recent.assign(wd=recent["date"].dt.dayofweek).groupby("wd")["active"].mean()
        best, worst = g.idxmax(), g.idxmin()
        if g[worst] > 0:
            out.append(("neutral", f"Over the last 90 days, <b>{WEEKDAYS[best]}</b> is the busiest day "
                                   f"({fmt_num(g[best])} active accounts on average) and <b>{WEEKDAYS[worst]}</b> the quietest "
                                   f"({fmt_num(g[worst])}) — a {((g[best] / g[worst]) - 1) * 100:.0f}% gap."))
    return out


insights = build_insights()
with insights_box:
    items = "".join(
        f'<li style="margin:6px 0;"><span style="color:{TONE_STYLE[t][1]}; font-weight:700;">{TONE_STYLE[t][0]}</span> {txt}</li>'
        for t, txt in insights
    )
    st.markdown(
        f"""
        <div style="background:#F1EAFE; border:1px solid #d9c8fb; border-left:6px solid #7132f5;
                    border-radius:10px; padding:14px 20px; margin-top:12px; color:#1a1a1a; font-size:15.5px; line-height:1.55;">
            <div style="font-weight:700; font-size:18px; margin-bottom:4px;">📰 Key Insights — latest complete day: {last_day.strftime('%Y-%m-%d')} (UTC)</div>
            <ul style="list-style:none; padding-left:0; margin:6px 0 4px 0;">{items}</ul>
            <div style="font-size:12px; color:#6b7280;">Auto-generated from the daily data; independent of the Time Frame and Range filters below.</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

st.markdown("---")


# ============================================================
# --- Chart helpers ---
# ============================================================
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


view = in_range(base)          # selected time frame + range
view_daily = in_range(D)       # selected range, always daily (weekday patterns)


def tf_title(title: str) -> str:
    return title if gran_used == "Daily" else f"{title} — {gran_used}"


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


def bar_chart(title, col, units):
    """Purple bars + black moving-average line."""
    df = view
    fig = go.Figure(go.Bar(x=df["date"], y=df[col], marker_color=ACCENT, name=title))
    legend = bool(show_ma)
    if legend and len(df) > MA_WINDOW:
        fig.add_trace(go.Scatter(x=df["date"], y=df[col].rolling(MA_WINDOW).mean(), mode="lines",
                                 line=dict(color=MA_COLOR, width=2), name=f"{MA_WINDOW}-period MA"))
    return style_layout(fig, tf_title(title), units, legend=legend)


def area_chart(title, col, units):
    df = view
    fig = go.Figure(go.Scatter(x=df["date"], y=df[col], mode="lines", fill="tozeroy",
                               line=dict(color=ACCENT, width=2), fillcolor=ACCENT_FILL, name=title))
    return style_layout(fig, tf_title(title), units)


def line_chart(title, col, units):
    """Black line."""
    df = view
    fig = go.Figure(go.Scatter(x=df["date"], y=df[col], mode="lines",
                               line=dict(color=MA_COLOR, width=2), name=title))
    return style_layout(fig, tf_title(title), units)


def composition_chart():
    """Active accounts split into returning (purple) and new (light purple)."""
    df = view
    fig = go.Figure()
    fig.add_trace(go.Bar(x=df["date"], y=df["returning"], marker_color=ACCENT, name="Returning"))
    fig.add_trace(go.Bar(x=df["date"], y=df["new"], marker_color=ACCENT_LIGHT, name="New"))
    fig.update_layout(barmode="stack")
    return style_layout(fig, tf_title("Active Accounts: New vs Returning"), "accounts", legend=True)


def weekday_chart(col, title, units):
    """Average of the daily value by weekday over the selected range."""
    if view_daily is None or view_daily.empty:
        return None
    g = view_daily.assign(wd=view_daily["date"].dt.dayofweek).groupby("wd")[col].mean().reindex(range(7))
    fig = go.Figure(go.Bar(x=WEEKDAYS, y=g.values, marker_color=ACCENT,
                           text=[fmt_num(x) if pd.notna(x) else "" for x in g.values], textposition="outside"))
    return style_layout(fig, f"{title} (Selected Range)", units)


def row(left, right):
    c1, c2 = st.columns(2)
    with c1:
        show_chart(left)
    with c2:
        show_chart(right)


# ============================================================
# --- Account Growth ---
# ============================================================
st.subheader("Account Growth")
row(area_chart("Cumulative Accounts", "cum", "accounts"),
    bar_chart("New Accounts", "new", "accounts"))
row(line_chart("Account Base Growth Rate (%)", "growth", "% vs previous period"),
    weekday_chart("new", "Average New Accounts by Day of Week", "New accounts"))

# ============================================================
# --- Active Addresses ---
# ============================================================
st.subheader("Active Addresses")
row(bar_chart("Active Accounts", "active", "accounts"),
    composition_chart())
row(weekday_chart("active", "Average Active Accounts by Day of Week", "Active accounts"),
    weekday_chart("returning", "Average Returning Accounts by Day of Week", "Returning accounts"))

# ============================================================
# --- Retention (Returning Addresses) ---
# ============================================================
st.subheader("Retention (Returning Addresses)")
row(bar_chart("Returning Accounts", "returning", "accounts"),
    line_chart("Returning Share of Active Accounts (%)", "ret_share", "% of active accounts"))

st.markdown("---")

# ============================================================
# --- Monthly summary table ---
# ============================================================
st.subheader("Monthly Summary")

m = D.assign(month=D["date"].dt.to_period("M"))
monthly = m.groupby("month").agg(
    days=("date", "count"),
    new=("new", "sum"),
    active_avg=("active", "mean"),
    returning_avg=("returning", "mean"),
    ret_sum=("returning", "sum"),
    act_sum=("active", "sum"),
    cum_end=("cum", "last"),
).reset_index()
monthly["ret_share"] = monthly["ret_sum"] / monthly["act_sum"].where(monthly["act_sum"] > 0) * 100
monthly["growth"] = monthly["cum_end"].pct_change() * 100
monthly = monthly.sort_values("month", ascending=False)

month_tbl = pd.DataFrame({
    "Month": monthly["month"].astype(str) + monthly["month"].map(
        lambda p: " (partial)" if p == pd.Period(last_day, "M") and last_day != last_day + pd.offsets.MonthEnd(0) else ""),
    "Days": monthly["days"],
    "New Accounts": monthly["new"].map(lambda x: f"{x:,.0f}"),
    "Avg Daily Active": monthly["active_avg"].map(lambda x: f"{x:,.0f}"),
    "Avg Daily Returning": monthly["returning_avg"].map(lambda x: f"{x:,.0f}"),
    "Returning Share": monthly["ret_share"].map(pct_str),
    "Total Accounts (month end)": monthly["cum_end"].map(lambda x: f"{x:,.0f}"),
    "MoM Growth": monthly["growth"].map(lambda x: f"{x:+.2f}%" if pd.notna(x) else "N/A"),
})
st.dataframe(month_tbl, use_container_width=True, hide_index=True)
st.caption("Avg Daily Active / Returning are averages of the daily values in each month (unique monthly actives "
           "are not available from the API). Returning Share = total returning ÷ total active over the month.")

# ============================================================
# --- Detailed data table + download ---
# ============================================================
st.subheader(f"Detailed Data — {gran_used}")

detail = view.sort_values("date", ascending=False)
detail_tbl = pd.DataFrame({
    "Date": detail["date"].dt.strftime("%Y-%m-%d"),
    "Active Accounts": detail["active"].astype("int64"),
    "New Accounts": detail["new"].astype("int64"),
    "Returning Accounts": detail["returning"].astype("int64"),
    "Returning Share (%)": detail["ret_share"].round(2),
    "Total Accounts": detail["cum"].astype("int64"),
    "Growth (%)": detail["growth"].round(3),
})
st.dataframe(detail_tbl, use_container_width=True, hide_index=True)
st.download_button("Download CSV", data=detail_tbl.to_csv(index=False).encode("utf-8"),
                   file_name=f"ink_address_analysis_{gran_used.lower()}.csv", mime="text/csv")

st.markdown("---")

# ============================================================
# --- Sources ---
# ============================================================
st.subheader("Sources")
st.markdown(
    """
| Metric | Meaning | Source |
|---|---|---|
| Cumulative Accounts | Cumulative account growth over time | [Ink Explorer](https://explorer.inkonchain.com) · `.../stats-service/api/v1/lines/accountsGrowth` |
| Active Accounts | Active accounts number per period | Ink Explorer · `.../stats-service/api/v1/lines/activeAccounts` |
| New Accounts | Number of newly added accounts | Ink Explorer · `.../stats-service/api/v1/lines/newAccounts` |
| Returning Accounts, shares, growth rate, weekday patterns, monthly summary | Derived: Returning = Active − New | Calculated in this app from the three series above |
"""
)
st.caption(
    "Notes: the still-running day/week (flagged approximate by the API) is excluded. Time frames are Daily and Weekly "
    "because those are the resolutions the explorer API provides for active accounts; in Weekly mode, active accounts "
    "are unique accounts per week, taken directly from the API. If new accounts exceed active accounts in a period, "
    "returning accounts are shown as 0. 'Q' range = current calendar quarter to date. Period changes compare against "
    "the equal-length preceding period (YTD: same dates of the previous year). "
    "Moving average window: 7 periods (Daily) / 4 periods (Weekly)."
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
