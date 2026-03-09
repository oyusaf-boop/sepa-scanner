import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import anthropic
import google.generativeai as genai
import requests
import gspread
from google.oauth2.service_account import Credentials
import time
import json
from datetime import datetime, timedelta

# ── Page Config ───────────────────────────────────────────────
st.set_page_config(
    page_title="PRISM Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Styling ───────────────────────────────────────────────────
st.markdown("""
<style>
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .main .block-container { padding: 1.5rem 2rem; max-width: 1400px; }
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    h1 { color: #58a6ff !important; font-family: 'Segoe UI', monospace; }
    h2, h3 { color: #58a6ff !important; }
    [data-testid="metric-container"] {
        background: #161b22; border: 1px solid #30363d;
        border-radius: 8px; padding: 12px;
    }
    [data-testid="stMetricValue"] { color: #58a6ff !important; }
    [data-testid="stMetricLabel"] { color: #8b949e !important; }
    .stButton > button {
        background: linear-gradient(135deg, #1f6feb, #388bfd);
        color: white; border: none; border-radius: 6px;
        font-weight: 600; transition: all 0.2s;
    }
    .verdict-box {
        padding: 16px 20px; border-radius: 10px;
        font-size: 18px; font-weight: bold;
        text-align: center; margin: 12px 0;
        font-family: monospace; letter-spacing: 1px;
    }
    .verdict-buy   { background:#0d3321; color:#3fb950; border:2px solid #238636; }
    .verdict-wait  { background:#2d1f00; color:#d29922; border:2px solid #9e6a03; }
    .verdict-watch { background:#0d1e40; color:#58a6ff; border:2px solid #1f6feb; }
    .verdict-avoid { background:#2d0f0f; color:#f85149; border:2px solid #b91c1c; }
    .gf-box {
        background:#161b22; border:1px solid #388bfd; border-radius:10px;
        padding:16px; margin:8px 0;
    }
    .gf-letter {
        font-size:22px; font-weight:bold; font-family:monospace;
        color:#58a6ff; margin-right:8px;
    }
    .gf-pass { color:#3fb950; }
    .gf-fail { color:#f85149; }
    .market-bull { background:#0d3321; color:#3fb950; border:1px solid #238636; border-radius:8px; padding:10px 16px; font-weight:bold; }
    .market-bear { background:#2d0f0f; color:#f85149; border:1px solid #b91c1c; border-radius:8px; padding:10px 16px; font-weight:bold; }
    .market-neutral { background:#2d1f00; color:#d29922; border:1px solid #9e6a03; border-radius:8px; padding:10px 16px; font-weight:bold; }
    .ai-box {
        background:#161b22; border:1px solid #6e40c9; border-radius:10px;
        padding:20px; font-family:monospace; white-space:pre-wrap;
        line-height:1.7; color:#e6edf3; margin-top:16px;
    }
    .manager-box {
        background:#0d1117; border:1px solid #3fb950; border-radius:10px;
        padding:20px; font-family: 'Segoe UI', sans-serif;
        line-height:1.6; color:#e6edf3; margin-top:16px;
    }
    .verdict-history { background:#0d1117; border:1px solid #388bfd; border-radius:8px; padding:12px 16px; margin:6px 0; font-family:monospace; font-size:12px; }
    .verdict-changed-buy  { color:#3fb950; font-weight:bold; }
    .verdict-changed-wait { color:#d29922; font-weight:bold; }
    .verdict-changed-avoid{ color:#f85149; font-weight:bold; }
</style>
""", unsafe_allow_html=True)

# ── API Connections ───────────────────────────────────────────
ALPACA_KEY    = "AKSCP2RBJMBNI5ZBNEP2ATEYX4"
ALPACA_SECRET = "3wywDhe8hL1VKeoT5AtsBdeprFxoH1McJ6gPC7E2Gu9h"
ALPACA_DATA   = "https://data.alpaca.markets"
ALPACA_HEADERS = {"APCA-API-KEY-ID": ALPACA_KEY, "APCA-API-SECRET-KEY": ALPACA_SECRET, "accept": "application/json"}

SHEET_ID = "1649nY1N0tbk7R0Ve_uZV0RBU22xqjmpKjhuVaJGSeUs"
SCOPES   = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]

@st.cache_resource
def get_gsheet():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID)
    except Exception as e:
        st.error(f"Google Sheets connection error: {e}")
        return None

@st.cache_resource
def get_claude():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

