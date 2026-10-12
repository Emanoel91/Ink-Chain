import streamlit as st
import pandas as pd

# ============================================================
# --- Shared style constants ---
# ============================================================
ACCENT = "#7132f5"
ACCENT_FILL = "rgba(113,50,245,0.15)"
MA_COLOR = "#000000"


# ============================================================
# --- Error handling ---
# ============================================================
def safe_call(errors: list, fn, *args, default=None, label: str = None, **kwargs):
    """Call fn(*args, **kwargs); on failure, log a readable message to `errors` and
    return `default` instead of raising, so one broken data source never crashes the page."""
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        name = label or getattr(fn, "__name__", "call")
        errors.append(f"{name}: {e}")
        return default


def empty_ts() -> pd.DataFrame:
    """Empty timeseries placeholder with the shape callers expect (date + value columns)."""
    return pd.DataFrame(columns=["date", "value"])


# ============================================================
# --- Chart / page rendering helpers ---
# ============================================================
def show_chart(fig):
    """Render a Plotly figure full-width; silently does nothing if fig is None."""
    if fig is None:
        return
    st.plotly_chart(fig, use_container_width=True)


def page_header(title: str, logo_url: str):
    """Standard page title row: chain logo + heading, shared across this dashboard's pages."""
    st.markdown(
        f"""
        <div style="display: flex; align-items: center; gap: 15px;">
            <img src="{logo_url}" alt="logo" style="width:60px; height:60px;">
            <h1 style="margin: 0;">{title}</h1>
        </div>
        """,
        unsafe_allow_html=True
    )


def sidebar_controls():
    """Placeholder for shared sidebar controls; currently unused (kept for API parity
    with other pages in this project)."""
    return None


# ============================================================
# --- Formatting helpers ---
# ============================================================
def fmt_num(x, decimals: int = 2) -> str:
    """Compact number formatting: 1,234 / 12.34K / 5.67M / 1.23B."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return "N/A"
    a = abs(x)
    if a >= 1e9:
        return f"{x/1e9:,.{decimals}f}B"
    if a >= 1e6:
        return f"{x/1e6:,.{decimals}f}M"
    if a >= 1e3:
        return f"{x/1e3:,.{decimals}f}K"
    if float(x).is_integer():
        return f"{x:,.0f}"
    return f"{x:,.{decimals}f}"


def fmt_pct(x):
    """Signed percentage formatting: +12.34% / -5.67%. Returns None if no value."""
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    return f"{x:+.2f}%"
