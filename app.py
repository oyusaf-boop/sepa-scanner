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
    .verdict-buy   { background:#0d3321; color:#3fb950; border:2px solid #238636; }
    .verdict-wait  { background:#2d1f00; color:#d29922; border:2px solid #9e6a03; }
    .verdict-watch { background:#0d1e40; color:#58a6ff; border:2px solid #1f6feb; }
    .verdict-avoid { background:#2d0f0f; color:#f85149; border:2px solid #b91c1c; }
    .canslim-box {
        background:#161b22; border:1px solid #388bfd; border-radius:10px;
        padding:16px; margin:8px 0;
    }
    .canslim-letter {
        font-size:22px; font-weight:bold; font-family:monospace;
        color:#58a6ff; margin-right:8px;
    }
    .canslim-pass { color:#3fb950; }
    .canslim-fail { color:#f85149; }
    .canslim-warn { color:#d29922; }
    .market-bull { background:#0d3321; color:#3fb950; border:1px solid #238636;
                   border-radius:8px; padding:10px 16px; font-weight:bold; }
    .market-bear { background:#2d0f0f; color:#f85149; border:1px solid #b91c1c;
                   border-radius:8px; padding:10px 16px; font-weight:bold; }
    .market-neutral { background:#2d1f00; color:#d29922; border:1px solid #9e6a03;
                      border-radius:8px; padding:10px 16px; font-weight:bold; }
    .ai-box {
        background:#161b22; border:1px solid #6e40c9; border-radius:10px;
        padding:20px; font-family:monospace; white-space:pre-wrap;
        line-height:1.7; color:#e6edf3; margin-top:16px;
    }
    hr { border-color: #30363d; }
    .stTabs [data-baseweb="tab"] { color: #8b949e; }
    .stTabs [aria-selected="true"] { color: #58a6ff !important; }
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


# ── yfinance: Full CAN SLIM fundamentals ──────────────────────
@st.cache_data(ttl=3600, show_spinner=False)
def get_canslim_fundamentals(ticker):
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


def canslim_score(cs, market_status):
    """Score 0-7: one point per CAN SLIM letter."""
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
            "df": df, "price": price,
            "sma50": sma50, "sma150": sma150, "sma200": sma200,
            "high52": high52, "low52": low52,
            "tt": tt, "tt_score": int(sum(tt.values())),
            "stage": stage, "stage_label": stage_label,
            "slope20": round(slope20, 2),
            "vcp_score": vcp_score, "is_vcp": is_vcp,
            "contractions": contractions, "tight_rng": round(tight_rng, 2),
            "near_highs": near_highs, "vol_dry": vol_dry,
            "pivot": round(pivot, 2), "pct_to_pivot": round(pct_to_pivot, 2),
            "eps_growth": eps_growth, "rev_growth": rev_growth,
            "roe": roe, "mktcap": mktcap, "sector": sector, "name": name,
        }
    except Exception:
        return None


def get_verdict(d, cs_score=0):
    tt  = d["tt_score"]
    ext = (d["price"] / d["sma50"] - 1) * 100
    stg = d["stage"]
    vcp = d["vcp_score"]
    if tt >= 7 and stg == 2 and ext < 10 and vcp >= 60 and cs_score >= 5:
        return "BUY - HIGH CONVICTION SEPA + CAN SLIM SETUP", "buy"
    elif tt >= 7 and stg == 2 and ext < 10 and vcp >= 60:
        return "BUY - HIGH CONVICTION SEPA SETUP", "buy"
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
                 f"{d['stage_label']} | VCP: {d['vcp_score']}/100",
            font=dict(size=13, color="#58a6ff")
        ),
        margin=dict(t=60, b=20, l=50, r=80)
    )
    fig.update_xaxes(showgrid=True, gridcolor="#21262d")
    fig.update_yaxes(showgrid=True, gridcolor="#21262d")
    return fig


def render_canslim_panel(cs, breakdown, cs_score, market_status, market_detail):
    """Render the CAN SLIM analysis panel."""
    if cs is None:
        st.warning("CAN SLIM data unavailable for this ticker.")
        return

    # Market status badge
    css_class = {"Bull": "market-bull", "Bear": "market-bear"}.get(market_status, "market-neutral")
    st.markdown(
        f'<div class="{css_class}">M — Market Direction: {market_status} &nbsp;|&nbsp; {market_detail}</div>',
        unsafe_allow_html=True
    )
    st.markdown(f"### CAN SLIM Score: {cs_score}/7")

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
        c_cls  = "canslim-pass" if data["pass"] else "canslim-fail"
        with cols[i % 2]:
            st.markdown(
                f'<div class="canslim-box">'
                f'<span class="canslim-letter {c_cls}">{letter}</span>'
                f'<strong style="color:#e6edf3;">{icon} {data["label"]}</strong><br>'
                f'<span style="color:#8b949e;font-size:12px;">{data["detail"]}</span>'
                f'</div>',
                unsafe_allow_html=True
            )


def claude_analysis(ticker, d, stop, t2r, t3r, shares, cs, cs_score, market_status):
    client = get_claude()
    tt_lines = "\n".join([f"  {k}: {v}" for k, v in d['tt'].items()])

    canslim_lines = ""
    if cs:
        canslim_lines = (
            f"\nCAN SLIM SCORE: {cs_score}/7\n"
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
        f"Analyze this combined SEPA + CAN SLIM setup and give a concise, actionable assessment.\n\n"
        f"TICKER: {ticker} ({d['name']}) | Sector: {d['sector']}\n"
        f"Price: ${d['price']:.2f} | Market Cap: ${d['mktcap']/1e9:.1f}B\n\n"
        f"TREND TEMPLATE: {d['tt_score']}/8\n{tt_lines}\n\n"
        f"STAGE ANALYSIS: {d['stage_label']} | SMA150 slope (20d): {d['slope20']}%\n\n"
        f"VCP ANALYSIS (Score: {d['vcp_score']}/100):\n"
        f"Contractions: {d['contractions']} | Tight: {d['tight_rng']}% | Near highs: {d['near_highs']}\n"
        f"Volume drying: {d['vol_dry']} | VCP confirmed: {d['is_vcp']}\n"
        f"Pivot: ${d['pivot']} | Pct to pivot: {d['pct_to_pivot']}%\n"
        f"{canslim_lines}\n"
        f"RISK/REWARD:\n"
        f"Entry: ${d['pivot']:.2f} | Stop: ${stop:.2f} | 2R: ${t2r:.2f} | 3R: ${t3r:.2f}\n"
        f"Position: {shares} shares\n\n"
        f"SEPA FUNDAMENTALS:\n"
        f"EPS Growth Q: {d['eps_growth']*100:.1f}% | Revenue Growth: {d['rev_growth']*100:.1f}% | ROE: {d['roe']*100:.1f}%\n\n"
        f"Respond with:\n"
        f"1. SETUP VERDICT: (Actionable / Watch / Avoid - one line, blunt)\n"
        f"2. SEPA STRENGTHS: (3 bullets max)\n"
        f"3. CAN SLIM HIGHLIGHTS: (2-3 bullets on C, A, I findings)\n"
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
    min_vcp      = st.slider("Min VCP Score", 0, 100, 40, 10)
    min_canslim  = st.slider("Min CAN SLIM Score", 0, 7, 3, 1)
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
        "SEPA + CAN SLIM | Not financial advice</p>",
        unsafe_allow_html=True
    )

# ── Header ────────────────────────────────────────────────────
st.markdown("# SEPA + CAN SLIM Institutional Terminal")
st.markdown(
    "<p style='color:#8b949e;margin-top:-12px;'>"
    "SEPA | Trend Template | Stage 2 | VCP | CAN SLIM | Alpaca Market Direction | AI Mentor"
    "</p>", unsafe_allow_html=True
)
st.markdown("---")

tab_single, tab_scanner, tab_guide = st.tabs(["Single Stock", "Batch Scanner", "Guide"])

# ── TAB 1: Single Stock ───────────────────────────────────────
with tab_single:
    ticker_input = st.text_input("Enter Ticker", "NVDA", placeholder="e.g. NVDA, AAPL, MSFT").strip().upper()

    if ticker_input:
        with st.spinner(f"Analyzing {ticker_input}..."):
            d  = fetch_data(ticker_input)
            cs = get_canslim_fundamentals(ticker_input)
            cs_score, cs_breakdown = canslim_score(cs, mkt_status)

        if d is None:
            st.error("Insufficient data or invalid ticker.")
        else:
            verdict_text, verdict_class = get_verdict(d, cs_score)
            extension = (d["price"] / d["sma50"] - 1) * 100

            st.markdown(
                f'<div class="verdict-box verdict-{verdict_class}">{verdict_text}</div>',
                unsafe_allow_html=True
            )

            c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
            c1.metric("Price",          f"${d['price']:.2f}")
            c2.metric("Trend Template", f"{d['tt_score']}/8",
                      delta="PASS" if d['tt_score'] >= min_tt else "FAIL",
                      delta_color="normal" if d['tt_score'] >= min_tt else "inverse")
            c3.metric("Stage", str(d['stage']),
                      delta=d['stage_label'],
                      delta_color="normal" if d['stage'] == 2 else "inverse")
            c4.metric("VCP Score", f"{d['vcp_score']}/100",
                      delta="Confirmed" if d['is_vcp'] else "Not confirmed",
                      delta_color="normal" if d['is_vcp'] else "off")
            c5.metric("CAN SLIM", f"{cs_score}/7",
                      delta="Strong" if cs_score >= 5 else ("OK" if cs_score >= 3 else "Weak"),
                      delta_color="normal" if cs_score >= 5 else ("off" if cs_score >= 3 else "inverse"))
            c6.metric("50MA Ext", f"{extension:.1f}%",
                      delta="Buyable" if extension < 10 else "Extended",
                      delta_color="normal" if extension < 10 else "inverse")
            c7.metric("Market", mkt_status,
                      delta_color="normal" if mkt_status == "Bull" else "inverse")

            st.markdown("---")
            st.markdown("### Execution & Position Sizing")
            ex1, ex2, ex3 = st.columns(3)

            with ex1:
                suggested_stop = round(d["price"] * 0.92, 2)
                stop_price = st.number_input("Stop Loss ($)", value=suggested_stop,
                                             step=0.01, key="stop_single")

            risk_per_share = d["pivot"] - stop_price
            if risk_per_share > 0:
                dollar_risk = portfolio * risk_pct
                shares      = int(dollar_risk / risk_per_share)
                pos_value   = shares * d["pivot"]
                target_2r   = d["pivot"] + risk_per_share * 2
                target_3r   = d["pivot"] + risk_per_share * 3
                with ex2:
                    st.metric("Entry (Pivot)",  f"${d['pivot']:.2f}")
                    st.metric("Position Size",   f"{shares:,} shares")
                    st.metric("Position Value",  f"${pos_value:,.0f} ({pos_value/portfolio*100:.1f}%)")
                with ex3:
                    st.metric("Risk/Share",  f"${risk_per_share:.2f} ({risk_per_share/d['pivot']*100:.1f}%)")
                    st.metric("2R Target",   f"${target_2r:.2f}", delta=f"+{(target_2r/d['price']-1)*100:.1f}%")
                    st.metric("3R Target",   f"${target_3r:.2f}", delta=f"+{(target_3r/d['price']-1)*100:.1f}%")
            else:
                st.warning("Stop loss must be below pivot price.")
                stop_price = round(d["price"] * 0.92, 2)
                target_2r  = d["pivot"] * 1.10
                target_3r  = d["pivot"] * 1.15
                shares     = 0

            st.markdown("---")

            # Three columns: Trend Template | VCP | Fundamentals
            left, mid, right = st.columns(3)

            with left:
                st.markdown("#### Trend Template")
                for criterion, passed in d["tt"].items():
                    st.markdown(f"{'✅' if passed else '❌'} {criterion}")
                st.markdown("#### Stage Analysis")
                st.markdown(f"**{d['stage_label']}**")
                st.markdown(f"SMA150 slope (20d): **{d['slope20']}%**")
                pct_above = (d['price'] - d['sma150']) / d['sma150'] * 100
                st.markdown(f"% above SMA150: **{pct_above:.1f}%**")

            with mid:
                st.markdown("#### VCP Analysis")
                st.markdown(f"Score: **{d['vcp_score']}/100** {'✅ Confirmed' if d['is_vcp'] else ''}")
                st.markdown(f"Contractions: **{d['contractions']}**")
                st.markdown(f"Tight range (10d): **{d['tight_rng']}%** {'✅' if d['tight_rng'] < 8 else '❌'}")
                st.markdown(f"Near highs: {'✅' if d['near_highs'] else '❌'}")
                st.markdown(f"Volume drying: {'✅' if d['vol_dry'] else '❌'}")

            with right:
                st.markdown("#### SEPA Fundamentals")
                st.markdown(f"**{d['name']}** | {d['sector']}")
                st.markdown(f"EPS Growth (Q): **{d['eps_growth']*100:.1f}%**")
                st.markdown(f"Revenue Growth: **{d['rev_growth']*100:.1f}%**")
                st.markdown(f"ROE: **{d['roe']*100:.1f}%**")
                if d['mktcap']:
                    st.markdown(f"Mkt Cap: **${d['mktcap']/1e9:.1f}B**")

            # CAN SLIM Panel
            st.markdown("---")
            st.markdown("### CAN SLIM Analysis")
            render_canslim_panel(cs, cs_breakdown, cs_score, mkt_status, mkt_detail)

            st.markdown("---")
            st.markdown("#### Chart")
            fig = make_chart(d, ticker_input, stop_price, target_2r, target_3r)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("---")
            if st.button("Request Claude AI Mentor Analysis", type="primary"):
                if "ANTHROPIC_API_KEY" not in st.secrets:
                    st.error("Missing ANTHROPIC_API_KEY in Streamlit Secrets.")
                else:
                    with st.spinner("Consulting Claude AI Mentor..."):
                        try:
                            commentary = claude_analysis(
                                ticker_input, d, stop_price, target_2r, target_3r,
                                shares, cs, cs_score, mkt_status
                            )
                            st.markdown(
                                f'<div class="ai-box">{commentary}</div>',
                                unsafe_allow_html=True
                            )
                        except Exception as e:
                            st.error(f"Claude error: {e}")

# ── TAB 2: Batch Scanner ──────────────────────────────────────
with tab_scanner:
    st.markdown("### Batch SEPA + CAN SLIM Scanner")
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
        require_vcp    = st.checkbox("Require VCP Confirmed", value=False)
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
            if d["vcp_score"] < min_vcp: continue
            if require_stage2 and d["stage"] != 2: continue
            if require_vcp and not d["is_vcp"]: continue

            cs = get_canslim_fundamentals(t)
            cs_score, _ = canslim_score(cs, mkt_status)
            if cs_score < min_canslim: continue
            if require_bull and mkt_status != "Bull": continue

            verdict_text, _ = get_verdict(d, cs_score)
            ext = (d["price"] / d["sma50"] - 1) * 100

            rows.append({
                "Ticker":      t,
                "Name":        d["name"],
                "Price":       d["price"],
                "TT Score":    d["tt_score"],
                "Stage":       d["stage_label"],
                "VCP Score":   d["vcp_score"],
                "VCP":         "Yes" if d["is_vcp"] else "No",
                "CAN SLIM":    f"{cs_score}/7",
                "C EPS%":      round(cs["c_eps_growth"], 1) if cs else "N/A",
                "A EPS%":      round(cs["a_avg_growth"], 1) if cs else "N/A",
                "Inst Own%":   round(cs["inst_own"], 1) if cs else "N/A",
                "Ext%":        round(ext, 1),
                "Pivot":       d["pivot"],
                "%toPivot":    d["pct_to_pivot"],
                "EPS Gr%":     round(d["eps_growth"]*100, 1),
                "Rev Gr%":     round(d["rev_growth"]*100, 1),
                "Sector":      d["sector"],
                "Verdict":     verdict_text,
            })
            time.sleep(0.05)

        prog.empty()

        if not rows:
            st.warning("No tickers passed all filters. Try relaxing the settings in the sidebar.")
        else:
            df_r = pd.DataFrame(rows).sort_values(
                ["CAN SLIM", "VCP Score"], ascending=False
            ).reset_index(drop=True)
            st.session_state["scan_results"] = df_r
            st.success(f"Scan complete — {len(df_r)} setups found from {total} tickers. Market: {mkt_status}")

    if "scan_results" in st.session_state:
        df_r = st.session_state["scan_results"]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Total Setups",   len(df_r))
        c2.metric("VCP Confirmed",  (df_r["VCP"] == "Yes").sum())
        c3.metric("Avg TT Score",   f"{df_r['TT Score'].mean():.1f}")
        c4.metric("Avg VCP Score",  f"{df_r['VCP Score'].mean():.1f}")
        c5.metric("Market Status",  mkt_status)

        def color_tt(val):
            if val >= 7: return "background-color:#0d3321;color:#3fb950"
            if val >= 6: return "background-color:#2d1f00;color:#d29922"
            return "background-color:#2d0f0f;color:#f85149"

        def color_vcp(val):
            if val >= 70: return "background-color:#0d3321;color:#3fb950"
            if val >= 40: return "background-color:#2d1f00;color:#d29922"
            return ""

        def color_canslim(val):
            try:
                n = int(str(val).split("/")[0])
                if n >= 5: return "background-color:#0d3321;color:#3fb950"
                if n >= 3: return "background-color:#2d1f00;color:#d29922"
                return "background-color:#2d0f0f;color:#f85149"
            except Exception:
                return ""

        styled = (
            df_r.style
            .applymap(color_tt,      subset=["TT Score"])
            .applymap(color_vcp,     subset=["VCP Score"])
            .applymap(color_canslim, subset=["CAN SLIM"])
            .format({
                "Price":    "${:.2f}",
                "Pivot":    "${:.2f}",
                "Ext%":     "{:.1f}%",
                "%toPivot": "{:.1f}%",
                "EPS Gr%":  "{:.1f}%",
                "Rev Gr%":  "{:.1f}%",
            })
        )
        st.dataframe(styled, use_container_width=True, height=500)

        csv = df_r.to_csv(index=False)
        st.download_button(
            "Download CSV", csv,
            f"sepa_canslim_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )

        st.markdown("---")
        st.markdown("**Quick Deep Dive from results**")
        dive_ticker = st.selectbox("Select ticker", df_r["Ticker"].tolist(), key="scanner_dive")
        if st.button("Deep Dive this ticker"):
            st.info(f"Go to the Single Stock tab and type: {dive_ticker}")

# ── TAB 3: Guide ──────────────────────────────────────────────
with tab_guide:
    st.markdown("## SEPA + CAN SLIM Methodology Guide")
    st.markdown("""
### How To Use This Terminal
1. **Single Stock tab** — full SEPA + CAN SLIM analysis on any ticker
2. **Batch Scanner tab** — scan S&P 500 or Nasdaq 100 for combined setups
3. **AI Mentor button** — Claude gives a Minervini + O'Neil verdict
4. **Market Direction (sidebar)** — live SPY/QQQ trend via Alpaca API

---

### Score Reference
| Metric | Range | Target |
|--------|-------|--------|
| Trend Template | 0-8 | 7-8 ideal, 6 minimum |
| Stage | 1-4 | Stage 2 only |
| VCP Score | 0-100 | 70+ strong, 50+ acceptable |
| CAN SLIM Score | 0-7 | 5+ strong, 3+ acceptable |
| Extension above 50MA | % | Under 10% = buyable |
| % to Pivot | % | Under 5% = near entry |

---

### CAN SLIM Breakdown
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

### Minervini SEPA Checklist
- EPS accelerating — at least 2 consecutive quarters of growth
- Revenue growing — ideally 20%+ YoY
- Institutional accumulation — RS line making new highs
- VCP forming on declining, dry volume
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
    "Ask anything about SEPA, CAN SLIM, VCP, Stage 2, position sizing, or a specific ticker."
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

user_input = st.chat_input("Ask about SEPA, CAN SLIM, VCP, Stage 2, position sizing, a specific ticker...")

if user_input:
    if "ANTHROPIC_API_KEY" not in st.secrets:
        st.error("Missing ANTHROPIC_API_KEY in Streamlit Secrets.")
    else:
        system_prompt = (
            "You are an expert in Mark Minervini's SEPA trading methodology, Stan Weinstein's Stage Analysis, "
            "and William O'Neil's CAN SLIM framework. You understand VCP patterns, trend templates, "
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
st.caption("Terminal Mandate: 1% Portfolio Risk Rule | Stage 2 Only | SEPA + CAN SLIM | Alpaca Market Data")

