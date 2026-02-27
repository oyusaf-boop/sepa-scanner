"""
Minervini SEPA Scanner — Streamlit Web App
Methodology: SEPA + Trend Template + Stage 2 + VCP + RS + AI Mentor
Data: Alpaca Markets (OHLCV) + yfinance (Fundamentals)
"""

import warnings
warnings.filterwarnings("ignore")

import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import anthropic
import json
import time
from datetime import datetime, timedelta

from alpaca.data.historical import StockHistoricalDataClient
from alpaca.data.requests import StockBarsRequest
from alpaca.data.timeframe import TimeFrame

# ═══════════════════════════════════════════════════════════════════════
# PAGE CONFIG
# ═══════════════════════════════════════════════════════════════════════
st.set_page_config(
    page_title="SEPA Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ═══════════════════════════════════════════════════════════════════════
# STYLING
# ═══════════════════════════════════════════════════════════════════════
st.markdown("""
<style>
    /* Dark trading terminal theme */
    .stApp { background-color: #0d1117; color: #e6edf3; }
    .main .block-container { padding: 1.5rem 2rem; max-width: 1400px; }

    /* Sidebar */
    [data-testid="stSidebar"] { background-color: #161b22; border-right: 1px solid #30363d; }
    [data-testid="stSidebar"] .stMarkdown { color: #8b949e; }

    /* Headers */
    h1 { color: #58a6ff !important; font-family: 'Segoe UI', monospace; letter-spacing: 1px; }
    h2, h3 { color: #58a6ff !important; }

    /* Metric cards */
    [data-testid="metric-container"] {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 8px;
        padding: 12px;
    }
    [data-testid="stMetricValue"] { color: #58a6ff !important; font-size: 1.4rem !important; }
    [data-testid="stMetricLabel"] { color: #8b949e !important; }
    [data-testid="stMetricDelta"] svg { display: none; }

    /* Buttons */
    .stButton > button {
        background: linear-gradient(135deg, #1f6feb, #388bfd);
        color: white;
        border: none;
        border-radius: 6px;
        font-weight: 600;
        letter-spacing: 0.5px;
        transition: all 0.2s;
    }
    .stButton > button:hover { transform: translateY(-1px); box-shadow: 0 4px 12px rgba(31,111,235,0.4); }

    /* Tables */
    .stDataFrame { border: 1px solid #30363d; border-radius: 8px; }
    thead th { background-color: #161b22 !important; color: #58a6ff !important; }

    /* Info / success / warning boxes */
    .stAlert { border-radius: 8px; }

    /* Score badge */
    .score-badge {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 12px;
        font-weight: bold;
        font-size: 13px;
    }
    .score-high  { background: #0d3321; color: #3fb950; border: 1px solid #238636; }
    .score-mid   { background: #2d1f00; color: #d29922; border: 1px solid #9e6a03; }
    .score-low   { background: #2d0f0f; color: #f85149; border: 1px solid #b91c1c; }

    /* AI Mentor box */
    .ai-box {
        background: #161b22;
        border: 1px solid #6e40c9;
        border-radius: 10px;
        padding: 20px;
        font-family: monospace;
        white-space: pre-wrap;
        line-height: 1.7;
        color: #e6edf3;
        margin-top: 16px;
    }

    /* Divider */
    hr { border-color: #30363d; }

    /* Slider labels */
    .stSlider label { color: #8b949e !important; }

    /* Selectbox */
    .stSelectbox label { color: #8b949e !important; }
</style>
""", unsafe_allow_html=True)

# ═══════════════════════════════════════════════════════════════════════
# API CLIENTS — pull from Streamlit Secrets
# ═══════════════════════════════════════════════════════════════════════
@st.cache_resource
def init_clients():
    alpaca = StockHistoricalDataClient(
        st.secrets["ALPACA_API_KEY"],
        st.secrets["ALPACA_SECRET_KEY"]
    )
    claude = anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])
    return alpaca, claude

alpaca_client, anthropic_client = init_clients()

# ═══════════════════════════════════════════════════════════════════════
# CONSTANTS
# ═══════════════════════════════════════════════════════════════════════
LOOKBACK_DAYS = 300

# ═══════════════════════════════════════════════════════════════════════
# DATA FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════
@st.cache_data(ttl=3600, show_spinner=False)
def get_sp500_tickers():
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    df  = pd.read_html(url)[0]
    return df["Symbol"].str.replace(".", "-", regex=False).tolist()

@st.cache_data(ttl=3600, show_spinner=False)
def get_nasdaq100_tickers():
    url = "https://en.wikipedia.org/wiki/Nasdaq-100"
    for t in pd.read_html(url):
        if "Ticker" in t.columns:
            return t["Ticker"].tolist()
    return []

def fetch_bars(ticker: str, days: int = LOOKBACK_DAYS) -> pd.DataFrame:
    end   = datetime.now()
    start = end - timedelta(days=int(days * 1.6))
    try:
        req = StockBarsRequest(
            symbol_or_symbols=ticker,
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
            limit=days
        )
        bars = alpaca_client.get_stock_bars(req)
        df   = bars.df
        if df.empty:
            return pd.DataFrame()
        if isinstance(df.index, pd.MultiIndex):
            df = df.xs(ticker, level="symbol")
        df.index = pd.to_datetime(df.index).tz_localize(None)
        df = df.rename(columns={"open":"Open","high":"High","low":"Low",
                                 "close":"Close","volume":"Volume"})
        return df[["Open","High","Low","Close","Volume"]].tail(days)
    except:
        return pd.DataFrame()

