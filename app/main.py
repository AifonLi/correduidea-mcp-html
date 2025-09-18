import os, re, json, xml.etree.ElementTree as ET
from urllib.parse import urlparse
import httpx
from bs4 import BeautifulSoup
from starlette.responses import PlainTextResponse, Response
from starlette.routing import Route
from mcp.server.fastmcp import FastMCP

# ------------------ MCP server ------------------
mcp = FastMCP("Correduidea MCP (HTML)", stateless_http=True)

ALLOWED_DOMAIN = "correduidea.com"  # admite www.correduidea.com
SITEMAP_URL = "https://www.correduidea.com/sitemap.xml"
ALLOWLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "allowlist_urls.txt")

# ------------------ utils -----------------------
def _allowed(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc.endswith(ALLOWED_DOMAIN)

def _extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
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
    # dedup
    seen, out = set(), []
    for u in urls:
        if u not in seen:
            seen.add(u); out.append(u)
    return out

async def _get_urls_combined() -> list[str]:
    site = await _read_sitemap()
    allow = _read_allowlist()
    return (site + [u for u in allow if u not in site])[:200]

# ------------------ tools existentes ------------------
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

# ------------------ tools estándar para la UI ------------------
@mcp.tool(name="search")
async def tool_search(query: str, max_results: int = 8) -> list[dict]:
    """Devuelve resultados en el formato que espera ChatGPT."""
    q = (query or "").strip().lower()
    results = []
    urls = await _get_urls_combined()

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for u in urls[:20]:
            try:
                r = await client.get(u)
                if r.status_code != 200:
                    continue
                html = r.text
                text = _extract_visible_text(html)
                if q in text.lower() or q in u.lower():
                    m = re.search(r"<title>(.*?)</title>", html, flags=re.I | re.S)
                    title = (m.group(1).strip() if m else u)[:120]
                    results.append({"id": u, "title": title, "url": u})
                    if len(results) >= max_results:
                        break
            except Exception:
                pass

    return [{"type": "text", "text": json.dumps({"results": results}, ensure_ascii=False)}]

@mcp.tool(name="fetch")
async def tool_fetch(id: str) -> list[dict]:
    """Recibe un id (usamos la URL) y devuelve texto de la página."""
    url = id.strip()
    if not _allowed(url):
        return [{"type": "text", "text": json.dumps({"error": "URL no permitida"}, ensure_ascii=False)}]
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(url)
            r.raise_for_status()
            text = _extract_visible_text(r.text)[:8000]
            return [{"type": "text", "text": text}]
    except Exception as e:
        return [{"type": "text", "text": f"Error: {e}"}]

# ------------------ HTTP (salud/CORS) ------------------
def _cors_headers():
    return {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "POST, GET, HEAD, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }

async def mcp_health(request):
    return PlainTextResponse("MCP server OK", headers=_cors_headers())

async def mcp_options(request):
    return Response(status_code=204, headers=_cors_headers())

# App principal: el propio servidor MCP
app = mcp.streamable_http_app()
# GET/HEAD/OPTIONS sobre el mismo router (evita errores de startup)
app.router.routes.insert(0, Route("/mcp", mcp_options, methods=["OPTIONS"]))
app.router.routes.insert(0, Route("/mcp", mcp_health, methods=["GET", "HEAD"]))
