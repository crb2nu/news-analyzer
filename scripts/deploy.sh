#!/usr/bin/env bash
set -euo pipefail

# News Analyzer — end-to-end cluster bootstrap
# - Creates namespace and Harbor imagePullSecret
# - Applies base infra (secrets, configmap, Postgres, MinIO, ntfy)
# - Applies application workloads (scraper, extractor, summarizer, notifier)
# - Applies in-cluster ops and Kaniko builders
# - Optionally builds component images and triggers a first run

# Defaults (override via env or flags)
NAMESPACE=${NAMESPACE:-news-analyzer}
HARBOR_SECRET_NAME=${HARBOR_SECRET_NAME:-harbor-regcred}
HARBOR_SRC_NS=${HARBOR_SRC_NS:-home}
HARBOR_SRC_SECRET=${HARBOR_SRC_SECRET:-harbor-creds}
REGISTRY_PREFIX=${REGISTRY_PREFIX:-registry.harbor.lan/library/news-analyzer}
GIT_URL=${GIT_URL:-}
GIT_REF=${GIT_REF:-main}
BUILD=${BUILD:-all} # all|none|comma-separated list (scraper,extractor,notifier,summarizer)
TRIGGER_PIPELINE=${TRIGGER_PIPELINE:-true}

usage() {
  cat <<EOF
Usage: $(basename "$0") [options]

Options:
  --namespace NAME            Target namespace (default: ${NAMESPACE})
  --harbor-src-ns NS          Source namespace of existing Harbor secret (default: ${HARBOR_SRC_NS})
  --harbor-src-secret NAME    Source secret name to copy (default: ${HARBOR_SRC_SECRET})
  --harbor-user USER          Create pull secret using credentials (alternative to copy)
  --harbor-pass PASS          Harbor password
  --harbor-server HOST        Harbor registry, default registry.harbor.lan
  --harbor-email EMAIL        Email for docker-registry secret (default: devnull@example.com)
  --git-url URL               Repo URL for Kaniko builder (defaults to current repo remote if detected)
  --git-ref REF               Git ref/branch for builder (default: ${GIT_REF})
  --build {all|none|list}     Build images in-cluster (default: ${BUILD})
  --no-trigger                Do not trigger first scrape/extract/summarize/notify
  -h, --help                  Show this help
EOF
}

log() { printf "\033[1;34m==>\033[0m %s\n" "$*"; }
warn() { printf "\033[1;33mWARN\033[0m %s\n" "$*"; }

warn_unready_nodes() {
  local unready
  unready=$(kubectl get nodes --no-headers 2>/dev/null | awk '$2 != "Ready" {print $1 " (" $2 ")"}')
  if [[ -n "$unready" ]]; then
    warn "Cluster has NotReady nodes: $unready"
    warn "Workloads may be evicted until those nodes recover or are removed."
  fi
}

