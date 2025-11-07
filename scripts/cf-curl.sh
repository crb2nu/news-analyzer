#!/usr/bin/env bash
set -euo pipefail

# Simple Cloudflare Access-aware curl wrapper.
# Pulls CF service token headers from env (exported in your shell, e.g., ~/.zshrc):
#   export CF_ACCESS_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxx.access
#   export CF_ACCESS_CLIENT_SECRET=yyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyyy
#
# Usage:
#   scripts/cf-curl.sh /health
#   scripts/cf-curl.sh -X POST -d '{"x":1}' /summarize
#   scripts/cf-curl.sh https://news.flexinfer.ai/oauth/reddit/start
#
# Env overrides:
#   CF_ACCESS_HOST   default: news.flexinfer.ai
#   CURL_BIN         default: curl

CURL_BIN=${CURL_BIN:-curl}
HOST_DEFAULT=${CF_ACCESS_HOST:-news.flexinfer.ai}

if [[ -z "${CF_ACCESS_CLIENT_ID:-}" || -z "${CF_ACCESS_CLIENT_SECRET:-}" ]]; then
  echo "CF_ACCESS_CLIENT_ID and CF_ACCESS_CLIENT_SECRET must be set in the environment." >&2
  echo "Tip: ensure your ~/.zshrc exports them, then 'source ~/.zshrc'" >&2
  exit 2
fi

args=()
path_or_url=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    http://*|https://*)
      path_or_url="$1"; shift ;;
    /*)
      path_or_url="https://${HOST_DEFAULT}$1"; shift ;;
    *)
      args+=("$1"); shift ;;
  esac
done

if [[ -z "$path_or_url" ]]; then
  echo "Usage: scripts/cf-curl.sh [curl-args] </path|full-url>" >&2
  exit 1
fi

# Always defined array; safe to expand even when empty
# Bash 3.2 + `set -u` chokes on expanding empty arrays; temporarily disable nounset.
set +u
exec "$CURL_BIN" -fsSL \
  -H "CF-Access-Client-Id: ${CF_ACCESS_CLIENT_ID}" \
  -H "CF-Access-Client-Secret: ${CF_ACCESS_CLIENT_SECRET}" \
  "${args[@]}" \
  "$path_or_url"
