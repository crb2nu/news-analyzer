import datetime as dt
import json
import pathlib
from typing import Any, Dict, Iterable, Optional

import requests

from .config import Settings


class FacebookAPIError(RuntimeError):
    pass


class FacebookClient:
    """
    Minimal Meta Graph API client focused on compliant ingestion of public data
    from Facebook Pages you manage (no scraping, no automated login).

    Usage requires a user access token with appropriate permissions and
    page access tokens are derived per page.
    """

    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or Settings()
        self.base_url = f"https://graph.facebook.com/{self.settings.facebook_graph_version}"
        self.user_token = self.settings.facebook_user_access_token or ""

    # ------------------------------- helpers ---------------------------------
    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}/{path.lstrip('/')}"
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code != 200:
            raise FacebookAPIError(f"GET {url} failed: {resp.status_code} {resp.text}")
        data = resp.json()
        if "error" in data:
            raise FacebookAPIError(str(data["error"]))
        return data

    def _paginate(self, first_page: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
        page = first_page
        while True:
            for item in page.get("data", []):
                yield item
            paging = page.get("paging", {})
            next_url = paging.get("next")
            if not next_url:
                break
            resp = requests.get(next_url, timeout=30)
            if resp.status_code != 200:
                break
            page = resp.json()

    # ------------------------------- tokens ----------------------------------
    def get_page_access_token(self, page_id: str) -> str:
        """
        For a page the user manages, exchange the user token for a page access token.
        Permissions needed: pages_manage_metadata.
        """
        if not self.user_token:
            raise FacebookAPIError("facebook_user_access_token is not set")
        data = self._get(page_id, params={"fields": "access_token", "access_token": self.user_token})
        token = data.get("access_token")
        if not token:
            raise FacebookAPIError("Could not obtain page access token. Ensure the user manages the page and permissions are granted.")
        return token

    # ------------------------------- fetchers --------------------------------
    def fetch_page_posts(self, page_id: str, since: Optional[dt.datetime] = None, limit: int = 100) -> Iterable[Dict[str, Any]]:
        token = self.get_page_access_token(page_id)
        params: Dict[str, Any] = {
            "access_token": token,
            "limit": limit,
            "fields": "id,message,permalink_url,created_time,story,attachments{media_type,url,unshimmed_url,title},shares,likes.summary(true),comments.summary(true)",
        }
        if since:
            # Graph API expects a unix timestamp for 'since'
            params["since"] = int(since.timestamp())
        first = self._get(f"{page_id}/posts", params=params)
        yield from self._paginate(first)

    def fetch_page_events(self, page_id: str, since: Optional[dt.datetime] = None, limit: int = 50) -> Iterable[Dict[str, Any]]:
        token = self.get_page_access_token(page_id)
        params: Dict[str, Any] = {
            "access_token": token,
            "limit": limit,
            "fields": "id,name,description,start_time,end_time,place,attending_count,maybe_count,interested_count,updated_time,is_online",
        }
        if since:
            params["since"] = int(since.timestamp())
        first = self._get(f"{page_id}/events", params=params)
        yield from self._paginate(first)

    # ------------------------------- persistence -----------------------------
    @staticmethod
    def write_jsonl(path: pathlib.Path, items: Iterable[Dict[str, Any]]) -> int:
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0
        with path.open("w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
                count += 1
        return count

