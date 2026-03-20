"""
Content Machine — Streamlit Web App
=====================================
Deploy on Streamlit Cloud (free).
Supabase for auth + article history.
"""

import streamlit as st
import sys
import os
import json
import requests
from datetime import datetime

# Point to Content Machine folder for all agent imports
_root = os.path.dirname(os.path.abspath(__file__))
_cm = os.path.join(_root, "Content Machine")
if _cm not in sys.path:
    sys.path.insert(0, _cm)
if _root not in sys.path:
    sys.path.insert(0, _root)

# ─────────────────────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Content Machine",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# LOAD SECRETS (Streamlit Cloud secrets or .env fallback)
# ─────────────────────────────────────────────────────────────
def _get_secret(key: str, default: str = "") -> str:
    try:
        return st.secrets[key]
    except Exception:
        pass
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except Exception:
        pass
    return os.getenv(key, default)

SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")

# ─────────────────────────────────────────────────────────────
# SUPABASE AUTH (REST API — no extra package needed)
# ─────────────────────────────────────────────────────────────
def sb_signup(email: str, password: str) -> dict:
    url = f"{SUPABASE_URL}/auth/v1/signup"
    r = requests.post(url, headers={"apikey": SUPABASE_KEY}, json={"email": email, "password": password}, timeout=10)
    return r.json()

def sb_login(email: str, password: str) -> dict:
    url = f"{SUPABASE_URL}/auth/v1/token?grant_type=password"
    r = requests.post(url, headers={"apikey": SUPABASE_KEY}, json={"email": email, "password": password}, timeout=10)
    return r.json()

def sb_get_articles(user_id: str) -> list:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    try:
        url = f"{SUPABASE_URL}/rest/v1/articles?user_id=eq.{user_id}&order=published_at.desc&limit=50&select=id,keyword,quality_score,word_count,status,published_at,body"
        headers = {"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"}
        r = requests.get(url, headers=headers, timeout=10)
        return r.json() if isinstance(r.json(), list) else []
    except Exception:
        return []


def sb_save_article(user_id: str, keyword: str, body: str, quality_score: int, word_count: int, status: str = "published") -> bool:
    if not SUPABASE_URL or not SUPABASE_KEY:
        return False
    try:
        url = f"{SUPABASE_URL}/rest/v1/articles"
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        }
        payload = {
            "user_id": user_id,
            "keyword": keyword,
            "body": body,
            "quality_score": quality_score,
            "word_count": word_count,
            "status": status,
            "published_at": datetime.utcnow().isoformat(),
        }
        r = requests.post(url, headers=headers, json=payload, timeout=10)
        return r.status_code in (200, 201)
    except Exception:
        return False

# ─────────────────────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "user" not in st.session_state:
    st.session_state.user = {}
if "page" not in st.session_state:
    st.session_state.page = "login"
if "last_article" not in st.session_state:
    st.session_state.last_article = {}
if "pipeline_log" not in st.session_state:
    st.session_state.pipeline_log = []

# Pre-import pipeline so module-level code runs with real stdout
try:
    from main import run_pipeline as _run_pipeline
except Exception as _import_err:
    _run_pipeline = None
    _import_err_msg = str(_import_err)


# ─────────────────────────────────────────────────────────────
# PIPELINE STDOUT CAPTURE
# ─────────────────────────────────────────────────────────────
class StreamlitWriter:
    """Redirect agent print() output to a Streamlit container."""
    def __init__(self, container):
        self.container = container
        self.lines = []
        self.encoding = "utf-8"
        self.errors = "replace"

    def write(self, text: str) -> int:
        if text and text.strip():
            self.lines.append(text.strip())
            self.container.markdown(
                "\n".join(f"`{l}`" for l in self.lines[-30:])
            )
        return len(text)

    def flush(self):
        pass

    def reconfigure(self, **kwargs):
        pass

    def isatty(self):
        return False


