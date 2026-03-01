import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
import google.generativeai as genai
from datetime import datetime, timedelta

# --- INSTITUTIONAL CONFIGURATION ---
st.set_page_config(page_title="SEPA Institutional Terminal", layout="wide")

# Secure API Handling
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
except Exception:
    st.error("Credential Error: Please add GEMINI_API_KEY to Streamlit Secrets.")

# --- CORE SEPA LOGIC ENGINE ---
def get_sepa_data(ticker):
    stock = yf.Ticker(ticker)
    # Pulling 2 years of data to ensure we have enough for 200 SMA and 52-week metrics
    hist = stock.history(period="2y")
    if hist.empty or len(hist) < 260: return None
    
    # Technical Indicators
    hist['SMA50'] = hist['Close'].rolling(window=50).mean()
    hist['SMA150'] = hist['Close'].rolling(window=150).mean()
    hist['SMA200'] = hist['Close'].rolling(window=200).mean()
    
    curr_price = hist['Close'].iloc[-1]
    
    # Correct 52-week High/Low Logic
    past_year = hist.iloc[-252:]
    low_52 = past_year['Low'].min()
    high_52 = past_year['High'].max()
    
    # Trend Template Alignment (Minervini Criteria)
    criteria = {
        "Price > SMA150 & 200": curr_price > hist['SMA150'].iloc[-1] and curr_price > hist['SMA200'].iloc[-1],
        "SMA150 > SMA200": hist['SMA150'].iloc[-1] > hist['SMA200'].iloc[-1],
        "SMA200 Trending Up": hist['SMA200'].iloc[-1] > hist['SMA200'].iloc[-20],
        "SMA50 > SMA150 & 200": hist['SMA50'].iloc[-1] > hist['SMA150'].iloc[-1],
        "Price 30% above Low": curr_price >= (low_52 * 1.3),
        "Price within 25% of High": curr_price >= (high_52 * 0.75)
    }
    
    score = sum(criteria.values())
    return {"hist": hist, "criteria": criteria, "score": score, "price": curr_price}

# --- GUI INTERFACE ---
st.title("🚀 SEPA Growth Terminal")
st.markdown("---")

# Sidebar: Risk Mandate (Minervini 1% Rule)
st.sidebar.header("Risk Management")
equity = st.sidebar.number_input("Portfolio Equity ($)", value=100000)
risk_pct = st.sidebar.slider("Risk Per Trade (%)", 0.5, 2.0, 1.0) / 100

ticker = st.text_input("Enter Ticker Symbol", "NVDA").upper()

if ticker:
    data = get_sepa_data(ticker)
    
    if data:
        # 1. Dashboard Metrics
        col1, col2, col3 = st.columns(3)
        col1.metric("Current Price", f"${data['price']:.2f}")
        col2.metric("SEPA Score", f"{data['score']}/6")
        
        # Position Sizing (Buy Cheat Sheet)
        stop_loss = st.number_input("Stop Loss Price ($)", value=data['price']*0.93)
        risk_per_share = data['price'] - stop_loss
        if risk_per_share > 0:
            pos_size = int((equity * risk_pct) / risk_per_share)
            col3.metric("Position Size", f"{pos_size} Shares")
        
        # 2. Visual Terminal
        fig = go.Figure(data=[go.Candlestick(x=data['hist'].index,
                        open=data['hist']['Open'], high=data['hist']['High'],
                        low=data['hist']['Low'], close=data['hist']['Close'], name="Price")])
        fig.add_trace(go.Scatter(x=data['hist'].index, y=data['hist']['SMA50'], name="50 SMA", line=dict(color='blue')))
        fig.add_trace(go.Scatter(x=data['hist'].index, y=data['hist']['SMA200'], name="200 SMA", line=dict(color='red')))
        st.plotly_chart(fig, use_container_width=True)

        # 3. AI Mentor Commentary
        if st.button("Request AI Mentor Analysis"):
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"Act as Mark Minervini. Analyze {ticker} at ${data['price']}. Trend Template score is {data['score']}/6. Provide a concise strategic verdict on whether this is a Stage 2 breakout or a late-stage base."
            response = model.generate_content(prompt)
            st.info(response.text)
    else:
        st.error("Data Unavailable for this ticker.")

st.markdown("---")
st.caption("Institutional Disclaimer: Analysis for educational purposes only. Maintain strict stop-losses.")