cleanup_jobs() {
  if ! kubectl get ns "$NAMESPACE" >/dev/null 2>&1; then
    log "Namespace $NAMESPACE not present yet; skipping job cleanup"
    return
  fi
  log "Pruning completed/failed Jobs to stay under quota"
  local to_delete=()
  while IFS= read -r name; do
    [[ -n "$name" ]] && to_delete+=("$name")
  done < <(kubens get jobs -o jsonpath='{range .items[?(@.status.succeeded==1)]}{.metadata.name}{"\n"}{end}' 2>/dev/null)
  while IFS= read -r name; do
    [[ -n "$name" ]] && to_delete+=("$name")
  done < <(kubens get jobs -o jsonpath='{range .items[?(@.status.failed>=1)]}{.metadata.name}{"\n"}{end}' 2>/dev/null)

  # Deduplicate job names (a job may match succeeded and failed filters edge-case)
  if [[ ${#to_delete[@]} -gt 0 ]]; then
    local uniq_jobs=()
    declare -A seen_jobs=()
    for job in "${to_delete[@]}"; do
      if [[ -n "$job" && -z "${seen_jobs[$job]:-}" ]]; then
        uniq_jobs+=("$job")
        seen_jobs[$job]=1
      fi
    done
    to_delete=("${uniq_jobs[@]}")
  fi

  if [[ ${#to_delete[@]} -eq 0 ]]; then
    log "No completed Jobs to delete"
    return
  fi

  for job in "${to_delete[@]}"; do
    log "Deleting old job $job"
    kubens delete job "$job" --ignore-not-found >/dev/null 2>&1 || true
  done
}

cleanup_pods() {
  if ! kubectl get ns "$NAMESPACE" >/dev/null 2>&1; then
    log "Namespace $NAMESPACE not present yet; skipping pod cleanup"
    return
  fi
  log "Removing leftover pods in Succeeded/Failed phases"
  local pods=()
  while IFS= read -r name; do
    [[ -n "$name" ]] && pods+=("$name")
  done < <(kubens get pods -o jsonpath='{range .items[?(@.status.phase=="Succeeded")]}{.metadata.name}{"\n"}{end}' 2>/dev/null)
  while IFS= read -r name; do
    [[ -n "$name" ]] && pods+=("$name")
  done < <(kubens get pods -o jsonpath='{range .items[?(@.status.phase=="Failed")]}{.metadata.name}{"\n"}{end}' 2>/dev/null)

  # Also sweep ad-hoc debug pods launched via kubectl run (label run=*) even if still running
  while IFS= read -r name; do
    [[ -n "$name" ]] && pods+=("$name")
  done < <(kubens get pods -l run -o jsonpath='{range .items}{.metadata.name}{"\n"}{end}' || true)

  if [[ ${#pods[@]} -gt 0 ]]; then
    local uniq_pods=()
    declare -A seen_pods=()
    for pod in "${pods[@]}"; do
      if [[ -n "$pod" && -z "${seen_pods[$pod]:-}" ]]; then
        uniq_pods+=("$pod")
        seen_pods[$pod]=1
      fi
    done
    pods=("${uniq_pods[@]}")
  fi

  if [[ ${#pods[@]} -eq 0 ]]; then
    log "No stray pods to delete"
    return
  fi

  for pod in "${pods[@]}"; do
    log "Deleting pod $pod"
    kubens delete pod "$pod" --ignore-not-found >/dev/null 2>&1 || true
  done
}

ensure_postgres_ready() {
  log "Waiting for Postgres statefulset (up to 10m)"
  if kubens rollout status statefulset/postgres --timeout=10m; then
    return 0
  fi

  warn "Postgres rollout timed out; attempting to recycle pods"
  warn_unready_nodes

  local pods=()
  while IFS= read -r name; do
    [[ -n "$name" ]] && pods+=("$name")
  done < <(kubens get pods -l app=news-analyzer,component=postgres -o jsonpath='{range .items}{.metadata.name}{"\n"}{end}' 2>/dev/null)

  for pod in "${pods[@]}"; do
    warn "Force deleting stuck Postgres pod $pod"
    kubens delete pod "$pod" --force --grace-period=0 >/dev/null 2>&1 || true
  done

  log "Retrying Postgres rollout"
  kubens rollout status statefulset/postgres --timeout=10m
}

# Parse flags
HARBOR_USER=""; HARBOR_PASS=""; HARBOR_SERVER="registry.harbor.lan"; HARBOR_EMAIL="devnull@example.com"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --namespace) NAMESPACE="$2"; shift 2;;
    --harbor-src-ns) HARBOR_SRC_NS="$2"; shift 2;;
    --harbor-src-secret) HARBOR_SRC_SECRET="$2"; shift 2;;
    --harbor-user) HARBOR_USER="$2"; shift 2;;
    --harbor-pass) HARBOR_PASS="$2"; shift 2;;
    --harbor-server) HARBOR_SERVER="$2"; shift 2;;
    --harbor-email) HARBOR_EMAIL="$2"; shift 2;;
    --git-url) GIT_URL="$2"; shift 2;;
    --git-ref) GIT_REF="$2"; shift 2;;
    --build) BUILD="$2"; shift 2;;
    --no-trigger) TRIGGER_PIPELINE=false; shift;;
    -h|--help) usage; exit 0;;
    *) warn "Unknown option: $1"; usage; exit 1;;
  esac
done

kubens() { kubectl -n "$NAMESPACE" "$@"; }