def run_pipeline_captured(keyword, niche, skip_exp, repurpose, site_url, log_container):
    """Run the pipeline, capturing all print output into the Streamlit container."""
    if _run_pipeline is None:
        return {"output_path": "", "error": f"Import error: {_import_err_msg}", "state": {}}

    old_stdout = sys.stdout
    writer = StreamlitWriter(log_container)
    sys.stdout = writer

    result = {"output_path": "", "error": None, "state": {}}
    try:
        run_pipeline = _run_pipeline
        output_path = run_pipeline(
            keyword=keyword,
            niche=niche,
            skip_experience=skip_exp,
            do_repurpose=repurpose,
            site_url=site_url,
        )
        result["output_path"] = output_path

        # Load the generated article
        if output_path and os.path.exists(output_path):
            with open(output_path, encoding="utf-8") as f:
                result["markdown"] = f.read()

        # Get quality score from shared memory
        try:
            from shared_memory.memory import _load
            data = _load()
            for k, v in data.items():
                if isinstance(v, dict) and v.get("keyword", "").lower() == keyword.lower():
                    result["state"] = v
                    break
        except Exception:
            pass

    except Exception as e:
        result["error"] = str(e)
    finally:
        sys.stdout = old_stdout

    return result


# ─────────────────────────────────────────────────────────────
# PAGES
# ─────────────────────────────────────────────────────────────

def page_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("## ⚡ Content Machine")
        st.markdown("AI-powered 21-agent content system")
        st.divider()

        tab_login, tab_signup = st.tabs(["Login", "Sign Up"])

        with tab_login:
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True, type="primary"):
                if not email or not password:
                    st.error("Enter email and password.")
                else:
                    with st.spinner("Logging in..."):
                        res = sb_login(email, password)
                    if res.get("access_token"):
                        st.session_state.logged_in = True
                        st.session_state.user = {
                            "email": email,
                            "id": res.get("user", {}).get("id", "local"),
                            "token": res.get("access_token"),
                        }
                        st.session_state.page = "dashboard"
                        st.rerun()
                    else:
                        msg = res.get("error_description") or res.get("msg") or "Login failed"
                        st.error(msg)

            st.caption("No Supabase? Use any email + password — runs in local mode.")
            if st.button("Continue without account", use_container_width=True):
                st.session_state.logged_in = True
                st.session_state.user = {"email": "local", "id": "local", "token": ""}
                st.session_state.page = "dashboard"
                st.rerun()

        with tab_signup:
            s_email = st.text_input("Email", key="signup_email")
            s_pass = st.text_input("Password (min 6 chars)", type="password", key="signup_pass")
            if st.button("Create Account", use_container_width=True, type="primary"):
                if not s_email or not s_pass:
                    st.error("Enter email and password.")
                elif len(s_pass) < 6:
                    st.error("Password must be at least 6 characters.")
                else:
                    with st.spinner("Creating account..."):
                        res = sb_signup(s_email, s_pass)
                    if res.get("id") or res.get("user"):
                        st.success("Account created! Check your email to confirm, then login.")
                    else:
                        msg = res.get("error_description") or res.get("msg") or "Signup failed"
                        st.error(msg)


def page_dashboard():
    st.markdown("## ⚡ Content Machine")
    st.markdown("Write a new article using the 21-agent pipeline.")
    st.divider()

    with st.form("pipeline_form"):
        col1, col2 = st.columns(2)
        with col1:
            keyword = st.text_input("Keyword *", placeholder="e.g. best AI writing tools 2025")
            niche = st.text_input("Niche", placeholder="e.g. ai tools", value="general")
            site_url = st.text_input("Your site URL (optional)", placeholder="https://yoursite.com")
        with col2:
            skip_exp = st.checkbox("Skip experience bullets (AG·20)", value=True)
            repurpose = st.checkbox("Repurpose to social media (AG·17)", value=False)
            st.markdown("&nbsp;")
            st.markdown("**Pipeline phases:**")
            st.markdown("Phase 1 → Research & Strategy  \nPhase 2 → Write & Optimize  \nPhase 3 → Technical & QA  \nPhase 4 → Quality Gate  \nPhase 5 → Save & Index")

        submitted = st.form_submit_button("Run Pipeline ▶", type="primary", use_container_width=True)

    if submitted:
        if not keyword:
            st.error("Keyword is required.")
        else:
            st.session_state.page = "running"
            st.session_state.run_params = {
                "keyword": keyword,
                "niche": niche or "general",
                "skip_exp": skip_exp,
                "repurpose": repurpose,
                "site_url": site_url,
            }
            st.rerun()


