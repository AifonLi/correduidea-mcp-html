# Correduidea MCP (HTML estático) — Conector sencillo para ChatGPT

Este repositorio expone un **servidor MCP** (Model Context Protocol) listo para conectar ChatGPT con tu web **HTML estática** (sin WordPress).  
Incluye herramientas básicas para **leer páginas de tu dominio** y **buscar texto** en varias URLs.

## ✅ Qué puedes hacer desde ChatGPT
- **`ping()`**: comprobar que todo funciona.
- **`listar_urls()`**: ver qué páginas va a usar el conector.
- **`leer_url(url)`**: traer el HTML de una página de `correduidea.com`.
- **`buscar_texto(query, max_pages=10)`**: buscar palabras/frases en varias URLs y devolver fragmentos.

> **No necesitas programar.** Solo tendrás que **editar un archivo de texto** para añadir tus URLs si tu web no tiene `sitemap.xml` o quieres forzar páginas específicas.

---

## 1) Requisitos
- **Python 3.11+** instalado.
- Cuenta de ChatGPT con **Connectors (MCP)**.
- (Recomendado) Un hosting con **HTTPS** (Render, Railway, Fly.io, etc.).

---

## 2) Instalar en tu ordenador (paso a paso — fácil)
1. **Descarga o clona** este repositorio en una carpeta.
2. Abre una **Terminal** dentro de la carpeta y ejecuta:
   ```bash
   pip install -r requirements.txt
   uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
3. El servidor queda disponible en: `http://localhost:8000/mcp`

> Para pruebas desde ChatGPT es preferible un **URL HTTPS público**. Si no tienes, sigue el punto 3 (despliegue).

---

## 3) Despliegue rápido (Render, Railway…)
1. Sube esta carpeta a **GitHub** (o usa la opción “Deploy from repo/zip” de tu proveedor).
2. Crea un **Web Service** nuevo.
3. **Comando de inicio** (ya incluido en `Procfile`):
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```
4. Al publicar, tu endpoint será parecido a:
   ```
   https://tu-app.onrender.com/mcp
   ```

---

## 4) Conectar en ChatGPT
1. ChatGPT → **Settings → Connectors → New connector**
2. Nombre: **Correduidea MCP (HTML)**
3. URL del servidor MCP: `https://TU-DOMINIO/mcp`
4. Autenticación: **Sin autenticación** para pruebas (en producción añade API Key).  
5. Marca **“Confío en esta aplicación”** y guarda.

---

## 5) Añadir/gestionar URLs (sin tocar código)
- Fichero: **`config/allowlist_urls.txt`**  
- Añade **una URL por línea** (debe ser de `correduidea.com`).  
- El conector también intentará leer `https://www.correduidea.com/sitemap.xml` si existe.
- `listar_urls()` devuelve la **combinación** de `sitemap` + `allowlist`.

Ejemplo de `config/allowlist_urls.txt`:
```
https://www.correduidea.com/
https://www.correduidea.com/contacto.html
https://www.correduidea.com/servicios.html
```

> **Importante:** Solo se aceptan URLs dentro de `correduidea.com` por seguridad.

---

## 6) Herramientas disponibles

### `ping() -> str`
Devuelve `"pong"` (prueba de salud).

### `listar_urls() -> list[str]`
Devuelve las URLs que el conector usará (combinando `sitemap.xml` + `allowlist_urls.txt`).

### `leer_url(url: str) -> str`
Descarga el **HTML** de una URL de `correduidea.com` (recorta a 4000 caracteres).

### `buscar_texto(query: str, max_pages: int = 10) -> list[dict]`
1) Obtiene URLs desde `listar_urls()` (hasta `max_pages`).  
2) Descarga cada página, **extrae texto** y busca la `query`.  
3) Devuelve una lista con **{url, encontrado: bool, fragmento}** donde haya coincidencias.

---

## 7) Seguridad y límites
- **Dominio restringido**: solo `correduidea.com` (y subdominios) para evitar abusos.
- **Lectura**: este conector **no modifica** tu web (solo lee).
- **Producción**: si expones acciones sensibles (crear leads, enviar formularios), añade **API Key** u **OAuth** (te puedo preparar una versión segura).

---

## 8) Problemas típicos
- **No aparece como conector válido**: revisa que uses `/mcp` y que el servicio esté en línea.
- **No encuentra páginas**: añade tus URLs en `config/allowlist_urls.txt` y vuelve a probar `listar_urls()`.
- **Errores al leer**: comprueba que la URL existe y carga en navegador.

---

## 9) Estructura
```
correduidea-mcp-html/
├── app/
│   └── main.py
├── config/
│   └── allowlist_urls.txt
├── requirements.txt
├── Procfile
├── runtime.txt
└── README.md
```

Licencia: MIT
