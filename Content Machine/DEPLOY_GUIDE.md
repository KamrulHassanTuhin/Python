# Deploy Guide — Streamlit Cloud (Free)

## Step 1 — Supabase Setup (5 min)
1. Go to supabase.com → your project
2. Click "SQL Editor" → "New Query"
3. Paste the contents of `supabase_setup.sql`
4. Click "Run"

## Step 2 — GitHub (5 min)
1. Go to github.com → Sign in → "New repository"
2. Name: `content-machine` (private)
3. Click "Create repository"
4. Upload your entire `Content Machine` folder
   - Drag and drop all files into the GitHub upload page
   - **Important:** Do NOT upload `.streamlit/secrets.toml` or `.env`

## Step 3 — Streamlit Cloud (5 min)
1. Go to share.streamlit.io
2. Sign in with GitHub
3. Click "New app"
4. Select your `content-machine` repo
5. Main file path: `app.py`
6. Click "Advanced settings" → "Secrets"
7. Paste this (replace with your actual keys):

```toml
ANTHROPIC_API_KEY = "your_key"
SERPER_API_KEY = "your_key"
FIRECRAWL_API_KEY = "your_key"
DATAFORSEO_LOGIN = "your_login"
DATAFORSEO_PASSWORD = "your_password"
SUPABASE_URL = "your_url"
SUPABASE_KEY = "your_key"
TAVILY_API_KEY = "your_key"
SAPLING_API_KEY = "your_key"
```

8. Click "Deploy"

## Done!
Your app will be live at: `https://your-app-name.streamlit.app`

## Local Run (for testing)
```
cd "f:\Python\Content Machine"
python -m streamlit run app.py
```