def page_running():
    params = st.session_state.get("run_params", {})
    keyword = params.get("keyword", "")

    st.markdown(f"## Running pipeline for: `{keyword}`")
    st.info("This takes 2-5 minutes. Do not close this tab.")
    st.divider()

    log_container = st.empty()
    log_container.markdown("`Starting pipeline...`")

    with st.spinner("Pipeline running..."):
        result = run_pipeline_captured(
            keyword=params.get("keyword", ""),
            niche=params.get("niche", "general"),
            skip_exp=params.get("skip_exp", True),
            repurpose=params.get("repurpose", False),
            site_url=params.get("site_url", ""),
            log_container=log_container,
        )

    st.session_state.last_article = result

    if result.get("error"):
        st.error(f"Pipeline error: {result['error']}")
        if st.button("Back to Dashboard"):
            st.session_state.page = "dashboard"
            st.rerun()
    else:
        quality = result.get("state", {}).get("quality_result", {}).get("total", 0)
        verdict = result.get("state", {}).get("quality_result", {}).get("verdict", "")
        markdown_body = result.get("markdown", "")
        word_count = len(markdown_body.split())

        # Auto-save to Supabase
        user_id = st.session_state.user.get("id", "local")
        if user_id != "local" and markdown_body:
            saved = sb_save_article(
                user_id=user_id,
                keyword=params.get("keyword", ""),
                body=markdown_body,
                quality_score=quality,
                word_count=word_count,
                status=verdict or "published",
            )
            if saved:
                st.success(f"Pipeline complete! Score: {quality}/110 — {verdict} ✓ Saved to database")
            else:
                st.success(f"Pipeline complete! Score: {quality}/110 — {verdict}")
        else:
            st.success(f"Pipeline complete! Score: {quality}/110 — {verdict}")
        col1, col2 = st.columns(2)
        with col1:
            if st.button("View Article", type="primary", use_container_width=True):
                st.session_state.page = "article"
                st.rerun()
        with col2:
            if st.button("Write Another", use_container_width=True):
                st.session_state.page = "dashboard"
                st.rerun()


def page_article():
    result = st.session_state.get("last_article", {})
    state = result.get("state", {})
    keyword = state.get("keyword", "Article")
    quality = state.get("quality_result", {}).get("total", 0)
    verdict = state.get("quality_result", {}).get("verdict", "")
    word_count = len((result.get("markdown", "")).split())

    # Header
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Quality Score", f"{quality}/110")
    col2.metric("Verdict", verdict or "—")
    col3.metric("Word Count", f"{word_count:,}")
    col4.metric("Keyword", keyword[:20] + "..." if len(keyword) > 20 else keyword)

    st.divider()

    tab_preview, tab_raw, tab_scores = st.tabs(["Preview", "Raw Markdown", "Score Breakdown"])

    markdown_content = result.get("markdown", "_No content generated._")

    with tab_preview:
        st.markdown(markdown_content)

    with tab_raw:
        st.code(markdown_content, language="markdown")
        st.download_button(
            label="Download .md file",
            data=markdown_content,
            file_name=f"{keyword.replace(' ', '_').lower()}.md",
            mime="text/markdown",
            use_container_width=True,
        )

    with tab_scores:
        scores = state.get("scores", {})
        if scores:
            for dim, score in scores.items():
                max_score = 10 if dim == "voice_bonus" else 20
                st.progress(score / max_score, text=f"{dim.replace('_', ' ').title()}: {score}/{max_score}")
        issues = state.get("quality_result", {}).get("issues", [])
        if issues:
            st.markdown("**Issues to fix:**")
            for issue in issues:
                st.warning(issue)
        quick_fixes = state.get("quality_result", {}).get("quick_fixes", [])
        if quick_fixes:
            st.markdown("**Quick fixes:**")
            for fix in quick_fixes:
                st.info(fix)

    st.divider()
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Write Another Article", type="primary", use_container_width=True):
            st.session_state.page = "dashboard"
            st.rerun()
    with col2:
        if st.button("View History", use_container_width=True):
            st.session_state.page = "history"
            st.rerun()


