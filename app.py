import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import anthropic
import requests
import time
from datetime import datetime, timedelta

st.set_page_config(
    page_title="SEPA Institutional Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Enhanced Institutional Terminal CSS ───────────────────────
st.markdown("""
<style>
    /* Base Terminal Theme */
    .stApp { background-color: #090c10; color: #c9d1d9; font-family: 'SF Mono', Consolas, 'Liberation Mono', Menlo, Courier, monospace; }
    .main .block-container { padding: 1rem 1.5rem; max-width: 100%; }
    [data-testid="stSidebar"] { background-color: #010409; border-right: 1px solid #21262d; }
    h1, h2, h3, h4 { color: #58a6ff !important; font-family: 'SF Mono', Consolas, monospace; text-transform: uppercase; letter-spacing: 1px; }
    
    /* High-Density Metrics */
    [data-testid="metric-container"] {
        background: #0d1117; border: 1px solid #30363d;
        border-radius: 4px; padding: 8px 12px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.5);
    }
    [data-testid="stMetricValue"] { color: #79c0ff !important; font-size: 1.4rem !important; font-weight: 700 !important; }
    [data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 0.8rem !important; text-transform: uppercase; }
    
    /* Execution & Risk Module */
    .risk-panel {
        background: #161b22; border: 1px solid #f85149; border-radius: 6px;
        padding: 16px; margin-bottom: 16px;
    }
    .risk-panel h4 { color: #f85149 !important; margin-top: 0; border-bottom: 1px solid #30363d; padding-bottom: 8px;}
    
    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #238636, #2ea043);
        color: white; border: 1px solid #2ea043; border-radius: 4px;
        font-weight: 600; text-transform: uppercase; letter-spacing: 1px;
        width: 100%; transition: all 0.2s;
    }
    .stButton > button:hover { background: #2ea043; border-color: #3fb950; transform: translateY(-1px); }
    
    /* Verdicts */
    .verdict-box {
        padding: 12px 16px; border-radius: 4px;
        font-size: 16px; font-weight: 800;
        text-align: center; margin: 8px 0;
        text-transform: uppercase; letter-spacing: 2px;
    }
    .verdict-buy   { background:#04260f; color:#3fb950; border:1px solid #238636; }
    .verdict-wait  { background:#332200; color:#d29922; border:1px solid #9e6a03; }
    .verdict-watch { background:#0c2242; color:#58a6ff; border:1px solid #1f6feb; }
    .verdict-avoid { background:#3b0a0a; color:#f85149; border:1px solid #b91c1c; }
    
    /* Data Tables & CAN SLIM */
    .canslim-box {
        background:#0d1117; border:1px solid #21262d; border-radius:4px;
        padding:12px; margin:4px 0; font-size: 13px;
    }
    .canslim-letter { font-size:18px; font-weight:bold; color:#58a6ff; margin-right:8px; }
    .canslim-pass { color:#3fb950; }
    .canslim-fail { color:#f85149; }
    
    hr { border-color: #21262d; margin: 1.5rem 0; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; font-weight: 600; text-transform: uppercase; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; background: #0d1117; border-top: 2px solid #58a6ff; }
</style>
""", unsafe_allow_html=True)


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


# ── Alpaca: Market Direction (M in CAN SLIM) ──────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_market_direction():
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


# ── yfinance: Full CAN SLIM fundamentals ──────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_canslim_fundamentals(ticker):
    try:
        stock = yf.Ticker(ticker)
        info  = stock.info

        # C: Current Quarter EPS growth
        try:
            qe = stock.quarterly_earnings
            if qe is not None and len(qe) >= 2:
                eps_recent  = float(qe["Earnings"].iloc[0])
                eps_yr_ago  = float(qe["Earnings"].iloc[4]) if len(qe) >= 5 else None
                if eps_yr_ago and eps_yr_ago != 0:
                    c_eps_growth = (eps_recent - eps_yr_ago) / abs(eps_yr_ago)
                else:
                    c_eps_growth = float(info.get("earningsQuarterlyGrowth", 0) or 0)
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

        # A: Annual EPS growth
        try:
            ae = stock.earnings 
            if ae is not None and len(ae) >= 2:
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

        # N: New High / Near 52-week high
        price   = float(info.get("currentPrice", info.get("regularMarketPrice", 0)) or 0)
        high52  = float(info.get("fiftyTwoWeekHigh", 0) or 0)
        n_pass  = bool(high52 > 0 and price >= high52 * 0.85)
        n_pct   = round((price / high52 - 1) * 100, 1) if high52 > 0 else 0.0

        # S: Supply/Demand
        float_shares = float(info.get("floatShares", 0) or 0)
        avg_vol      = float(info.get("averageVolume", 0) or 0)
        avg_vol10    = float(info.get("averageVolume10days", 0) or 0)
        s_accum = bool(avg_vol10 > avg_vol * 1.05) if avg_vol > 0 else False
        s_float_ok = bool(0 < float_shares < 500_000_000)
        s_pass = bool(s_accum or s_float_ok)

        # L: Leader
        try:
            hist = stock.history(period="1y")
            if len(hist) > 0:
                l_perf_1yr = float((hist["Close"].iloc[-1] / hist["Close"].iloc[0] - 1) * 100)
            else:
                l_perf_1yr = 0.0
        except Exception:
            l_perf_1yr = 0.0
        l_pass = bool(l_perf_1yr > 20)

        # I: Institutional Sponsorship
        inst_own   = float(info.get("institutionalOwnershipPercentage",
                          info.get("heldPercentInstitutions", 0)) or 0)
        i_pass = bool(0.30 <= inst_own <= 0.85)

        return {
            "c_eps_growth": round(c_eps_growth * 100, 1),
            "c_accel":      c_accel,
            "c_pass":       c_pass,
            "a_avg_growth": round(a_avg_growth * 100, 1),
            "a_consistent": a_consistent,
            "a_pass":       a_pass,
            "n_pct_from_high": n_pct,
            "n_pass":          n_pass,
            "float_shares": float_shares,
            "avg_vol":      avg_vol,
            "avg_vol10":    avg_vol10,
            "s_accum":      s_accum,
            "s_float_ok":   s_float_ok,
            "s_pass":       s_pass,
            "l_perf_1yr": round(l_perf_1yr, 1),
            "l_pass":     l_pass,
            "inst_own": round(inst_own * 100, 1),
            "i_pass":   i_pass,
        }
    except Exception as e:
        return None

def canslim_score(cs, market_status):
    if cs is None:
        return 0, {}
    m_pass = market_status == "Bull"
    breakdown = {
        "C": cs["c_pass"], "A": cs["a_pass"], "N": cs["n_pass"],
        "S": cs["s_pass"], "L": cs["l_pass"], "I": cs["i_pass"],
        "M": m_pass,
    }
    score = sum(breakdown.values())
    return score, breakdown

# (Universe Fetchers - Truncated internal list to save space, but logic intact)
@st.cache_data(ttl=86400, show_spinner=False)
def get_sp500(): return ["AAPL","MSFT","NVDA","AVGO","ORCL","CRM"]

@st.cache_data(ttl=86400, show_spinner=False)
def get_nasdaq100(): return ["AAPL","MSFT","NVDA","AMZN","META","GOOGL"]

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
            "1. Price > 150 & 200 MA":       bool(price > sma150 and price > sma200),
            "2. 150 MA > 200 MA":            bool(sma150 > sma200),
            "3. 200 MA Trending Up":         bool(sma200 > sma200_1mo),
            "4. 50 MA > 150 & 200 MA":       bool(sma50 > sma150 and sma50 > sma200),
            "5. Price > 50 MA":              bool(price > sma50),
            "6. 30% Above 52w Low":          bool(price >= low52 * 1.30),
            "7. Within 25% of 52w High":     bool(price >= high52 * 0.75),
            "8. RS vs 200 MA":               bool(price > sma200),
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
        vcp_score  = int(min(100, 30*contractions + (15 if vol_dry else 0)
                             + (15 if is_tight else 0) + (10 if near_highs else 0)))
        is_vcp = bool(contractions >= 2 and is_tight and near_highs)

        info       = stock.info
        eps_growth = float(info.get("earningsQuarterlyGrowth", 0) or 0)
        rev_growth = float(info.get("revenueGrowth", 0) or 0)
        roe        = float(info.get("returnOnEquity", 0) or 0)
        mktcap     = float(info.get("marketCap", 0) or 0)
        sector     = str(info.get("sector", "N/A"))
        name       = str(info.get("shortName", ticker))

        return {
            "df": df, "price": price, "sma50": sma50, "sma150": sma150, "sma200": sma200,
            "high52": high52, "low52": low52, "tt": tt, "tt_score": int(sum(tt.values())),
            "stage": stage, "stage_label": stage_label, "slope20": round(slope20, 2),
            "vcp_score": vcp_score, "is_vcp": is_vcp, "contractions": contractions,
            "tight_rng": round(tight_rng, 2), "near_highs": near_highs, "vol_dry": vol_dry,
            "pivot": round(pivot, 2), "pct_to_pivot": round(pct_to_pivot, 2),
            "eps_growth": eps_growth, "rev_growth": rev_growth, "roe": roe, 
            "mktcap": mktcap, "sector": sector, "name": name,
        }
    except Exception:
        return None

def get_verdict(d, cs_score=0):
    tt  = d["tt_score"]
    ext = (d["price"] / d["sma50"] - 1) * 100
    stg = d["stage"]
    vcp = d["vcp_score"]
    if tt >= 7 and stg == 2 and ext < 10 and vcp >= 60 and cs_score >= 5:
        return "BUY: INSTITUTIONAL SEPA+CANSLIM", "buy"
    elif tt >= 7 and stg == 2 and ext < 10 and vcp >= 60:
        return "BUY: HIGH CONVICTION SEPA", "buy"
    elif tt >= 6 and stg == 2 and ext >= 10:
        return "WAIT: PRICE EXTENDED", "wait"
    elif tt >= 6 and stg == 2:
        return "WATCH: STAGE 2 BASE BUILDING", "watch"
    elif tt < 5 or stg == 4:
        return "AVOID: FAILED TREND TEMPLATE", "avoid"
    else:
        return "WATCH: STAGE 1 FORMATION", "watch"

def make_chart(d, ticker, stop_price, target_2r, target_3r):
    df = d["df"].tail(180)
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.65, 0.15, 0.20],
        subplot_titles=("", "", "Relative Strength (Price / 200MA)")
    )
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"],
        increasing_line_color="#2ea043", decreasing_line_color="#f85149",
        name="Price"
    ), row=1, col=1)
    for col, color, width, name in [
        ("SMA50",  "#e3b341", 1.2, "50 Day"),
        ("SMA150", "#d29922", 1.2, "150 Day"),
        ("SMA200", "#c93c37", 1.8, "200 Day"),
    ]:
        fig.add_trace(go.Scatter(
            x=df.index, y=df[col], name=name,
            line=dict(color=color, width=width)
        ), row=1, col=1)
    
    fig.add_hline(y=d["pivot"],  line=dict(color="#58a6ff", width=1.5, dash="dash"), annotation_text=f"Pivot ${d['pivot']:.2f}", row=1, col=1)
    fig.add_hline(y=stop_price,  line=dict(color="#f85149", width=1.2, dash="dot"), annotation_text=f"Stop ${stop_price:.2f}", row=1, col=1)
    
    colors = ["#2ea043" if c >= o else "#f85149" for c, o in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(
        x=df.index, y=df["Volume"], marker_color=colors,
        opacity=0.75, name="Volume"
    ), row=2, col=1)
    fig.add_trace(go.Scatter(
        x=df.index, y=df["VolAvg50"], name="VolAvg50",
        line=dict(color="#8b949e", width=1, dash="dash")
    ), row=2, col=1)
    
    rs_line  = df["Close"] / df["SMA200"]
    rs_color = "#58a6ff" if float(rs_line.iloc[-1]) >= float(rs_line.tail(20).max()) * 0.99 else "#8b949e"
    fig.add_trace(go.Scatter(
        x=df.index, y=rs_line, name="RS vs 200MA",
        line=dict(color=rs_color, width=1.5)
    ), row=3, col=1)
    
    fig.update_layout(
        height=650, template="plotly_dark",
        plot_bgcolor="#0d1117", paper_bgcolor="#0d1117",
        font=dict(color="#c9d1d9", family="monospace"),
        legend=dict(orientation="h", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        xaxis_rangeslider_visible=False,
        margin=dict(t=30, b=20, l=40, r=40)
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262d")
    fig.update_yaxes(showgrid=True, gridcolor="#21262d")
    return fig


# ── Sidebar Configuration ─────────────────────────────────────
with st.sidebar:
    st.markdown("## RISK MANDATE")
    portfolio = st.number_input("Fund AUM / Portfolio Size ($)", value=100000, step=10000, format="%d")
    risk_pct  = st.slider("Max Capital Risk per Trade (%)", 0.10, 2.0, 1.0, 0.10) / 100
    st.markdown("---")
    st.markdown("## SCANNER PARAMETERS")
    min_tt       = st.slider("Min Trend Template", 4, 8, 7)
    min_vcp      = st.slider("Min VCP Condition", 0, 100, 50, 10)
    min_canslim  = st.slider("Min CAN SLIM Check", 0, 7, 4, 1)
    min_price    = st.number_input("Liquidity: Min Price ($)", value=10.0, step=1.0)
    min_vol      = st.number_input("Liquidity: Min Volume", value=500000, step=100000)
    
    st.markdown("---")
    st.markdown("## SYSTEM MARKET DIRECTION")
    with st.spinner("Fetching Institutional Flow..."):
        mkt_status, mkt_data, mkt_detail = get_market_direction()
    
    css_class = {"Bull": "market-bull", "Bear": "market-bear"}.get(mkt_status, "market-neutral")
    st.markdown(f'<div class="{css_class}">STATUS: {mkt_status.upper()}</div>', unsafe_allow_html=True)
    if mkt_data:
        for sym, r in mkt_data.items():
            st.markdown(f"<span style='color:#8b949e;font-size:11px;'>{sym}: ${r['price']} | vs 50MA: {r['pct_vs_50']}%</span>", unsafe_allow_html=True)


# ── Main Header ───────────────────────────────────────────────
st.markdown("## QUANTITATIVE SEPA / CAN SLIM TERMINAL")
st.markdown("---")

tab_single, tab_scanner = st.tabs(["EXECUTION & ANALYSIS", "BATCH SCANNER"])

# ── TAB 1: Single Stock / Execution View ──────────────────────
with tab_single:
    top_c1, top_c2 = st.columns([1, 4])
    with top_c1:
        ticker_input = st.text_input("TICKER ENTRY", "NVDA", placeholder="e.g. NVDA").strip().upper()
    
    if ticker_input:
        with st.spinner(f"Aggregating Order Book & Technicals for {ticker_input}..."):
            d  = fetch_data(ticker_input)
            cs = get_canslim_fundamentals(ticker_input)
            cs_score, cs_breakdown = canslim_score(cs, mkt_status)

        if d is None:
            st.error("Invalid ticker or insufficient historical data.")
        else:
            verdict_text, verdict_class = get_verdict(d, cs_score)
            
            with top_c2:
                st.markdown(f'<div class="verdict-box verdict-{verdict_class}">{verdict_text}</div>', unsafe_allow_html=True)

            # High-Density Metrics Row
            st.markdown("<br>", unsafe_allow_html=True)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("LTP (Price)", f"${d['price']:.2f}")
            c2.metric("Trend Template", f"{d['tt_score']}/8", delta="VALID" if d['tt_score'] >= min_tt else "INVALID", delta_color="normal" if d['tt_score'] >= min_tt else "inverse")
            c3.metric("Stage Analysis", str(d['stage']), delta=d['stage_label'], delta_color="normal" if d['stage'] == 2 else "inverse")
            c4.metric("VCP Condition", f"{d['vcp_score']}/100", delta="CONFIRMED" if d['is_vcp'] else "UNCONFIRMED", delta_color="normal" if d['is_vcp'] else "off")
            c5.metric("CAN SLIM Check", f"{cs_score}/7", delta="PASS" if cs_score >= min_canslim else "FAIL", delta_color="normal" if cs_score >= min_canslim else "inverse")

            st.markdown("<br>", unsafe_allow_html=True)
            
            # Architecture Layout: Chart (Left 70%) | Risk Engine (Right 30%)
            col_chart, col_risk = st.columns([7, 3])
            
            with col_risk:
                st.markdown('<div class="risk-panel">', unsafe_allow_html=True)
                st.markdown("#### RISK MANAGEMENT ENGINE")
                
                suggested_stop = round(d["price"] * 0.92, 2)
                stop_price = st.number_input("Hard Stop Level ($)", value=suggested_stop, step=0.01)
                
                risk_per_share = d["pivot"] - stop_price
                if risk_per_share > 0:
                    dollar_risk = portfolio * risk_pct
                    shares      = int(dollar_risk / risk_per_share)
                    pos_value   = shares * d["pivot"]
                    target_2r   = d["pivot"] + (risk_per_share * 2)
                    target_3r   = d["pivot"] + (risk_per_share * 3)
                    
                    st.markdown("---")
                    st.metric("Total Capital at Risk", f"${dollar_risk:,.2f}")
                    st.metric("Risk Per Share", f"${risk_per_share:.2f} ({(risk_per_share/d['pivot']*100):.1f}%)")
                    st.metric("Optimal Position Size", f"{shares:,} Shares")
                    st.markdown("---")
                    st.metric("Projected Entry Value", f"${pos_value:,.2f} ({(pos_value/portfolio*100):.1f}% AUM)")
                    st.metric("Target Level (2R)", f"${target_2r:.2f}")
                else:
                    st.warning("Stop loss must be below pivot entry price to calculate risk.")
                    target_2r, target_3r = d["pivot"] * 1.10, d["pivot"] * 1.15
                st.markdown('</div>', unsafe_allow_html=True)
                
            with col_chart:
                fig = make_chart(d, ticker_input, stop_price, target_2r, target_3r)
                st.plotly_chart(fig, use_container_width=True)

            # Data Density Section (Bottom)
            st.markdown("### FUNDAMENTAL & TECHNICAL METRICS")
            st.markdown("---")
            d1, d2, d3, d4 = st.columns(4)
            
            with d1:
                st.markdown("**TREND TEMPLATE CRITERIA**")
                for criterion, passed in d["tt"].items():
                    color = "#3fb950" if passed else "#f85149"
                    st.markdown(f"<span style='color:{color}; font-size:12px;'>{'■' if passed else '□'} {criterion}</span>", unsafe_allow_html=True)
            
            with d2:
                st.markdown("**VCP DYNAMICS**")
                st.markdown(f"Contractions: **{d['contractions']}**")
                st.markdown(f"10-Day Tightness: **{d['tight_rng']}%**")
                st.markdown(f"Near 52W Highs: **{'Yes' if d['near_highs'] else 'No'}**")
                st.markdown(f"Volume Dry-Up: **{'Yes' if d['vol_dry'] else 'No'}**")
                st.markdown(f"Pivot Proximity: **{d['pct_to_pivot']}%**")

            with d3:
                st.markdown("**SEPA FUNDAMENTALS**")
                st.markdown(f"Sector: **{d['sector']}**")
                st.markdown(f"Market Cap: **${d['mktcap']/1e9:.1f}B**")
                st.markdown(f"Qrtly EPS Growth: **{d['eps_growth']*100:.1f}%**")
                st.markdown(f"Revenue Growth: **{d['rev_growth']*100:.1f}%**")
                st.markdown(f"Return on Equity: **{d['roe']*100:.1f}%**")

            with d4:
                st.markdown("**CAN SLIM CHECKLIST**")
                if cs:
                    metrics = [
                        ("C", f"{cs['c_eps_growth']}% Q-EPS", cs['c_pass']),
                        ("A", f"{cs['a_avg_growth']}% A-EPS", cs['a_pass']),
                        ("N", f"Near Highs", cs['n_pass']),
                        ("S", f"Accumulation", cs['s_pass']),
                        ("L", f"{cs['l_perf_1yr']}% RS", cs['l_pass']),
                        ("I", f"{cs['inst_own']}% Inst", cs['i_pass']),
                    ]
                    for letter, label, passed in metrics:
                        color = "#3fb950" if passed else "#f85149"
                        st.markdown(f"<span style='color:{color}; font-size:12px;'><strong>{letter}</strong> | {label}</span>", unsafe_allow_html=True)


# ── TAB 2: Batch Scanner ──────────────────────────────────────
with tab_scanner:
    st.markdown("### BATCH SCREENING ENGINE")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        universe = st.selectbox("Universe Selection", ["S&P 500", "Nasdaq 100", "Custom List"])
    with sc2:
        max_tickers = st.slider("Limit Processing", 10, 200, 50, 10)
    with sc3:
        custom_raw = st.text_input("Custom Identifiers (CSV)", "AAPL,NVDA,MSFT,META")

    if st.button("EXECUTE SCAN", type="primary", use_container_width=True):
        tickers = get_sp500()[:max_tickers] if universe == "S&P 500" else get_nasdaq100()[:max_tickers] if universe == "Nasdaq 100" else [t.strip().upper() for t in custom_raw.split(",") if t.strip()]

        prog  = st.progress(0, text="Initializing Quantitative Screen...")
        rows  = []
        total = len(tickers)

        for i, t in enumerate(tickers):
            prog.progress((i+1)/total, text=f"Processing Book: {t} ({i+1}/{total})")
            d = fetch_data(t)
            if d is None or d["price"] < min_price or d["df"]["Volume"].tail(50).mean() < min_vol: continue
            if d["tt_score"] < min_tt or d["vcp_score"] < min_vcp or d["stage"] != 2: continue

            cs = get_canslim_fundamentals(t)
            cs_score, _ = canslim_score(cs, mkt_status)
            if cs_score < min_canslim: continue

            ext = (d["price"] / d["sma50"] - 1) * 100
            rows.append({
                "Ticker": t, "Price": d["price"], "TT Score": d["tt_score"], 
                "VCP": d["vcp_score"], "CANSLIM": cs_score, 
                "Ext%": round(ext, 1), "%toPivot": d["pct_to_pivot"],
                "EPS Gr%": round(d["eps_growth"]*100, 1)
            })
            time.sleep(0.05)

        prog.empty()
        if rows:
            df_r = pd.DataFrame(rows).sort_values(["CANSLIM", "VCP"], ascending=False).reset_index(drop=True)
            st.dataframe(df_r.style.format({"Price": "${:.2f}", "Ext%": "{:.1f}%", "%toPivot": "{:.1f}%", "EPS Gr%": "{:.1f}%"}), use_container_width=True, height=400)
        else:
            st.warning("Zero assets passed the active liquidity and technical threshold parameters.")
