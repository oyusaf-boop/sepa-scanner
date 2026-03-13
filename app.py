import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import anthropic
import requests
import gspread
from google.oauth2.service_account import Credentials
import time
import json
from datetime import datetime, timedelta

st.set_page_config(
    page_title="PRISM Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Inter:wght@400;500;600;700&display=swap');

    /* ── Base ── */
    .stApp { background-color: #080c14; color: #d1d9e6; font-family: 'Inter', sans-serif; }
    .main .block-container { padding: 0.75rem 1.5rem 4rem; max-width: 1600px; }
    [data-testid="stSidebar"] { background-color: #0d1117; border-right: 1px solid #1e2736; }
    footer { display: none !important; }

    /* ── Typography ── */
    h1 { color: #e6edf3 !important; font-family: 'Inter', sans-serif !important;
         font-weight: 700 !important; letter-spacing: -0.5px; }
    h2, h3, h4 { color: #c9d1d9 !important; font-family: 'Inter', sans-serif !important;
                  font-weight: 600 !important; }

    /* ── Tabs ── */
    .stTabs [data-baseweb="tab-list"] {
        background: #0d1117; border-bottom: 1px solid #1e2736; gap: 0;
    }
    .stTabs [data-baseweb="tab"] {
        color: #6e7f96; font-family: 'Inter', sans-serif;
        font-size: 13px; font-weight: 500; padding: 10px 20px;
        border-bottom: 2px solid transparent;
    }
    .stTabs [aria-selected="true"] {
        color: #58a6ff !important; border-bottom: 2px solid #58a6ff !important;
        background: transparent !important;
    }

    /* ── Metrics ── */
    [data-testid="metric-container"] {
        background: #0d1117; border: 1px solid #1e2736;
        border-radius: 6px; padding: 10px 14px;
    }
    [data-testid="stMetricValue"] {
        color: #e6edf3 !important;
        font-family: 'IBM Plex Mono', monospace !important;
        font-size: 20px !important; font-weight: 600 !important;
    }
    [data-testid="stMetricLabel"] { color: #6e7f96 !important; font-size: 11px !important;
                                    text-transform: uppercase; letter-spacing: 0.5px; }
    [data-testid="stMetricDelta"] { font-family: 'IBM Plex Mono', monospace !important;
                                    font-size: 11px !important; }

    /* ── Buttons ── */
    .stButton > button {
        background: #1a2332; color: #58a6ff;
        border: 1px solid #2a3a52; border-radius: 5px;
        font-family: 'Inter', sans-serif; font-size: 13px;
        font-weight: 500; padding: 6px 16px; transition: all 0.15s;
    }
    .stButton > button:hover {
        background: #1f6feb; color: white; border-color: #1f6feb;
    }
    .stButton > button[kind="primary"] {
        background: #1f6feb; color: white; border-color: #1f6feb;
    }

    /* ── Terminal Panel ── */
    .term-panel {
        background: #0d1117; border: 1px solid #1e2736;
        border-radius: 6px; padding: 14px 16px; margin-bottom: 10px;
        font-family: 'IBM Plex Mono', monospace;
    }
    .term-panel-header {
        font-size: 10px; font-weight: 600; color: #6e7f96;
        text-transform: uppercase; letter-spacing: 1.5px;
        border-bottom: 1px solid #1e2736; padding-bottom: 8px; margin-bottom: 10px;
    }
    .term-row {
        display: flex; justify-content: space-between;
        align-items: center; padding: 3px 0;
        border-bottom: 1px solid #111820; font-size: 12px;
    }
    .term-label { color: #6e7f96; }
    .term-val   { color: #e6edf3; font-weight: 600; }
    .term-pass  { color: #3fb950; font-weight: 700; }
    .term-fail  { color: #f85149; font-weight: 700; }
    .term-warn  { color: #d29922; font-weight: 700; }

    /* ── Verdict ── */
    .verdict-box {
        padding: 12px 20px; border-radius: 5px;
        font-size: 15px; font-weight: 700; text-align: center;
        font-family: 'IBM Plex Mono', monospace; letter-spacing: 2px;
        text-transform: uppercase;
    }
    .verdict-buy   { background:#061810; color:#3fb950; border:1px solid #238636; }
    .verdict-wait  { background:#1a1200; color:#d29922; border:1px solid #9e6a03; }
    .verdict-watch { background:#060f1e; color:#58a6ff; border:1px solid #1f6feb; }
    .verdict-avoid { background:#160808; color:#f85149; border:1px solid #b91c1c; }

    /* ── Ticker header bar ── */
    .ticker-header {
        display: flex; align-items: baseline; gap: 16px;
        padding: 10px 0 6px; border-bottom: 1px solid #1e2736; margin-bottom: 12px;
    }
    .ticker-symbol {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 28px; font-weight: 700; color: #e6edf3;
    }
    .ticker-name   { font-size: 13px; color: #6e7f96; }
    .ticker-price  {
        font-family: 'IBM Plex Mono', monospace;
        font-size: 26px; font-weight: 600; color: #e6edf3; margin-left: auto;
    }
    .ticker-chg-pos { color: #3fb950; font-family: 'IBM Plex Mono', monospace;
                      font-size: 14px; font-weight: 600; }
    .ticker-chg-neg { color: #f85149; font-family: 'IBM Plex Mono', monospace;
                      font-size: 14px; font-weight: 600; }
    .ticker-sector { font-size: 11px; color: #58a6ff; background: #061828;
                     padding: 2px 8px; border-radius: 3px; border: 1px solid #1a3a5c; }

    /* ── Score badges ── */
    .score-badge {
        display: inline-block; font-family: 'IBM Plex Mono', monospace;
        font-size: 11px; font-weight: 700; padding: 2px 7px;
        border-radius: 3px; letter-spacing: 0.5px;
    }
    .badge-green { background:#0d2f1a; color:#3fb950; border:1px solid #238636; }
    .badge-amber { background:#1f1500; color:#d29922; border:1px solid #9e6a03; }
    .badge-red   { background:#1e0a0a; color:#f85149; border:1px solid #b91c1c; }
    .badge-blue  { background:#06101e; color:#58a6ff; border:1px solid #1f6feb; }

    /* ── GF boxes ── */
    .gf-box {
        background:#0d1117; border:1px solid #1e2736; border-radius:5px;
        padding:10px 12px; margin:4px 0;
    }
    .gf-letter { font-size:18px; font-weight:700; font-family:'IBM Plex Mono',monospace;
                 margin-right:6px; }
    .gf-pass { color:#3fb950; }
    .gf-fail { color:#f85149; }
    .gf-warn { color:#d29922; }

    /* ── Market badge ── */
    .market-bull { background:#061810; color:#3fb950; border:1px solid #238636;
                   border-radius:4px; padding:6px 12px; font-weight:700;
                   font-family:'IBM Plex Mono',monospace; font-size:12px; display:inline-block; }
    .market-bear { background:#160808; color:#f85149; border:1px solid #b91c1c;
                   border-radius:4px; padding:6px 12px; font-weight:700;
                   font-family:'IBM Plex Mono',monospace; font-size:12px; display:inline-block; }
    .market-neutral { background:#1a1200; color:#d29922; border:1px solid #9e6a03;
                      border-radius:4px; padding:6px 12px; font-weight:700;
                      font-family:'IBM Plex Mono',monospace; font-size:12px; display:inline-block; }

    /* ── AI box ── */
    .ai-box {
        background:#0a0d14; border:1px solid #2a1f4e; border-radius:5px;
        padding:18px 20px; font-family:'IBM Plex Mono',monospace; white-space:pre-wrap;
        line-height:1.8; color:#d1d9e6; margin-top:12px; font-size:12px;
    }

    /* ── Dividers ── */
    hr { border-color: #1e2736 !important; }

    /* ── Verdict history ── */
    .verdict-history { background:#0a0d14; border:1px solid #1e2736; border-radius:5px;
                       padding:10px 14px; margin:6px 0; font-family:'IBM Plex Mono',monospace;
                       font-size:11px; }
    .verdict-changed-buy  { color:#3fb950; font-weight:700; }
    .verdict-changed-wait { color:#d29922; font-weight:700; }
    .verdict-changed-avoid{ color:#f85149; font-weight:700; }

    /* ── Watchlist ── */
    .watchlist-row { background:#0d1117; border:1px solid #1e2736; border-radius:5px;
                     padding:8px 12px; margin:3px 0; font-family:'IBM Plex Mono',monospace;
                     font-size:12px; }

    /* ── Inputs ── */
    .stTextInput input, .stNumberInput input {
        background: #0d1117 !important; color: #e6edf3 !important;
        border: 1px solid #1e2736 !important; border-radius: 4px !important;
        font-family: 'IBM Plex Mono', monospace !important;
    }
    .stSelectbox > div { background: #0d1117 !important; border: 1px solid #1e2736 !important; }

    /* ── Chat ── */
    [data-testid="stBottom"] { background-color: #080c14 !important;
                                border-top: 1px solid #1e2736 !important; }
    [data-testid="stBottom"] > div { background-color: #080c14 !important; }
    .stChatInput textarea { background-color: #0d1117 !important; color: #e6edf3 !important;
                            border: 1px solid #1e2736 !important; border-radius: 4px !important;
                            font-family: 'IBM Plex Mono', monospace !important; }

    /* ── Execution panel ── */
    .exec-panel {
        background: #0d1117; border: 1px solid #1e2736; border-radius: 6px;
        padding: 14px 16px;
    }
    .exec-header { font-size: 10px; font-weight: 600; color: #6e7f96;
                   text-transform: uppercase; letter-spacing: 1.5px;
                   padding-bottom: 8px; margin-bottom: 10px;
                   border-bottom: 1px solid #1e2736; }
    .exec-row { display: flex; justify-content: space-between; padding: 4px 0;
                border-bottom: 1px solid #111820; font-size: 13px; }
    .exec-label { color: #6e7f96; font-family: 'IBM Plex Mono', monospace; }
    .exec-val   { color: #e6edf3; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
    .exec-target-2r { color: #3fb950; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
    .exec-target-3r { color: #b9f6ca; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
    .exec-stop  { color: #f85149; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
    .exec-entry { color: #58a6ff; font-family: 'IBM Plex Mono', monospace; font-weight: 600; }
</style>
""", unsafe_allow_html=True)


# ── Google Sheets Config ──────────────────────────────────────
SHEET_ID = "1649nY1N0tbk7R0Ve_uZV0RBU22xqjmpKjhuVaJGSeUs"
SCOPES   = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

@st.cache_resource
def get_gsheet():
    """Connect to Google Sheets using service account credentials from Streamlit secrets."""
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        sh = client.open_by_key(SHEET_ID)

        # Ensure worksheets exist
        existing = [ws.title for ws in sh.worksheets()]
        if "Watchlist" not in existing:
            ws = sh.add_worksheet(title="Watchlist", rows=500, cols=10)
            ws.append_row(["Ticker", "Note", "Date Added", "Verdict", "Price",
                           "TT Score", "VCS Score", "GF Score", "Stage", "Pivot"])
        if "History" not in existing:
            wh = sh.add_worksheet(title="History", rows=2000, cols=10)
            wh.append_row(["Ticker", "Date", "Verdict", "Price", "Pivot",
                           "TT Score", "VCS Score", "GF Score", "Market", "Note"])
        return sh
    except Exception as e:
        st.error(f"Google Sheets connection error: {e}")
        return None


# ── Watchlist: Google Sheets backed ──────────────────────────
def wl_load():
    """Load watchlist from Google Sheets into session_state cache."""
    if "watchlist_loaded" not in st.session_state:
        sh = get_gsheet()
        if sh is None:
            st.session_state["watchlist"] = {}
            st.session_state["watchlist_loaded"] = True
            return {}
        try:
            ws = sh.worksheet("Watchlist")
            rows = ws.get_all_records()
            wl = {}
            for r in rows:
                t = r.get("Ticker", "").strip().upper()
                if t:
                    wl[t] = {
                        "note":       r.get("Note", ""),
                        "date_added": r.get("Date Added", ""),
                        "verdict":    r.get("Verdict", ""),
                        "current_price":   r.get("Price", ""),
                        "tt_score":        r.get("TT Score", ""),
                        "vgf_score":       r.get("VCS Score", ""),
                        "gf_score":        r.get("GF Score", ""),
                        "stage":           r.get("Stage", ""),
                        "pivot":           r.get("Pivot", ""),
                    }
            st.session_state["watchlist"] = wl
            st.session_state["watchlist_loaded"] = True
        except Exception as e:
            st.session_state["watchlist"] = {}
            st.session_state["watchlist_loaded"] = True
    return st.session_state.get("watchlist", {})


def wl_add(ticker, note="", verdict="", price="", tt="", vcp="", cs="", stage="", pivot=""):
    """Add ticker to watchlist in Google Sheets."""
    sh = get_gsheet()
    wl = wl_load()
    date_added = datetime.now().strftime("%Y-%m-%d")
    if sh:
        try:
            ws = sh.worksheet("Watchlist")
            # Check if ticker already exists and update, else append
            existing_tickers = ws.col_values(1)
            if ticker in existing_tickers:
                row_idx = existing_tickers.index(ticker) + 1
                ws.update(f"A{row_idx}:J{row_idx}",
                          [[ticker, note, date_added, verdict, price, tt, vcp, cs, stage, pivot]])
            else:
                ws.append_row([ticker, note, date_added, verdict, price, tt, vcp, cs, stage, pivot])
        except Exception as e:
            st.error(f"Sheets write error: {e}")
    # Update local cache
    wl[ticker] = {
        "note": note, "date_added": date_added, "verdict": verdict,
        "current_price": price, "tt_score": tt, "vgf_score": vcp,
        "gf_score": cs, "stage": stage, "pivot": pivot
    }
    st.session_state["watchlist"] = wl


def wl_remove(ticker):
    """Remove ticker from watchlist in Google Sheets."""
    sh = get_gsheet()
    if sh:
        try:
            ws = sh.worksheet("Watchlist")
            existing = ws.col_values(1)
            if ticker in existing:
                row_idx = existing.index(ticker) + 1
                ws.delete_rows(row_idx)
        except Exception as e:
            st.error(f"Sheets delete error: {e}")
    wl = wl_load()
    wl.pop(ticker, None)
    st.session_state["watchlist"] = wl


def wl_refresh_cache():
    """Force reload watchlist from Sheets."""
    if "watchlist_loaded" in st.session_state:
        del st.session_state["watchlist_loaded"]
    if "watchlist" in st.session_state:
        del st.session_state["watchlist"]


# ── Verdict Memory: Google Sheets backed ─────────────────────
def vm_save(ticker, verdict, tt_score, vgf_score, gf_score, price, pivot, market=""):
    """Save verdict snapshot to History sheet."""
    sh = get_gsheet()
    date_str = datetime.now().strftime("%Y-%m-%d %H:%M")
    if sh:
        try:
            wh = sh.worksheet("History")
            wh.append_row([ticker, date_str, verdict, price, pivot,
                           tt_score, vgf_score, gf_score, market, ""])
        except Exception as e:
            st.error(f"History write error: {e}")
    # Also update local verdict memory
    if "verdict_memory" not in st.session_state:
        st.session_state["verdict_memory"] = {}
    vm = st.session_state["verdict_memory"]
    if ticker not in vm:
        vm[ticker] = []
    vm[ticker].append({
        "date": date_str, "verdict": verdict, "tt": tt_score,
        "vcp": vgf_score, "gf": gf_score, "price": price, "pivot": pivot,
    })
    vm[ticker] = vm[ticker][-10:]
    st.session_state["verdict_memory"] = vm


def vm_get(ticker):
    """Get verdict history — first check session, then Sheets."""
    # Check session cache first
    if "verdict_memory" in st.session_state:
        cached = st.session_state["verdict_memory"].get(ticker, [])
        if cached:
            return cached
    # Fall back to Sheets
    sh = get_gsheet()
    if not sh:
        return []
    try:
        wh = sh.worksheet("History")
        rows = wh.get_all_records()
        history = []
        for r in rows:
            if r.get("Ticker", "").strip().upper() == ticker:
                history.append({
                    "date":    r.get("Date", ""),
                    "verdict": r.get("Verdict", ""),
                    "tt":      r.get("TT Score", ""),
                    "vcp":     r.get("VCS Score", ""),
                    "gf": r.get("GF Score", ""),
                    "price":   r.get("Price", ""),
                    "pivot":   r.get("Pivot", ""),
                })
        # Cache in session
        if "verdict_memory" not in st.session_state:
            st.session_state["verdict_memory"] = {}
        st.session_state["verdict_memory"][ticker] = history[-10:]
        return history
    except Exception:
        return []


def vm_compare(ticker, current_verdict):
    """Compare current verdict vs last saved verdict."""
    history = vm_get(ticker)
    if not history:
        return None
    last = history[-1]
    if last["verdict"] != current_verdict:
        return last
    return None


# ── Alpaca Config ─────────────────────────────────────────────
ALPACA_KEY    = "AKSCP2RBJMBNI5ZBNEP2ATEYX4"
ALPACA_SECRET = "3wywDhe8hL1VKeoT5AtsBdeprFxoH1McJ6gPC7E2Gu9h"
ALPACA_BASE   = "https://api.alpaca.markets"
ALPACA_DATA   = "https://data.alpaca.markets"

ALPACA_HEADERS = {
    "APCA-API-KEY-ID":     ALPACA_KEY,
    "APCA-API-SECRET-KEY": ALPACA_SECRET,
    "accept":              "application/json"
}


@st.cache_resource
def get_claude():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


# ── Alpaca: Market Direction (M in GF Score) ──────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_market_direction():
    """
    M = Market Direction (O'Neil / IBD logic)
    Uses SPY and QQQ from Alpaca.
    Checks: price vs 50MA, 50MA vs 200MA, follow-through day concept.
    Returns: status (Bull / Bear / Neutral), details dict
    """
    try:
        results = {}
        for symbol in ["SPY", "QQQ"]:
            url = f"{ALPACA_DATA}/v2/stocks/{symbol}/bars"
            params = {
                "timeframe": "1Day",
                "start": (datetime.now() - timedelta(days=300)).strftime("%Y-%m-%d"),
                "end":   datetime.now().strftime("%Y-%m-%d"),
                "limit": 300,
                "feed":  "iex"
            }
            r = requests.get(url, headers=ALPACA_HEADERS, params=params, timeout=10)
            if r.status_code != 200:
                continue
            bars = r.json().get("bars", [])
            if not bars:
                continue
            df = pd.DataFrame(bars)
            df["t"] = pd.to_datetime(df["t"])
            df = df.sort_values("t").reset_index(drop=True)
            df["sma50"]  = df["c"].rolling(50).mean()
            df["sma200"] = df["c"].rolling(200).mean()

            price   = float(df["c"].iloc[-1])
            sma50   = float(df["sma50"].iloc[-1])
            sma200  = float(df["sma200"].iloc[-1])
            sma50_1mo = float(df["sma50"].iloc[-22])

            # follow-through day: 3 sessions of gains after a low
            recent = df.tail(10)
            gains  = (recent["c"] > recent["c"].shift(1)).sum()

            results[symbol] = {
                "price":      round(price, 2),
                "sma50":      round(sma50, 2),
                "sma200":     round(sma200, 2),
                "above50":    bool(price > sma50),
                "above200":   bool(price > sma200),
                "50gt200":    bool(sma50 > sma200),
                "50trending": bool(sma50 > sma50_1mo),
                "gains10d":   int(gains),
                "pct_vs_50":  round((price / sma50 - 1) * 100, 2),
            }

        if not results:
            return "Unknown", {}, "Could not fetch market data from Alpaca."

        # Score: both SPY and QQQ above 50MA and 50>200
        bull_signals = 0
        bear_signals = 0
        for sym, r in results.items():
            if r["above50"] and r["50gt200"] and r["50trending"]: bull_signals += 1
            if not r["above200"]: bear_signals += 1

        if bull_signals == 2:
            status = "Bull"
        elif bear_signals >= 1:
            status = "Bear"
        else:
            status = "Neutral"

        detail = f"SPY: ${results.get('SPY',{}).get('price','N/A')} | " \
                 f"QQQ: ${results.get('QQQ',{}).get('price','N/A')}"
        return status, results, detail

    except Exception as e:
        return "Unknown", {}, str(e)


# ── yfinance: Full GF Score fundamentals ──────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_gf_fundamentals(ticker):
    """
    Pulls data for C, A, N, S, L, I criteria from yfinance.
    Returns a dict with all raw values + pass/fail booleans.
    """
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        # ── C: Current Quarter EPS growth ────────────────────
        # Pull quarterly earnings
        try:
            qe = stock.quarterly_earnings
            if qe is not None and len(qe) >= 2:
                # Most recent vs same quarter 1 year ago
                eps_recent  = float(qe["Earnings"].iloc[0])
                eps_yr_ago  = float(qe["Earnings"].iloc[4]) if len(qe) >= 5 else None
                if eps_yr_ago and eps_yr_ago != 0:
                    c_eps_growth = (eps_recent - eps_yr_ago) / abs(eps_yr_ago)
                else:
                    c_eps_growth = float(info.get("earningsQuarterlyGrowth", 0) or 0)
                # Acceleration: q1 growth vs q2 growth
                if len(qe) >= 6:
                    eps_q2      = float(qe["Earnings"].iloc[1])
                    eps_q2_ago  = float(qe["Earnings"].iloc[5])
                    c_eps_prev  = (eps_q2 - eps_q2_ago) / abs(eps_q2_ago) if eps_q2_ago != 0 else 0
                    c_accel     = bool(c_eps_growth > c_eps_prev)
                else:
                    c_accel = False
            else:
                c_eps_growth = float(info.get("earningsQuarterlyGrowth", 0) or 0)
                c_accel = False
        except Exception:
            c_eps_growth = float(info.get("earningsQuarterlyGrowth", 0) or 0)
            c_accel = False

        c_pass = bool(c_eps_growth >= 0.25)

        # ── A: Annual EPS growth ──────────────────────────────
        try:
            ae = stock.earnings  # annual
            if ae is not None and len(ae) >= 2:
                # Check if last 2 years show growth
                yrs = ae["Earnings"].tolist()
                a_growths = []
                for i in range(len(yrs)-1):
                    if yrs[i] != 0 and yrs[i] is not None:
                        g = (yrs[i+1] - yrs[i]) / abs(yrs[i])
                        a_growths.append(g)
                a_avg_growth = float(np.mean(a_growths)) if a_growths else 0.0
                a_consistent = bool(all(g > 0 for g in a_growths[-2:]) if len(a_growths) >= 2 else False)
            else:
                a_avg_growth = float(info.get("earningsGrowth", 0) or 0)
                a_consistent = False
        except Exception:
            a_avg_growth = float(info.get("earningsGrowth", 0) or 0)
            a_consistent = False

        a_pass = bool(a_avg_growth >= 0.25)

        # ── N: New High / Near 52-week high ───────────────────
        price   = float(info.get("currentPrice", info.get("regularMarketPrice", 0)) or 0)
        high52  = float(info.get("fiftyTwoWeekHigh", 0) or 0)
        n_pass  = bool(high52 > 0 and price >= high52 * 0.85)
        n_pct   = round((price / high52 - 1) * 100, 1) if high52 > 0 else 0.0

        # ── S: Supply/Demand — float & accumulation ───────────
        float_shares = float(info.get("floatShares", 0) or 0)
        avg_vol      = float(info.get("averageVolume", 0) or 0)
        avg_vol10    = float(info.get("averageVolume10days", 0) or 0)
        # Volume increasing = accumulation signal
        s_accum = bool(avg_vol10 > avg_vol * 1.05) if avg_vol > 0 else False
        # Small/mid float preferred (under 500M shares)
        s_float_ok = bool(0 < float_shares < 500_000_000)
        s_pass = bool(s_accum or s_float_ok)

        # ── L: Leader — RS (relative strength) ───────────────
        # We use RS rating proxy: 1yr price performance
        try:
            hist = stock.history(period="1y")
            if len(hist) > 0:
                l_perf_1yr = float((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100)
            else:
                l_perf_1yr = 0.0
        except Exception:
            l_perf_1yr = 0.0
        # Leader = outperforming (proxy: >20% 1yr gain)
        l_pass = bool(l_perf_1yr > 20)

        # ── I: Institutional Sponsorship ─────────────────────
        inst_own   = float(info.get("institutionalOwnershipPercentage",
                          info.get("heldPercentInstitutions", 0)) or 0)
        # Acceptable range: 30-80% (too high = overcrowded)
        i_pass = bool(0.30 <= inst_own <= 0.85)

        return {
            # C
            "c_eps_growth": round(c_eps_growth * 100, 1),
            "c_accel":      c_accel,
            "c_pass":       c_pass,
            # A
            "a_avg_growth": round(a_avg_growth * 100, 1),
            "a_consistent": a_consistent,
            "a_pass":       a_pass,
            # N
            "n_pct_from_high": n_pct,
            "n_pass":          n_pass,
            # S
            "float_shares": float_shares,
            "avg_vol":      avg_vol,
            "avg_vol10":    avg_vol10,
            "s_accum":      s_accum,
            "s_float_ok":   s_float_ok,
            "s_pass":       s_pass,
            # L
            "l_perf_1yr": round(l_perf_1yr, 1),
            "l_pass":     l_pass,
            # I
            "inst_own": round(inst_own * 100, 1),
            "i_pass":   i_pass,
        }
    except Exception as e:
        return None


def calc_gf_score(cs, market_status):
    """Score 0-7: one point per GF Score letter."""
    if cs is None:
        return 0, {}
    m_pass = market_status == "Bull"
    breakdown = {
        "C": cs["c_pass"],
        "A": cs["a_pass"],
        "N": cs["n_pass"],
        "S": cs["s_pass"],
        "L": cs["l_pass"],
        "I": cs["i_pass"],
        "M": m_pass,
    }
    score = sum(breakdown.values())
    return score, breakdown


@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500():
    return [
        "AAPL","MSFT","NVDA","AVGO","ORCL","CRM","ACN","ADBE","CSCO","TXN",
        "QCOM","AMD","INTU","IBM","AMAT","LRCX","KLAC","ADI","SNPS","CDNS",
        "PANW","NOW","FTNT","MSI","CTSH","ANSS","KEYS","GDDY","AKAM","FFIV",
        "PTC","EPAM","ENPH","GLW","HPQ","HPE","STX","WDC","NTAP","ZBRA",
        "TER","TRMB","FSLR","ROP","LLY","JNJ","ABBV","MRK","TMO","ABT",
        "DHR","ISRG","AMGN","VRTX","REGN","GILD","MDT","BSX","SYK","IDXX",
        "DXCM","BIIB","ILMN","HOLX","PODD","BMRN","INCY","NBIX","ALGN",
        "AMZN","TSLA","HD","MCD","SBUX","LOW","TJX","BKNG","ORLY","AZO",
        "ROST","DLTR","DG","LULU","NVR","PHM","DHI","LEN","UBER","ABNB",
        "MAR","HLT","EXPE","LYFT","DASH","WMT","COST","PG","KO","PEP",
        "MDLZ","GIS","CLX","CHD","CL","KMB","CELH","SFM","GE","CAT",
        "HON","ETN","EMR","ITW","PH","ROK","CMI","IR","CARR","OTIS",
        "EXPD","JBHT","ODFL","XPO","SAIA","FDX","UPS","PCAR","DE",
        "XOM","CVX","EOG","MPC","PSX","VLO","COP","OXY","HAL","SLB",
        "LIN","APD","ECL","SHW","PPG","NUE","FCX","NEM","ALB","DD",
        "PLD","CCI","AMT","SBAC","EQIX","PSA","WELL","O","VICI","IRM",
        "NEE","SO","DUK","SRE","AEP","EXC","XEL","WEC","CEG","VST",
        "GOOGL","META","NFLX","TMUS","CMCSA","TTWO","EA","RBLX",
        "SPGI","MCO","MSCI","ICE","CME","VRSK","CPRT","CTAS","PAYX","ADP",
        "FI","GPN","FICO","BR","MANH","PAYC","APPF","DDOG","CRWD","ZS",
        "WDAY","VEEV","TEAM","SNOW","PLTR","NET","MDB","GTLB","CFLT","BILL"
    ]


@st.cache_data(ttl=86400, show_spinner=False)
def get_nasdaq100():
    return [
        "AAPL","MSFT","NVDA","AMZN","META","GOOGL","GOOG","TSLA","AVGO","COST",
        "NFLX","AMD","PEP","ADBE","CSCO","QCOM","INTU","AMGN","TXN","HON",
        "BKNG","ISRG","SBUX","GILD","ADP","VRTX","MDLZ","PANW","REGN","LRCX",
        "MU","ADI","KLAC","SNPS","CDNS","MELI","ORLY","MAR","CTAS","MNST",
        "PCAR","FTNT","PYPL","DXCM","ABNB","IDXX","FAST","ROST","ODFL","VRSK",
        "GEHC","KDP","DLTR","EXC","CTSH","BIIB","ON","ANSS","FANG","CEG",
        "ZS","TEAM","CRWD","DDOG","WDAY","VEEV","TTWO","EBAY","NXPI","MCHP",
        "LULU","CPRT","PAYX","ILMN","ENPH","ALGN","PODD","HOLX"
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        if df.empty or len(df) < 200:
            return None

        df["SMA10"]  = df["Close"].rolling(10).mean()
        df["SMA20"]  = df["Close"].rolling(20).mean()
        df["SMA50"]  = df["Close"].rolling(50).mean()
        df["SMA150"] = df["Close"].rolling(150).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()

        hl = df["High"] - df["Low"]
        hc = (df["High"] - df["Close"].shift()).abs()
        lc = (df["Low"]  - df["Close"].shift()).abs()
        df["ATR"]      = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
        df["VolAvg50"] = df["Volume"].rolling(50).mean()

        past   = df.tail(252)
        low52  = float(past["Low"].min())
        high52 = float(past["High"].max())
        price  = float(df["Close"].iloc[-1])
        sma50  = float(df["SMA50"].iloc[-1])
        sma150 = float(df["SMA150"].iloc[-1])
        sma200 = float(df["SMA200"].iloc[-1])
        sma200_1mo = float(df["SMA200"].iloc[-22])

        tt = {
            "1. Price > SMA150 and SMA200":      bool(price > sma150 and price > sma200),
            "2. SMA150 > SMA200":                bool(sma150 > sma200),
            "3. SMA200 Trending Up (1mo)":        bool(sma200 > sma200_1mo),
            "4. SMA50 > SMA150 and SMA200":      bool(sma50 > sma150 and sma50 > sma200),
            "5. Price > SMA50":                  bool(price > sma50),
            "6. Price 30pct Above 52w Low":      bool(price >= low52 * 1.30),
            "7. Price Within 25pct of 52w High": bool(price >= high52 * 0.75),
            "8. RS Positive vs SMA200":          bool(price > sma200),
        }

        slope20 = float((df["SMA150"].iloc[-1] - df["SMA150"].iloc[-20]) / df["SMA150"].iloc[-20] * 100)
        if price > sma150 and slope20 > 0.5:
            stage, stage_label = 2, "Stage 2 - Advancing"
        elif price > sma150 and abs(slope20) <= 0.5:
            stage, stage_label = 1, "Stage 1 - Basing"
        elif price < sma150 and slope20 < -0.5:
            stage, stage_label = 4, "Stage 4 - Declining"
        else:
            stage, stage_label = 3, "Stage 3 - Topping"

        recent60 = df.tail(60)
        seg  = 20
        segs = [recent60.iloc[0:seg], recent60.iloc[seg:2*seg], recent60.iloc[2*seg:]]
        ranges = [float((s["High"].max()-s["Low"].min())/s["Close"].mean()*100) for s in segs]
        vols   = [float(s["Volume"].mean()) for s in segs]
        contractions = int(sum([ranges[0]>ranges[1], ranges[1]>ranges[2]]))
        final10   = df.tail(10)
        tight_rng = float((final10["High"].max()-final10["Low"].min())/final10["Close"].mean()*100)
        is_tight  = bool(tight_rng < 8.0)
        near_highs = bool(price >= float(df.tail(60)["High"].max()) * 0.90)
        vol_dry    = bool(vols[0] > vols[1])
        pivot      = float(final10["High"].max())
        pct_to_pivot = float((pivot - price) / price * 100)
        vgf_score  = int(min(100, 30*contractions + (15 if vol_dry else 0)
                             + (15 if is_tight else 0) + (10 if near_highs else 0)))
        is_vcs = bool(contractions >= 2 and is_tight and near_highs)

        info       = stock.info
        eps_growth = float(info.get("earningsQuarterlyGrowth", 0) or 0)
        rev_growth = float(info.get("revenueGrowth", 0) or 0)
        roe        = float(info.get("returnOnEquity", 0) or 0)
        mktcap     = float(info.get("marketCap", 0) or 0)
        sector     = str(info.get("sector", "N/A"))
        name       = str(info.get("shortName", ticker))

        return {
            "df": df, "price": price,
            "sma50": sma50, "sma150": sma150, "sma200": sma200,
            "high52": high52, "low52": low52,
            "tt": tt, "tt_score": int(sum(tt.values())),
            "stage": stage, "stage_label": stage_label,
            "slope20": round(slope20, 2),
            "vgf_score": vgf_score, "is_vcs": is_vcs,
            "contractions": contractions, "tight_rng": round(tight_rng, 2),
            "near_highs": near_highs, "vol_dry": vol_dry,
            "pivot": round(pivot, 2), "pct_to_pivot": round(pct_to_pivot, 2),
            "eps_growth": eps_growth, "rev_growth": rev_growth,
            "roe": roe, "mktcap": mktcap, "sector": sector, "name": name,
        }
    except Exception:
        return None


def get_verdict(d, gf_score=0):
    tt  = d["tt_score"]
    ext = (d["price"] / d["sma50"] - 1) * 100
    stg = d["stage"]
    vcp = d["vgf_score"]
    if tt >= 7 and stg == 2 and ext < 10 and vcp >= 60 and gf_score >= 5:
        return "BUY - HIGH CONVICTION PRISM SETUP", "buy"
    elif tt >= 7 and stg == 2 and ext < 10 and vcp >= 60:
        return "BUY - HIGH CONVICTION PRISM SETUP", "buy"
    elif tt >= 6 and stg == 2 and ext >= 10:
        return "WAIT - EXTENDED, DO NOT CHASE", "wait"
    elif tt >= 6 and stg == 2:
        return "WATCH - STAGE 2, BUILDING SETUP", "watch"
    elif tt < 5 or stg == 4:
        return "AVOID - TREND TEMPLATE FAILED", "avoid"
    else:
        return "WATCH - FORMING BASE / STAGE 1", "watch"


def make_chart(d, ticker, stop_price, target_2r, target_3r):
    df = d["df"].tail(180)
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.60, 0.20, 0.20],
        subplot_titles=("", "Volume", "RS vs SMA200")
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color="#26a69a", decreasing_line_color="#ef5350",
        name="Price"
    ), row=1, col=1)
    for col, color, width, name in [
        ("SMA50",  "#ffd700", 1.2, "SMA50"),
        ("SMA150", "#ff9800", 1.2, "SMA150"),
        ("SMA200", "#e91e63", 1.8, "SMA200"),
    ]:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col], name=name,
            line=dict(color=color, width=width)
        ), row=1, col=1)
    fig.add_hline(y=d["pivot"],  line=dict(color="#00e5ff", width=1.5, dash="dash"),
                  annotation_text=f"Pivot ${d['pivot']:.2f}", row=1, col=1)
    fig.add_hline(y=stop_price,  line=dict(color="#f85149", width=1.2, dash="dot"),
                  annotation_text=f"Stop ${stop_price:.2f}", row=1, col=1)
    fig.add_hline(y=target_2r,   line=dict(color="#3fb950", width=1.0, dash="dashdot"),
                  annotation_text=f"2R ${target_2r:.2f}", row=1, col=1)
    fig.add_hline(y=target_3r,   line=dict(color="#b9f6ca", width=1.0, dash="dashdot"),
                  annotation_text=f"3R ${target_3r:.2f}", row=1, col=1)
    colors = ["#26a69a" if c >= o else "#ef5350"
              for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], marker_color=colors,
        opacity=0.75, name="Volume"
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["VolAvg50"], name="VolAvg50",
        line=dict(color="white", width=1, dash="dash")
    ), row=2, col=1)
    rs_line  = df["Close"] / df["SMA200"]
    rs_color = "#3fb950" if float(rs_line.iloc[-1]) >= float(rs_line.tail(20).max()) * 0.99 else "#ab47bc"
    fig.add_trace(go.Scatter(
        x=df.index, y=rs_line, name="RS vs SMA200",
        line=dict(color=rs_color, width=1.5)
    ), row=3, col=1)
    fig.update_layout(
        height=720, template="plotly_dark",
        plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
        font=dict(color="#e6edf3"),
        legend=dict(orientation="h", y=1.02, x=0,
                    bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
        xaxis_rangeslider_visible=False,
        title=dict(
            text=f"{ticker} | ${d['price']:.2f} | TT: {d['tt_score']}/8 | "
                 f"{d['stage_label']} | VCS: {d['vgf_score']}/100",
            font=dict(size=13, color="#58a6ff")
        ),
        margin=dict(t=60, b=20, l=50, r=80)
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262d")
    fig.update_yaxes(showgrid=True, gridcolor="#21262d")
    return fig


def render_gf_panel(cs, breakdown, gf_score, market_status, market_detail):
    """Render the GF Score analysis panel."""
    if cs is None:
        st.warning("GF Score data unavailable for this ticker.")
        return

    # Market status badge
    css_class = {"Bull": "market-bull", "Bear": "market-bear"}.get(market_status, "market-neutral")
    st.markdown(
        f'<div class="{css_class}">M — Market Direction: {market_status} &nbsp;|&nbsp; {market_detail}</div>',
        unsafe_allow_html=True
    )
    st.markdown(f"### GF Score: {gf_score}/7")

    letters = {
        "C": {
            "label": "Current Quarterly Earnings",
            "pass":  cs["c_pass"],
            "detail": f"{cs['c_eps_growth']}% EPS growth YoY | Accelerating: {'Yes' if cs['c_accel'] else 'No'} | Target: ≥25%"
        },
        "A": {
            "label": "Annual Earnings Growth",
            "pass":  cs["a_pass"],
            "detail": f"{cs['a_avg_growth']}% avg annual EPS growth | Consistent: {'Yes' if cs['a_consistent'] else 'No'} | Target: ≥25%"
        },
        "N": {
            "label": "New High / Near 52-Week High",
            "pass":  cs["n_pass"],
            "detail": f"{cs['n_pct_from_high']}% from 52-week high | Target: within 15%"
        },
        "S": {
            "label": "Supply & Demand",
            "pass":  cs["s_pass"],
            "detail": f"Float: {cs['float_shares']/1e6:.0f}M shares | Accumulation: {'Yes' if cs['s_accum'] else 'No'} | Float OK: {'Yes' if cs['s_float_ok'] else 'No'}"
        },
        "L": {
            "label": "Leader vs Laggard",
            "pass":  cs["l_pass"],
            "detail": f"1-Year performance: {cs['l_perf_1yr']}% | Target: >20%"
        },
        "I": {
            "label": "Institutional Sponsorship",
            "pass":  cs["i_pass"],
            "detail": f"Institutional ownership: {cs['inst_own']}% | Target: 30–85%"
        },
        "M": {
            "label": "Market Direction",
            "pass":  breakdown.get("M", False),
            "detail": f"SPY + QQQ trend via Alpaca | Status: {market_status}"
        },
    }

    cols = st.columns(2)
    for i, (letter, data) in enumerate(letters.items()):
        icon   = "✅" if data["pass"] else "❌"
        c_cls  = "gf-pass" if data["pass"] else "gf-fail"
        with cols[i % 2]:
            st.markdown(
                f'<div class="gf-box">'
                f'<span class="gf-letter {c_cls}">{letter}</span>'
                f'<strong style="color:#e6edf3;">{icon} {data["label"]}</strong><br>'
                f'<span style="color:#8b949e;font-size:12px;">{data["detail"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )


def claude_analysis(ticker, d, stop, t2r, t3r, shares, cs, gf_score, market_status):
    client = get_claude()
    tt_lines = "\n".join([f"  {k}: {v}" for k, v in d['tt'].items()])

    gf_lines = ""
    if cs:
        gf_lines = (
            f"\nGF SCORE: {gf_score}/7\n"
            f"  C - Current EPS Growth: {cs['c_eps_growth']}% (Pass: {cs['c_pass']}, Accel: {cs['c_accel']})\n"
            f"  A - Annual EPS Growth: {cs['a_avg_growth']}% (Pass: {cs['a_pass']})\n"
            f"  N - Near 52w High: {cs['n_pct_from_high']}% from high (Pass: {cs['n_pass']})\n"
            f"  S - Float: {cs['float_shares']/1e6:.0f}M, Accumulation: {cs['s_accum']} (Pass: {cs['s_pass']})\n"
            f"  L - 1yr Perf: {cs['l_perf_1yr']}% (Pass: {cs['l_pass']})\n"
            f"  I - Inst Ownership: {cs['inst_own']}% (Pass: {cs['i_pass']})\n"
            f"  M - Market: {market_status}\n"
        )

    prompt = (
        f"You are Mark Minervini and William O'Neil's trading methodology expert and mentor.\n"
        f"Analyze this combined PRISM setup and give a concise, actionable assessment.\n\n"
        f"TICKER: {ticker} ({d['name']}) | Sector: {d['sector']}\n"
        f"Price: ${d['price']:.2f} | Market Cap: ${d['mktcap']/1e9:.1f}B\n\n"
        f"TREND TEMPLATE: {d['tt_score']}/8\n{tt_lines}\n\n"
        f"STAGE ANALYSIS: {d['stage_label']} | SMA150 slope (20d): {d['slope20']}%\n\n"
        f"VCP ANALYSIS (Score: {d['vgf_score']}/100):\n"
        f"Contractions: {d['contractions']} | Tight: {d['tight_rng']}% | Near highs: {d['near_highs']}\n"
        f"Volume drying: {d['vol_dry']} | VCS confirmed: {d['is_vcs']}\n"
        f"Pivot: ${d['pivot']} | Pct to pivot: {d['pct_to_pivot']}%\n"
        f"{gf_lines}\n"
        f"RISK/REWARD:\n"
        f"Entry: ${d['pivot']:.2f} | Stop: ${stop:.2f} | 2R: ${t2r:.2f} | 3R: ${t3r:.2f}\n"
        f"Position: {shares} shares\n\n"
        f"PRISM FUNDAMENTALS:\n"
        f"EPS Growth Q: {d['eps_growth']*100:.1f}% | Revenue Growth: {d['rev_growth']*100:.1f}% | ROE: {d['roe']*100:.1f}%\n\n"
        f"Respond with:\n"
        f"1. SETUP VERDICT: (Actionable / Watch / Avoid - one line, blunt)\n"
        f"2. PRISM STRENGTHS: (3 bullets max)\n"
        f"3. GF HIGHLIGHTS: (2-3 bullets on C, A, I findings)\n"
        f"4. WEAKNESSES / RISKS: (3 bullets max)\n"
        f"5. IDEAL ENTRY: (specific price action to wait for)\n"
        f"6. MENTOR NOTE: (one key Minervini/O'Neil insight for this exact setup)"
    )
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=750,
        messages=[{"role": "user", "content": prompt}]
    )
    return msg.content[0].text


# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## Risk Mandate")
    st.markdown("---")
    portfolio = st.number_input("Portfolio Size ($)", value=100000, step=5000)
    risk_pct  = st.slider("Risk Per Trade (%)", 0.25, 3.0, 1.0, 0.25) / 100
    st.markdown("---")
    st.markdown("## Scanner Filters")
    min_tt       = st.slider("Min Trend Template Score", 4, 8, 6)
    min_vcs      = st.slider("Min VCS Score", 0, 100, 40, 10)
    min_gf  = st.slider("Min GF Score", 0, 7, 3, 1)
    min_price    = st.number_input("Min Price ($)", value=10.0, step=1.0)
    min_vol      = st.number_input("Min Avg Volume", value=300000, step=50000)
    st.markdown("---")

    # Market Direction Widget in Sidebar
    st.markdown("## Market Direction (M)")
    with st.spinner("Checking market via Alpaca..."):
        mkt_status, mkt_data, mkt_detail = get_market_direction()
    css_class = {"Bull": "market-bull", "Bear": "market-bear"}.get(mkt_status, "market-neutral")
    st.markdown(f'<div class="{css_class}">{mkt_status} Market</div>', unsafe_allow_html=True)
    if mkt_data:
        for sym, r in mkt_data.items():
            st.markdown(
                f"<span style='color:#8b949e;font-size:11px;'>"
                f"{sym}: ${r['price']} | vs50MA: {r['pct_vs_50']}%</span>",
                unsafe_allow_html=True
            )
    st.markdown("---")
    st.markdown(
        "<p style='color:#8b949e;font-size:11px;'>Data: yfinance + Alpaca | AI: Claude<br>"
        "PRISM | Not financial advice</p>",
        unsafe_allow_html=True
    )

# ── Header ────────────────────────────────────────────────────
st.markdown("""
<div style="display:flex;align-items:center;justify-content:space-between;
            padding:8px 0 6px;border-bottom:1px solid #1e2736;margin-bottom:4px;">
  <div>
    <span style="font-family:'IBM Plex Mono',monospace;font-size:22px;font-weight:700;
                 color:#e6edf3;letter-spacing:2px;">PRISM</span>
    <span style="font-family:'Inter',sans-serif;font-size:13px;color:#6e7f96;
                 margin-left:12px;">Price · RS · Institutional · Stage · Momentum</span>
  </div>
  <div style="font-family:'IBM Plex Mono',monospace;font-size:11px;color:#3a4a5c;
              text-align:right;">PERSONAL TERMINAL&nbsp;&nbsp;|&nbsp;&nbsp;NOT FINANCIAL ADVICE</div>
</div>
""", unsafe_allow_html=True)

tab_single, tab_scanner, tab_watchlist, tab_guide = st.tabs(["Single Stock", "Batch Scanner", "⭐ Watchlist", "Guide"])

# ── TAB 1: Single Stock ───────────────────────────────────────
with tab_single:
    # Pre-populate from Deep Dive button
    default_ticker = st.session_state.pop("dive_ticker", "NVDA")
    auto_analyze   = default_ticker != "NVDA" or st.session_state.get("active_tab") == "single"
    if "active_tab" in st.session_state:
        del st.session_state["active_tab"]

    ticker_input = st.text_input(
        "Enter Ticker", default_ticker,
        placeholder="e.g. NVDA, AAPL, MSFT"
    ).strip().upper()

    if ticker_input:
        with st.spinner(f""):
            d  = fetch_data(ticker_input)
            cs = get_gf_fundamentals(ticker_input)
            try:
                gf_score, gf_breakdown = calc_gf_score(cs, mkt_status)
            except Exception:
                gf_score, gf_breakdown = 0, {}

        if d is None:
            st.error(f"No data for {ticker_input} — check the ticker symbol.")
        else:
            verdict_text, verdict_class = get_verdict(d, gf_score)
            extension   = (d["price"] / d["sma50"] - 1) * 100
            pct_above150 = (d["price"] - d["sma150"]) / d["sma150"] * 100

            # ── Default execution values ──────────────────────
            suggested_stop = round(d["price"] * 0.92, 2)
            stop_price     = suggested_stop
            dollar_risk    = portfolio * risk_pct
            risk_per_share = max(d["pivot"] - stop_price, 0.01)
            shares         = int(dollar_risk / risk_per_share)
            pos_value      = shares * d["pivot"]
            target_2r      = d["pivot"] + risk_per_share * 2
            target_3r      = d["pivot"] + risk_per_share * 3

            # ── TICKER HEADER BAR ─────────────────────────────
            day_chg    = d["price"] - d.get("prev_close", d["price"])
            day_chg_pct = (day_chg / d.get("prev_close", d["price"])) * 100 if d.get("prev_close") else 0
            chg_color  = "#3fb950" if day_chg >= 0 else "#f85149"
            chg_sign   = "+" if day_chg >= 0 else ""
            mktcap_str = f"${d['mktcap']/1e9:.1f}B" if d.get("mktcap") else "—"
            vol_str    = f"{d['df']['Volume'].iloc[-1]/1e6:.1f}M" if len(d["df"]) else "—"
            avg_vol_str= f"{d['df']['Volume'].tail(50).mean()/1e6:.1f}M" if len(d["df"]) else "—"
            rvol       = d['df']['Volume'].iloc[-1] / d['df']['Volume'].tail(50).mean() if len(d["df"]) else 1
            w52_hi     = d["df"]["High"].tail(252).max()
            w52_lo     = d["df"]["Low"].tail(252).min()

            st.markdown(f"""
            <div style="background:#0d1117;border:1px solid #1e2736;border-radius:6px;
                        padding:14px 18px;margin-bottom:10px;">
              <div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;">
                <span style="font-family:'IBM Plex Mono',monospace;font-size:26px;
                             font-weight:700;color:#e6edf3;">{ticker_input}</span>
                <span style="font-size:13px;color:#6e7f96;max-width:300px;
                             white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{d['name']}</span>
                <span style="font-size:11px;color:#58a6ff;background:#061828;
                             padding:2px 8px;border-radius:3px;border:1px solid #1a3a5c;">{d['sector']}</span>
                <div style="margin-left:auto;text-align:right;">
                  <span style="font-family:'IBM Plex Mono',monospace;font-size:26px;
                               font-weight:700;color:#e6edf3;">${d['price']:.2f}</span>
                  <span style="font-family:'IBM Plex Mono',monospace;font-size:14px;
                               color:{chg_color};margin-left:10px;">
                    {chg_sign}{day_chg:.2f} ({chg_sign}{day_chg_pct:.2f}%)
                  </span>
                </div>
              </div>
              <div style="display:flex;gap:24px;margin-top:10px;flex-wrap:wrap;
                          font-family:'IBM Plex Mono',monospace;font-size:11px;color:#6e7f96;">
                <span>MKT CAP <strong style="color:#c9d1d9;">{mktcap_str}</strong></span>
                <span>VOL <strong style="color:#c9d1d9;">{vol_str}</strong></span>
                <span>AVG VOL <strong style="color:#c9d1d9;">{avg_vol_str}</strong></span>
                <span>RVOL <strong style="color:{'#3fb950' if rvol>=1.5 else '#c9d1d9'};">{rvol:.1f}x</strong></span>
                <span>52W HI <strong style="color:#c9d1d9;">${w52_hi:.2f}</strong></span>
                <span>52W LO <strong style="color:#c9d1d9;">${w52_lo:.2f}</strong></span>
                <span>EPS GR <strong style="color:{'#3fb950' if d['eps_growth']>0.25 else '#c9d1d9'};">{d['eps_growth']*100:.1f}%</strong></span>
                <span>REV GR <strong style="color:{'#3fb950' if d['rev_growth']>0.15 else '#c9d1d9'};">{d['rev_growth']*100:.1f}%</strong></span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            # ── VERDICT + VERDICT HISTORY ─────────────────────
            v_col, m_col = st.columns([4, 1])
            with v_col:
                st.markdown(
                    f'<div class="verdict-box verdict-{verdict_class}">{verdict_text}</div>',
                    unsafe_allow_html=True
                )
            with m_col:
                css_class = {"Bull": "market-bull", "Bear": "market-bear"}.get(mkt_status, "market-neutral")
                st.markdown(
                    f'<div class="{css_class}" style="height:100%;display:flex;'
                    f'align-items:center;justify-content:center;margin-top:4px;">'
                    f'MKT: {mkt_status}</div>',
                    unsafe_allow_html=True
                )

            prior = vm_compare(ticker_input, verdict_text)
            if prior:
                delta_color = "verdict-changed-buy" if "BUY" in verdict_text else \
                              "verdict-changed-wait" if "WAIT" in verdict_text else \
                              "verdict-changed-avoid"
                st.markdown(
                    f'<div class="verdict-history">'
                    f'🔄 Verdict changed &nbsp;|&nbsp; '
                    f'<span style="color:#6e7f96;">Last: {prior["date"]} · '
                    f'{prior["verdict"]} · ${prior["price"]} · TT {prior["tt"]}/8 · VCS {prior["vcp"]}</span>'
                    f'&nbsp;→&nbsp;<span class="{delta_color}">{verdict_text}</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

            # ── MAIN DASHBOARD: LEFT (scores) | RIGHT (chart) ─
            dash_left, dash_right = st.columns([1, 2])

            with dash_left:

                # PRISM SCORES PANEL
                def badge(val, good, warn):
                    if val >= good: cls = "badge-green"
                    elif val >= warn: cls = "badge-amber"
                    else: cls = "badge-red"
                    return f'<span class="score-badge {cls}">{val}</span>'

                tt_badge  = badge(d["tt_score"], 7, 5)
                vcs_badge = badge(d["vgf_score"], 70, 40)
                gf_badge  = badge(gf_score, 5, 3)
                ext_cls   = "badge-green" if extension < 10 else ("badge-amber" if extension < 20 else "badge-red")
                ext_badge = f'<span class="score-badge {ext_cls}">{extension:.1f}%</span>'
                stg_cls   = "badge-green" if d["stage"] == 2 else "badge-amber"
                stg_badge = f'<span class="score-badge {stg_cls}">{d["stage_label"]}</span>'

                st.markdown(f"""
                <div class="term-panel">
                  <div class="term-panel-header">PRISM SCORES</div>
                  <div class="term-row"><span class="term-label">Trend Template</span><span>{tt_badge}/8</span></div>
                  <div class="term-row"><span class="term-label">Stage</span><span>{stg_badge}</span></div>
                  <div class="term-row"><span class="term-label">VCS Score</span><span>{vcs_badge}/100</span></div>
                  <div class="term-row"><span class="term-label">VCS Confirmed</span>
                    <span class="{'term-pass' if d['is_vcs'] else 'term-fail'}">{'YES' if d['is_vcs'] else 'NO'}</span></div>
                  <div class="term-row"><span class="term-label">GF Score</span><span>{gf_badge}/7</span></div>
                  <div class="term-row"><span class="term-label">50MA Extension</span><span>{ext_badge}</span></div>
                  <div class="term-row"><span class="term-label">SMA150 slope</span>
                    <span class="term-val">{d['slope20']}%</span></div>
                  <div class="term-row"><span class="term-label">% above SMA150</span>
                    <span class="term-val">{pct_above150:.1f}%</span></div>
                </div>
                """, unsafe_allow_html=True)

                # TREND TEMPLATE CHECKLIST
                tt_rows = "".join([
                    f'<div class="term-row">'
                    f'<span class="term-label" style="font-size:11px;">{k}</span>'
                    f'<span class="{"term-pass" if v else "term-fail"}">{"✔" if v else "✘"}</span>'
                    f'</div>'
                    for k, v in d["tt"].items()
                ])
                st.markdown(f"""
                <div class="term-panel" style="margin-top:8px;">
                  <div class="term-panel-header">TREND TEMPLATE</div>
                  {tt_rows}
                </div>
                """, unsafe_allow_html=True)

                # VCS PANEL
                vcs_rows = f"""
                  <div class="term-row"><span class="term-label">Contractions</span>
                    <span class="term-val">{d['contractions']}</span></div>
                  <div class="term-row"><span class="term-label">Tight Range (10d)</span>
                    <span class="{'term-pass' if d['tight_rng'] < 8 else 'term-fail'}">{d['tight_rng']:.1f}%</span></div>
                  <div class="term-row"><span class="term-label">Near Highs</span>
                    <span class="{'term-pass' if d['near_highs'] else 'term-fail'}">{'YES' if d['near_highs'] else 'NO'}</span></div>
                  <div class="term-row"><span class="term-label">Volume Drying</span>
                    <span class="{'term-pass' if d['vol_dry'] else 'term-fail'}">{'YES' if d['vol_dry'] else 'NO'}</span></div>
                """
                st.markdown(f"""
                <div class="term-panel" style="margin-top:8px;">
                  <div class="term-panel-header">VCS ANALYSIS · {d['vgf_score']}/100 {'· CONFIRMED' if d['is_vcs'] else ''}</div>
                  {vcs_rows}
                </div>
                """, unsafe_allow_html=True)

                # EXECUTION PANEL — stop input then full panel
                st.markdown("<div style='margin-top:8px;'>", unsafe_allow_html=True)
                stop_price = st.number_input("Stop Loss ($)", value=suggested_stop, step=0.01, key="stop_single")
                st.markdown("</div>", unsafe_allow_html=True)

                risk_per_share = d["pivot"] - stop_price
                if risk_per_share > 0:
                    shares    = int(dollar_risk / risk_per_share)
                    pos_value = shares * d["pivot"]
                    target_2r = d["pivot"] + risk_per_share * 2
                    target_3r = d["pivot"] + risk_per_share * 3
                    st.markdown(f"""
                    <div class="term-panel" style="margin-top:4px;">
                      <div class="term-panel-header">EXECUTION</div>
                      <div class="term-row"><span class="term-label">Entry (Pivot)</span>
                        <span class="exec-entry">${d['pivot']:.2f}</span></div>
                      <div class="term-row"><span class="term-label">Stop Loss</span>
                        <span class="exec-stop">${stop_price:.2f} ({(stop_price/d['pivot']-1)*100:.1f}%)</span></div>
                      <div class="term-row"><span class="term-label">Risk / Share</span>
                        <span class="term-val">${risk_per_share:.2f}</span></div>
                      <div class="term-row"><span class="term-label">Position Size</span>
                        <span class="term-val">{shares:,} shares</span></div>
                      <div class="term-row"><span class="term-label">Position Value</span>
                        <span class="term-val">${pos_value:,.0f} ({pos_value/portfolio*100:.1f}%)</span></div>
                      <div class="term-row"><span class="term-label">2R Target</span>
                        <span class="exec-target-2r">${target_2r:.2f} (+{(target_2r/d['price']-1)*100:.1f}%)</span></div>
                      <div class="term-row"><span class="term-label">3R Target</span>
                        <span class="exec-target-3r">${target_3r:.2f} (+{(target_3r/d['price']-1)*100:.1f}%)</span></div>
                    </div>
                    """, unsafe_allow_html=True)
                else:
                    st.warning("Stop must be below pivot price.")
                    target_2r = d["pivot"] * 1.10
                    target_3r = d["pivot"] * 1.15
                    shares    = 0

            with dash_right:
                # CHART fills right side
                fig = make_chart(d, ticker_input, stop_price, target_2r, target_3r)
                fig.update_layout(height=680, margin=dict(t=40, b=20, l=40, r=60))
                st.plotly_chart(fig, use_container_width=True)

            # ── GF SCORE PANEL (full width below) ────────────
            st.markdown("<div style='margin-top:4px;'>", unsafe_allow_html=True)
            render_gf_panel(cs, gf_breakdown, gf_score, mkt_status, mkt_detail)
            st.markdown("</div>", unsafe_allow_html=True)

            # ── AI MENTOR ────────────────────────────────────
            st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
            ai_col1, ai_col2 = st.columns([1, 4])
            with ai_col1:
                run_ai = st.button("🤖 AI Mentor Analysis", type="primary", use_container_width=True)
            with ai_col2:
                st.markdown(
                    "<p style='color:#6e7f96;font-size:11px;font-family:IBM Plex Mono,monospace;"
                    "margin-top:8px;'>Claude analyzes PRISM scores, GF Score, VCS setup, "
                    "and generates trade commentary with risk levels.</p>",
                    unsafe_allow_html=True
                )
            if run_ai:
                if "ANTHROPIC_API_KEY" not in st.secrets:
                    st.error("Missing ANTHROPIC_API_KEY in Streamlit Secrets.")
                else:
                    with st.spinner("Consulting AI Mentor..."):
                        try:
                            commentary = claude_analysis(
                                ticker_input, d, stop_price, target_2r, target_3r,
                                shares, cs, gf_score, mkt_status
                            )
                            vm_save(ticker_input, verdict_text, d["tt_score"],
                                    d["vgf_score"], gf_score, d["price"], d["pivot"], mkt_status)
                            st.markdown(
                                f'<div class="ai-box">{commentary}</div>',
                                unsafe_allow_html=True
                            )
                            st.success(f"✅ Verdict saved for {ticker_input}")
                        except Exception as e:
                            st.error(f"AI Mentor error: {e}")

            # ── WATCHLIST CONTROLS ────────────────────────────
            st.markdown("<div style='height:4px;border-top:1px solid #1e2736;margin-top:10px;'></div>",
                        unsafe_allow_html=True)
            wl = wl_load()
            in_watchlist = ticker_input in wl
            wl_col1, wl_col2, wl_col3 = st.columns([3, 1, 1])
            with wl_col1:
                wl_note = st.text_input(
                    "Watchlist note (optional)",
                    value=wl.get(ticker_input, {}).get("note", ""),
                    placeholder="e.g. Waiting for VCS confirmation, earnings next week...",
                    key="wl_note"
                )
            with wl_col2:
                st.markdown("<br>", unsafe_allow_html=True)
                if in_watchlist:
                    if st.button("✅ Remove from Watchlist", key="wl_remove"):
                        wl_remove(ticker_input)
                        st.rerun()
                else:
                    if st.button("⭐ Add to Watchlist", key="wl_add"):
                        wl_add(ticker_input, wl_note, verdict_text,
                               d["price"], d["tt_score"], d["vgf_score"],
                               gf_score, d["stage_label"], d["pivot"])
                        vm_save(ticker_input, verdict_text, d["tt_score"],
                                d["vgf_score"], gf_score, d["price"], d["pivot"], mkt_status)
                        st.rerun()
            with wl_col3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("💾 Save Verdict", key="vm_save_manual"):
                    vm_save(ticker_input, verdict_text, d["tt_score"],
                            d["vgf_score"], gf_score, d["price"], d["pivot"], mkt_status)
                    st.success("Saved.")

            # Verdict history expander
            history = vm_get(ticker_input)
            if len(history) > 1:
                with st.expander(f"📋 Verdict History ({len(history)} entries)"):
                    for entry in reversed(history):
                        v_cls = "verdict-changed-buy" if "BUY" in entry["verdict"] else \
                                "verdict-changed-wait" if "WAIT" in entry["verdict"] else \
                                "verdict-changed-avoid"
                        st.markdown(
                            f'<div class="verdict-history">'
                            f'<span style="color:#6e7f96;">{entry["date"]}</span> &nbsp;|&nbsp; '
                            f'${entry["price"]} &nbsp;|&nbsp; '
                            f'TT {entry["tt"]}/8 &nbsp;|&nbsp; '
                            f'VCS {entry["vcp"]} &nbsp;|&nbsp; '
                            f'GF {entry["gf"]}/7'
                            f'&nbsp;&nbsp;<span class="{v_cls}">{entry["verdict"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

# ── TAB 2: Batch Scanner ──────────────────────────────────────
with tab_scanner:
    st.markdown("### PRISM Scanner")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        universe = st.selectbox("Universe", ["S&P 500", "Nasdaq 100", "Custom"])
    with sc2:
        max_tickers = st.slider("Max Tickers", 10, 200, 100, 10)
    with sc3:
        custom_raw = st.text_input("Custom Tickers (comma separated)", "AAPL,NVDA,MSFT,META,GOOGL")

    fc1, fc2, fc3 = st.columns(3)
    with fc1:
        require_stage2 = st.checkbox("Require Stage 2", value=True)
    with fc2:
        require_vcs    = st.checkbox("Require VCS Confirmed", value=False)
    with fc3:
        require_bull   = st.checkbox("Require Bull Market (M)", value=False)

    if st.button("Run Scan", type="primary", use_container_width=True):
        if require_bull and mkt_status != "Bull":
            st.warning(f"Market is currently {mkt_status}. Bull filter is active — relaxing or disable 'Require Bull Market' to see results.")

        if universe == "S&P 500":
            tickers = get_sp500()[:max_tickers]
        elif universe == "Nasdaq 100":
            tickers = get_nasdaq100()[:max_tickers]
        else:
            tickers = [t.strip().upper() for t in custom_raw.split(",") if t.strip()]

        prog  = st.progress(0, text="Scanning...")
        rows  = []
        total = len(tickers)

        for i, t in enumerate(tickers):
            prog.progress((i+1)/total, text=f"Scanning {t} ({i+1}/{total})")
            d = fetch_data(t)
            if d is None: continue
            if d["price"] < min_price: continue
            if d["df"]["Volume"].tail(50).mean() < min_vol: continue
            if d["tt_score"] < min_tt: continue
            if d["vgf_score"] < min_vcs: continue
            if require_stage2 and d["stage"] != 2: continue
            if require_vcs and not d["is_vcs"]: continue

            cs = get_gf_fundamentals(t)
            try:
                gf_score, _ = calc_gf_score(cs, mkt_status)
            except Exception:
                gf_score = 0
            if gf_score < min_gf: continue
            if require_bull and mkt_status != "Bull": continue

            verdict_text, _ = get_verdict(d, gf_score)
            ext = (d["price"] / d["sma50"] - 1) * 100

            closes_60 = d["df"]["Close"].tail(60).tolist()
            day_chg   = round((d["price"] / d["df"]["Close"].iloc[-2] - 1) * 100, 2)                         if len(d["df"]) > 1 else 0.0
            rvol      = round(d["df"]["Volume"].iloc[-1] /
                              d["df"]["Volume"].tail(50).mean(), 1)                         if len(d["df"]) > 1 else 1.0

            rows.append({
                "Ticker":    t,
                "Name":      d["name"],
                "Price":     d["price"],
                "Day%":      day_chg,
                "TT Score":  d["tt_score"],
                "Stage":     d["stage_label"],
                "VCS Score": d["vgf_score"],
                "VCS":       "Yes" if d["is_vcs"] else "No",
                "GF Score":  gf_score,
                "C EPS%":    round(cs["c_eps_growth"], 1) if cs else 0,
                "Inst Own%": round(cs["inst_own"], 1) if cs else 0,
                "Ext%":      round(ext, 1),
                "Pivot":     d["pivot"],
                "%toPivot":  d["pct_to_pivot"],
                "RVOL":      rvol,
                "Sector":    d["sector"],
                "Verdict":   verdict_text,
                "_closes":   closes_60,
            })
            time.sleep(0.05)

        prog.empty()

        if not rows:
            st.warning("No tickers passed all filters. Try relaxing the settings in the sidebar.")
        else:
            df_r = pd.DataFrame(rows).sort_values(
                ["GF Score", "VCS Score"], ascending=False
            ).reset_index(drop=True)
            st.session_state["scan_results"] = df_r
            st.success(f"Scan complete — {len(df_r)} setups found from {total} tickers. Market: {mkt_status}")

    if "scan_results" in st.session_state:
        df_r = st.session_state["scan_results"]

        # ── Summary bar ───────────────────────────────────────
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Setups",  len(df_r))
        c2.metric("VCS Confirmed", (df_r["VCS"] == "Yes").sum())
        c3.metric("Avg TT Score",  f"{df_r['TT Score'].mean():.1f}")
        c4.metric("Avg VCS Score", f"{df_r['VCS Score'].mean():.1f}")
        c5.metric("Market",        mkt_status)

        # ── Helper: build inline SVG sparkline ────────────────
        def make_sparkline_svg(closes, w=90, h=30):
            if not closes or len(closes) < 2:
                return ""
            mn, mx = min(closes), max(closes)
            rng = mx - mn if mx != mn else 1
            pts = []
            for i, v in enumerate(closes):
                x = i / (len(closes) - 1) * w
                y = h - ((v - mn) / rng) * (h - 4) - 2
                pts.append(f"{x:.1f},{y:.1f}")
            color = "#3fb950" if closes[-1] >= closes[0] else "#f85149"
            path  = "M " + " L ".join(pts)
            return (
                f'<svg width="{w}" height="{h}" style="display:block">' +
                f'<path d="{path}" fill="none" stroke="{color}" ' +
                f'stroke-width="1.5" stroke-linejoin="round"/>' +
                f'</svg>'
            )

        # ── Helper: heat cell bg ──────────────────────────────
        def tt_bg(v):
            if v >= 7:   return "#061810", "#3fb950"
            if v >= 6:   return "#1a1200", "#d29922"
            return "#160808", "#f85149"

        def vcs_bg(v):
            if v >= 70:  return "#061810", "#3fb950"
            if v >= 40:  return "#1a1200", "#d29922"
            return "#0a0a0a", "#6e7f96"

        def gf_bg(v):
            if v >= 5:   return "#061810", "#3fb950"
            if v >= 3:   return "#1a1200", "#d29922"
            return "#160808", "#f85149"

        def ext_bg(v):
            if v < 5:    return "#061810", "#3fb950"
            if v < 10:   return "#1a1200", "#d29922"
            return "#160808", "#f85149"

        def day_bg(v):
            if v > 1:    return "#061810", "#3fb950"
            if v < -1:   return "#160808", "#f85149"
            return "#0d1117", "#8b949e"

        def verdict_cell(v):
            if "BUY"   in v: return "#061810", "#3fb950", "BUY"
            if "WAIT"  in v: return "#1a1200", "#d29922", "WAIT"
            if "WATCH" in v: return "#060f1e", "#58a6ff", "WATCH"
            return "#160808", "#f85149", "AVOID"

        # ── Build HTML table ──────────────────────────────────
        cols_display = ["Ticker","Name","Price","Day%","Sparkline",
                        "TT Score","Stage","VCS Score","GF Score",
                        "C EPS%","Inst Own%","Ext%","RVOL",
                        "%toPivot","Pivot","Verdict"]

        header_cells = "".join([
            f'<th style="padding:6px 10px;text-align:left;font-size:10px;' +
            f'color:#6e7f96;font-weight:600;text-transform:uppercase;' +
            f'letter-spacing:1px;border-bottom:1px solid #1e2736;' +
            f'white-space:nowrap;">{c}</th>'
            for c in cols_display
        ])

        row_htmls = []
        for _, row in df_r.iterrows():
            spark = make_sparkline_svg(row.get("_closes", []))

            tt_b,  tt_c  = tt_bg(row["TT Score"])
            vcs_b, vcs_c = vcs_bg(row["VCS Score"])
            gf_b,  gf_c  = gf_bg(row["GF Score"])
            ext_b, ext_c = ext_bg(row["Ext%"])
            day_b, day_c = day_bg(row["Day%"])
            vb, vc, vshort = verdict_cell(row["Verdict"])

            day_sign = "+" if row["Day%"] > 0 else ""
            rvol_c   = "#3fb950" if row["RVOL"] >= 1.5 else "#c9d1d9"

            cells = [
                # Ticker
                f'<td style="padding:6px 10px;font-family:IBM Plex Mono,monospace;' +
                f'font-size:13px;font-weight:700;color:#58a6ff;' +
                f'white-space:nowrap;cursor:pointer;">{row["Ticker"]}</td>',
                # Name
                f'<td style="padding:6px 10px;font-size:11px;color:#6e7f96;' +
                f'max-width:140px;overflow:hidden;text-overflow:ellipsis;' +
                f'white-space:nowrap;">{row["Name"][:20]}</td>',
                # Price
                f'<td style="padding:6px 10px;font-family:IBM Plex Mono,monospace;' +
                f'font-size:13px;color:#e6edf3;font-weight:600;">${row["Price"]:.2f}</td>',
                # Day%
                f'<td style="padding:6px 10px;font-family:IBM Plex Mono,monospace;' +
                f'font-size:12px;background:{day_b};color:{day_c};' +
                f'font-weight:600;">{day_sign}{row["Day%"]:.1f}%</td>',
                # Sparkline
                f'<td style="padding:4px 10px;">{spark}</td>',
                # TT Score
                f'<td style="padding:6px 10px;text-align:center;' +
                f'font-family:IBM Plex Mono,monospace;font-size:13px;' +
                f'font-weight:700;background:{tt_b};color:{tt_c};">{row["TT Score"]}/8</td>',
                # Stage
                f'<td style="padding:6px 10px;font-size:11px;color:#8b949e;' +
                f'white-space:nowrap;">{row["Stage"].replace("Stage ","S")}</td>',
                # VCS Score
                f'<td style="padding:6px 10px;text-align:center;' +
                f'font-family:IBM Plex Mono,monospace;font-size:13px;' +
                f'font-weight:700;background:{vcs_b};color:{vcs_c};">{row["VCS Score"]}</td>',
                # GF Score
                f'<td style="padding:6px 10px;text-align:center;' +
                f'font-family:IBM Plex Mono,monospace;font-size:13px;' +
                f'font-weight:700;background:{gf_b};color:{gf_c};">{row["GF Score"]}/7</td>',
                # C EPS%
                f'<td style="padding:6px 10px;font-family:IBM Plex Mono,monospace;' +
                f'font-size:12px;color:{"#3fb950" if row["C EPS%"]>=25 else "#8b949e"};">' +
                f'{row["C EPS%"]:+.1f}%</td>',
                # Inst Own%
                f'<td style="padding:6px 10px;font-family:IBM Plex Mono,monospace;' +
                f'font-size:12px;color:#8b949e;">{row["Inst Own%"]:.1f}%</td>',
                # Ext%
                f'<td style="padding:6px 10px;text-align:center;' +
                f'font-family:IBM Plex Mono,monospace;font-size:12px;' +
                f'background:{ext_b};color:{ext_c};">{row["Ext%"]:+.1f}%</td>',
                # RVOL
                f'<td style="padding:6px 10px;font-family:IBM Plex Mono,monospace;' +
                f'font-size:12px;color:{rvol_c};">{row["RVOL"]:.1f}x</td>',
                # %toPivot
                f'<td style="padding:6px 10px;font-family:IBM Plex Mono,monospace;' +
                f'font-size:12px;color:#6e7f96;">{row["%toPivot"]:+.1f}%</td>',
                # Pivot
                f'<td style="padding:6px 10px;font-family:IBM Plex Mono,monospace;' +
                f'font-size:12px;color:#58a6ff;">${row["Pivot"]:.2f}</td>',
                # Verdict
                f'<td style="padding:4px 10px;">' +
                f'<span style="background:{vb};color:{vc};border-radius:3px;' +
                f'padding:2px 7px;font-size:10px;font-weight:700;' +
                f'font-family:IBM Plex Mono,monospace;letter-spacing:0.5px;' +
                f'white-space:nowrap;">{vshort}</span></td>',
            ]
            hover_in  = "this.style.background='#0d1a28'"
            hover_out = "this.style.background='transparent'"
            row_html = (
                '<tr style="border-bottom:1px solid #111820;" '
                f'onmouseover="{hover_in}" onmouseout="{hover_out}">' +
                "".join(cells) + "</tr>"
            )
            row_htmls.append(row_html)

        table_html = f"""
        <div style="overflow-x:auto;margin-top:8px;">
          <table style="width:100%;border-collapse:collapse;
                        background:#080c14;font-family:Inter,sans-serif;">
            <thead><tr style="background:#0d1117;">{header_cells}</tr></thead>
            <tbody>{"".join(row_htmls)}</tbody>
          </table>
        </div>
        """
        st.markdown(table_html, unsafe_allow_html=True)

        # ── CSV download + Deep Dive ──────────────────────────
        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)
        dl_col, dive_col, btn_col = st.columns([2, 2, 1])
        with dl_col:
            export_cols = [c for c in df_r.columns if not c.startswith("_")]
            csv = df_r[export_cols].to_csv(index=False)
            st.download_button(
                "⬇ Download CSV", csv,
                f"prism_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                "text/csv", use_container_width=True
            )
        with dive_col:
            dive_ticker = st.selectbox(
                "Deep Dive into:", df_r["Ticker"].tolist(), key="scanner_dive"
            )
        with btn_col:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("🔍 Deep Dive", type="primary", use_container_width=True):
                st.session_state["dive_ticker"] = dive_ticker
                st.session_state["active_tab"]  = "single"
                st.rerun()

# ── TAB 3: Watchlist ──────────────────────────────────────────
with tab_watchlist:
    st.markdown("### ⭐ My Watchlist")
    wl = wl_load()

    if not wl:
        st.info("No tickers in your watchlist yet. Go to Single Stock tab, analyze a ticker, and click '⭐ Add to Watchlist'.")
    else:
        # Quick re-scan watchlist
        if st.button("🔄 Refresh All Watchlist Data", type="primary"):
            with st.spinner("Refreshing watchlist from Google Sheets..."):
                wl_refresh_cache()
                wl = wl_load()
                for t in list(wl.keys()):
                    d_wl = fetch_data(t)
                    cs_wl = get_gf_fundamentals(t)
                    try:
                        gf_score_wl, _ = calc_gf_score(cs_wl, mkt_status)
                    except Exception:
                        gf_score_wl = 0
                    if d_wl:
                        new_verdict, _ = get_verdict(d_wl, gf_score_wl)
                        wl_add(t, wl[t].get("note",""), new_verdict,
                               d_wl["price"], d_wl["tt_score"], d_wl["vgf_score"],
                               gf_score_wl, d_wl["stage_label"], d_wl["pivot"])
            st.success("Watchlist refreshed and saved to Google Sheets!")
            st.rerun()

        st.markdown("---")

        for ticker, data in wl.items():
            history = vm_get(ticker)
            current_verdict = data.get("current_verdict", data.get("verdict", "—"))
            original_verdict = history[0]["verdict"] if history else data.get("verdict", "—")

            # Detect verdict change
            verdict_changed = len(history) >= 2 and history[-1]["verdict"] != history[-2]["verdict"]
            change_badge = " 🔔 **VERDICT CHANGED**" if verdict_changed else ""

            with st.expander(
                f"**{ticker}** — {current_verdict}{change_badge} | "
                f"Added: {data['date_added']}",
                expanded=verdict_changed
            ):
                wl_c1, wl_c2, wl_c3, wl_c4, wl_c5 = st.columns(5)
                wl_c1.metric("Price",     f"${data.get('current_price', '—')}")
                wl_c2.metric("TT Score",  f"{data.get('tt_score', '—')}/8")
                wl_c3.metric("VCS Score", f"{data.get('vgf_score', '—')}")
                wl_c4.metric("GF Score",  f"{data.get('gf_score', '—')}/7")
                wl_c5.metric("% to Pivot",f"{data.get('pct_to_pivot', '—')}%")

                if data.get("note"):
                    st.markdown(f"📝 **Note:** {data['note']}")

                # Verdict history
                if history:
                    st.markdown("**Verdict History:**")
                    for entry in reversed(history[-5:]):
                        v_cls = "verdict-changed-buy" if "BUY" in entry["verdict"] else \
                                "verdict-changed-wait" if "WAIT" in entry["verdict"] else \
                                "verdict-changed-avoid"
                        st.markdown(
                            f'<div class="verdict-history">'
                            f'<span style="color:#8b949e;">{entry["date"]}</span> &nbsp;|&nbsp; '
                            f'${entry["price"]} &nbsp;|&nbsp; TT:{entry["tt"]} VCS:{entry["vcp"]} CS:{entry["gf"]}/7<br>'
                            f'<span class="{v_cls}">{entry["verdict"]}</span>'
                            f'</div>',
                            unsafe_allow_html=True
                        )

                # Update note + remove button
                nc1, nc2 = st.columns([4, 1])
                with nc1:
                    new_note = st.text_input("Update note", value=data.get("note",""),
                                             key=f"note_{ticker}")
                with nc2:
                    st.markdown("<br>", unsafe_allow_html=True)
                    if st.button("Remove", key=f"rm_{ticker}"):
                        wl_remove(ticker)
                        st.rerun()
                if new_note != data.get("note",""):
                    wl[ticker]["note"] = new_note
                    st.session_state["watchlist"] = wl

with tab_guide:
    st.markdown("## PRISM Methodology Guide")
    st.markdown("""
### How To Use This Terminal
1. **Single Stock tab** — full PRISM analysis on any ticker
2. **Batch Scanner tab** — scan S&P 500 or Nasdaq 100 for combined setups
3. **AI Mentor button** — Claude gives a Minervini + O'Neil verdict
4. **Market Direction (sidebar)** — live SPY/QQQ trend via Alpaca API

---

### Score Reference
| Metric | Range | Target |
|--------|-------|--------|
| Trend Template | 0-8 | 7-8 ideal, 6 minimum |
| Stage | 1-4 | Stage 2 only |
| VCS Score | 0-100 | 70+ strong, 50+ acceptable |
| GF Score | 0-7 | 5+ strong, 3+ acceptable |
| Extension above 50MA | % | Under 10% = buyable |
| % to Pivot | % | Under 5% = near entry |

---

### Growth Fundamentals Breakdown
| Letter | Criteria | Minimum Target |
|--------|----------|----------------|
| **C** | Current Quarterly EPS Growth | ≥25% YoY, accelerating |
| **A** | Annual EPS Growth (3yr) | ≥25% consistently |
| **N** | New High / New Product | Within 15% of 52-week high |
| **S** | Supply & Demand | Float <500M, volume accumulation |
| **L** | Leader vs Laggard | 1yr performance >20%, RS rank top 20% |
| **I** | Institutional Sponsorship | 30–85% institutional ownership |
| **M** | Market Direction | SPY + QQQ above 50MA, uptrending — via Alpaca |

---

### Minervini PRISM Checklist
- EPS accelerating — at least 2 consecutive quarters of growth
- Revenue growing — ideally 20%+ YoY
- Institutional accumulation — RS line making new highs
- VCS forming on declining, dry volume
- Entry exactly at the pivot on a volume surge
- Market in a confirmed uptrend

---

### Key Rules
- Cut losses at 7-8% without exception
- Never average down — only add to winning positions
- Sell partial at 2R, let the rest run to 3R+
- No volume on breakout = failed breakout, exit immediately
- In a Bear market (M = Bear): reduce position sizes or go to cash
    """)

# ── Chat Window ───────────────────────────────────────────────
st.markdown("---")
st.markdown("## Ask Claude")
st.markdown(
    "<p style='color:#8b949e;font-size:13px;margin-top:-10px;'>"
    "Ask anything about PRISM methodology, GF Score, VCS, Stage 2, position sizing, or a specific ticker."
    "</p>",
    unsafe_allow_html=True
)

if "chat_history" not in st.session_state:
    st.session_state["chat_history"] = []

for msg in st.session_state["chat_history"]:
    if msg["role"] == "user":
        st.markdown(
            f"""<div style="background:#1f2937;border-radius:10px;padding:12px 16px;
            margin:6px 0;border-left:3px solid #388bfd;">
            <span style="color:#8b949e;font-size:11px;">YOU</span><br>
            <span style="color:#e6edf3;">{msg["content"]}</span></div>""",
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""<div style="background:#161b22;border-radius:10px;padding:12px 16px;
            margin:6px 0;border-left:3px solid #6e40c9;font-family:monospace;
            white-space:pre-wrap;line-height:1.6;">
            <span style="color:#8b949e;font-size:11px;">CLAUDE</span><br>
            <span style="color:#e6edf3;">{msg["content"]}</span></div>""",
            unsafe_allow_html=True
        )

user_input = st.chat_input("Ask about PRISM methodology, GF Score, VCS, Stage 2, position sizing, a specific ticker...")

if user_input:
    if "ANTHROPIC_API_KEY" not in st.secrets:
        st.error("Missing ANTHROPIC_API_KEY in Streamlit Secrets.")
    else:
        system_prompt = (
            "You are an expert in momentum trading, Stage 2 analysis, growth fundamentals, and the PRISM methodology. "
            "and William O'Neil's GF Score framework. You understand VCS patterns, trend templates, "
            "relative strength, institutional sponsorship, market direction analysis, position sizing, "
            "and risk management. Give concise, direct, actionable answers like a trading mentor. "
            "Keep responses under 350 words unless detail is needed."
        )
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        messages = [{"role": m["role"], "content": m["content"]}
                    for m in st.session_state["chat_history"]]
        with st.spinner("Claude is thinking..."):
            try:
                client = get_claude()
                response = client.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=500,
                    system=system_prompt,
                    messages=messages
                )
                reply = response.content[0].text
                st.session_state["chat_history"].append({"role": "assistant", "content": reply})
                st.rerun()
            except Exception as e:
                st.error(f"Chat error: {e}")

if st.session_state["chat_history"]:
    if st.button("Clear Chat"):
        st.session_state["chat_history"] = []
        st.rerun()

st.divider()
st.caption("Terminal Mandate: 1% Portfolio Risk Rule | Stage 2 Only | PRISM | Alpaca Market Data")
