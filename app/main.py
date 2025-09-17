from starlette.applications import Starlette
from starlette.routing import Mount, Route
from starlette.responses import PlainTextResponse
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
import httpx, os, re, xml.etree.ElementTree as ET

# -------------------------- MCP server (HTTP streamable) ---------------------
# ⚠️ IMPORTANTE: stateless_http=True evita el error de "Task group is not initialized"
mcp = FastMCP("Correduidea MCP (HTML)", stateless_http=True)

ALLOWED_DOMAIN = "correduidea.com"
SITEMAP_URL = "https://www.correduidea.com/sitemap.xml"
ALLOWLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "allowlist_urls.txt")

def _allowed(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc.endswith(ALLOWED_DOMAIN)

def _extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")  # sin lxml para máxima compatibilidad
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

# --------------------------------- TOOLS -------------------------------------
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
    out = []
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for u in urls:
            try:
                r = await client.get(u)
                if r.status_code != 200:
                    out.append({"url": u, "encontrado": False, "fragmento": f"HTTP {r.status_code}"})
                    continue
                text = _extract_visible_text(r.text)
                pos = text.lower().find(q)
                if pos >= 0:
                    start = max(0, pos - 120); end = min(len(text), pos + 120)
                    out.append({"url": u, "encontrado": True, "fragmento": text[start:end]})
                else:
                    out.append({"url": u, "encontrado": False, "fragmento": ""})
            except Exception as e:
                out.append({"url": u, "encontrado": False, "fragmento": f"Error: {e}"})
    return out

# -------------------------- App HTTP (GET/HEAD/POST) -------------------------
async def mcp_health(request):
    # Respuesta simple para validaciones GET/HEAD
    return PlainTextResponse("MCP server OK")

inner_app = mcp.streamable_http_app()  # maneja POST /mcp para ChatGPT
app = Starlette(routes=[
    Route("/mcp", mcp_health, methods=["GET", "HEAD"]),  # 200 OK para GET/HEAD
    Mount("/", app=inner_app),                           # POST /mcp (MCP real)
])