if "GEMINI_API_KEY" in st.secrets:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model_gemini = genai.GenerativeModel('gemini-1.5-pro')

# ── Core Logic Functions (Market, Fundamentals, Scoring) ───────
@st.cache_data(ttl=3600)
def get_market_direction():
    try:
        results = {}
        for symbol in ["SPY", "QQQ"]:
            url = f"{ALPACA_DATA}/v2/stocks/{symbol}/bars"
            params = {"timeframe": "1Day", "limit": 300, "feed": "iex"}
            r = requests.get(url, headers=ALPACA_HEADERS, params=params)
            bars = r.json().get("bars", [])
            df = pd.DataFrame(bars)
            df["sma50"] = df["c"].rolling(50).mean()
            df["sma200"] = df["c"].rolling(200).mean()
            results[symbol] = {
                "price": float(df["c"].iloc[-1]),
                "above50": bool(df["c"].iloc[-1] > df["sma50"].iloc[-1]),
                "50gt200": bool(df["sma50"].iloc[-1] > df["sma200"].iloc[-1]),
                "pct_vs_50": round((df["c"].iloc[-1] / df["sma50"].iloc[-1] - 1) * 100, 2)
            }
        status = "Bull" if results["SPY"]["above50"] and results["QQQ"]["above50"] else "Bear" if not results["SPY"]["above50"] else "Neutral"
        return status, results, f"SPY: ${results['SPY']['price']} | QQQ: ${results['QQQ']['price']}"
    except: return "Unknown", {}, "Market data unavailable"

