from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import PlainTextResponse
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
import httpx, os, re, xml.etree.ElementTree as ET

# -----------------------------------------------------------------------------
# Servidor MCP (Streamable HTTP)
# -----------------------------------------------------------------------------
mcp = FastMCP("Correduidea MCP (HTML)", stateless_http=True)

ALLOWED_DOMAIN = "correduidea.com"
SITEMAP_URL = "https://www.correduidea.com/sitemap.xml"
ALLOWLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "allowlist_urls.txt")

# --------------------------- utilidades internas -----------------------------
def _allowed(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc.endswith(ALLOWED_DOMAIN)

def _extract_visible_text(html: str) -> str:
    # Usamos el parser estándar de Python para evitar dependencias extra
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    return re.sub(r"\s+", " ", text)

def _read_allowlist() -> list[str]:
    urls: list[str] = []
    try:
        with open(ALLOWLIST_FILE, "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if u and _allowed(u):
                    urls.append(u)
    except FileNotFoundError:
        pass
    return urls

async def _read_sitemap() -> list[str]:
    urls: list[str] = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(SITEMAP_URL)
            if r.status_code != 200:
                return []
            root = ET.fromstring(r.text)
            for loc in root.findall(".//{*}url/{*}loc"):
                u = (loc.text or "").strip()
                if _allowed(u):
                    urls.append(u)
    except Exception:
        pass
    # únicos manteniendo orden
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); out.app
