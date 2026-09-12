"""
CyberGenetic Gym — API Gateway.

Routes requests to all internal services.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
import uvicorn

from core.config import settings

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="AI-agent training, qualification, and competitive environment",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Landing page ──────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return """<!DOCTYPE html>
<html>
<head><title>CyberGenetic Gym</title>
<style>
body { font-family: system-ui; max-width: 800px; margin: 40px auto; padding: 0 20px; line-height: 1.6; background: #0a0a1a; color: #e0e0ff; }
h1 { color: #00ff88; border-bottom: 2px solid #00ff88; padding-bottom: 10px; }
h2 { color: #00aaff; margin-top: 30px; }
code { background: #1a1a3a; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; }
pre { background: #1a1a3a; padding: 15px; border-radius: 8px; overflow-x: auto; font-size: 0.85em; }
a { color: #00aaff; }
.healthy { color: #00ff88; font-weight: bold; }
.gate { display: inline-block; padding: 4px 10px; border-radius: 12px; font-size: 0.8em; margin: 2px; }
.gate-pass { background: #003300; color: #00ff88; }
.gate-pending { background: #333300; color: #ffff00; }
.free { background: #003344; color: #00ddff; padding: 2px 8px; border-radius: 8px; font-size: 0.75em; }
</style></head>
<body>
<h1>🧬 CyberGenetic Gym</h1>
<p class="healthy">● System Healthy — Free Evaluation Engine Active</p>
<p>AI-agent training, qualification, and competitive environment.<br>
<span class="free">FREE</span> Built-in evaluator — no API keys needed.</p>

<h2>📋 Quick Start</h2>
<pre>
# Register athletes
curl -X POST https://01a08608-7967-7cea-a1b1-fc7f24c0234e.skydive.app/api/v1/gym/athletes \
  -H "Content-Type: application/json" \
  -d '{"name":"RECON-01","division":"CORE"}'

# Run drills
curl -X POST https://01a08608-7967-7cea-a1b1-fc7f24c0234e.skydive.app/api/v1/gym/drills \
  -H "Content-Type: application/json" \
  -d '{"name":"Precision Shot","capability":"PRECISION","difficulty":"BASIC"}'

# Import conversations from any AI app
curl -X POST https://01a08608-7967-7cea-a1b1-fc7f24c0234e.skydive.app/api/v1/imports/import \
  -H "Content-Type: application/json" \
  -d '{"source":"chatgpt","messages":[{"role":"user","content":"..."}]}'
</pre>

<h2>🗂️ Services</h2>
<pre>
GET  /health                          — System health
GET  /api/v1/status                   — Full status
POST /api/v1/gym/athletes             — Register athlete
POST /api/v1/gym/drills               — Create drill
POST /api/v1/gym/drills/{id}/run      — Execute drill
POST /api/v1/arena/events             — Create arena event
POST /api/v1/treasury/accounts        — Open treasury account
POST /api/v1/credentials/credentials  — Issue credential
POST /api/v1/imports/import           — Import AI conversation 🆕
POST /api/v1/imports/import/paste     — Paste conversation text 🆕
GET  /api/v1/imports/conversations    — List imported convos 🆕
</pre>

<h2>🔧 Build Gates</h2>
<p>
<span class="gate gate-pass">G0-G7 MVP</span>
<span class="gate gate-pass">G8 Arena</span>
<span class="gate gate-pass">G9 SovereignOS</span>
<span class="gate gate-pass">G10 Treasury</span>
<span class="gate gate-pass">G11 Treasury Cred</span>
<span class="gate gate-pending">G12 Live</span>
</p>
<p><a href="https://github.com/shalominattii-us/cybergennet-gym">GitHub →</a></p>
</body>
</html>
"""


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
        "version": "0.1.0",
        "evaluator": "free (no API keys required)",
    }


# ─── Mount sub-applications ────────────────────────────────────────────────

from apps.gym.service import app as gym_app
from apps.evaluator.service import app as evaluator_app
from apps.credentials.service import app as credentials_app
from apps.genetic.service import app as genetic_app
from apps.arena.service import app as arena_app
from apps.treasury.service import app as treasury_app
from apps.sovereign.service import app as sovereign_app
from apps.imports.service import app as imports_app
from apps.geoint.service import app as geoint_app

app.mount("/api/v1/gym", gym_app)
app.mount("/api/v1/evaluate", evaluator_app)
app.mount("/api/v1/credentials", credentials_app)
app.mount("/api/v1/genetic", genetic_app)
app.mount("/api/v1/arena", arena_app)
app.mount("/api/v1/treasury", treasury_app)
app.mount("/api/v1/sovereign", sovereign_app)
app.mount("/api/v1/imports", imports_app)
app.mount("/api/v1/geoint", geoint_app)


# ─── System status ─────────────────────────────────────────────────────────

@app.get("/api/v1/status")
async def status():
    return {
        "system": "CyberGenetic Gym",
        "version": "0.1.0",
        "environment": settings.environment,
        "evaluator": "free (built-in, no API keys)",
        "conversation_import": True,
        "gates": {
            "g0_g7_mvp": True,
            "g8_arena": True,
            "g9_sovereign_os": True,
            "g10_treasury_sim": True,
            "g11_treasury_credential": True,
            "g12_live_integrations": "pending_governance",
        },
        "services": {
            "gym": "mounted",
            "evaluator": "mounted",
            "credentials": "mounted",
            "genetic": "mounted",
            "arena": "mounted",
            "treasury": "mounted",
            "sovereign": "mounted",
            "imports": "mounted 🆕",
            "geoint": "mounted 🆕",
        },
        "constitutional_separation": True,
        "default_deny_network": settings.default_deny_network,
    }


def main():
    uvicorn.run(
        "apps.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.environment == "development",
        log_level="info",
    )


if __name__ == "__main__":
    main()