def _find_local_article_file(keyword: str) -> str:
    """Search output/articles/ folder for an .md file matching the keyword."""
    try:
        _root = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(_root, "Content Machine", "output", "articles")
        if not os.path.isdir(output_dir):
            return ""
        slug = keyword.lower().replace(" ", "_")
        # Look for files that start with the keyword slug
        for fname in sorted(os.listdir(output_dir), reverse=True):
            if fname.endswith(".md") and slug in fname:
                return os.path.join(output_dir, fname)
        # Fallback: return the most recent .md file
        md_files = sorted(
            [os.path.join(output_dir, f) for f in os.listdir(output_dir) if f.endswith(".md")],
            key=os.path.getmtime, reverse=True
        )
        return md_files[0] if md_files else ""
    except Exception:
        return ""


def page_history():
    st.markdown("## Article History")

    user_id = st.session_state.user.get("id", "local")

    # Try Supabase first, fall back to local shared_memory
    supabase_articles = sb_get_articles(user_id)
    local_articles = []

    if not supabase_articles:
        try:
            from shared_memory.memory import _load
            data = _load()
            local_articles = [
                {
                    "keyword": v.get("keyword", k),
                    "quality_score": v.get("quality_result", {}).get("total", 0),
                    "status": v.get("status", ""),
                    "published_at": v.get("published_at", ""),
                    "word_count": len(v.get("draft", "").split()),
                    "_source": "local",
                }
                for k, v in data.items()
                if isinstance(v, dict) and not k.startswith("_") and "keyword" in v
            ]
        except Exception:
            local_articles = []

    articles = supabase_articles if supabase_articles else local_articles

    # Also scan output/articles/ folder for any .md files not in shared_memory
    try:
        _root = os.path.dirname(os.path.abspath(__file__))
        output_dir = os.path.join(_root, "Content Machine", "output", "articles")
        if os.path.isdir(output_dir):
            existing_keywords = {a.get("keyword", "").lower() for a in articles}
            for fname in sorted(os.listdir(output_dir), reverse=True):
                if not fname.endswith(".md"):
                    continue
                # Extract keyword from filename (strip date suffix)
                base = fname.replace(".md", "")
                parts = base.rsplit("_", 1)
                kw = parts[0].replace("_", " ") if len(parts) == 2 and parts[1].isdigit() else base.replace("_", " ")
                if kw.lower() not in existing_keywords:
                    fpath = os.path.join(output_dir, fname)
                    mtime = datetime.fromtimestamp(os.path.getmtime(fpath)).strftime("%Y-%m-%d")
                    articles.append({
                        "keyword": kw,
                        "quality_score": 0,
                        "status": "saved",
                        "published_at": mtime,
                        "word_count": 0,
                        "_source": "file",
                        "_file": fpath,
                    })
                    existing_keywords.add(kw.lower())
    except Exception:
        pass

    if not articles:
        st.info("No articles yet. Write your first article!")
        if st.button("Write Article", type="primary"):
            st.session_state.page = "dashboard"
            st.rerun()
        return

    st.markdown(f"**{len(articles)} article(s)** — click View to read any article")
    st.divider()

    for i, art in enumerate(articles):
        col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 2, 1])
        with col1:
            st.markdown(f"**{art.get('keyword', '—')}**")
        with col2:
            score = art.get("quality_score", 0)
            st.markdown(f"Score: **{score}**")
        with col3:
            wc = art.get("word_count", 0)
            st.markdown(f"{wc:,} words" if wc else "—")
        with col4:
            st.caption(art.get("status", "") or art.get("published_at", "") or "—")
        with col5:
            if st.button("View", key=f"view_{i}", type="primary"):
                # Load content from file or Supabase body
                content = art.get("body", "") or art.get("markdown", "")
                if not content:
                    # Try to find local file
                    fpath = art.get("_file", "") or _find_local_article_file(art.get("keyword", ""))
                    if fpath and os.path.exists(fpath):
                        with open(fpath, encoding="utf-8") as f:
                            content = f.read()
                st.session_state.last_article = {
                    "markdown": content or "_Article content not found. The file may have been deleted._",
                    "state": {
                        "keyword": art.get("keyword", ""),
                        "quality_result": {"total": art.get("quality_score", 0), "verdict": art.get("status", "")},
                    },
                }
                st.session_state.page = "article"
                st.rerun()
        st.divider()

    if st.button("Write New Article", type="primary"):
        st.session_state.page = "dashboard"
        st.rerun()


