import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import anthropic

# --- INSTITUTIONAL CONFIGURATION ---
st.set_page_config(page_title="SEPA Institutional Terminal", layout="wide", initial_sidebar_state="expanded")

# --- ENGINE: DATA & SEPA LOGIC ---
@st.cache_data(ttl=3600)
def fetch_sepa_data(ticker):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period="2y")
        if df.empty or len(df) < 260: return None
        
        df['SMA50'] = df['Close'].rolling(window=50).mean()
        df['SMA150'] = df['Close'].rolling(window=150).mean()
        df['SMA200'] = df['Close'].rolling(window=200).mean()
        
        price = df['Close'].iloc[-1]
        past_year = df.tail(252)
        low_52 = past_year['Low'].min()
        high_52 = past_year['High'].max()
        
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
        
        info = stock.info
        eps_growth = info.get('earningsQuarterlyGrowth', 0) or 0
        rev_growth = info.get('revenueGrowth', 0) or 0
        
        return {
            "df": df, "tt": tt, "price": price, "high_52": high_52,
            "low_52": low_52, "eps_growth": eps_growth, "rev_growth": rev_growth
        }
    except Exception:
        return None

# --- UI ---
st.title("🛡️ SEPA Institutional Terminal")
st.sidebar.header("Risk Mandate")
acct_size = st.sidebar.number_input("Portfolio Size ($)", value=100000, step=1000)
risk_pct = st.sidebar.slider("Risk Per Trade (%)", 0.25, 2.0, 1.0) / 100

ticker = st.text_input("Enter Growth Ticker", "NVDA").upper()

if ticker:
    with st.spinner(f"Analyzing {ticker}..."):
        data = fetch_sepa_data(ticker)
        
    if data:
        tt_passed = sum(data['tt'].values())
        extension = ((data['price'] / data['df']['SMA50'].iloc[-1]) - 1) * 100
        
        if tt_passed == 8 and extension < 10:
            verdict, color = "BUY - HIGH CONVICTION SETUP", "green"
        elif tt_passed >= 6 and extension >= 10:
            verdict, color = "WAIT - EXTENDED (DO NOT CHASE)", "orange"
        elif tt_passed < 5:
            verdict, color = "AVOID - TREND TEMPLATE FAILED", "red"
        else:
            verdict, color = "WATCH - FORMING BASE / STAGE 1", "blue"
            
        st.markdown(f"### Institutional Verdict: :{color}[{verdict}]")
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Trend Template", f"{tt_passed}/8")
        m2.metric("50MA Extension", f"{extension:.1f}%")
        m3.metric("EPS Growth (Q)", f"{data['eps_growth']*100:.1f}%")
        m4.metric("Rev Growth (Q)", f"{data['rev_growth']*100:.1f}%")

        with st.expander("📊 Execution & Position Sizing", expanded=True):
            c1, c2, c3 = st.columns(3)
            suggested_stop = data['df']['Low'].tail(15).min()
            stop_price = c1.number_input("Stop Loss Price ($)", value=float(round(suggested_stop, 2)))
            
            risk_per_share = data['price'] - stop_price
            if risk_per_share > 0:
                shares = int((acct_size * risk_pct) / risk_per_share)
                c2.metric("Position Size", f"{shares} Shares")
                c2.caption(f"Risking ${acct_size * risk_pct:,.2f}")
                target_2r = data['price'] + (risk_per_share * 2)
                c3.metric("2R Profit Target", f"${target_2r:.2f}")
            else:
                st.warning("Stop loss must be below current price.")

        fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])
        fig.add_trace(go.Candlestick(x=data['df'].index, open=data['df']['Open'], high=data['df']['High'], low=data['df']['Low'], close=data['df']['Close'], name="Price"), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['df'].index, y=data['df']['SMA50'], name="50 SMA", line=dict(color='blue', width=1)), row=1, col=1)
        fig.add_trace(go.Scatter(x=data['df'].index, y=data['df']['SMA200'], name="200 SMA", line=dict(color='red', width=2)), row=1, col=1)
        fig.add_trace(go.Bar(x=data['df'].index, y=data['df']['Volume'], name="Volume", marker_color='gray'), row=2, col=1)
        fig.update_layout(height=600, template="plotly_dark", showlegend=False, xaxis_rangeslider_visible=False)
        st.plotly_chart(fig, use_container_width=True)

        with st.expander("📋 Trend Template Breakdown"):
            for criterion, passed in data['tt'].items():
                st.markdown(f"{'✅' if passed else '❌'} {criterion}")

        if st.button("🧠 Request Claude Deep Dive"):
            try:
                if "ANTHROPIC_API_KEY" in st.secrets:
                    client = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
                    prompt = (
                        f"Analyze {ticker} at ${data['price']:.2f}. Trend Score: {tt_passed}/8. "
                        f"Extension above 50MA: {extension:.1f}%. EPS Growth: {data['eps_growth']*100:.1f}%. "
                        f"Revenue Growth: {data['rev_growth']*100:.1f}%. "
                        f"52w High: ${data['high_52']:.2f}, 52w Low: ${data['low_52']:.2f}. "
                        "Provide a blunt Mark Minervini style verdict on Stage 2 status, "
                        "VCP quality, and whether this is actionable right now. "
                        "Structure: 1) Verdict 2) Strengths 3) Risks 4) Ideal Entry Advice"
                    )
                    with st.spinner("Consulting Claude..."):
                        message = client.messages.create(
                            model="claude-sonnet-4-5",
                            max_tokens=600,
                            messages=[{"role": "user", "content": prompt}]
                        )
                        st.info(f"**Claude's Verdict:**\n\n{message.content[0].text}")
                else:
                    st.error("Missing 'ANTHROPIC_API_KEY' in Secrets.")
            except Exception as e:
                st.error(f"Claude Connection Error: {str(e)}")
    else:
        st.error("Insufficient data or invalid ticker.")

st.divider()
st.caption("Terminal Mandate: 1% Portfolio Risk Rule | Stage 2 Detection.")