@st.cache_data(ttl=86400, show_spinner=False)
def fetch_fundamentals(ticker: str) -> dict:
    try:
        info = yf.Ticker(ticker).info
        return {
            "eps_ttm":         info.get("trailingEps"),
            "eps_forward":     info.get("forwardEps"),
            "revenue_growth":  info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "roe":             info.get("returnOnEquity"),
            "profit_margin":   info.get("profitMargins"),
            "sector":          info.get("sector", "N/A"),
            "industry":        info.get("industry", "N/A"),
            "market_cap":      info.get("marketCap"),
            "name":            info.get("shortName", ticker),
        }
    except:
        return {}

# ═══════════════════════════════════════════════════════════════════════
# TECHNICAL INDICATORS
# ═══════════════════════════════════════════════════════════════════════
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    c  = df["Close"]
    df["MA10"]  = c.rolling(10).mean()
    df["MA20"]  = c.rolling(20).mean()
    df["MA50"]  = c.rolling(50).mean()
    df["MA150"] = c.rolling(150).mean()
    df["MA200"] = c.rolling(200).mean()
    df["High52w"]  = df["High"].rolling(252).max()
    df["Low52w"]   = df["Low"].rolling(252).min()
    df["AvgVol50"] = df["Volume"].rolling(50).mean()
    hl  = df["High"] - df["Low"]
    hc  = (df["High"] - c.shift()).abs()
    lc  = (df["Low"]  - c.shift()).abs()
    tr  = pd.concat([hl, hc, lc], axis=1).max(axis=1)
    df["ATR14"]       = tr.rolling(14).mean()
    df["MA200_slope"] = df["MA200"].diff(20)
    return df

# ═══════════════════════════════════════════════════════════════════════
# SCREENING MODULES
# ═══════════════════════════════════════════════════════════════════════
def check_trend_template(df: pd.DataFrame) -> dict:
    if len(df) < 200:
        return {"score": 0, "criteria": {}, "passes": False}
    r = df.iloc[-1]
    criteria = {
        "C1 Price > 150 & 200 MA":    r["Close"] > r["MA150"] and r["Close"] > r["MA200"],
        "C2 150 MA > 200 MA":         r["MA150"] > r["MA200"],
        "C3 200 MA trending up":      r["MA200_slope"] > 0,
        "C4 50 MA > 150 & 200 MA":    r["MA50"] > r["MA150"] and r["MA50"] > r["MA200"],
        "C5 Price > 50 MA":           r["Close"] > r["MA50"],
        "C6 25% above 52w low":       r["Close"] >= r["Low52w"] * 1.25,
        "C7 Within 25% of 52w high":  r["Close"] >= r["High52w"] * 0.75,
        "C8 RS positive vs SPY":      True,  # updated after RS calc
    }
    score = sum(criteria.values())
    return {
        "score": score, "criteria": criteria, "passes": score >= 6,
        "price": r["Close"], "ma50": r["MA50"],
        "ma150": r["MA150"], "ma200": r["MA200"],
        "high52w": r["High52w"], "low52w": r["Low52w"],
    }

def detect_stage(df: pd.DataFrame) -> dict:
    if len(df) < 150:
        return {"stage": 0, "stage_label": "Unknown", "is_stage2": False}
    r     = df.iloc[-1]
    price = r["Close"]
    slope = (df["MA150"].iloc[-1] - df["MA150"].iloc[-20]) / df["MA150"].iloc[-20] * 100
    pct_above = (price - r["MA150"]) / r["MA150"] * 100
    pct_from_high = (price - r["High52w"]) / r["High52w"] * 100
    if price > r["MA150"] and slope > 0.5:
        stage, label = 2, "Stage 2 — Advancing ✅"
    elif price > r["MA150"] and abs(slope) <= 0.5:
        stage, label = 1, "Stage 1 — Basing"
    elif price < r["MA150"] and slope < -0.5 and pct_from_high < -20:
        stage, label = 4, "Stage 4 — Declining ❌"
    else:
        stage, label = 3, "Stage 3 — Topping ⚠️"
    return {
        "stage": stage, "stage_label": label, "is_stage2": stage == 2,
        "ma150_slope_pct": round(slope, 2), "pct_above_ma150": round(pct_above, 2),
    }

