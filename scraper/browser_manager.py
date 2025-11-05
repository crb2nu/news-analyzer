from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable

from playwright.sync_api import sync_playwright, Browser, BrowserContext

from .config import Settings
from .observability import TraceHelper

try:
    from filelock import FileLock
except Exception:  # pragma: no cover
    FileLock = None  # type: ignore


def storage_state_dir() -> Path:
    d = Path(os.getenv("STORAGE_STATE_DIR", "storage"))
    d.mkdir(parents=True, exist_ok=True)
    return d


def storage_state_path(settings: Settings) -> Path:
    # Bind the storage state to the proxy endpoint to keep sessions consistent per egress IP
    proxy = settings.get_playwright_proxy()
    server = proxy.get("server", "no-proxy").replace("://", "_").replace(":", "_")
    return storage_state_dir() / f"eedition_{server}.json"


def default_route_blocker(route, request) -> None:
    rtype = request.resource_type
    url = request.url
    if rtype in ("image", "media", "font"):
        return route.abort()
    if any(s in url for s in ("googletagmanager", "doubleclick", "adservice", "analytics", "facebook")):
        return route.abort()
    return route.continue_()


@dataclass
class BrowserManager:
    settings: Settings
    headless: bool = True
    browser_name: str = os.getenv("PW_BROWSER", "firefox")  # firefox/chromium/webkit
    _playwright = None
    _browser: Optional[Browser] = None
    _lock: threading.Lock = threading.Lock()

    def start(self) -> None:
        if self._browser is not None:
            return
        with self._lock:
            if self._browser is not None:
                return
            self._playwright = sync_playwright().start()
            proxy = self.settings.get_playwright_proxy()
            args = [
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-gpu",
                "--disable-software-rasterizer",
                "--single-process",
                "--no-zygote",
            ]
            if self.browser_name == "chromium":
                self._browser = self._playwright.chromium.launch(headless=self.headless, proxy=proxy, args=args)
            elif self.browser_name == "webkit":
                self._browser = self._playwright.webkit.launch(headless=self.headless, proxy=proxy, args=args)
            else:
                self._browser = self._playwright.firefox.launch(headless=self.headless, proxy=proxy, args=args)

    def close(self) -> None:
        with self._lock:
            try:
                if self._browser:
                    self._browser.close()
            finally:
                self._browser = None
                try:
                    if self._playwright:
                        self._playwright.stop()
                finally:
                    self._playwright = None

    def new_context(
        self,
        storage_path: Optional[Path] = None,
        route_blocker: Optional[Callable] = default_route_blocker,
        tracing_name: Optional[str] = None,
    ) -> BrowserContext:
        self.start()
        assert self._browser is not None
        storage = str(storage_path or storage_state_path(self.settings))
        ctx = self._browser.new_context(storage_state=storage)
        if route_blocker:
            try:
                ctx.route("**/*", route_blocker)
            except Exception:
                pass
        if tracing_name:
            TraceHelper(ctx).start()
        return ctx

    def save_storage_state(self, context: BrowserContext, storage_path: Optional[Path] = None) -> Path:
        path = storage_path or storage_state_path(self.settings)
        context.storage_state(path=str(path))
        return path

    def with_session(self, ensure_auth: Callable[[Path], bool], tracing_name: Optional[str] = None) -> BrowserContext:
        """Return a context with a valid session, logging in if necessary.

        The ensure_auth callback should verify storage_state validity and perform login if needed.
        A simple file lock is used to avoid concurrent re-logins when running parallel tasks.
        """
        spath = storage_state_path(self.settings)
        lock: Optional[FileLock] = None
        if FileLock is not None:
            lock = FileLock(str(spath) + ".lock")
        if lock is not None:
            lock.acquire(timeout=60)  # best-effort; raises on timeout
        try:
            # verify (and refresh if needed) before creating the context
            ensure_auth(spath)
            return self.new_context(storage_path=spath, tracing_name=tracing_name)
        finally:
            if lock is not None:
                try:
                    lock.release()
                except Exception:
                    pass

