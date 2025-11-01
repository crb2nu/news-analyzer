from pathlib import Path
import os
import json
from datetime import datetime, timedelta
from urllib.parse import quote_plus
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from .config import Settings
import time
import logging
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

E_EDITION_URL = "https://swvatoday.com/eedition/smyth_county/"
LOGIN_URL = f"https://swvatoday.com/users/login/?referer_url={quote_plus(E_EDITION_URL)}"
LOCKOUT_LOCAL_FILENAME = ".login_lockout.json"


class LockoutGuard:
    def __init__(
        self,
        helper,
        storage_path: Path,
        cooldown_minutes: int,
        lock_key: str,
    ) -> None:
        self.helper = helper
        self.storage_path = storage_path
        self.cooldown_minutes = max(int(cooldown_minutes or 0), 0)
        self.lock_key = lock_key
        local_dir = storage_path.parent if storage_path else Path(".")
        self.local_path = local_dir / LOCKOUT_LOCAL_FILENAME

    def is_active(self) -> bool:
        if self.cooldown_minutes <= 0:
            return False
        info = self._load_marker()
        if not info:
            return False
        until_ts = info.get("active_until_ts")
        reason = info.get("reason", "unknown")
        if until_ts is None:
            self.clear()
            return False
        now_ts = datetime.utcnow().timestamp()
        if now_ts < float(until_ts):
            until_str = info.get("active_until", "unknown time")
            logger.warning(
                "Skipping login: lockout active until %s UTC (reason: %s)",
                until_str,
                reason,
            )
            return True
        self.clear()
        return False

    def activate(self, reason: str) -> None:
        if self.cooldown_minutes <= 0:
            return
        now = datetime.utcnow()
        until = now + timedelta(minutes=self.cooldown_minutes)
        payload = {
            "timestamp": now.isoformat(timespec="seconds") + "Z",
            "reason": reason,
            "active_until": until.isoformat(timespec="seconds") + "Z",
            "active_until_ts": until.timestamp(),
        }
        data = json.dumps(payload)
        if self.helper:
            try:
                self.helper.put_text(self.lock_key, data, encoding="utf-8")
            except Exception:
                logger.debug("Failed to persist lockout marker to MinIO", exc_info=True)
        try:
            self.local_path.write_text(data, encoding="utf-8")
        except Exception:
            logger.debug("Failed to persist lockout marker locally", exc_info=True)
        logger.warning(
            "Login attempts suspended for %d minutes (reason: %s)",
            self.cooldown_minutes,
            reason,
        )

    def clear(self) -> None:
        if self.helper:
            try:
                self.helper.delete_object(self.lock_key)
            except Exception:
                logger.debug("Failed to delete remote lockout marker", exc_info=True)
        try:
            if self.local_path.exists():
                self.local_path.unlink()
        except Exception:
            logger.debug("Failed to delete local lockout marker", exc_info=True)

    def _load_marker(self) -> Optional[dict]:
        text = None
        if self.helper:
            try:
                text = self.helper.get_text(self.lock_key)
            except Exception:
                logger.debug("Unable to read remote lockout marker", exc_info=True)
        if not text and self.local_path.exists():
            try:
                text = self.local_path.read_text(encoding="utf-8")
            except Exception:
                logger.debug("Unable to read local lockout marker", exc_info=True)
                text = None
        if not text:
            return None
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None


def _dismiss_cookie_banner(page, helper, label: str) -> bool:
    selectors = [
        "button.osano-cm-accept",
        "button.osano-cm-accept-all",
        "button.osano-cm-accept-all2",
        "button:has-text('Accept')",
        "button:has-text('Accept All')",
        "button:has-text('I Agree')",
        "button:has-text('Continue')",
    ]
    start = time.time()
    dismissed = False
    while time.time() - start < 6:
        clicked = False
        for sel in selectors:
            try:
                loc = page.locator(sel).first
                if loc.count() > 0 and loc.is_visible():
                    loc.click(timeout=2000)
                    page.wait_for_timeout(500)
                    dismissed = True
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            for frame in page.frames:
                for sel in selectors:
                    try:
                        loc = frame.locator(sel).first
                        if loc.count() > 0 and loc.is_visible():
                            loc.click(timeout=2000)
                            page.wait_for_timeout(500)
                            dismissed = True
                            clicked = True
                            break
                    except Exception:
                        continue
                if clicked:
                    break
        if not clicked:
            break
        if dismissed:
            break
    if not dismissed and helper:
        _debug_upload(page, helper, prefix=f"debug/login/cookie_block_{label}")
    return dismissed


