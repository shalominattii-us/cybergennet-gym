"""
CyberGenetic Gym — API Gateway.

Routes requests to all internal services.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
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


# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "environment": settings.environment,
        "version": "0.1.0",
    }


# ─── Mount sub-applications ────────────────────────────────────────────────

from apps.gym.service import app as gym_app
from apps.evaluator.service import app as evaluator_app
from apps.credentials.service import app as credentials_app
from apps.genetic.service import app as genetic_app
from apps.arena.service import app as arena_app
from apps.treasury.service import app as treasury_app
from apps.sovereign.service import app as sovereign_app

app.mount("/api/v1/gym", gym_app)
app.mount("/api/v1/evaluate", evaluator_app)
app.mount("/api/v1/credentials", credentials_app)
app.mount("/api/v1/genetic", genetic_app)
app.mount("/api/v1/arena", arena_app)
app.mount("/api/v1/treasury", treasury_app)
app.mount("/api/v1/sovereign", sovereign_app)


# ─── System status ─────────────────────────────────────────────────────────

@app.get("/api/v1/status")
async def status():
    return {
        "system": "CyberGenetic Gym",
        "version": "0.1.0",
        "environment": settings.environment,
        "gates": {
            "g0_g7_mvp": True,
            "g8_arena": True,
            "g9_sovereign_os": True,
            "g10_treasury_sim": True,
            "g11_treasury_credential": "pending_live",
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
