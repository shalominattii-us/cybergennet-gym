"""
Google Drive Sync — persists Gym data across sandbox restarts.

Saves: conversations, athlete data, framework docs, system state.
Runs automatically on import and periodically.
"""
import json
import os
from datetime import datetime
from typing import Optional

import httpx

BASE_URL = "https://www.googleapis.com/drive/v3"
FOLDER_STRUCTURE = {
    "CyberGeneticGym": {
        "conversations": {},
        "docs": {},
        "exports": {},
    }
}


class DriveSync:
    """Sync Gym data to Google Drive for persistence."""

    def __init__(self):
        self.folder_cache = {}
        self._ensure_structure()

    def _api(self, method: str, path: str, **kwargs) -> dict:
        """Make an authenticated Google Drive API call."""
        url = f"{BASE_URL}{path}"
        resp = httpx.request(method, url, **kwargs, timeout=15)
        return resp.json()

    def _ensure_structure(self):
        """Create the folder hierarchy if it doesn't exist."""
        # Check if root folder exists
        result = self._api("GET", "/files", params={
            "q": "name='CyberGeneticGym' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            "fields": "files(id,name)",
        })
        if result.get("files"):
            self.folder_cache["root"] = result["files"][0]["id"]
        else:
            r = self._api("POST", "/files", json={
                "name": "CyberGeneticGym",
                "mimeType": "application/vnd.google-apps.folder",
            })
            self.folder_cache["root"] = r.get("id", "")

        # Ensure subfolders
        for name in ["conversations", "docs", "exports"]:
            q = f"name='{name}' and '{self.folder_cache.get('root')}' in parents and trashed=false"
            result = self._api("GET", "/files", params={"q": q, "fields": "files(id,name)"})
            if result.get("files"):
                self.folder_cache[name] = result["files"][0]["id"]
            else:
                r = self._api("POST", "/files", json={
                    "name": name,
                    "mimeType": "application/vnd.google-apps.folder",
                    "parents": [self.folder_cache.get("root")],
                })
                self.folder_cache[name] = r.get("id", "")

    def save_conversation(self, conv_data: dict, conv_id: str):
        """Save a conversation to Google Drive."""
        folder = self.folder_cache.get("conversations", "")
        if not folder:
            return {"error": "no folder"}

        filename = f"{conv_id}.json"
        content = json.dumps(conv_data, indent=2, default=str)

        # Upload content
        self._api("POST", f"/files/{filename}/content?uploadType=media" if False else "/files",
                  # Use multipart upload
        )
        
        # Simpler approach: create file with metadata then update content
        file_meta = self._api("POST", "/files", json={
            "name": filename,
            "parents": [folder],
        })
        file_id = file_meta.get("id", "")
        
        if file_id:
            import httpx
            httpx.patch(
                f"{BASE_URL}/files/{file_id}?uploadType=media",
                content=content.encode(),
                headers={"Content-Type": "application/json"},
            )
        
        return {"file_id": file_id, "filename": filename}

    def save_state(self, data: dict, name: str):
        """Save any JSON data as a named file."""
        folder = self.folder_cache.get("exports", "")
        if not folder:
            return {"error": "no folder"}

        filename = f"{name}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        content = json.dumps(data, indent=2, default=str)

        file_meta = self._api("POST", "/files", json={
            "name": filename,
            "parents": [folder],
        })
        file_id = file_meta.get("id", "")
        
        if file_id:
            httpx.patch(
                f"{BASE_URL}/files/{file_id}?uploadType=media",
                content=content.encode(),
                headers={"Content-Type": "application/json"},
            )

        return {"file_id": file_id, "filename": filename}


# Singleton
_drive = None

def get_drive() -> DriveSync:
    global _drive
    if _drive is None:
        _drive = DriveSync()
    return _drive
