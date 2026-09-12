"""
CyberGenetic Gym — Credentials Service.

Gated, scoped, revocable credentials for athletes.
G11: Treasury credentials only issued to Arena-proven athletes (ARENA_READY+).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from core.models.credential import Credential, CredentialEvent, CredentialLevel, RiskLevel, LEVEL_MAP
from core.events import emit_audit

# ─── In-memory store ───────────────────────────────────────────────────────
_credentials: dict[str, Credential] = {}
_credential_events: list[CredentialEvent] = []
# Track credential level per athlete (fast lookup)
_athlete_levels: dict[str, int] = {}

app = FastAPI(title="Credentials Service", version="0.1.0")


# ─── G11: Treasury Credential Gating ──────────────────────────────────────

# Only athletes with ARENA_READY (4) or higher can get Treasury credentials
TREASURY_CREDENTIAL_MIN_LEVEL = 5  # SPECIALIZED
TREASURY_SCOPES = ["treasury:read", "treasury:trade", "treasury:simulation"]

# Cache of athlete arena credentials (populated by arena service)
_arena_verified: dict[str, bool] = {}


def _check_arena_prerequisite(athlete_id: str, level: CredentialLevel) -> bool:
    """
    G11 rule: Treasury credentials require Arena-proven athlete.
    
    Returns True if the athlete meets the prerequisite for the requested level.
    """
    level_num = LEVEL_MAP.get(level, 0)
    
    # Treasury credentials require ARENA_READY (4) or higher
    if level_num >= 4:
        current = _athlete_levels.get(athlete_id, 0)
        if current < TREASURY_CREDENTIAL_MIN_LEVEL:
            return False
    
    return True


def _verify_arena_proven(athlete_id: str) -> bool:
    """Check if athlete has proven themselves in Arena."""
    return _arena_verified.get(athlete_id, False)


def _mark_arena_proven(athlete_id: str):
    """Mark athlete as Arena-proven (called by Arena service on qualification)."""
    _arena_verified[athlete_id] = True


# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "credentials_issued": len(_credentials),
        "athletes_registered": len(_athlete_levels),
        "arena_proven": sum(1 for v in _arena_verified.values() if v),
    }


# ─── Issue Credential ─────────────────────────────────────────────────────

class IssueRequest(BaseModel):
    athlete_id: str
    level: CredentialLevel = CredentialLevel.REGISTERED
    scope: list[str] = []
    maximum_risk: RiskLevel = RiskLevel.NONE
    issued_by: str = "system"
    evidence_hash: str = ""


@app.post("/credentials", response_model=Credential, status_code=201)
async def issue_credential(req: IssueRequest):
    """Issue a credential. G11: Treasury creds require Arena-proven athlete."""
    level_num = LEVEL_MAP.get(req.level, 0)
    
    # G11 gate: Treasury-level credentials (SPECIALIZED+) require Arena proof
    if level_num >= 5 and not _verify_arena_proven(req.athlete_id):
        raise HTTPException(
            status_code=403,
            detail=f"G11 gate: Athlete {req.athlete_id} not Arena-proven. "
                   f"Treasury credentials (level {req.level.value}) require "
                   f"Arena qualification first.",
        )
    
    cred = Credential(
        athlete_id=req.athlete_id,
        level=req.level,
        scope=req.scope,
        maximum_risk=req.maximum_risk,
        issued_by=req.issued_by,
        evidence_hash=req.evidence_hash,
        expires_at=datetime.utcnow() + timedelta(days=30),
    )
    
    _credentials[cred.credential_id] = cred
    
    # Update athlete level cache
    current = _athlete_levels.get(req.athlete_id, -1)
    if level_num > current:
        _athlete_levels[req.athlete_id] = level_num
    
    # Audit
    event = CredentialEvent(
        actor=req.issued_by,
        subject=req.athlete_id,
        action="issued",
        result="success",
        credential_id=cred.credential_id,
    )
    _credential_events.append(event)
    emit_audit(
        actor=req.issued_by,
        subject=f"credential:{cred.credential_id}",
        action="credential.issued",
        result="success",
        details=f"Level: {req.level.value}, Athlete: {req.athlete_id}",
    )
    
    return cred


# ─── Get Credential ────────────────────────────────────────────────────────

@app.get("/credentials/{credential_id}", response_model=Credential)
async def get_credential(credential_id: str):
    cred = _credentials.get(credential_id)
    if not cred:
        raise HTTPException(404, f"Credential {credential_id} not found")
    return cred


@app.get("/athletes/{athlete_id}/credentials", response_model=list[Credential])
async def list_athlete_credentials(athlete_id: str):
    return [c for c in _credentials.values() if c.athlete_id == athlete_id]


# ─── Revoke Credential ────────────────────────────────────────────────────

class RevokeRequest(BaseModel):
    reason: str
    actor: str = "system"


@app.post("/credentials/{credential_id}/revoke", response_model=Credential)
async def revoke_credential(credential_id: str, req: RevokeRequest):
    cred = _credentials.get(credential_id)
    if not cred:
        raise HTTPException(404, f"Credential {credential_id} not found")
    if cred.revoked:
        raise HTTPException(400, "Credential already revoked")
    if not cred.revocable:
        raise HTTPException(400, "Credential is not revocable")
    
    cred.revoked = True
    cred.revoked_at = datetime.utcnow()
    cred.revocation_reason = req.reason
    
    # Update athlete level cache (recalculate highest active)
    athlete_creds = [c for c in _credentials.values() if c.athlete_id == cred.athlete_id and not c.revoked]
    _athlete_levels[cred.athlete_id] = max(
        (LEVEL_MAP.get(c.level, 0) for c in athlete_creds),
        default=0,
    )
    
    event = CredentialEvent(
        actor=req.actor,
        subject=cred.athlete_id,
        action="revoked",
        result="success",
        credential_id=credential_id,
    )
    _credential_events.append(event)
    emit_audit(
        actor=req.actor,
        subject=f"credential:{credential_id}",
        action="credential.revoked",
        result="success",
        details=f"Reason: {req.reason}",
    )
    
    return cred


# ─── Verify Credential ────────────────────────────────────────────────────

class VerifyRequest(BaseModel):
    required_level: str = "REGISTERED"
    required_scope: str = ""


@app.post("/credentials/{credential_id}/verify")
async def verify_credential(credential_id: str, req: VerifyRequest):
    cred = _credentials.get(credential_id)
    if not cred:
        return {"valid": False, "reason": "not_found"}
    if cred.revoked:
        return {"valid": False, "reason": "revoked"}
    if cred.expires_at and cred.expires_at < datetime.utcnow():
        return {"valid": False, "reason": "expired"}
    
    try:
        required_level = CredentialLevel(req.required_level)
    except ValueError:
        return {"valid": False, "reason": "invalid_level"}
    
    if LEVEL_MAP.get(cred.level, 0) < LEVEL_MAP.get(required_level, 0):
        return {"valid": False, "reason": "level_too_low"}
    
    if req.required_scope:
        allowed = False
        for s in cred.scope:
            if s.endswith("*"):
                if req.required_scope.startswith(s[:-1]):
                    allowed = True
                    break
            elif s == req.required_scope:
                allowed = True
                break
        if not allowed:
            return {"valid": False, "reason": "scope_mismatch"}
    
    return {
        "valid": True,
        "credential_id": credential_id,
        "level": cred.level.value,
        "reason": None,
    }


# ─── Athlete Level ────────────────────────────────────────────────────────

@app.get("/athletes/{athlete_id}/level")
async def get_athlete_level(athlete_id: str):
    level = _athlete_levels.get(athlete_id, 0)
    level_name = {v: k.value for k, v in LEVEL_MAP.items()}.get(level, "REGISTERED")
    return {
        "athlete_id": athlete_id,
        "level": level,
        "level_name": level_name,
    }


class CheckAuthRequest(BaseModel):
    required_level: int
    required_scope: str = ""


@app.post("/athletes/{athlete_id}/check-authorization")
async def check_authorization(athlete_id: str, req: CheckAuthRequest):
    current_level = _athlete_levels.get(athlete_id, 0)
    authorized = current_level >= req.required_level
    
    if not authorized:
        return {
            "authorized": False,
            "athlete_id": athlete_id,
            "required_level": req.required_level,
            "required_scope": req.required_scope,
            "current_level": current_level,
            "reason": "level_too_low",
        }
    
    # Check scope against any matching credential
    if req.required_scope:
        matching = [
            c for c in _credentials.values()
            if c.athlete_id == athlete_id and not c.revoked
        ]
        scope_match = False
        for c in matching:
            for s in c.scope:
                if s.endswith("*") and req.required_scope.startswith(s[:-1]):
                    scope_match = True
                    break
                elif s == req.required_scope:
                    scope_match = True
                    break
            if scope_match:
                break
        if not scope_match:
            return {
                "authorized": False,
                "athlete_id": athlete_id,
                "required_level": req.required_level,
                "required_scope": req.required_scope,
                "current_level": current_level,
                "reason": "scope_mismatch",
            }
    
    return {
        "authorized": True,
        "athlete_id": athlete_id,
        "required_level": req.required_level,
        "required_scope": req.required_scope,
        "current_level": current_level,
        "reason": None,
    }


# ─── G11: Arena-Treasury Bridge ───────────────────────────────────────────

class ArenaProofRequest(BaseModel):
    athlete_id: str
    proven: bool = True


@app.post("/athletes/{athlete_id}/arena-proof")
async def set_arena_proof(athlete_id: str, req: ArenaProofRequest):
    """Called by Arena service when athlete qualifies for Treasury access."""
    if req.proven:
        _mark_arena_proven(athlete_id)
        emit_audit(
            actor="arena",
            subject=f"athlete:{athlete_id}",
            action="arena_proven.set",
            result="success",
            details="Athlete qualified for Treasury access via Arena",
        )
    return {
        "athlete_id": athlete_id,
        "arena_proven": _arena_verified.get(athlete_id, False),
    }
