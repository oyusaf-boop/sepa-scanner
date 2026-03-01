import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import google.generativeai as genai

# --- INSTITUTIONAL CONFIGURATION ---
st.set_page_config(page_title="SEPA Institutional Terminal", layout="wide", initial_sidebar_state="expanded")

# --- ENGINE: DATA & SEPA LOGIC ---
@st.cache_data(ttl=3600)
def fetch_sepa_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        if df.empty or len(df) < 260: return None
        
        # Technical Indicators
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['SMA150'] = df['Close'].rolling(window=150).mean()
        df['SMA200'] = df['Close'].rolling(window=200).mean()
        
        price = df['Close'].iloc[-1]
        
        # Robust 52-Week Logic
        past_year = df.tail(252)
        low_52 = past_year['Low'].min()
        high_52 = past_year['High'].max()
        
        # 8-Point Trend Template Check (Minervini)
        tt = {
            "1. Price > SMA150 & SMA200": price > df['SMA150'].iloc[-1] and price > df['SMA200'].iloc[-1],
            "2. SMA150 > SMA200": df['SMA150'].iloc[-1] > df['SMA200'].iloc[-1],
            "3. SMA200 Trending Up (1mo)": df['SMA200'].iloc[-1] > df['SMA200'].iloc[-22],
            "4. SMA50 > SMA150 & SMA200": df['SMA50'].iloc[-1] > df['SMA150'].iloc[-1] and df['SMA50'].iloc[-1] > df['SMA200'].iloc[-1],
            "5. Price > SMA50": price > df['SMA50'].iloc[-1],
            "6. Price 30% Above 52w Low": price >= (low_52 * 1.30),
            "7. Price within 25% of 52w High": price >= (high_52 * 0.75),
            "8. Trend Alignment (Positive)": price > df['SMA200'].iloc[-1]
        }
        
        # Fundamental Data
        info = stock.info
        eps_growth = info.get('earningsQuarterlyGrowth', 0) or 0
        rev_growth = info.get('revenueGrowth', 0) or 0
        
        return {
            "df": df, "tt": tt, "price": price, "high_52": high_52, 
            "low_52": low_52, "eps_growth": eps_growth, "rev_growth": rev_growth
        }
    except Exception:
        return None

# --- UI COMPONENTS ---
st.title("🛡️ SEPA Institutional Terminal")
st.sidebar.header("Risk Mandate")
acct_size = st.sidebar.number_input("Portfolio Size ($)", value=100000, step=1000)
risk_pct = st.sidebar.slider("Risk Per Trade (%)", 0.25, 2.0, 1.0) / 100

ticker = st.text_input("Enter Growth Ticker (e.g., NVDA, CELH, SMCI)", "NVDA").upper()

if ticker:
    with st.spinner(f"Analyzing {ticker}..."):
        data = fetch_sepa_data(ticker)
        
    if data:
        # --- VERDICT ENGINE ---
        tt_passed = sum(data['tt'].values())
        extension = ((data['price'] / data['df']['SMA50'].iloc[-1]) - 1) * 100
        
        # Decision Matrix
        if tt_passed == 8 and extension < 10:
            verdict, color = "🚀 BUY - HIGH CONVICTION SETUP", "green"
        elif tt_passed >= 6 and extension >= 10:
            verdict, color = "⚠️ WAIT - EXTENDED (DO NOT CHASE)", "orange"
        elif tt_passed < 5:
            verdict, color = "❌ AVOID - TREND TEMPLATE FAILED", "red"
        else:
            verdict, color = "👀 WATCH -