def detect_vcp(df: pd.DataFrame, lookback: int = 60) -> dict:
    if len(df) < lookback:
        return {"vcp_score": 0, "contractions": 0, "is_vcp": False,
                "pivot": df["High"].iloc[-1] if len(df) else 0,
                "pct_to_pivot": 0, "tight_range_pct": 0,
                "range_contracting": False, "vol_contracting": False,
                "near_highs": False, "atr_contracted": False, "atr_ratio": 1.0}
    recent   = df.tail(lookback).copy()
    seg      = lookback // 3
    segs     = [recent.iloc[0:seg], recent.iloc[seg:2*seg], recent.iloc[2*seg:]]
    ranges   = [(s["High"].max()-s["Low"].min())/s["Close"].mean()*100 for s in segs]
    vol_avg  = [s["Volume"].mean() for s in segs]
    contractions = sum([ranges[0]>ranges[1], ranges[1]>ranges[2]])
    final10  = recent.tail(10)
    tight_rng = (final10["High"].max()-final10["Low"].min())/final10["Close"].mean()*100
    is_tight  = tight_rng < 8.0
    period_high = recent["High"].max()
    current     = recent["Close"].iloc[-1]
    near_highs  = current >= period_high * 0.90
    atr_r = recent["ATR14"].tail(5).mean() if "ATR14" in recent.columns else 1
    atr_b = recent["ATR14"].head(20).mean() if "ATR14" in recent.columns else 1
    atr_ratio = atr_r / atr_b if atr_b > 0 else 1.0
    pivot = final10["High"].max()
    score = min(100, 30*contractions + (15 if vol_avg[0]>vol_avg[1] else 0)
                + (15 if is_tight else 0) + (10 if near_highs else 0))
    return {
        "vcp_score": score, "contractions": contractions,
        "range_contracting": ranges[0]>ranges[1]>ranges[2],
        "vol_contracting": vol_avg[0]>vol_avg[1],
        "is_tight": is_tight, "tight_range_pct": round(tight_rng, 2),
        "near_highs": near_highs, "atr_contracted": atr_ratio < 0.7,
        "atr_ratio": round(atr_ratio, 2),
        "pivot": round(pivot, 2),
        "pct_to_pivot": round((pivot-current)/current*100, 2),
        "is_vcp": contractions >= 2 and is_tight and near_highs,
    }

def calc_rs(stock_df: pd.DataFrame, spy_df: pd.DataFrame) -> dict:
    common = stock_df.index.intersection(spy_df.index)
    if len(common) < 63:
        return {"rs_3m": None, "rs_6m": None, "rs_ratio": None,
                "rs_line_new_high": False, "rs_line_52w_high": False, "rs_line": None}
    s = stock_df.loc[common, "Close"]
    b = spy_df.loc[common, "Close"]
    rs_line = s / b
    rs_3m   = (s.iloc[-1]/s.iloc[-63]-1) - (b.iloc[-1]/b.iloc[-63]-1)
    rs_6m   = ((s.iloc[-1]/s.iloc[-126]-1)-(b.iloc[-1]/b.iloc[-126]-1)) if len(common)>=126 else None
    rs_ratio = 0.4*rs_3m + 0.6*rs_6m if rs_6m else rs_3m
    rs_now  = rs_line.iloc[-1]
    return {
        "rs_3m": round(rs_3m*100, 1),
        "rs_6m": round(rs_6m*100, 1) if rs_6m else None,
        "rs_ratio": round(rs_ratio*100, 1),
        "rs_line_new_high": rs_now >= rs_line.tail(20).max() * 0.99,
        "rs_line_52w_high": rs_now >= rs_line.tail(252).max() * 0.99,
        "rs_line": rs_line,
    }

def score_base_quality(df, tt, vcp, stage) -> dict:
    tt_s    = (tt["score"] / 8) * 30
    stg_s   = 20 if stage["is_stage2"] else 5 if stage["stage"]==1 else 0
    vcp_s   = (vcp["vcp_score"] / 100) * 30
    rvol    = df["Volume"].tail(10).mean() / (df["Volume"].tail(50).mean()+1)
    vol_b   = 10 if rvol < 0.75 else 5 if rvol < 0.90 else 0
    bh, bl  = df["High"].tail(60).max(), df["Low"].tail(60).min()
    depth   = (bh-bl)/bh*100 if len(df)>=60 else 30
    dep_s   = 10 if depth<20 else 7 if depth<30 else 3 if depth<40 else 0
    total   = min(100, round(tt_s+stg_s+vcp_s+vol_b+dep_s, 1))
    return {"base_score": total, "tt_comp": round(tt_s,1), "stage_comp": stg_s,
            "vcp_comp": round(vcp_s,1), "vol_bonus": vol_b, "depth_score": dep_s}

def calc_risk_reward(df, vcp, portfolio_size=100000, risk_pct=1.0) -> dict:
    price   = df["Close"].iloc[-1]
    pivot   = vcp["pivot"]
    stop    = df.tail(10)["Low"].min() - df["ATR14"].iloc[-1]*0.25
    rps     = pivot - stop
    rpt     = rps / pivot * 100 if pivot > 0 else 0
    dollar_risk = portfolio_size * (risk_pct/100)
    shares  = int(dollar_risk / rps) if rps > 0 else 0
    return {
        "current_price": round(price, 2), "pivot": round(pivot, 2),
        "stop": round(stop, 2), "risk_per_share": round(rps, 2),
        "risk_pct_trade": round(rpt, 2), "shares": shares,
        "position_value": round(shares*pivot, 2),
        "position_pct": round(shares*pivot/portfolio_size*100, 1),
        "target_2r": round(pivot+rps*2, 2), "target_3r": round(pivot+rps*3, 2),
    }