def _debug_upload(page, helper, prefix: str = "debug/login"):
    try:
        ts = helper.ts()
        html = page.content()
        helper.put_text(f"{prefix}/{ts}.html", html)
        img = page.screenshot(full_page=True)
        helper.put_bytes(f"{prefix}/{ts}.png", img, content_type="image/png")
    except Exception:
        # best-effort only
        pass

def login(
    storage_path: Path = Path("storage_state.json"),
    max_retries: int = 3,
    use_proxy: bool = True,
) -> bool:
    """
    Login to swvatoday.com e-edition and save session state.
    
    Args:
        storage_path: Path to save the session state JSON file
        max_retries: Maximum number of retry attempts
        use_proxy: Whether to use SmartProxy for the login
        
    Returns:
        bool: True if login successful, False otherwise
    """
    settings = Settings()
    debug_enabled = str(os.getenv("SCRAPER_DEBUG", "0")).lower() in ("1", "true", "yes")
    minio_helper = None
    cooldown_minutes = getattr(settings, "lockout_cooldown_minutes", 0)
    lock_key = getattr(settings, "lockout_marker_key", "locks/login-lockout.json")

    if debug_enabled or cooldown_minutes > 0:
        try:
            from .minio_utils import MinioHelper
            minio_helper = MinioHelper(settings)
        except Exception:
            minio_helper = None

    debug_helper = minio_helper if debug_enabled else None
    lockout_guard = LockoutGuard(
        helper=minio_helper,
        storage_path=storage_path,
        cooldown_minutes=cooldown_minutes,
        lock_key=lock_key,
    )

    if lockout_guard.is_active():
        return False

    for attempt in range(max_retries):
        logger.info(f"Login attempt {attempt + 1}/{max_retries}")

        modes = [True, False] if use_proxy else [False]
        for mode in modes:
            proxy_config = settings.get_playwright_proxy() if mode else None
            if proxy_config:
                logger.info(f"Using proxy: {proxy_config['server']}")
            else:
                logger.info("Using direct connection (no proxy)")

            try:
                with sync_playwright() as p:
                    # Prefer Firefox in containers; chromium can crash in some K8s setups
                    browser = p.firefox.launch(
                        headless=True,
                        proxy=proxy_config,
                        args=[
                            "--no-sandbox",
                            "--disable-setuid-sandbox",
                            "--disable-dev-shm-usage",
                            "--disable-gpu",
                            "--disable-software-rasterizer",
                            "--single-process",
                            "--no-zygote",
                        ],
                    )

                    context = browser.new_context()
                    page = context.new_page()

                    logger.info("Navigating to account login page")
                    try:
                        response = page.goto(LOGIN_URL, timeout=45000, wait_until="domcontentloaded")
                        if response and response.status == 429:
                            logger.error("Login page responded with HTTP 429 (Too Many Requests)")
                            lockout_guard.activate("http 429 from login page")
                            browser.close()
                            return False
                        page.wait_for_load_state("domcontentloaded", timeout=20000)
                    except PlaywrightTimeoutError as exc:
                        logger.error("Failed to load login page: %s", exc)
                        if debug_helper:
                            _debug_upload(page, debug_helper, prefix="debug/login/login_page_timeout")
                        browser.close()
                        continue

                    if debug_helper:
                        _debug_upload(page, debug_helper, prefix="debug/login/initial")
                    _dismiss_cookie_banner(page, debug_helper, label="initial")

                    email_field = page.locator("#user-username").first
                    if email_field.count() == 0:
                        email_field = page.locator("form.user-login-form input[name='username']").first
                    if email_field.count() == 0:
                        if debug_helper:
                            _debug_upload(page, debug_helper, prefix="debug/login/no_username")
                        raise PlaywrightTimeoutError("Username field not found")

                    password_field = page.locator("#user-password").first
                    if password_field.count() == 0:
                        password_field = page.locator("form.user-login-form input[name='password']").first
                    if password_field.count() == 0:
                        if debug_helper:
                            _debug_upload(page, debug_helper, prefix="debug/login/no_password")
                        raise PlaywrightTimeoutError("Password field not found")

                    logger.info("Filling login credentials")
                    email_field.fill(settings.eedition_user)
                    password_field.fill(settings.eedition_pass)

                    logger.info("Submitting login form")
                    submit_btn = page.locator("form.user-login-form button.btn-primary").first
                    if submit_btn.count() > 0:
                        submit_btn.click()
                    else:
                        password_field.press('Enter')

                    try:
                        _dismiss_cookie_banner(page, debug_helper, label="post_credentials")
                        page.wait_for_load_state("networkidle", timeout=20000)
                    except PlaywrightTimeoutError:
                        logger.warning("Timeout waiting for post-login network idle; continuing")

                    error_banner = page.locator(".alert-danger").first
                    if error_banner.count() > 0 and error_banner.is_visible():
                        try:
                            error_text = error_banner.inner_text().strip()
                        except Exception:
                            error_text = "Unknown error"
                        logger.error("Login error banner: %s", error_text)
                        if debug_helper:
                            _debug_upload(page, debug_helper, prefix="debug/login/error_banner")
                        if "too many login attempts" in error_text.lower():
                            lockout_guard.activate("site lockout message")
                            browser.close()
                            return False
                        browser.close()
                        continue

                    if "users/login" in page.url.lower():
                        logger.error("Login failed - still on login page")
                        if debug_helper:
                            _debug_upload(page, debug_helper, prefix="debug/login/post_submit")
                        browser.close()
                        continue

                    if not page.url.startswith(E_EDITION_URL):
                        try:
                            page.goto(E_EDITION_URL, timeout=45000)
                            page.wait_for_load_state("domcontentloaded", timeout=20000)
                        except PlaywrightTimeoutError:
                            logger.error("Unable to load e-edition after login")
                            if debug_helper:
                                _debug_upload(page, debug_helper, prefix="debug/login/eedition_failed")
                            browser.close()
                            continue

                    _dismiss_cookie_banner(page, debug_helper, label="post_login_edition")

                    logger.info(f"Saving session state to {storage_path}")
                    context.storage_state(path=str(storage_path))
                    if storage_path.exists() and storage_path.stat().st_size > 0:
                        logger.info("Login successful and session state saved")
                        lockout_guard.clear()
                        browser.close()
                        return True
                    else:
                        logger.error("Storage state file not created or empty")
                        browser.close()
                        continue

            except Exception as e:
                logger.error(f"Login attempt mode ({'proxy' if mode else 'direct'}) failed: {str(e)}")
                continue

        if attempt < max_retries - 1:
            wait_time = (attempt + 1) * 2
            logger.info(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
        else:
            break
    
    logger.error(f"All {max_retries} login attempts failed")
    return False


def verify_session(storage_path: Path = Path("storage_state.json")) -> bool:
    """
    Verify that the saved session is still valid.
    
    Args:
        storage_path: Path to the session state JSON file
        
    Returns:
        bool: True if session is valid, False otherwise
    """
    if not storage_path.exists():
        logger.warning("No session state file found")
        return False
    
    settings = Settings()
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(storage_state=str(storage_path))
            page = context.new_page()
            
            # Try to access a protected page
            page.goto("https://swvatoday.com/eedition/smyth_county/", timeout=60000)
            page.wait_for_load_state("networkidle", timeout=30000)
            
            # Check if we're redirected to login (session expired)
            if "login" in page.url.lower() or page.locator("input[name='email']").is_visible():
                logger.info("Session expired - login required")
                browser.close()
                return False
            
            logger.info("Session is still valid")
            browser.close()
            return True
            
    except Exception as e:
        logger.error(f"Session verification failed: {str(e)}")
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Login to swvatoday.com e-edition")
    parser.add_argument("--no-proxy", action="store_true", help="Disable proxy usage")
    parser.add_argument("--verify", action="store_true", help="Verify existing session")
    parser.add_argument("--storage", type=str, default="storage_state.json", help="Storage state file path")
    
    args = parser.parse_args()
    
    storage_path = Path(args.storage)
    
    if args.verify:
        if verify_session(storage_path):
            print("Session is valid")
            exit(0)
        else:
            print("Session is invalid or expired")
            exit(1)
    else:
        success = login(storage_path, use_proxy=not args.no_proxy)
        if success:
            print("Login successful")
            exit(0)
        else:
            print("Login failed")
            exit(1)
