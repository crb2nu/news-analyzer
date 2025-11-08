#!/usr/bin/env bash
set -euo pipefail

# Quick build and deploy script for summarizer with frontend
# Usage: ./BUILD_AND_DEPLOY.sh [--push] [--deploy]

PUSH=false
DEPLOY=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --push) PUSH=true; shift;;
    --deploy) DEPLOY=true; shift;;
    *) echo "Unknown option: $1"; exit 1;;
  esac
done

echo "==> Building summarizer with frontend..."

if [[ "$PUSH" == true ]]; then
  echo "==> Building and pushing to registry..."
  ./scripts/build-and-push.sh -c summarizer --push
else
  echo "==> Building locally (use --push to push to registry)..."
  ./scripts/build-and-push.sh -c summarizer --load
fi

if [[ "$DEPLOY" == true ]]; then
  echo "==> Deploying to Kubernetes..."
  kubectl -n news-analyzer rollout restart deployment/news-analyzer-summarizer
  echo "==> Waiting for rollout..."
  kubectl -n news-analyzer rollout status deployment/news-analyzer-summarizer
  echo "==> Done! Check logs:"
  echo "    kubectl -n news-analyzer logs -l component=summarizer --tail=50"
fi

echo "==> Complete!"
