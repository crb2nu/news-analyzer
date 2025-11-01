#!/usr/bin/env bash
set -euo pipefail

# Build and optionally push News Analyzer component images to Harbor.
#
# Examples:
#   scripts/build-and-push.sh                     # build all components, load locally
#   TAG=nightly scripts/build-and-push.sh --push  # build all, push TAG and latest
#   scripts/build-and-push.sh -c scraper -t dev --push --no-latest

REGISTRY_DEFAULT="registry.harbor.lan/library/news-analyzer"
DEFAULT_COMPONENTS=(scraper extractor summarizer notifier)

REGISTRY_PREFIX=${REGISTRY:-$REGISTRY_DEFAULT}
TAG=${TAG:-$(git rev-parse --short HEAD 2>/dev/null || date +%Y%m%d%H%M%S)}
PLATFORM=${PLATFORM:-linux/amd64}
COMPONENTS=()
EXTRA_TAGS=()
PUSH=false
LOAD=true
LATEST=true
NO_CACHE=false

usage() {
  cat <<'EOF'
Usage: scripts/build-and-push.sh [options]

Options:
  -c, --component NAME   Component to build (scraper, extractor, summarizer, notifier).
                         May be specified multiple times. Default: all components.
  -t, --tag TAG          Primary tag to assign (default: current git short SHA or timestamp).
  -r, --registry PREFIX  Registry prefix (default: $REGISTRY_DEFAULT). Final image name is
                         PREFIX-COMPONENT:TAG.
      --extra-tag TAG    Additional tag(s) to apply (may repeat).
      --no-latest        Do not automatically tag/push "latest".
      --push             Push images to the registry (uses docker buildx --push).
      --load             Load image into local Docker daemon instead of pushing (default).
      --platform SPEC    Target platform(s) for buildx (default: linux/amd64).
      --no-cache         Disable build cache.
  -h, --help             Show this help message.

Environment overrides:
  REGISTRY, TAG, PLATFORM can be exported instead of passing flags.

Prerequisites:
  - Docker CLI with buildx plugin (Docker 20.10+)
  - Logged in to Harbor for --push (docker login registry.harbor.lan)
EOF
}

log() { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
err() { printf '\033[1;31mERR\033[0m %s\n' "$*" >&2; }

while [[ $# -gt 0 ]]; do
  case "$1" in
    -c|--component)
      COMPONENTS+=("$2"); shift 2;;
    -t|--tag)
      TAG="$2"; shift 2;;
    -r|--registry)
      REGISTRY_PREFIX="$2"; shift 2;;
    --extra-tag)
      EXTRA_TAGS+=("$2"); shift 2;;
    --no-latest)
      LATEST=false; shift;;
    --push)
      PUSH=true; LOAD=false; shift;;
    --load)
      LOAD=true; PUSH=false; shift;;
    --platform)
      PLATFORM="$2"; shift 2;;
    --no-cache)
      NO_CACHE=true; shift;;
    -h|--help)
      usage; exit 0;;
    *)
      err "Unknown option: $1"; usage; exit 1;;
  esac
done

if [[ ${#COMPONENTS[@]} -eq 0 ]]; then
  COMPONENTS=(${DEFAULT_COMPONENTS[@]})
fi

if ! command -v docker >/dev/null 2>&1; then
  err "docker CLI not found."; exit 1
fi

if ! docker buildx version >/dev/null 2>&1; then
  err "docker buildx is required (Docker 20.10+)."; exit 1
fi

if [[ "$PUSH" == true ]]; then
  if ! docker info >/dev/null 2>&1; then
    err "docker daemon unavailable."; exit 1
  fi
  if ! docker system info | grep -q "Username:"; then
    log "Harbor login status unknown; ensure 'docker login ${REGISTRY_PREFIX%/*}' succeeded."
  fi
fi

build_component() {
  local component="$1"
  local context dockerfile

  case "$component" in
    scraper)
      context="scraper"
      dockerfile="scraper/Dockerfile"
      ;;
    extractor)
      context="extractor"
      dockerfile="extractor/Dockerfile"
      ;;
    summarizer)
      context="summarizer"
      dockerfile="summarizer/Dockerfile"
      ;;
    notifier)
      context="."
      dockerfile="notifier/Dockerfile"
      ;;
    *)
      err "Unsupported component: $component"; exit 1;;
  esac

  if [[ ! -f "$dockerfile" ]]; then
    err "Missing $dockerfile"; exit 1
  fi

  local base_image="${REGISTRY_PREFIX}-${component}"
  local primary_tag="${base_image}:${TAG}"

  log "Building ${component} -> ${primary_tag}"

  local cmd=(docker buildx build "$context" -f "$dockerfile" --platform "$PLATFORM" --tag "$primary_tag")

  if [[ "$LATEST" == true ]]; then
    cmd+=(--tag "${base_image}:latest")
  fi

  if [[ ${#EXTRA_TAGS[@]} -gt 0 ]]; then
    for extra in "${EXTRA_TAGS[@]}"; do
      cmd+=(--tag "${base_image}:${extra}")
    done
  fi

  if [[ "$PUSH" == true ]]; then
    cmd+=(--push)
  elif [[ "$LOAD" == true ]]; then
    cmd+=(--load)
  fi

  if [[ "$NO_CACHE" == true ]]; then
    cmd+=(--no-cache)
  fi

  cmd+=("--build-arg" "BUILDKIT_INLINE_CACHE=1")

  "${cmd[@]}"
}

for component in "${COMPONENTS[@]}"; do
  build_component "$component"
done

log "Done."
