import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY   = os.getenv("ANTHROPIC_API_KEY")
SERPER_API_KEY      = os.getenv("SERPER_API_KEY")
FIRECRAWL_API_KEY   = os.getenv("FIRECRAWL_API_KEY")
DATAFORSEO_LOGIN    = os.getenv("DATAFORSEO_LOGIN")
DATAFORSEO_PASSWORD = os.getenv("DATAFORSEO_PASSWORD")
SUPABASE_URL        = os.getenv("SUPABASE_URL")
SUPABASE_KEY        = os.getenv("SUPABASE_KEY")
INDEXNOW_KEY        = os.getenv("INDEXNOW_KEY", "")
SITE_URL            = os.getenv("SITE_URL", "")

# Free alternatives
TAVILY_API_KEY      = os.getenv("TAVILY_API_KEY")   # replaces Perplexity
SAPLING_API_KEY     = os.getenv("SAPLING_API_KEY")  # replaces Originality.ai

OUTPUT_DIR = "output/articles"
