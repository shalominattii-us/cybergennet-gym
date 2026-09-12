"""
Universal Conversation Import Service.

Accepts conversations from any AI app (ChatGPT, Kimi, Gemini, DeepSeek,
Venice, Antigravity, Manus, Delos, etc.) and stores them for reference.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field

from core.events import emit_audit

app = FastAPI(title="Conversation Import Service", version="0.1.0")

# ─── In-memory store ───────────────────────────────────────────────────────
_conversations: dict[str, dict] = {}
_tags: dict[str, list[str]] = {}  # tag -> list of conversation IDs


class Message(BaseModel):
    role: str  # user, assistant, system, tool
    content: str
    timestamp: Optional[str] = None


class ConversationImport(BaseModel):
    source: str  # chatgpt, kimi, gemini, deepseek, venice, antigravity, manus, delos, etc.
    title: str = "Untitled"
    messages: list[Message]
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)


# ─── Health ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "conversation-import",
        "conversations_stored": len(_conversations),
        "sources": list(set(c.get("source", "unknown") for c in _conversations.values())),
    }


# ─── Import conversation ───────────────────────────────────────────────────

@app.post("/import", status_code=201)
async def import_conversation(conv: ConversationImport):
    """Import a conversation from any AI app."""
    conv_id = f"conv-{uuid.uuid4().hex[:12]}"
    
    entry = {
        "id": conv_id,
        "source": conv.source,
        "title": conv.title,
        "messages": [m.model_dump() for m in conv.messages],
        "tags": conv.tags,
        "metadata": conv.metadata,
        "message_count": len(conv.messages),
        "imported_at": datetime.utcnow().isoformat(),
    }
    
    _conversations[conv_id] = entry
    
    for tag in conv.tags:
        if tag not in _tags:
            _tags[tag] = []
        _tags[tag].append(conv_id)
    
    emit_audit(
        actor="system",
        subject=f"conversation:{conv_id}",
        action="conversation.imported",
        result="success",
        details=f"Source: {conv.source}, Messages: {len(conv.messages)}, Tags: {conv.tags}",
    )
    
    return {"id": conv_id, "message_count": len(conv.messages), "source": conv.source}


# ─── Import from text paste ────────────────────────────────────────────────

@app.post("/import/paste", status_code=201)
async def import_from_paste(
    source: str = Form(...),
    title: str = Form("Untitled"),
    content: str = Form(...),
    tags: str = Form(""),
):
    """Import a conversation by pasting the text content directly."""
    lines = content.strip().split("\n")
    messages = []
    current_role = "user"
    current_content = []
    
    for line in lines:
        line_lower = line.strip().lower()
        if line_lower.startswith("user:") or line_lower.startswith("me:"):
            if current_content:
                messages.append(Message(role=current_role, content="\n".join(current_content).strip()))
            current_role = "user"
            current_content = [line.split(":", 1)[1].strip() if ":" in line else ""]
        elif line_lower.startswith("assistant:") or line_lower.startswith("ai:") or line_lower.startswith("chatgpt:"):
            if current_content:
                messages.append(Message(role=current_role, content="\n".join(current_content).strip()))
            current_role = "assistant"
            current_content = [line.split(":", 1)[1].strip() if ":" in line else ""]
        elif line_lower.startswith("system:"):
            if current_content:
                messages.append(Message(role=current_role, content="\n".join(current_content).strip()))
            current_role = "system"
            current_content = [line.split(":", 1)[1].strip() if ":" in line else ""]
        else:
            current_content.append(line)
    
    if current_content:
        messages.append(Message(role=current_role, content="\n".join(current_content).strip()))
    
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    conv = ConversationImport(
        source=source,
        title=title,
        messages=messages,
        tags=tag_list,
        metadata={"import_method": "paste"},
    )
    
    return await import_conversation(conv)


# ─── Import from file ──────────────────────────────────────────────────────

@app.post("/import/file", status_code=201)
async def import_from_file(
    file: UploadFile = File(...),
    source: str = Form("unknown"),
    title: str = Form("Untitled"),
    tags: str = Form(""),
):
    """Import a conversation from an uploaded file (JSON, TXT, MD)."""
    content = await file.read()
    text = content.decode("utf-8", errors="replace")
    
    # Try JSON first
    try:
        data = json.loads(text)
        if isinstance(data, dict) and "messages" in data:
            messages = [Message(**m) if isinstance(m, dict) else Message(role="user", content=str(m)) for m in data["messages"]]
            conv = ConversationImport(
                source=data.get("source", source),
                title=data.get("title", title),
                messages=messages,
                tags=[t.strip() for t in tags.split(",") if t.strip()],
            )
            return await import_conversation(conv)
    except json.JSONDecodeError:
        pass
    
    # Fall back to paste import
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    return await import_from_paste(
        source=source, title=title, content=text, tags=tags,
    )


# ─── Query conversations ───────────────────────────────────────────────────

@app.get("/conversations")
async def list_conversations(
    source: Optional[str] = None,
    tag: Optional[str] = None,
    limit: int = 50,
):
    """List imported conversations, optionally filtered."""
    convs = list(_conversations.values())
    
    if source:
        convs = [c for c in convs if c["source"] == source]
    if tag:
        conv_ids = _tags.get(tag, [])
        convs = [c for c in convs if c["id"] in conv_ids]
    
    convs.sort(key=lambda c: c["imported_at"], reverse=True)
    
    return [
        {
            "id": c["id"],
            "source": c["source"],
            "title": c["title"],
            "message_count": c["message_count"],
            "tags": c["tags"],
            "imported_at": c["imported_at"],
        }
        for c in convs[:limit]
    ]


@app.get("/conversations/{conv_id}")
async def get_conversation(conv_id: str):
    """Get a full conversation by ID."""
    conv = _conversations.get(conv_id)
    if not conv:
        raise HTTPException(404, f"Conversation {conv_id} not found")
    return conv


@app.get("/conversations/{conv_id}/messages")
async def get_conversation_messages(conv_id: str):
    """Get just the messages from a conversation."""
    conv = _conversations.get(conv_id)
    if not conv:
        raise HTTPException(404, f"Conversation {conv_id} not found")
    return conv["messages"]


@app.get("/tags")
async def list_tags():
    """List all tags and their conversation counts."""
    return {tag: len(ids) for tag, ids in _tags.items()}


@app.delete("/conversations/{conv_id}")
async def delete_conversation(conv_id: str):
    """Delete an imported conversation."""
    conv = _conversations.pop(conv_id, None)
    if not conv:
        raise HTTPException(404, f"Conversation {conv_id} not found")
    for tag, ids in _tags.items():
        if conv_id in ids:
            ids.remove(conv_id)
    return {"deleted": conv_id}
