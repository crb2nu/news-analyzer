from pathlib import Path
import os
import re
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from .config import Settings
import time
import logging
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
    if debug_enabled:
        try:
            from .minio_utils import MinioHelper
            minio_helper = MinioHelper(settings)
        except Exception:
            minio_helper = None
    
    for attempt in range(max_retries):
        logger.info(f"Login attempt {attempt + 1}/{max_retries}")

        modes = [True, False] if use_proxy else [False]
        for mode in modes:
            proxy_config = Settings().get_playwright_proxy() if mode else None
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

                    logger.info("Navigating to e-edition login page")
                    page.goto("https://swvatoday.com/eedition/smyth_county/", timeout=30000)
                    page.wait_for_load_state("domcontentloaded", timeout=15000)
                    if minio_helper:
                        _debug_upload(page, minio_helper, prefix="debug/login/initial")
                    _dismiss_cookie_banner(page, minio_helper, label="initial")

                    # Some sites show a sign-in button to reveal the form
                    try:
                        signin = page.locator("text=/sign\s*in|log\s*in/i").first
                        if signin.count() > 0:
                            _dismiss_cookie_banner(page, minio_helper, label="pre_signin_button")

                            # Click Sign In; handle popup if it opens
                            try:
                                with page.expect_popup(timeout=5000) as pop:
                                    signin.click()
                                newp = pop.value
                                page = newp
                                page.wait_for_load_state("domcontentloaded", timeout=15000)
                            except Exception:
                                signin.click()
                            page.wait_for_load_state("networkidle", timeout=5000)
                            _dismiss_cookie_banner(page, minio_helper, label="post_signin_button")
                    except Exception:
                        pass

                    # Find email/user field
                    email_selectors = [
                        "input[name='email']",
                        "input[type='email']",
                        "input[id*='email' i]",
                        "input[name*='email' i]",
                        "input[id*='user' i]",
                        "input[name*='user' i]",
                    ]
                    email_field = None
                    for sel in email_selectors:
                        loc = page.locator(sel).first
                        if loc.count() > 0:
                            email_field = loc
                            break
                    if not email_field:
                        try:
                            email_field = page.get_by_label(re.compile("email", re.I))
                            if email_field.count() == 0:
                                email_field = page.get_by_placeholder(re.compile("email", re.I))
                        except Exception:
                            pass
                    if not email_field:
                        raise PlaywrightTimeoutError("Email field not found")

                    # Find password field
                    password_selectors = [
                        "input[name='password']",
                        "input[type='password']",
                        "input[id*='pass' i]",
                        "input[name*='pass' i]",
                    ]
                    password_field = None
                    for sel in password_selectors:
                        loc = page.locator(sel).first
                        if loc.count() > 0:
                            password_field = loc
                            break
                    if not password_field:
                        try:
                            password_field = page.get_by_label(re.compile("password", re.I))
                            if password_field.count() == 0:
                                password_field = page.get_by_placeholder(re.compile("password", re.I))
                        except Exception:
                            pass
                    if not password_field:
                        # Try within iframes
                        for frame in page.frames:
                            try:
                                f_email = frame.query_selector("input[type='email'], input[name*='email' i]")
                                f_pass = frame.query_selector("input[type='password'], input[name*='pass' i]")
                                if f_email and f_pass:
                                    f_email.fill(settings.eedition_user)
                                    f_pass.fill(settings.eedition_pass)
                                    password_field = f_pass
                                    break
                            except Exception:
                                continue
                        if not password_field:
                            if minio_helper:
                                _debug_upload(page, minio_helper, prefix="debug/login/no_password")
                            raise PlaywrightTimeoutError("Password field not found")

                    logger.info("Filling login credentials")
                    email_field.fill(settings.eedition_user)
                    password_field.fill(settings.eedition_pass)

                    logger.info("Submitting login form")
                    # Prefer Enter on password field to avoid clicking unrelated site buttons
                    try:
                        password_field.press('Enter')
                    except Exception:
                        # Fallback: submit button inside same form
                        submit_btn = password_field.locator("xpath=ancestor::form[1]//button[@type='submit' or contains(., 'Sign in') or contains(., 'Log in')]").first
                        if submit_btn.count() > 0:
                            submit_btn.click()
                        else:
                            page.keyboard.press('Enter')

                    try:
                        _dismiss_cookie_banner(page, minio_helper, label="post_credentials")
                        page.wait_for_load_state("networkidle", timeout=15000)
                        if "login" in page.url.lower() or page.locator("input[name='email']").is_visible():
                            logger.error("Login failed - still on login page")
                            if minio_helper:
                                _debug_upload(page, minio_helper, prefix="debug/login/post_submit")
                            browser.close()
                            continue

                        logger.info(f"Saving session state to {storage_path}")
                        context.storage_state(path=str(storage_path))
                        if storage_path.exists() and storage_path.stat().st_size > 0:
                            logger.info("Login successful and session state saved")
                            browser.close()
                            return True
                        else:
                            logger.error("Storage state file not created or empty")
                            browser.close()
                            continue
                    except PlaywrightTimeoutError:
                        logger.error("Timeout waiting for login to complete")
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
            page.goto("https://swvatoday.com/eedition/smyth_county/", timeout=30000)
            page.wait_for_load_state("networkidle", timeout=10000)
            
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
