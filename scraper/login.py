from pathlib import Path
from playwright.sync_api import sync_playwright
from .config import Settings


def login(storage_path: Path = Path("storage_state.json")) -> None:
    settings = Settings()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        page.goto("https://swvatoday.com/eedition/smyth_county/")
        page.fill("input[name='email']", settings.eedition_user)
        page.fill("input[name='password']", settings.eedition_pass)
        page.click("button[type='submit']")
        page.wait_for_load_state("networkidle")
        context.storage_state(path=str(storage_path))
        browser.close()


if __name__ == "__main__":
    login()