def check_market_condition(spy_df: pd.DataFrame) -> dict:
    df   = add_indicators(spy_df.copy())
    r    = df.iloc[-1]
    price = r["Close"]
    avg_vol = df["Volume"].tail(50).mean()
    dist = sum(1 for i in range(1, min(26, len(df)))
               if df["Close"].iloc[-i] < df["Close"].iloc[-i-1]
               and df["Volume"].iloc[-i] > avg_vol)
    above_50  = price > r["MA50"]
    above_200 = price > r["MA200"]
    if above_50 and price > r["MA150"] and above_200 and dist <= 4:
        status, ok = "Confirmed Uptrend 🟢", True
    elif above_200 and dist <= 6:
        status, ok = "Rally Attempt 🟡", True
    else:
        status, ok = "Market Under Pressure 🔴", False
    return {
        "status": status, "ok_to_trade": ok, "dist_days": dist,
        "spy_price": round(price, 2),
        "spy_from_high": round((price-r["High52w"])/r["High52w"]*100, 2),
        "above_50": above_50, "above_200": above_200,
        "ma50": round(r["MA50"], 2), "ma200": round(r["MA200"], 2),
    }

# ═══════════════════════════════════════════════════════════════════════
# CORE ANALYSIS ENGINE
# ═══════════════════════════════════════════════════════════════════════
def analyze_ticker(ticker, spy_df, min_price, min_vol,
                   min_tt, min_base, portfolio_size, risk_pct,
                   include_fundamentals=False):
    df = fetch_bars(ticker)
    if df.empty or len(df) < 150:
        return None
    price   = df["Close"].iloc[-1]
    avg_vol = df["Volume"].tail(50).mean()
    if price < min_price or avg_vol < min_vol:
        return None
    df   = add_indicators(df)
    tt   = check_trend_template(df)
    stg  = detect_stage(df)
    vcp  = detect_vcp(df)
    rs   = calc_rs(df, spy_df)
    if rs["rs_ratio"] is not None:
        tt["criteria"]["C8 RS positive vs SPY"] = rs["rs_ratio"] > 0
        tt["score"] = sum(tt["criteria"].values())
        tt["passes"] = tt["score"] >= min_tt
    base = score_base_quality(df, tt, vcp, stg)
    rr   = calc_risk_reward(df, vcp, portfolio_size, risk_pct)
    fund = fetch_fundamentals(ticker) if include_fundamentals else {}
    return {
        "ticker": ticker, "price": round(price,2),
        "avg_volume": int(avg_vol),
        "tt": tt, "stage": stg, "vcp": vcp,
        "rs": rs, "base": base, "rr": rr,
        "fundamentals": fund, "df": df,
    }

# ═══════════════════════════════════════════════════════════════════════
# AI MENTOR
# ═══════════════════════════════════════════════════════════════════════
def get_ai_commentary(ticker, tt, stage, vcp, base, rs, rr, fund) -> str:
    prompt = f"""You are Mark Minervini's trading methodology expert and mentor.
Analyze this stock setup and give a concise, actionable assessment using SEPA principles.
Be specific and direct — like an experienced trading mentor would be.

TICKER: {ticker}

TREND TEMPLATE ({tt['score']}/8):
{json.dumps({k: v for k,v in tt['criteria'].items()}, indent=2)}

STAGE: {stage['stage_label']} | MA150 slope: {stage['ma150_slope_pct']}% | % above MA150: {stage['pct_above_ma150']}%

VCP (Score: {vcp['vcp_score']}/100):
- Contractions: {vcp['contractions']} | Range contracting: {vcp['range_contracting']}
- Volume contracting: {vcp['vol_contracting']} | Tight area: {vcp['is_tight']} ({vcp['tight_range_pct']}%)
- ATR contracted: {vcp['atr_contracted']} (ratio: {vcp['atr_ratio']})
- Pivot: ${vcp['pivot']} | % to pivot: {vcp['pct_to_pivot']}%

BASE QUALITY: {base['base_score']}/100

RS vs SPY: 3m={rs.get('rs_3m')}% | 6m={rs.get('rs_6m')}% | RS line new high: {rs.get('rs_line_new_high')}

RISK/REWARD:
- Entry: ${rr.get('pivot')} | Stop: ${rr.get('stop')} | Risk: {rr.get('risk_pct_trade')}%
- 2R: ${rr.get('target_2r')} | 3R: ${rr.get('target_3r')}

FUNDAMENTALS: Sector={fund.get('sector')} | EPS growth={fund.get('earnings_growth')} | Rev growth={fund.get('revenue_growth')} | ROE={fund.get('roe')}

Structure your response:
1. SETUP VERDICT: (Actionable / Watch / Avoid — one line)
2. STRENGTHS: (bullets)
3. WEAKNESSES / RISKS: (bullets)
4. IDEAL ENTRY: (specific advice)
5. MENTOR NOTE: (one key Minervini insight for this setup)"""

    try:
        msg = anthropic_client.messages.create(
            model="claude-opus-4-6",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}]
        )
        return msg.content[0].text
    except Exception as e:
        return f"AI commentary unavailable: {e}"

