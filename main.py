from starlette.applications import Starlette
from starlette.routing import Mount
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from mcp.server.fastmcp import FastMCP
import httpx, os, io, re, xml.etree.ElementTree as ET

# -----------------------------------------------------------------------------
# Servidor MCP (Streamable HTTP)
# -----------------------------------------------------------------------------
mcp = FastMCP("Correduidea MCP (HTML)", stateless_http=True)

ALLOWED_DOMAIN = "correduidea.com"
ALLOWLIST_FILE = os.path.join(os.path.dirname(__file__), "..", "config", "allowlist_urls.txt")
SITEMAP_URL = "https://www.correduidea.com/sitemap.xml"

# Utilidad: validar dominio
def _allowed(url: str) -> bool:
    p = urlparse(url)
    return p.scheme in ("http", "https") and p.netloc.endswith(ALLOWED_DOMAIN)

# Utilidad: leer allowlist del archivo
def _read_allowlist() -> list[str]:
    urls = []
    try:
        with open(ALLOWLIST_FILE, "r", encoding="utf-8") as f:
            for line in f:
                u = line.strip()
                if u and _allowed(u):
                    urls.append(u)
    except FileNotFoundError:
        pass
    return urls

# Intentar leer sitemap.xml simple
async def _read_sitemap() -> list[str]:
    urls = []
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(SITEMAP_URL)
            if r.status_code != 200:
                return []
            content = r.text
        # Parse XML (soporta <urlset> simple; no manejamos índices múltiples aquí)
        try:
            root = ET.fromstring(content)
            for url in root.findall(".//{*}url/{*}loc"):
                u = url.text.strip()
                if _allowed(u):
                    urls.append(u)
        except Exception:
            # Si no es un urlset simple, ignoramos y seguimos con allowlist
            pass
    except Exception:
        pass
    # Quitar duplicados manteniendo orden
    seen = set()
    out = []
    for u in urls:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out

async def _get_urls_combined() -> list[str]:
    site = await _read_sitemap()
    allow = _read_allowlist()
    combined = site + [u for u in allow if u not in site]
    # Limitar un poco por seguridad
    return combined[:200]

def _extract_visible_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    # Eliminar scripts y styles
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(separator=" ", strip=True)
    # Normalizar espacios
    text = re.sub(r"\s+", " ", text)
    return text

# -----------------------------------------------------------------------------
# Tools
# -----------------------------------------------------------------------------
@mcp.tool()
async def ping() -> str:
    """Devuelve 'pong' para comprobar el estado del conector."""
    return "pong"

@mcp.tool()
async def listar_urls() -> list[str]:
    """Devuelve la lista de URLs (sitemap.xml + allowlist)."""
    return await _get_urls_combined()

@mcp.tool()
async def leer_url(url: str) -> str:
    """
    Descarga el HTML de una URL (solo correduidea.com) y devuelve un recorte (4000 chars).
    """
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
    """
    Busca 'query' en una selección de páginas del dominio.
    Devuelve una lista de dicts: {url, encontrado, fragmento}
    """
    query_low = (query or "").strip().lower()
    if not query_low:
        return [{"error": "La query no puede estar vacía."}]

    urls = await _get_urls_combined()
    urls = urls[: max(1, min(max_pages, len(urls)))]
    results = []

    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for u in urls:
            try:
                r = await client.get(u)
                if r.status_code != 200:
                    results.append({"url": u, "encontrado": False, "fragmento": f"HTTP {r.status_code}"})
                    continue
                text = _extract_visible_text(r.text)
                pos = text.lower().find(query_low)
                if pos >= 0:
                    start = max(0, pos - 120)
                    end = min(len(text), pos + 120)
                    snippet = text[start:end]
                    results.append({"url": u, "encontrado": True, "fragmento": snippet})
                else:
                    results.append({"url": u, "encontrado": False, "fragmento": ""})
            except Exception as e:
                results.append({"url": u, "encontrado": False, "fragmento": f"Error: {e}"})
    return results

# -----------------------------------------------------------------------------
# App HTTP streamable (requerido por ChatGPT Connectors)
# -----------------------------------------------------------------------------
app = Starlette(routes=[Mount("/", app=mcp.streamable_http_app())])
# Endpoint: https://TU-DOMINIO/mcp
