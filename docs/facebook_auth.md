Facebook Ingestion (Compliant) — Auth Setup
==========================================

Goal
----
Ingest posts and events from Facebook Pages you manage using Meta’s Graph API. This avoids scraping and respects Facebook’s Terms of Service.

What You Can Pull
-----------------
- Posts from Pages you manage
- Events from Pages you manage

Reading public content from Pages you do not manage requires Page Public Content Access and App Review by Meta. This project does not do that.

High‑Level Steps
----------------
1) Create a Meta app
   - Go to developers.facebook.com → My Apps → Create App (type: Consumer).
   - Add the “Facebook Login” product (for generating a user token) and ensure the app is in Development mode.

2) Grant permissions to your app
   - Under App → App Review → Permissions and Features, request (for Development use only):
     - `pages_manage_metadata` (to exchange for Page tokens)
     - `pages_read_engagement` (to read posts and basic engagement)
     - Optional: `pages_read_user_content` (to read UGC on your Pages)
   - In Development mode, you can test with your own account as a Developer without full App Review.

3) Generate a long‑lived User Access Token
   - Use the Graph API Explorer (Tools → Graph API Explorer) with your app selected.
   - Add the permissions above, click “Generate Access Token”, and authorize.
   - Exchange for a long‑lived token (60‑day) via the Access Token Debugger → “Extend Access Token”.

4) Ensure you manage the target Pages
   - Your Facebook account must be an Admin/Editor of each Page you intend to ingest.
   - The code will derive a Page Access Token per Page at runtime.

5) Configure environment
   - Add the following to your `.env` (or Kubernetes Secret):
     - `FACEBOOK_APP_ID=...`
     - `FACEBOOK_APP_SECRET=...`
     - `FACEBOOK_USER_ACCESS_TOKEN=LONG_LIVED_USER_TOKEN`
     - `FACEBOOK_PAGE_IDS=1234567890,0987654321`  (numeric IDs of Pages you manage)

6) Test locally
   - `poetry run python -m scraper.fb_ingest --since 2025-10-01`
   - Output JSONL files appear under `cache/facebook/YYYY-MM-DD/raw/`.

Notes
-----
- Do not share your tokens or secrets. Store them in Secrets (Kubernetes/GitHub Actions/Doppler).
- This module does not automate a browser login or scrape Facebook webpages.
- If you later need public Page content at scale, you must pass Meta’s App Review for Page Public Content Access; scopes and data retention policies apply.