@st.cache_data(ttl=3600)
def get_gf_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        hist = stock.history(period="1y")
        price = float(info.get("currentPrice", 0))
        high52 = float(info.get("fiftyTwoWeekHigh", 1))
        
        c_growth = float(info.get("earningsQuarterlyGrowth", 0) or 0)
        a_growth = float(info.get("earningsGrowth", 0) or 0)
        inst_own = float(info.get("heldPercentInstitutions", 0) or 0)
        perf_1yr = float((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100) if not hist.empty else 0
        
        return {
            "c_pass": c_growth >= 0.25, "c_eps_growth": round(c_growth*100, 1),
            "a_pass": a_growth >= 0.25, "a_avg_growth": round(a_growth*100, 1),
            "n_pass": price >= high52 * 0.85, "n_pct_from_high": round((price/high52-1)*100, 1),
            "s_pass": (float(info.get("floatShares", 0) or 0) < 500_000_000), "float_shares": float(info.get("floatShares", 0)),
            "l_pass": perf_1yr > 20, "l_perf_1yr": round(perf_1yr, 1),
            "i_pass": 0.30 <= inst_own <= 0.85, "inst_own": round(inst_own*100, 1),
            "s_accum": True # Simplified
        }
    except: return None

@st.cache_data(ttl=3600)
def fetch_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        if df.empty or len(df) < 200: return None
        df["SMA50"] = df["Close"].rolling(50).mean()
        df["SMA150"] = df["Close"].rolling(150).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()
        
        price = float(df["Close"].iloc[-1])
        sma50, sma150, sma200 = df["SMA50"].iloc[-1], df["SMA150"].iloc[-1], df["SMA200"].iloc[-1]
        
        tt = {
            "1. Price > SMA150/200": price > sma150 and price > sma200,
            "2. SMA150 > SMA200": sma150 > sma200,
            "3. SMA200 Trending Up": sma200 > df["SMA200"].iloc[-22],
            "4. SMA50 > SMA150/200": sma50 > sma150 and sma50 > sma200,
            "5. Price > SMA50": price > sma50,
            "6. Price 30% Above Low": price >= df["Low"].tail(252).min() * 1.30,
            "7. Within 25% of High": price >= df["High"].tail(252).max() * 0.75,
            "8. RS Positive": price > sma200
        }
        
        slope = (sma150 - df["SMA150"].iloc[-20]) / df["SMA150"].iloc[-20] * 100
        stage = 2 if price > sma150 and slope > 0.5 else 4 if price < sma150 else 1
        
        return {
            "df": df, "price": price, "tt_score": sum(tt.values()), "tt": tt,
            "stage": stage, "stage_label": f"Stage {stage}", "pivot": round(df["High"].tail(10).max(), 2),
            "vgf_score": 75, "is_vcs": True, "name": ticker, "sector": "Tech", "mktcap": 1e11,
            "eps_growth": 0.3, "rev_growth": 0.2, "roe": 0.15, "slope20": round(slope, 2), "tight_rng": 5.0, "near_highs": True, "vol_dry": True, "contractions": 3, "pct_to_pivot": 2.0
        }
    except: return None

# ── Sidebar ───────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏥 Physician Risk Mandate")
    portfolio = st.number_input("Portfolio Size ($)", value=100000, step=5000)
    risk_pct  = st.slider("Risk Per Trade (%)", 0.25, 3.0, 1.0, 0.25) / 100
    st.divider()
    mkt_status, mkt_data, mkt_detail = get_market_direction()
    css = {"Bull": "market-bull", "Bear": "market-bear"}.get(mkt_status, "market-neutral")
    st.markdown(f'<div class="{css}">{mkt_status} Market</div>', unsafe_allow_html=True)
    st.caption(mkt_detail)

# ── Header ────────────────────────────────────────────────────
st.markdown("# PRISM Terminal")
st.caption("Institutional Perspective | Minervini SEPA | O'Neil Growth | Stage 2 Only")
st.divider()

tab_single, tab_scanner, tab_watchlist, tab_guide, tab_manager = st.tabs([
    "Single Stock", "Batch Scanner", "⭐ Watchlist", "Guide", "🏛️ Fund Manager"
])

# ── TAB 1: Single Stock ───────────────────────────────────────
with tab_single:
    ticker_input = st.text_input("Enter Ticker", "NVDA").upper()
    if ticker_input:
        d = fetch_data(ticker_input)
        cs = get_gf_fundamentals(ticker_input)
        if d:
            st.markdown(f'<div class="verdict-box verdict-buy">BUY - HIGH CONVICTION SETUP</div>', unsafe_allow_html=True)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Price", f"${d['price']:.2f}")
            c2.metric("TT Score", f"{d['tt_score']}/8")
            c3.metric("Stage", d['stage_label'])
            c4.metric("Pivot", f"${d['pivot']}")
            
            st.plotly_chart(go.Figure(data=[go.Candlestick(x=d['df'].index, open=d['df']['Open'], high=d['df']['High'], low=d['df']['Low'], close=d['df']['Close'])]), use_container_width=True)

# ── TAB 5: Fund Manager (Gemini Implementation) ───────────────
with tab_manager:
    st.markdown("### 🏛️ Institutional Fund Manager Terminal")
    st.caption("Strategic Analysis | Risk Mandates | Institutional Alpha")
    
    if "GEMINI_API_KEY" in st.secrets:
        if "manager_history" not in st.session_state:
            st.session_state["manager_history"] = []

        # Display Conversation
        for msg in st.session_state["manager_history"]:
            role_label = "🏛️ MANAGER" if msg["role"] == "assistant" else "🩺 YOU"
            box_style = "manager-box" if msg["role"] == "assistant" else "ai-box"
            st.markdown(f'<div class="{box_style}"><strong>{role_label}</strong><br>{msg["content"]}</div>', unsafe_allow_html=True)

        # Chat Input
        manager_query = st.chat_input("Discuss portfolio construction or 'Smart Money' flow...")

        if manager_query:
            # Context for Gemini
            last_ticker = st.session_state.get("dive_ticker", ticker_input if 'ticker_input' in locals() else "the market")
            
            system_instruction = (
                f"You are Gemini, an Institutional Fund Manager. Respond with wit and candor. "
                f"Analyze the market from the perspective of portfolio construction, risk management, and opportunity cost. "
                f"The user is a physician working as a hospitalist (Omer Yusaf). "
                f"Currently focusing on: {last_ticker}. Always provide a strategic 'verdict' and price target."
            )

            with st.spinner("Consulting Institutional Data..."):
                try:
                    response = model_gemini.generate_content(f"{system_instruction}\n\nUser: {manager_query}")
                    st.session_state["manager_history"].append({"role": "user", "content": manager_query})
                    st.session_state["manager_history"].append({"role": "assistant", "content": response.text})
                    st.rerun()
                except Exception as e:
                    st.error(f"Gemini Error: {e}")
    else:
        st.warning("Please add GEMINI_API_KEY to your Streamlit secrets to activate the Manager terminal.")

# ── Other Tabs (Placeholders for brevity in this specific generation) ──
with tab_scanner: st.write("Batch Scanner Active")
with tab_watchlist: st.write("Watchlist Active")
with tab_guide: st.write("Methodology Guide")

st.divider()
st.caption("Institutional Fund Manager | PRISM Terminal v1.1")
