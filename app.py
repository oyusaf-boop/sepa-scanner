import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import anthropic
import json
import time
from datetime import datetime

# ═══════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SEPA Institutional Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════
# STYLING
# ═══════════════════════════════════════════════════════════════
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
    .stButton > button:hover { transform: translateY(-1px); }
    .verdict-box {
        padding: 16px 20px; border-radius: 10px;
        font-size: 18px; font-weight: bold;
        text-align: center; margin: 12px 0;
        font-family: monospace; letter-spacing: 1px;
    }
    .verdict-buy    { background:#0d3321; color:#3fb950; border:2px solid #238636; }
    .verdict-wait   { background:#2d1f00; color:#d29922; border:2px solid #9e6a03; }
    .verdict-watch  { background:#0d1e40; color:#58a6ff; border:2px solid #1f6feb; }
    .verdict-avoid  { background:#2d0f0f; color:#f85149; border:2px solid #b91c1c; }
    .ai-box {
        background:#161b22; border:1px solid #6e40c9; border-radius:10px;
        padding:20px; font-family:monospace; white-space:pre-wrap;
        line-height:1.7; color:#e6edf3; margin-top:16px;
    }
    .score-pill {
        display:inline-block; padding:2px 10px; border-radius:12px;
        font-weight:bold; font-size:13px; margin:2px;
    }
    .pill-green { background:#0d3321; color:#3fb950; border:1px solid #238636; }
    .pill-red   { background:#2d0f0f; color:#f85149; border:1px solid #b91c1c; }
    hr { border-color: #30363d; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════
# ANTHROPIC CLIENT
# ═══════════════════════════════════════════════════════════════
@st.cache_resource
def get_claude():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])

# ═══════════════════════════════════════════════════════════════
# UNIVERSE LOADERS
# ═══════════════════════════════════════════════════════════════
@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500():
    df = pd.read_html("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")[0]
    return df["Symbol"].str.replace(".", "-", regex=False).tolist()

@st.cache_data(ttl=86400, show_spinner=False)
def get_nasdaq100():
    for t in pd.read_html("https://en.wikipedia.org/wiki/Nasdaq-100"):
        if "Ticker" in t.columns:
            return t["Ticker"].tolist()
    return []

# ═══════════════════════════════════════════════════════════════
# CORE DATA & INDICATORS
# ═══════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def fetch_data(ticker: str):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        if df.empty or len(df) < 200:
            return None

        # Moving averages
        df["SMA10"]  = df["Close"].rolling(10).mean()
        df["SMA20"]  = df["Close"].rolling(20).mean()
        df["SMA50"]  = df["Close"].rolling(50).mean()
        df["SMA150"] = df["Close"].rolling(150).mean()
        df["SMA200"] = df["Close"].rolling(200).mean()

        # ATR
        hl  = df["High"] - df["Low"]
        hc  = (df["High"] - df["Close"].shift()).abs()
        lc  = (df["Low"]  - df["Close"].shift()).abs()
        df["ATR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()

        # Volume avg
        df["VolAvg50"] = df["Volume"].rolling(50).mean()

        # 52w
        past   = df.tail(252)
        low52  = past["Low"].min()
        high52 = past["High"].max()
        price  = df["Close"].iloc[-1]

        # ── Trend Template (8 criteria) ──────────────────────────
        sma50      = df["SMA50"].iloc[-1]
        sma150     = df["SMA150"].iloc[-1]
        sma200     = df["SMA200"].iloc[-1]
        sma200_1mo = df["SMA200"].il
