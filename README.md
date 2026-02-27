# 📈 Minervini SEPA Scanner — Web App

A professional stock screening web app built on Minervini's SEPA methodology.

**Stack:** Streamlit · Alpaca Markets · yfinance · Claude AI

---

## 🚀 Deploy in 5 Steps

### Step 1 — Create GitHub Repository
1. Go to [github.com](https://github.com) and sign in (create account if needed)
2. Click **"New repository"** (green button, top right)
3. Name it: `sepa-scanner`
4. Set to **Public** (required for free Streamlit Cloud)
5. Click **"Create repository"**

### Step 2 — Upload Your Files
In your new empty repo, click **"uploading an existing file"**

Upload these 3 files:
- `app.py`
- `requirements.txt`
- `.gitignore`

**Do NOT upload** `.streamlit/secrets.toml` — your keys stay private

Click **"Commit changes"**

### Step 3 — Deploy on Streamlit Cloud
1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Click **"Sign in with GitHub"** — authorize it
3. Click **"New app"**
4. Select:
   - **Repository:** `your-username/sepa-scanner`
   - **Branch:** `main`
   - **Main file path:** `app.py`
5. Click **"Deploy"** — it will build (takes ~2 minutes first time)

### Step 4 — Add Your API Keys (Secrets)
While it's deploying (or after):
1. In Streamlit Cloud, click **"⋮" (three dots)** next to your app → **"Settings"**
2. Click **"Secrets"**
3. Paste this (with your real keys):

```toml
ALPACA_API_KEY    = "your_alpaca_api_key"
ALPACA_SECRET_KEY = "your_alpaca_secret_key"
ANTHROPIC_API_KEY = "your_anthropic_api_key"
```

4. Click **"Save"** — the app will restart automatically

### Step 5 — Open Your App
Streamlit gives you a URL like:
`https://your-username-sepa-scanner-app-xxxxxx.streamlit.app`

Bookmark it. Share it with anyone you want.

---

## 📁 File Structure

```
sepa-scanner/
├── app.py                ← The entire web app
├── requirements.txt      ← Python packages (Streamlit Cloud installs these)
├── .gitignore            ← Protects your secrets file from being uploaded
└── .streamlit/
    └── secrets.toml      ← API keys — NEVER upload this to GitHub
```

---

## 🔄 Updating the App

Any time you push a change to GitHub, Streamlit Cloud auto-redeploys:
1. Edit `app.py` on GitHub (click the file → pencil icon)
2. Commit the change
3. Streamlit redeploys in ~30 seconds

---

## ⚠️ Important Notes

- **Free tier limits:** Streamlit Cloud free tier sleeps after inactivity — first load may take 30s to wake up
- **API costs:** Alpaca data is free. Claude AI mentor costs ~$0.01–0.03 per deep dive call
- **Rate limits:** Full S&P 500 scan takes 3–5 minutes. Start with max 100 tickers while testing
- **Secrets:** Never paste API keys into `app.py` directly — always use Streamlit Secrets

---

## 🛠️ Troubleshooting

| Problem | Fix |
|---------|-----|
| App won't start | Check `requirements.txt` — all versions must be compatible |
| "Secrets not found" | Add keys in Streamlit Cloud → Settings → Secrets |
| Alpaca data empty | Verify your API key is for live data (not paper trading only) |
| Slow scan | Reduce max tickers, disable fundamentals checkbox |
| AI mentor fails | Check Anthropic API key has credits |
