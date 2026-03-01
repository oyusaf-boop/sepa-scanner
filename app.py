import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import anthropic
import time
from datetime import datetime

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


@st.cache_resource
def get_claude():
    return anthropic.Anthropic(api_key=st.secrets["ANTHROPIC_API_KEY"])


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
        df["ATR"] = pd.concat([hl, hc, lc], axis=1).max(axis=1).rolling(14).mean()
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
            "1. Price > SMA150 and SMA200":    bool(price > sma150 and price > sma200),
            "2. SMA150 > SMA200":              bool(sma150 > sma200),
            "3. SMA200 Trending Up (1mo)":     bool(sma200 > sma200_1mo),
            "4. SMA50 > SMA150 and SMA200":    bool(sma50 > sma150 and sma50 > sma200),
            "5. Price > SMA50":                bool(price > sma50),
            "6. Price 30pct Above 52w Low":    bool(price >= low52 * 1.30),
            "7. Price Within 25pct of 52w High": bool(price >= high52 * 0.75),
            "8. RS Positive vs SMA200":        bool(price > sma200),
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


def get_verdict(d):
    tt  = d["tt_score"]
    ext = (d["price"] / d["sma50"] - 1) * 100
    stg = d["stage"]
    vcp = d["vcp_score"]
    if tt >= 7 and stg == 2 and ext < 10 and vcp >= 60:
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
    fig.add_hline(y=d["pivot"],   line=dict(color="#00e5ff", width=1.5, dash="dash"),
                  annotation_text=f"Pivot ${d['pivot']:.2f}", row=1, col=1)
    fig.add_hline(y=stop_price,   line=dict(color="#f85149", width=1.2, dash="dot"),
                  annotation_text=f"Stop ${stop_price:.2f}", row=1, col=1)
    fig.add_hline(y=target_2r,    line=dict(color="#3fb950", width=1.0, dash="dashdot"),
                  annotation_text=f"2R ${target_2r:.2f}", row=1, col=1)
    fig.add_hline(y=target_3r,    line=dict(color="#b9f6ca", width=1.0, dash="dashdot"),
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
    rs_line = df["Close"] / df["SMA200"]
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


def claude_analysis(ticker, d, stop, t2r, t3r, shares):
    client = get_claude()
    tt_lines = "\n".join([f"  {k}: {v}" for k, v in d['tt'].items()])
    prompt = (
        f"You are Mark Minervini's trading methodology expert and mentor.\n"
        f"Analyze this SEPA setup and give a concise, actionable assessment. Be direct and specific.\n\n"
        f"TICKER: {ticker} ({d['name']}) | Sector: {d['sector']}\n"
        f"Price: ${d['price']:.2f} | Market Cap: ${d['mktcap']/1e9:.1f}B\n\n"
        f"TREND TEMPLATE: {d['tt_score']}/8\n{tt_lines}\n\n"
        f"STAGE ANALYSIS: {d['stage_label']}\n"
        f"SMA150 slope (20d): {d['slope20']}%\n\n"
        f"VCP ANALYSIS (Score: {d['vcp_score']}/100):\n"
        f"Contractions: {d['contractions']} | Tight area: {d['tight_rng']}% | Near highs: {d['near_highs']}\n"
        f"Volume drying: {d['vol_dry']} | Confirmed VCP: {d['is_vcp']}\n"
        f"Pivot: ${d['pivot']} | Pct to pivot: {d['pct_to_pivot']}%\n\n"
        f"RISK/REWARD:\n"
        f"Entry: ${d['pivot']:.2f} | Stop: ${stop:.2f} | 2R: ${t2r:.2f} | 3R: ${t3r:.2f}\n"
        f"Position: {shares} shares\n\n"
        f"FUNDAMENTALS:\n"
        f"EPS Growth Q: {d['eps_growth']*100:.1f}%\n"
        f"Revenue Growth: {d['rev_growth']*100:.1f}%\n"
        f"ROE: {d['roe']*100:.1f}%\n\n"
        f"Respond with:\n"
        f"1. SETUP VERDICT: (Actionable / Watch / Avoid - one line, blunt)\n"
        f"2. STRENGTHS: (3 bullets max)\n"
        f"3. WEAKNESSES / RISKS: (3 bullets max)\n"
        f"4. IDEAL ENTRY: (specific price action to wait for)\n"
        f"5. MENTOR NOTE: (one key Minervini insight for this exact setup)"
    )
    msg = client.messages.create(
        model="claude-sonnet-4-5",
        max_tokens=650,
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
    min_tt    = st.slider("Min Trend Template Score", 4, 8, 6)
    min_vcp   = st.slider("Min VCP Score", 0, 100, 40, 10)
    min_price = st.number_input("Min Price ($)", value=10.0, step=1.0)
    min_vol   = st.number_input("Min Avg Volume", value=300000, step=50000)
    st.markdown("---")
    st.markdown(
        "<p style='color:#8b949e;font-size:11px;'>Data: yfinance | AI: Claude<br>Not financial advice</p>",
        unsafe_allow_html=True
    )

# ── Header ────────────────────────────────────────────────────
st.markdown("# SEPA Institutional Terminal")
st.markdown(
    "<p style='color:#8b949e;margin-top:-12px;'>"
    "SEPA | Trend Template | Stage 2 | VCP | RS Line | AI Mentor"
    "</p>", unsafe_allow_html=True
)
st.markdown("---")

tab_single, tab_scanner, tab_guide = st.tabs(["Single Stock", "Batch Scanner", "Guide"])

# ── TAB 1: Single Stock ───────────────────────────────────────
with tab_single:
    ticker_input = st.text_input("Enter Ticker", "NVDA", placeholder="e.g. NVDA, AAPL, MSFT").strip().upper()

    if ticker_input:
        with st.spinner(f"Analyzing {ticker_input}..."):
            d = fetch_data(ticker_input)

        if d is None:
            st.error("Insufficient data or invalid ticker.")
        else:
            verdict_text, verdict_class = get_verdict(d)
            extension = (d["price"] / d["sma50"] - 1) * 100

            st.markdown(
                f'<div class="verdict-box verdict-{verdict_class}">{verdict_text}</div>',
                unsafe_allow_html=True
            )

            c1, c2, c3, c4, c5, c6 = st.columns(6)
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
            c5.metric("50MA Extension", f"{extension:.1f}%",
                      delta="Buyable" if extension < 10 else "Extended",
                      delta_color="normal" if extension < 10 else "inverse")
            c6.metric("% To Pivot", f"{d['pct_to_pivot']:.1f}%")

            st.markdown("---")
            st.markdown("### Execution & Position Sizing")
            ex1, ex2, ex3 = st.columns(3)

            with ex1:
                suggested_stop = float(d["df"]["Low"].tail(15).min())
                stop_price = st.number_input("Stop Loss ($)", value=round(suggested_stop, 2),
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
                stop_price = suggested_stop
                target_2r  = d["pivot"] * 1.10
                target_3r  = d["pivot"] * 1.15
                shares     = 0

            st.markdown("---")
            left, right = st.columns(2)

            with left:
                st.markdown("#### Trend Template")
                for criterion, passed in d["tt"].items():
                    st.markdown(f"{'✅' if passed else '❌'} {criterion}")
                st.markdown("#### Stage Analysis")
                st.markdown(f"**{d['stage_label']}**")
                st.markdown(f"SMA150 slope (20d): **{d['slope20']}%**")
                pct_above = (d['price'] - d['sma150']) / d['sma150'] * 100
                st.markdown(f"% above SMA150: **{pct_above:.1f}%**")

            with right:
                st.markdown("#### VCP Analysis")
                st.markdown(f"Score: **{d['vcp_score']}/100** {'✅ Confirmed' if d['is_vcp'] else ''}")
                st.markdown(f"Contractions: **{d['contractions']}**")
                st.markdown(f"Tight range (10d): **{d['tight_rng']}%** {'✅' if d['tight_rng'] < 8 else '❌'}")
                st.markdown(f"Near highs: {'✅' if d['near_highs'] else '❌'}")
                st.markdown(f"Volume drying: {'✅' if d['vol_dry'] else '❌'}")
                st.markdown("#### Fundamentals")
                st.markdown(f"**{d['name']}** | {d['sector']}")
                st.markdown(f"EPS Growth (Q): **{d['eps_growth']*100:.1f}%**")
                st.markdown(f"Revenue Growth: **{d['rev_growth']*100:.1f}%**")
                st.markdown(f"ROE: **{d['roe']*100:.1f}%**")
                if d['mktcap']:
                    st.markdown(f"Mkt Cap: **${d['mktcap']/1e9:.1f}B**")

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
                                ticker_input, d, stop_price, target_2r, target_3r, shares
                            )
                            st.markdown(
                                f'<div class="ai-box">{commentary}</div>',
                                unsafe_allow_html=True
                            )
                        except Exception as e:
                            st.error(f"Claude error: {e}")

# ── TAB 2: Batch Scanner ──────────────────────────────────────
with tab_scanner:
    st.markdown("### Batch SEPA Scanner")
    sc1, sc2, sc3 = st.columns(3)
    with sc1:
        universe = st.selectbox("Universe", ["S&P 500", "Nasdaq 100", "Custom"])
    with sc2:
        max_tickers = st.slider("Max Tickers", 10, 503, 100, 10)
    with sc3:
        custom_raw = st.text_input("Custom Tickers (comma separated)", "AAPL,NVDA,MSFT,META,GOOGL")

    require_stage2 = st.checkbox("Require Stage 2", value=True)
    require_vcp    = st.checkbox("Require VCP Confirmed", value=False)

    if st.button("Run Scan", type="primary", use_container_width=True):
        with st.spinner("Loading universe..."):
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

            verdict_text, _ = get_verdict(d)
            ext = (d["price"] / d["sma50"] - 1) * 100
            rows.append({
                "Ticker":     t,
                "Name":       d["name"],
                "Price":      d["price"],
                "TT Score":   d["tt_score"],
                "Stage":      d["stage_label"],
                "VCP Score":  d["vcp_score"],
                "VCP":        "Yes" if d["is_vcp"] else "No",
                "Ext%":       round(ext, 1),
                "Pivot":      d["pivot"],
                "%toPivot":   d["pct_to_pivot"],
                "EPS Gr%":    round(d["eps_growth"]*100, 1),
                "Rev Gr%":    round(d["rev_growth"]*100, 1),
                "Sector":     d["sector"],
                "Verdict":    verdict_text,
            })
            time.sleep(0.05)

        prog.empty()

        if not rows:
            st.warning("No tickers passed all filters. Try relaxing the settings in the sidebar.")
        else:
            df_r = pd.DataFrame(rows).sort_values("VCP Score", ascending=False).reset_index(drop=True)
            st.session_state["scan_results"] = df_r
            st.success(f"Scan complete — {len(df_r)} setups found from {total} tickers.")

    if "scan_results" in st.session_state:
        df_r = st.session_state["scan_results"]
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total Setups",  len(df_r))
        c2.metric("VCP Confirmed", (df_r["VCP"] == "Yes").sum())
        c3.metric("Avg TT Score",  f"{df_r['TT Score'].mean():.1f}")
        c4.metric("Avg VCP Score", f"{df_r['VCP Score'].mean():.1f}")

        def color_tt(val):
            if val >= 7: return "background-color:#0d3321;color:#3fb950"
            if val >= 6: return "background-color:#2d1f00;color:#d29922"
            return "background-color:#2d0f0f;color:#f85149"

        def color_vcp(val):
            if val >= 70: return "background-color:#0d3321;color:#3fb950"
            if val >= 40: return "background-color:#2d1f00;color:#d29922"
            return ""

        styled = (
            df_r.style
            .applymap(color_tt,  subset=["TT Score"])
            .applymap(color_vcp, subset=["VCP Score"])
            .format({"Price": "${:.2f}", "Pivot": "${:.2f}",
                     "Ext%": "{:.1f}%", "%toPivot": "{:.1f}%",
                     "EPS Gr%": "{:.1f}%", "Rev Gr%": "{:.1f}%"})
        )
        st.dataframe(styled, use_container_width=True, height=500)

        csv = df_r.to_csv(index=False)
        st.download_button(
            "Download CSV", csv,
            f"sepa_scan_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
            "text/csv"
        )

        st.markdown("---")
        st.markdown("**Quick Deep Dive from results**")
        dive_ticker = st.selectbox("Select ticker", df_r["Ticker"].tolist(), key="scanner_dive")
        if st.button("Deep Dive this ticker"):
            st.info(f"Go to the Single Stock tab and type: {dive_ticker}")

# ── TAB 3: Guide ──────────────────────────────────────────────
with tab_guide:
    st.markdown("## SEPA Methodology Guide")
    st.markdown("""
### How To Use This Terminal
1. **Single Stock tab** — type any ticker for instant full analysis
2. **Batch Scanner tab** — scan S&P 500 or Nasdaq 100 for setups
3. **AI Mentor button** — get a Claude-powered Minervini-style verdict

---

### Score Reference
| Metric | Range | Target |
|--------|-------|--------|
| Trend Template | 0-8 | 7-8 ideal, 6 minimum |
| Stage | 1-4 | Stage 2 only |
| VCP Score | 0-100 | 70+ strong, 50+ acceptable |
| Extension above 50MA | % | Under 10% = buyable |
| % to Pivot | % | Under 5% = near entry |

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
    """)

st.divider()
st.caption("Terminal Mandate: 1% Portfolio Risk Rule | Stage 2 Only | Minervini SEPA Methodology")
