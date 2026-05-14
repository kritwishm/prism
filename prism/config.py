import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5-20250929")
JINA_API_KEY = os.getenv("JINA_API_KEY")
HUBSPOT_ACCESS_TOKEN = os.getenv("HUBSPOT_ACCESS_TOKEN")
SANITY_PROJECT_ID = os.getenv("SANITY_PROJECT_ID")
SANITY_DATASET = os.getenv("SANITY_DATASET", "production")
SANITY_TOKEN = os.getenv("SANITY_TOKEN")
SANITY_API_VERSION = os.getenv("SANITY_API_VERSION", "2024-01-01")
SANITY_STUDIO_PATH = os.getenv("SANITY_STUDIO_PATH", "desk")  # 'desk' (v2) or 'structure' (v3)

JINA_READER_BASE = "https://r.jina.ai/"

DISCOVERY_PATH_HINTS = [
    "", "/about", "/about-us", "/company", "/our-story", "/why",
    "/what-we-do", "/product", "/products", "/solutions", "/platform",
    "/services", "/customers", "/case-studies", "/blog",
]

DISCOVERY_KEYWORDS = (
    "about", "company", "story", "why", "what", "product", "solution",
    "platform", "service", "customer", "case", "blog", "press",
)

_required = {
    "ANTHROPIC_API_KEY": ANTHROPIC_API_KEY,
    "HUBSPOT_ACCESS_TOKEN": HUBSPOT_ACCESS_TOKEN,
    "SANITY_PROJECT_ID": SANITY_PROJECT_ID,
    "SANITY_TOKEN": SANITY_TOKEN,
}
missing = [k for k, v in _required.items() if not v]
if missing:
    raise RuntimeError(f"Missing required env vars: {missing}")