ensure_namespace() {
  if ! kubectl get ns "$NAMESPACE" >/dev/null 2>&1; then
    log "Creating namespace $NAMESPACE"
    kubectl create namespace "$NAMESPACE"
  else
    log "Namespace $NAMESPACE already exists"
  fi
}

ensure_harbor_pull_secret() {
  if kubens get secret "$HARBOR_SECRET_NAME" >/dev/null 2>&1; then
    log "Pull secret $NAMESPACE/$HARBOR_SECRET_NAME exists"
    return
  fi

  if [[ -n "$HARBOR_USER" && -n "$HARBOR_PASS" ]]; then
    log "Creating pull secret from provided Harbor credentials"
    kubens create secret docker-registry "$HARBOR_SECRET_NAME" \
      --docker-server="$HARBOR_SERVER" \
      --docker-username="$HARBOR_USER" \
      --docker-password="$HARBOR_PASS" \
      --docker-email="$HARBOR_EMAIL"
    return
  fi

  log "Copying pull secret from ${HARBOR_SRC_NS}/${HARBOR_SRC_SECRET}"
  if ! kubectl -n "$HARBOR_SRC_NS" get secret "$HARBOR_SRC_SECRET" >/dev/null 2>&1; then
    warn "Source secret $HARBOR_SRC_NS/$HARBOR_SRC_SECRET not found. Provide --harbor-user/--harbor-pass or create secret manually."
    exit 1
  fi
  DOCKERCFG=$(kubectl -n "$HARBOR_SRC_NS" get secret "$HARBOR_SRC_SECRET" -o jsonpath='{.data\.dockerconfigjson}')
  kubens apply -f - <<EOF
apiVersion: v1
kind: Secret
metadata:
  name: ${HARBOR_SECRET_NAME}
  namespace: ${NAMESPACE}
type: kubernetes.io/dockerconfigjson
data:
  .dockerconfigjson: ${DOCKERCFG}
EOF
}

apply_base() {
  log "Applying base manifests (namespace, configmap, secrets)"
  # namespace.yaml may exist; safe to apply
  [[ -f k8s/namespace.yaml ]] && kubectl apply -f k8s/namespace.yaml || true
  kubens apply -f k8s/configmap.yaml
  kubens apply -f k8s/secrets.yaml || true

  # If a quota update file exists, apply it to raise object limits (e.g., CronJobs)
  if [[ -f k8s/resource-quota-update.yaml ]]; then
    log "Applying resource quota update"
    kubens apply -f k8s/resource-quota-update.yaml || true
  fi

  log "Deploying Postgres, MinIO, and ntfy"
  kubens apply -f k8s/postgres-deployment.yaml
  kubens apply -f k8s/minio-statefulset.yaml
  kubens apply -f k8s/ntfy-deployment.yaml

  log "Waiting for infra to become ready"
  ensure_postgres_ready
  kubens rollout status statefulset/minio --timeout=10m
  kubens rollout status deployment/ntfy --timeout=10m
}

apply_app() {
  log "Applying application workloads"
  if [[ -f k8s/scraper-login-override.yaml ]]; then
    kubens apply -f k8s/scraper-login-override.yaml
  fi
  kubens apply -f k8s/scraper-cronjob.yaml
  kubens apply -f k8s/extractor-cronjob.yaml
  kubens apply -f k8s/summarizer-deployment.yaml
  kubens apply -f k8s/notifier-cronjob.yaml || true

  log "Waiting for summarizer deployment (up to 60s)"
  kubens rollout status deployment/news-analyzer-summarizer --timeout=60s \
    || warn "Summarizer not ready yet; images may be missing. Continuing to builders."
}

