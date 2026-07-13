"""Build a static HTML preview of the TPDL AI Team platform.

Renders the 3 pages (/, /intel, /marketing) to HTML with all data inlined
as a JSON blob + a small fetch() shim so the existing JS keeps working
without a backend.

Output: dist/  (ready to drag-drop onto Netlify Drop or any static host).
"""
import json
import shutil
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app


DIST = Path("dist")
ROOT = Path(__file__).parent


def main() -> None:
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir()

    # 1. Copy static assets verbatim (css, js, etc.)
    shutil.copytree(ROOT / "static", DIST / "static")

    # 2. Pre-fetch every GET API endpoint the JS would call.
    client = TestClient(app)
    endpoints = {
        "/api/agents": client.get("/api/agents").json(),
        "/api/intel/companies": client.get("/api/intel/companies").json(),
        "/api/intel/signals": client.get("/api/intel/signals").json(),
        "/api/intel/stats": client.get("/api/intel/stats").json(),
        "/api/marketing/linkedin/drafts": client.get("/api/marketing/linkedin/drafts").json(),
        "/api/marketing/linkedin/metrics": client.get("/api/marketing/linkedin/metrics").json(),
        "/api/marketing/case-studies": client.get("/api/marketing/case-studies").json(),
        "/api/marketing/website-pages": client.get("/api/marketing/website-pages").json(),
        "/api/marketing/outreach": client.get("/api/marketing/outreach").json(),
    }

    # 3. Build the fetch shim. Intercepts ANY /api/* call:
    #    - GET on known endpoint  → return inlined data
    #    - POST /api/chat/...     → return friendly "demo offline" error
    #    - anything else          → fall through to real fetch (CDN, dicebear)
    shim = (
        "<script>\n"
        "(function() {\n"
        f"  const STATIC_DATA = {json.dumps(endpoints, ensure_ascii=False)};\n"
        "  const ORIG_FETCH = window.fetch.bind(window);\n"
        "  window.fetch = async function(input, init) {\n"
        "    const url = (typeof input === 'string') ? input : input.url;\n"
        "    let path = url;\n"
        "    try {\n"
        "      if (url.startsWith('http')) {\n"
        "        const u = new URL(url);\n"
        "        path = u.pathname;\n"
        "      } else if (url.includes('?')) {\n"
        "        path = url.split('?')[0];\n"
        "      }\n"
        "    } catch (_) {}\n"
        "    if (STATIC_DATA[path] !== undefined) {\n"
        "      return new Response(JSON.stringify(STATIC_DATA[path]), {\n"
        "        status: 200, headers: { 'Content-Type': 'application/json' }\n"
        "      });\n"
        "    }\n"
        "    if (path.startsWith('/api/chat/')) {\n"
        "      return new Response(JSON.stringify({\n"
        "        detail: 'Demo estática — los chats están desactivados aquí. Para hablar con los agentes de verdad, hay que desplegar el backend con una API key de Anthropic.'\n"
        "      }), { status: 503, headers: { 'Content-Type': 'application/json' } });\n"
        "    }\n"
        "    if (path.startsWith('/api/marketing/linkedin/drafts/') && (path.endsWith('/approve') || path.endsWith('/reject'))) {\n"
        "      return new Response(JSON.stringify({ detail: 'Demo estática — acción simulada.' }), {\n"
        "        status: 200, headers: { 'Content-Type': 'application/json' }\n"
        "      });\n"
        "    }\n"
        "    return ORIG_FETCH(input, init);\n"
        "  };\n"
        "})();\n"
        "</script>\n"
    )

    # 4. A tiny notice banner so the visitor knows what they're looking at.
    banner = (
        "<div style=\"position:fixed;bottom:0;left:0;right:0;background:#0a0a0a;"
        "color:white;text-align:center;padding:10px;font-size:12px;z-index:9999;"
        "font-family:Inter,sans-serif;\">"
        "📌 Borrador estático del platform TPDL · AI Team — "
        "chats desactivados. "
        "<a href=\"#\" onclick=\"this.parentElement.style.display='none';return false;\" "
        "style=\"color:#34D591;margin-left:1rem;\">cerrar</a>"
        "</div>\n"
    )

    # 5. Render each page through the live FastAPI app and patch the HTML.
    pages = [
        ("/", DIST / "index.html"),
        ("/intel", DIST / "intel" / "index.html"),
        ("/marketing", DIST / "marketing" / "index.html"),
    ]
    for route, out_path in pages:
        res = client.get(route)
        if res.status_code != 200:
            raise RuntimeError(f"Got {res.status_code} on {route}")
        html = res.text
        # Inject the shim BEFORE the page's own scripts (which live in {% block content %}).
        # base.html closes </head> right after the Alpine + Tailwind CDN includes — perfect anchor.
        html = html.replace("</head>", shim + "</head>", 1)
        # Inject the bottom banner before </body>.
        html = html.replace("</body>", banner + "</body>", 1)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(html, encoding="utf-8")
        print(f"  built {out_path} ({len(html):,} bytes)")

    # 6. 404 page so any stray link (e.g. /agent/sarah) doesn't show the Netlify default.
    notfound = (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8'>"
        "<title>Demo · TPDL</title>"
        "<link rel='stylesheet' href='https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap'>"
        "<style>body{font-family:Inter,sans-serif;background:#fafaf8;color:#0a0a0a;"
        "min-height:100vh;display:flex;align-items:center;justify-content:center;text-align:center;}"
        "h1{font-size:2rem;font-weight:600;letter-spacing:-0.02em;}p{color:#5c5c5c;}"
        "a{color:#0a0a0a;border-bottom:2px solid #34D591;text-decoration:none;}</style>"
        "</head><body><div><h1>Página no disponible en la demo</h1>"
        "<p style='margin:1rem 0 2rem'>Esta sección requiere el backend funcionando.</p>"
        "<a href='/'>← Volver al landing</a></div></body></html>"
    )
    (DIST / "404.html").write_text(notfound, encoding="utf-8")

    print()
    print(f"✓ Built static site in: {DIST.resolve()}")
    print()
    print("To preview locally:")
    print(f"  cd {DIST}")
    print("  python3 -m http.server 8765")
    print("  open http://localhost:8765")
    print()
    print("To publish:")
    print("  1. Go to https://app.netlify.com/drop")
    print(f"  2. Drag the '{DIST}' folder onto the page")
    print("  3. Copy the URL it gives you and share")


if __name__ == "__main__":
    main()
