from pathlib import Path
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
from .config import Settings
import time
import logging
from typing import Optional

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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

                    # Some sites show a sign-in button to reveal the form
                    try:
                        signin = page.locator("text=/sign\s*in|log\s*in/i").first
                        if signin.count() > 0:
                            signin.click()
                            page.wait_for_load_state("networkidle", timeout=5000)
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
                        # Dump a snippet for debugging
                        try:
                            html_snippet = page.content()[:2000]
                            logger.debug(f"Login page snippet:\n{html_snippet}")
                        except Exception:
                            pass
                        raise PlaywrightTimeoutError("Password field not found")

                    logger.info("Filling login credentials")
                    email_field.fill(settings.eedition_user)
                    password_field.fill(settings.eedition_pass)

                    logger.info("Submitting login form")
                    # Click submit/login button
                    submit_btn = page.locator("button[type='submit'], button:has-text('Sign in'), button:has-text('Log in')").first
                    if submit_btn.count() > 0:
                        submit_btn.click()
                    else:
                        password_field.press('Enter')

                    try:
                        page.wait_for_load_state("networkidle", timeout=15000)
                        if "login" in page.url.lower() or page.locator("input[name='email']").is_visible():
                            logger.error("Login failed - still on login page")
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
