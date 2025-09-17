from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import PlainTextResponse
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
import httpx, os, re, xml.etree.ElementTree as ET

# -------------------------- MCP server (HTTP streamable) ---------------------
mcp = FastMCP("Correduidea MCP (HTML)", stateless_http=True)

ALLOWED_DOMAIN = "correduidea.com"
SITEMAP_URL = "https://www.correduidea.com/sitemap.xml"
ALLOWLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "allowlist_urls.txt")

def _allowed(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc.endswith(ALLOWED_DOMAIN)

def _extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")  # sin lxml (más compatible en Render)
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return re.sub(r"\s+", " ", soup.get_text(separator=" ", strip=True))

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
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out

async def _get_urls_combined() -> list[str]:
    site = await _read_sitemap()
    allow = _read_allowlist()
    return (site + [u for u in allow if u not in site])[:200]

# ------------------------------- TOOLS ---------------------------------------
@mcp.tool()
async def ping() -> str:
    return "pong"

@mcp.tool()
async def listar_urls() -> list[str]:
    return await _get_urls_combined()

@mcp.tool()
async def leer_url(url: str) -> str:
    if not _allowed(url):
        return "Error: Solo se permiten URLs de correduidea.com"
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            return r.text[:4000]
    except Exception as e:
        return f"Error al leer la URL: {e}"

@mcp.tool()
async def buscar_texto(query: str, max_pages: int = 10) -> list[dict]:
    q = (query or "").strip().lower()
    if not q:
        return [{"error": "La query no puede estar vacía."}]
    urls = (await _get_urls_combined())[:max(1, max_pages)]
