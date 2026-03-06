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
        font
