# News Analyzer

This project is a proof‑of‑concept scraper and summarizer for the
Southwest Virginia Today e‑edition. It uses Playwright to log in,
fetch pages, and will eventually extract articles for AI summarization.

## Setup

1. Install dependencies using [Poetry](https://python-poetry.org/):

   ```bash
   poetry install --no-root
   ```

2. Copy `.env.example` to `.env` and fill in your subscriber
   credentials for the e‑edition:

   ```bash
   cp .env.example .env
   ```

## Login Script

A simple script is provided to generate an authenticated storage state
for later scraper runs:

```bash
poetry run python -m scraper.login
```

This will save `storage_state.json` in the project root.
