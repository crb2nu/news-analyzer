import base64
import os
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import requests

try:
    from .config import Settings
    from .database import DatabaseManager
except Exception:
    from config import Settings
    from database import DatabaseManager


AUTHORIZE_URL = "https://www.reddit.com/api/v1/authorize"
AUTHORIZE_COMPACT_URL = "https://www.reddit.com/api/v1/authorize.compact"
TOKEN_URL = "https://www.reddit.com/api/v1/access_token"


def build_auth_url(state: str, settings: Settings, compact: bool = False) -> str:
    assert settings.reddit_client_id and settings.reddit_redirect_uri, "Reddit client_id and redirect_uri required"
    params = {
        "client_id": settings.reddit_client_id,
        "response_type": "code",
        "state": state,
        "redirect_uri": settings.reddit_redirect_uri,
        "duration": "permanent",
        "scope": settings.reddit_scopes,
    }
    # manual encoding to keep spaces
    from urllib.parse import urlencode
    base = AUTHORIZE_COMPACT_URL if compact else AUTHORIZE_URL
    return f"{base}?{urlencode(params)}"


def _basic_auth_header(client_id: str, client_secret: str | None) -> str:
    token = f"{client_id}:{client_secret or ''}".encode()
    return "Basic " + base64.b64encode(token).decode()


def exchange_code_for_tokens(code: str, settings: Settings) -> Tuple[str, Optional[str], Optional[datetime]]:
    assert settings.reddit_client_id and settings.reddit_redirect_uri, "Missing Reddit OAuth config"
    headers = {
        "User-Agent": settings.reddit_user_agent,
        "Authorization": _basic_auth_header(settings.reddit_client_id, settings.reddit_client_secret),
    }
    data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": settings.reddit_redirect_uri,
    }
    resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    access = payload.get("access_token")
    refresh = payload.get("refresh_token")
    expires_at = None
    if payload.get("expires_in"):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(payload["expires_in"]))
    return access, refresh, expires_at


def refresh_access_token(refresh_token: str, settings: Settings) -> Tuple[str, Optional[datetime]]:
    assert settings.reddit_client_id, "Missing Reddit client_id"
    headers = {
        "User-Agent": settings.reddit_user_agent,
        "Authorization": _basic_auth_header(settings.reddit_client_id, settings.reddit_client_secret),
    }
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
    }
    resp = requests.post(TOKEN_URL, headers=headers, data=data, timeout=20)
    resp.raise_for_status()
    payload = resp.json()
    access = payload.get("access_token")
    expires_at = None
    if payload.get("expires_in"):
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=int(payload["expires_in"]))
    return access, expires_at


def new_state() -> str:
    return secrets.token_urlsafe(24)