def page_gap_detector():
    st.markdown("## Gap Detector (AG·19)")
    st.markdown("Find content gaps and get new keyword ideas.")
    st.divider()

    niche = st.text_input("Your niche", placeholder="e.g. ai tools")

    if st.button("Find Gaps", type="primary"):
        if not niche:
            st.error("Enter a niche.")
        else:
            with st.spinner("Analyzing gaps..."):
                try:
                    from shared_memory.memory import _load
                    from agents import ag19_gap_detector
                    existing = [v.get("keyword", "") for k, v in _load().items()
                                if not k.startswith("_") and "keyword" in v]
                    gaps = ag19_gap_detector.find_gaps(niche, existing)

                    high = gaps.get("high_priority_gaps", [])
                    wins = gaps.get("quick_wins", [])

                    col1, col2 = st.columns(2)
                    with col1:
                        st.markdown(f"### High Priority ({len(high)})")
                        for g in high:
                            with st.container(border=True):
                                st.markdown(f"**{g.get('keyword')}**")
                                st.caption(f"Difficulty: {g.get('estimated_difficulty')} | {g.get('reason', '')}")
                                if st.button(f"Write this →", key=f"hp_{g.get('keyword')}"):
                                    st.session_state.run_params = {
                                        "keyword": g.get("keyword"),
                                        "niche": niche,
                                        "skip_exp": True,
                                        "repurpose": False,
                                        "site_url": "",
                                    }
                                    st.session_state.page = "running"
                                    st.rerun()

                    with col2:
                        st.markdown(f"### Quick Wins ({len(wins)})")
                        for w in wins:
                            with st.container(border=True):
                                st.markdown(f"**{w.get('keyword')}**")
                                st.caption(w.get("action", ""))
                                if st.button(f"Write this →", key=f"qw_{w.get('keyword')}"):
                                    st.session_state.run_params = {
                                        "keyword": w.get("keyword"),
                                        "niche": niche,
                                        "skip_exp": True,
                                        "repurpose": False,
                                        "site_url": "",
                                    }
                                    st.session_state.page = "running"
                                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")


# ─────────────────────────────────────────────────────────────
# SIDEBAR + ROUTING
# ─────────────────────────────────────────────────────────────
def sidebar():
    with st.sidebar:
        st.markdown("### ⚡ Content Machine")
        if st.session_state.logged_in:
            email = st.session_state.user.get("email", "")
            st.caption(f"Logged in as: {email}")
            st.divider()

            if st.button("New Article", use_container_width=True, type="primary"):
                st.session_state.page = "dashboard"
                st.rerun()

            if st.button("Article History", use_container_width=True):
                st.session_state.page = "history"
                st.rerun()

            if st.button("Gap Detector", use_container_width=True):
                st.session_state.page = "gap_detector"
                st.rerun()

            st.divider()
            if st.button("Logout", use_container_width=True):
                st.session_state.logged_in = False
                st.session_state.user = {}
                st.session_state.page = "login"
                st.rerun()


def main():
    sidebar()

    if not st.session_state.logged_in:
        page_login()
        return

    page = st.session_state.page

    if page == "dashboard":
        page_dashboard()
    elif page == "running":
        page_running()
    elif page == "article":
        page_article()
    elif page == "history":
        page_history()
    elif page == "gap_detector":
        page_gap_detector()
    else:
        page_dashboard()


if __name__ == "__main__":
    main()