# ═══════════════════════════════════════════════════════════════════════
# CHART
# ═══════════════════════════════════════════════════════════════════════
def make_chart(ticker, result):
    df  = result["df"].tail(120).copy()
    vcp = result["vcp"]
    rr  = result["rr"]
    rs  = result["rs"]

    fig, axes = plt.subplots(3, 1, figsize=(14, 10),
                             gridspec_kw={"height_ratios": [4, 1.5, 1.5]})
    bg = "#0d1117"
    fig.patch.set_facecolor(bg)
    for ax in axes:
        ax.set_facecolor(bg)
        for spine in ax.spines.values():
            spine.set_color("#30363d")
        ax.tick_params(colors="#8b949e", labelsize=8)
        ax.yaxis.label.set_color("#8b949e")

    ax1 = axes[0]
    for i, (_, row) in enumerate(df.iterrows()):
        col = "#26a69a" if row["Close"] >= row["Open"] else "#ef5350"
        ax1.plot([i, i], [row["Low"], row["High"]], color=col, lw=0.8)
        ax1.add_patch(plt.Rectangle(
            (i-0.4, min(row["Open"], row["Close"])),
            0.8, abs(row["Close"]-row["Open"]), color=col, alpha=0.9))

    x = range(len(df))
    ax1.plot(x, df["MA50"],  color="#ffd700", lw=1.2, label="MA50")
    ax1.plot(x, df["MA150"], color="#ff9800", lw=1.2, label="MA150")
    ax1.plot(x, df["MA200"], color="#e91e63", lw=1.5, label="MA200")
    ax1.axhline(vcp["pivot"],      color="#00e5ff", lw=1.5, ls="--",
                label=f"Pivot ${vcp['pivot']:.2f}")
    ax1.axhline(rr["stop"],        color="#f85149", lw=1.2, ls=":",
                label=f"Stop ${rr['stop']:.2f}")
    ax1.axhline(rr["target_2r"],   color="#3fb950", lw=1.0, ls="-.",
                label=f"2R ${rr['target_2r']:.2f}")
    ax1.axhline(rr["target_3r"],   color="#b9f6ca", lw=1.0, ls="-.",
                label=f"3R ${rr['target_3r']:.2f}")

    tt, stage, base = result["tt"], result["stage"], result["base"]
    ax1.set_title(
        f"{ticker}  |  Price: ${result['price']:.2f}  |  "
        f"TT: {tt['score']}/8  |  {stage['stage_label']}  |  "
        f"VCP: {vcp['vcp_score']}/100  |  Base: {base['base_score']}/100",
        color="white", fontsize=10, pad=8)
    ax1.legend(loc="upper left", fontsize=7.5, facecolor="#161b22",
               labelcolor="white", framealpha=0.9)
    ax1.set_xlim(-2, len(df)+2)

    # Volume
    ax2 = axes[1]
    vcols = ["#26a69a" if df["Close"].iloc[i] >= df["Open"].iloc[i]
             else "#ef5350" for i in range(len(df))]
    ax2.bar(x, df["Volume"], color=vcols, alpha=0.75, width=0.8)
    ax2.plot(x, df["AvgVol50"], color="white", lw=1.0, ls="--",
             label="Avg Vol 50d", alpha=0.7)
    ax2.legend(loc="upper left", fontsize=7.5, facecolor="#161b22",
               labelcolor="white", framealpha=0.9)
    ax2.set_xlim(-2, len(df)+2)

    # RS Line
    ax3 = axes[2]
    if rs.get("rs_line") is not None:
        rs_line   = rs["rs_line"].reindex(df.index)
        ax3.plot(x, rs_line.values, color="#ab47bc", lw=1.5, label="RS vs SPY")
        rc = "#3fb950" if rs["rs_line_new_high"] else "#f85149"
        ax3.set_title(f"RS Line — New High: {rs['rs_line_new_high']}",
                      color=rc, fontsize=9, pad=4)
        ax3.legend(loc="upper left", fontsize=7.5, facecolor="#161b22",
                   labelcolor="white", framealpha=0.9)
    ax3.set_xlim(-2, len(df)+2)

    dates = df.index.strftime("%b %y")
    ticks = list(range(0, len(df), max(1, len(df)//8)))
    ax3.set_xticks(ticks)
    ax3.set_xticklabels([dates[i] for i in ticks], color="#8b949e", fontsize=7.5)

    plt.tight_layout()
    return fig

# ═══════════════════════════════════════════════════════════════════════
# HELPER: score badge color
# ═══════════════════════════════════════════════════════════════════════
def score_color(score, thresholds=(65, 45)):
    if score >= thresholds[0]: return "🟢"
    if score >= thresholds[1]: return "🟡"
    return "🔴"

# ═══════════════════════════════════════════════════════════════════════
# SIDEBAR
# ═══════════════════════════════════════════════════════════════════════
with st.sidebar:
    st.markdown("## ⚙️ Scanner Settings")
    st.markdown("---")

    universe = st.selectbox(
        "Universe",
        options=["S&P 500", "Nasdaq 100", "Custom"],
        index=0
    )

    custom_input = ""
    if universe == "Custom":
        custom_input = st.text_area(
            "Custom Tickers (comma-separated)",
            value="AAPL, NVDA, MSFT, META, GOOGL",
            height=80
        )

    max_tickers = st.slider("Max Tickers to Scan", 10, 503, 100, 10)

    st.markdown("---")
    st.markdown("**🔧 Filters**")
    min_price  = st.number_input("Min Price ($)", value=10.0, step=1.0)
    min_vol    = st.number_input("Min Avg Volume", value=200000, step=50000)
    min_tt     = st.slider("Min Trend Template Score", 4, 8, 6)
    min_base   = st.slider("Min Base Quality Score", 20, 90, 50, 5)

    st.markdown("---")
    st.markdown("**💰 Risk Management**")
    portfolio_size = st.number_input("Portfolio Size ($)", value=100000, step=5000)
    risk_pct       = st.slider("Risk % per Trade", 0.25, 3.0, 1.0, 0.25)

    st.markdown("---")
    st.markdown("**⚙️ Options**")
    include_fund = st.checkbox("Include Fundamentals (slower)", value=False)

    st.markdown("---")
    st.markdown(
        "<p style='color:#8b949e; font-size:11px;'>"
        "Data: Alpaca + yfinance<br>"
        "AI: Claude (Anthropic)<br>"
        "⚠️ Not financial advice"
        "</p>",
        unsafe_allow_html=True
    )

# ═══════════════════════════════════════════════════════════════════════
# MAIN CONTENT
# ═══════════════════════════════════════════════════════════════════════
st.markdown("# 📈 Minervini SEPA Scanner")
st.markdown(
    "<p style='color:#8b949e; margin-top:-12px;'>"
    "SEPA · Trend Template · Stage 2 · VCP · Relative Strength · AI Mentor"
    "</p>",
    unsafe_allow_html=True
)
st.markdown("---")

# ── Tabs ──────────────────────────────────────────────────────────────
tab_scan, tab_dive, tab_about = st.tabs(["🔍 Scanner", "📊 Deep Dive", "📖 Guide"])

# ════════════════════════════════════════════
# TAB 1 — SCANNER
# ════════════════════════════════════════════
with tab_scan:

    col_mkt, col_scan = st.columns([1, 1])

    with col_mkt:
        if st.button("🌡️ Check Market Condition", use_container_width=True):
            with st.spinner("Fetching SPY data..."):
                spy_df = fetch_bars("SPY")
                if spy_df.empty:
                    st.error("Could not fetch SPY data.")
                else:
                    spy_df = add_indicators(spy_df)
                    mkt = check_market_condition(spy_df)
                    st.session_state["spy_df"] = spy_df
                    st.session_state["market"] = mkt

    with col_scan:
        run_scan = st.button("🚀 Run Full Scan", use_container_width=True, type="primary")

    # Display market status if available
    if "market" in st.session_state:
        mkt = st.session_state["market"]
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Market Status", mkt["status"].split()[0] + " " + mkt["status"].split()[1])
        c2.metric("SPY Price", f"${mkt['spy_price']}")
        c3.metric("From 52w High", f"{mkt['spy_from_high']}%")
        c4.metric("Dist. Days", mkt["dist_days"],
                  delta="High ⚠️" if mkt["dist_days"] > 4 else "Normal ✅",
                  delta_color="inverse")
        c5.metric("Above 200 MA", "✅ Yes" if mkt["above_200"] else "❌ No")

        if mkt["ok_to_trade"]:
            st.success(f"✅ {mkt['status']} — Conditions favorable for SEPA setups.")
        else:
            st.warning("⚠️ Market under pressure. Minervini rule: when the market is sick, most stocks fail.")

    st.markdown("---")

    # ── Run scan ─────────────────────────────────────────────────────
    if run_scan:
        # Load tickers
        with st.spinner("Loading universe..."):
            if universe == "S&P 500":
                tickers = get_sp500_tickers()[:max_tickers]
            elif universe == "Nasdaq 100":
                tickers = get_nasdaq100_tickers()[:max_tickers]
            else:
                tickers = [t.strip().upper() for t in custom_input.split(",") if t.strip()]

        # Ensure SPY loaded
        if "spy_df" not in st.session_state:
            with st.spinner("Fetching SPY..."):
                spy_df = fetch_bars("SPY")
                spy_df = add_indicators(spy_df)
                st.session_state["spy_df"] = spy_df

        spy_df = st.session_state["spy_df"]

        # Scan
        progress_bar = st.progress(0, text="Initializing...")
        status_text  = st.empty()
        results      = []
        total        = len(tickers)

        for i, ticker in enumerate(tickers):
            pct = int((i+1) / total * 100)
            progress_bar.progress(pct, text=f"Scanning {ticker} ({i+1}/{total})")

            r = analyze_ticker(
                ticker, spy_df, min_price, min_vol,
                min_tt, min_base, portfolio_size, risk_pct,
                include_fund
            )
            if r is None:
                continue
            if not r["tt"]["passes"]:
                continue
            if not r["stage"]["is_stage2"]:
                continue
            if r["base"]["base_score"] < min_base:
                continue

            results.append({
                "Ticker":       ticker,
                "Price":        r["price"],
                "AvgVol":       r["avg_volume"],
                "TT":           r["tt"]["score"],
                "Stage":        r["stage"]["stage"],
                "VCP":          r["vcp"]["vcp_score"],
                "IsVCP":        "✅" if r["vcp"]["is_vcp"] else "—",
                "BaseScore":    r["base"]["base_score"],
                "RS_3m%":       r["rs"]["rs_3m"],
                "RS_NewHigh":   "✅" if r["rs"]["rs_line_new_high"] else "—",
                "Pivot":        r["vcp"]["pivot"],
                "%ToPivot":     r["vcp"]["pct_to_pivot"],
                "Stop":         r["rr"]["stop"],
                "Risk%":        r["rr"]["risk_pct_trade"],
                "Target2R":     r["rr"]["target_2r"],
                "Target3R":     r["rr"]["target_3r"],
                **( {"Sector": r["fundamentals"].get("sector",""),
                     "EPS_Gr": r["fundamentals"].get("earnings_growth",""),
                     "Rev_Gr": r["fundamentals"].get("revenue_growth","")}
                    if include_fund else {} )
            })
            time.sleep(0.05)

        progress_bar.empty()

        if not results:
            st.warning("No tickers passed all filters. Try relaxing the thresholds in the sidebar.")
        else:
            df_results = pd.DataFrame(results)
            df_results["RS_Rank"] = df_results["RS_3m%"].rank(pct=True).mul(100).round(1)
            df_results = df_results.sort_values("BaseScore", ascending=False).reset_index(drop=True)
            st.session_state["scan_results"] = df_results

            st.success(f"✅ Scan complete — **{len(df_results)} setups** found from {total} tickers scanned.")

    # ── Display results ───────────────────────────────────────────────
    if "scan_results" in st.session_state:
        df_r = st.session_state["scan_results"]

        # Summary metrics
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Setups",    len(df_r))
        c2.metric("VCP Confirmed",   df_r["IsVCP"].eq("✅").sum())
        c3.metric("RS New Highs",    df_r["RS_NewHigh"].eq("✅").sum())
        c4.metric("Avg Base Score",  f"{df_r['BaseScore'].mean():.1f}")

        st.markdown("### 📋 Qualifying Setups")

        # Color-coded table
        def color_score(val):
            if isinstance(val, (int, float)):
                if val >= 65: return "background-color: #0d3321; color: #3fb950"
                if val >= 45: return "background-color: #2d1f00; color: #d29922"
                return "background-color: #2d0f0f; color: #f85149"
            return ""

        styled = (
            df_r.style
            .applymap(color_score, subset=["BaseScore", "VCP"])
            .format({
                "Price": "${:.2f}", "Pivot": "${:.2f}",
                "Stop": "${:.2f}", "Target2R": "${:.2f}", "Target3R": "${:.2f}",
                "%ToPivot": "{:.1f}%", "Risk%": "{:.1f}%",
                "RS_3m%": "{:.1f}%"
            })
            .set_properties(**{"background-color": "#0d1117", "color": "#e6edf3"})
        )
        st.dataframe(styled, use_container_width=True, height=500)

        # Download
        csv = df_r.to_csv(index=False)
        st.download_button(
            label="⬇️ Download CSV",
            data=csv,
            file_name=f"sepa_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            mime="text/csv"
        )

# ════════════════════════════════════════════
# TAB 2 — DEEP DIVE
# ════════════════════════════════════════════
with tab_dive:
    st.markdown("### 🔬 Single Stock Deep Dive")

    col_in, col_opts = st.columns([1, 2])
    with col_in:
        dd_ticker = st.text_input("Ticker", value="NVDA",
                                  placeholder="e.g. NVDA").strip().upper()
    with col_opts:
        dd_fund = st.checkbox("Include Fundamentals", value=True, key="dd_fund")
        dd_ai   = st.checkbox("Include AI Mentor Commentary", value=True, key="dd_ai")

    if st.button("🔬 Analyze", type="primary", use_container_width=False):
        if not dd_ticker:
            st.warning("Enter a ticker first.")
        else:
            with st.spinner(f"Analyzing {dd_ticker}..."):
                if "spy_df" not in st.session_state:
                    spy_df = fetch_bars("SPY")
                    spy_df = add_indicators(spy_df)
                    st.session_state["spy_df"] = spy_df

                spy_df = st.session_state["spy_df"]
                result = analyze_ticker(
                    dd_ticker, spy_df, min_price, min_vol,
                    min_tt, min_base, portfolio_size, risk_pct, dd_fund
                )

            if result is None:
                st.error(f"Could not analyze {dd_ticker} — no data or failed basic filters.")
            else:
                tt    = result["tt"]
                stage = result["stage"]
                vcp   = result["vcp"]
                base  = result["base"]
                rs    = result["rs"]
                rr    = result["rr"]
                fund  = result["fundamentals"]

                # ── Score summary row ─────────────────────────────────
                st.markdown(f"#### {dd_ticker} — ${result['price']:.2f}")
                c1,c2,c3,c4,c5,c6 = st.columns(6)
                c1.metric("Trend Template", f"{tt['score']}/8",
                          delta="PASS" if tt["passes"] else "FAIL",
                          delta_color="normal" if tt["passes"] else "inverse")
                c2.metric("Stage", stage["stage"],
                          delta="✅ Stage 2" if stage["is_stage2"] else stage["stage_label"],
                          delta_color="normal" if stage["is_stage2"] else "inverse")
                c3.metric("VCP Score", f"{vcp['vcp_score']}/100",
                          delta="✅ VCP" if vcp["is_vcp"] else "Not confirmed",
                          delta_color="normal" if vcp["is_vcp"] else "off")
                c4.metric("Base Score", f"{base['base_score']}/100")
                c5.metric("RS 3m vs SPY", f"{rs['rs_3m']}%" if rs['rs_3m'] else "N/A",
                          delta="RS New High ✅" if rs["rs_line_new_high"] else "Not new high",
                          delta_color="normal" if rs["rs_line_new_high"] else "off")
                c6.metric("% To Pivot", f"{vcp['pct_to_pivot']}%")

                st.markdown("---")

                # ── Trend Template criteria ───────────────────────────
                with st.expander("📋 Trend Template Breakdown", expanded=True):
                    cols = st.columns(2)
                    for j, (k, v) in enumerate(tt["criteria"].items()):
                        icon = "✅" if v else "❌"
                        cols[j % 2].markdown(f"{icon} {k}")

                # ── Two-column detail ─────────────────────────────────
                col_l, col_r = st.columns(2)

                with col_l:
                    st.markdown("**VCP Analysis**")
                    st.markdown(f"- Contractions: **{vcp['contractions']}**")
                    st.markdown(f"- Tight range: **{vcp['tight_range_pct']}%** {'✅' if vcp['is_tight'] else '❌'}")
                    st.markdown(f"- Near highs: {'✅' if vcp['near_highs'] else '❌'}")
                    st.markdown(f"- Vol contracting: {'✅' if vcp['vol_contracting'] else '❌'}")
                    st.markdown(f"- ATR ratio: **{vcp['atr_ratio']}** {'✅ contracted' if vcp['atr_contracted'] else ''}")
                    st.markdown(f"- **Pivot: ${vcp['pivot']:.2f}**")

                    st.markdown("---")
                    st.markdown("**Stage Analysis**")
                    st.markdown(f"- {stage['stage_label']}")
                    st.markdown(f"- MA150 slope: **{stage['ma150_slope_pct']}%**")
                    st.markdown(f"- % above MA150: **{stage['pct_above_ma150']}%**")

                with col_r:
                    st.markdown("**Risk / Reward**")
                    st.markdown(f"- Entry (Pivot): **${rr['pivot']:.2f}**")
                    st.markdown(f"- Stop: **${rr['stop']:.2f}**")
                    st.markdown(f"- Risk/share: **${rr['risk_per_share']:.2f}** ({rr['risk_pct_trade']:.1f}%)")
                    st.markdown(f"- Shares: **{rr['shares']:,}** (${rr['position_value']:,.0f} — {rr['position_pct']:.1f}%)")
                    st.markdown(f"- 🎯 2R Target: **${rr['target_2r']:.2f}**")
                    st.markdown(f"- 🎯 3R Target: **${rr['target_3r']:.2f}**")

                    if fund:
                        st.markdown("---")
                        st.markdown("**Fundamentals**")
                        st.markdown(f"- {fund.get('name','')} | {fund.get('sector','')}")
                        st.markdown(f"- EPS Growth: **{fund.get('earnings_growth','N/A')}**")
                        st.markdown(f"- Rev Growth: **{fund.get('revenue_growth','N/A')}**")
                        st.markdown(f"- ROE: **{fund.get('roe','N/A')}**")
                        mc = fund.get('market_cap')
                        if mc:
                            st.markdown(f"- Mkt Cap: **${mc/1e9:.1f}B**")

                # ── Chart ─────────────────────────────────────────────
                st.markdown("---")
                st.markdown("**📉 Chart**")
                fig = make_chart(dd_ticker, result)
                st.pyplot(fig, use_container_width=True)
                plt.close(fig)

                # ── AI Mentor ─────────────────────────────────────────
                if dd_ai:
                    st.markdown("---")
                    st.markdown("**🤖 AI Mentor Commentary**")
                    with st.spinner("Consulting AI mentor..."):
                        commentary = get_ai_commentary(
                            dd_ticker, tt, stage, vcp, base, rs, rr, fund
                        )
                    st.markdown(
                        f'<div class="ai-box">{commentary}</div>',
                        unsafe_allow_html=True
                    )

# ════════════════════════════════════════════
# TAB 3 — GUIDE
# ════════════════════════════════════════════
with tab_about:
    st.markdown("## 📖 How to Use This Scanner")

    st.markdown("""
### Workflow
1. **Check Market Condition first** — never take setups in a downtrend
2. **Run the Full Scan** — start with max 100 tickers to gauge speed
3. **Sort by Base Score** — highest quality setups at the top
4. **Deep Dive on candidates** — get the full chart + AI mentor assessment
5. **Confirm fundamentals** — EPS acceleration, revenue growth, ROE

---

### Score Interpretation

| Score | Range | What to Look For |
|-------|-------|-----------------|
| **Trend Template** | 0–8 | 7–8 ideal, 6 acceptable |
| **Stage** | 1–4 | Stage 2 only |
| **VCP Score** | 0–100 | 70+ = strong setup |
| **Base Score** | 0–100 | 65+ = high quality |
| **RS 3m** | % vs SPY | Positive = outperforming market |
| **% to Pivot** | % | Under 5% = near entry |
| **Risk %** | % | Under 8% = tight risk |

---

### Minervini's SEPA Checklist
- ✅ Fundamental growth accelerating (EPS + Revenue)
- ✅ Stock under institutional accumulation (RS line making highs)
- ✅ VCP forming on dry, declining volume
- ✅ Entry at the pivot on a volume surge (at least 40-50% above average)
- ✅ Market in a confirmed uptrend
- ✅ Risk defined before entry, position sized correctly

---

### Key Rules
> *"The market is like a river — you want to swim with the current, not against it."* — Minervini

- **Never fight the market** — if SPY is in Stage 4, stand aside
- **Cut losses at 7-8%** — never let a small loss become a large one
- **Let winners run** — partial sell at 2R, hold rest for 3R+
- **Volume confirms breakouts** — no volume = no conviction
    """)