apply_ops_and_build() {
  if [[ -d k8s/ops ]]; then
    log "Applying ops overlay (health + cleanup)"
    kubectl apply -k k8s/ops
  fi
  if [[ -d k8s/build ]]; then
    log "Applying builder overlay (Kaniko nightly cronjobs + config)"
    kubectl apply -k k8s/build || warn "Builder overlay applied with warnings (quota?). Proceeding to on-demand builds."
    # Ensure Kaniko cache PVC exists (applied via kustomize). Pre-warm cache on first deploy?
    if [[ -n "${KANIKO_PRIME:-}" ]]; then
      log "Priming Kaniko cache: ${KANIKO_PRIME}"
      build_components "${KANIKO_PRIME}"
    fi
    # Optionally patch GIT_URL and GIT_REF
    if [[ -z "$GIT_URL" ]]; then
      # Try to detect current repo URL
      GIT_URL=$(git config --get remote.origin.url 2>/dev/null || true)
    fi
    if [[ -n "$GIT_URL" ]]; then
      log "Setting builder repo to ${GIT_URL} (${GIT_REF})"
      kubens patch configmap news-analyzer-builder-config --type=merge -p \
        "{\"data\":{\"GIT_URL\":\"${GIT_URL}\",\"GIT_REF\":\"${GIT_REF}\",\"REGISTRY_PREFIX\":\"${REGISTRY_PREFIX}\"}}" || true
    else
      warn "GIT_URL not set and no git remote found; update k8s/build/builder-configmap.yaml manually."
    fi
  fi
}

build_components() {
  local list="$1"
  IFS=',' read -r -a comps <<< "$list"
  for c in "${comps[@]}"; do
    c=$(echo "$c" | xargs)
    [[ -z "$c" ]] && continue
    local ts jobname
    ts=$(date +%Y%m%d%H%M%S)
    jobname="news-analyzer-kaniko-${c}-${ts}"
    log "Starting Kaniko build for $c -> ${REGISTRY_PREFIX}-$c:latest (job: ${jobname})"
    if kubens get cronjob "kaniko-${c}-nightly" >/dev/null 2>&1; then
      kubens create job "${jobname}" --from=cronjob/"kaniko-${c}-nightly" || true
    else
      # Fallback: synthesize a one-off Job from the template with per-component envs
      kubens create -f k8s/build/kaniko-build-job.yaml --dry-run=client -o yaml | \
        perl -pe "s/^\s*name:\s*news-analyzer-kaniko-build/  name: ${jobname}/" | \
        awk -v comp="$c" '\
          BEGIN{state=0}
          /name: COMPONENT/{print; getline; gsub(/value: .*/,"value: " comp); print; next}
          /name: CONTEXT_DIR/{print; getline; gsub(/value: .*/,"value: " comp); print; next}
          /name: DOCKERFILE/{print; getline; gsub(/value: .*/,"value: " comp "/Dockerfile"); print; next}
          {print}
        ' | \
        kubens apply -f -
    fi
  done
  log "Monitor builds: kubectl -n ${NAMESPACE} get jobs | grep news-analyzer-kaniko"
  log "Kaniko cache PVC: kubectl -n ${NAMESPACE} get pvc kaniko-cache"
}

trigger_pipeline() {
  log "Triggering first pipeline run (auth→scrape→extract→summarize)"
  local ts=$(date +%s)
  # auth refresh
  kubens create job --from=cronjob/news-analyzer-auth-refresh auth-${ts}
  # Wait briefly then trigger scraper
  sleep 5
  kubens create job --from=cronjob/news-analyzer-scraper scrape-${ts}
  # extractor and summarizer-batch
  sleep 5
  kubens create job --from=cronjob/news-analyzer-extractor extract-${ts}
  sleep 5
  kubens create job --from=cronjob/news-analyzer-summarizer-batch sum-${ts}
  # notifier is optional; enable if you want immediate digest
  if kubectl -n "$NAMESPACE" get cronjob/news-analyzer-notifier >/dev/null 2>&1; then
    kubens create job --from=cronjob/news-analyzer-notifier notify-${ts} || true
  fi
}

main() {
  warn_unready_nodes
  cleanup_jobs
  cleanup_pods

  ensure_namespace
  ensure_harbor_pull_secret
  apply_base
  apply_app
  apply_ops_and_build

  cleanup_jobs
  cleanup_pods

  case "$BUILD" in
    all) build_components "scraper,extractor,notifier,summarizer";;
    none) log "Skipping in-cluster builds";;
    *) build_components "$BUILD";;
  esac

  if [[ "$TRIGGER_PIPELINE" == "true" ]]; then
    cleanup_jobs
    cleanup_pods
    trigger_pipeline
  else
    log "Skipping initial pipeline trigger"
  fi

  log "Done. Check resources with: kubectl -n ${NAMESPACE} get all"
}

main "$@"
