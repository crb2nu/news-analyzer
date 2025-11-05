import json
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, push_to_gateway
except Exception:  # pragma: no cover - optional at runtime
    CollectorRegistry = None  # type: ignore
    Counter = Gauge = Histogram = None  # type: ignore
    push_to_gateway = None  # type: ignore


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:  # type: ignore[override]
        payload = {
            "level": record.levelname,
            "time": int(time.time()),
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        # attach extras
        for k, v in record.__dict__.items():
            if k.startswith("_"):
                continue
            if k in ("args", "msg", "levelname", "levelno", "pathname", "filename",
                     "module", "exc_info", "exc_text", "stack_info", "lineno",
                     "funcName", "created", "msecs", "relativeCreated", "thread",
                     "threadName", "processName", "process"):
                continue
            payload[k] = v
        return json.dumps(payload, ensure_ascii=False)


def setup_logging() -> None:
    fmt = os.getenv("LOG_FORMAT", "text").lower()
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(level=getattr(logging, level, logging.INFO))
    root = logging.getLogger()
    if fmt == "json":
        for h in list(root.handlers):
            h.setFormatter(JsonFormatter())


@dataclass
class Metrics:
    enabled: bool
    registry: Optional[CollectorRegistry]
    pushgateway: Optional[str]
    job: str
    grouping_key: Dict[str, str]
    # common metrics
    login_attempts: Optional[Counter] = None
    login_success: Optional[Counter] = None
    login_failures: Optional[Counter] = None
    session_verify_success: Optional[Counter] = None
    session_verify_failures: Optional[Counter] = None
    discover_runs: Optional[Counter] = None
    discover_pages_found: Optional[Histogram] = None
    action_seconds: Optional[Histogram] = None

    @classmethod
    def init(cls) -> "Metrics":
        pushgateway = os.getenv("METRICS_PUSHGATEWAY_URL")
        job = os.getenv("METRICS_JOB_NAME", "news_analyzer_scraper")
        grouping = {}
        # labels may come as JSON in env
        extra = os.getenv("METRICS_LABELS_JSON")
        if extra:
            try:
                grouping.update(json.loads(extra))
            except Exception:
                pass
        # Merge any METRICS_LABEL_* envs (e.g., injected via K8s downward API)
        for k, v in os.environ.items():
            if not k.startswith("METRICS_LABEL_"):
                continue
            key = k[len("METRICS_LABEL_"):].lower()
            if key and v:
                grouping[key] = v

        if CollectorRegistry is None:
            return cls(False, None, None, job, grouping)

        registry = CollectorRegistry()
        m = cls(True, registry, pushgateway, job, grouping)
        # counters and histograms with labels for granularity
        # label set kept small to avoid cardinality explosions
        labelnames = ("publication", "proxy")
        action_labels = ("action", "publication", "proxy")
        m.login_attempts = Counter("scraper_login_attempts_total", "Login attempts", labelnames=labelnames, registry=registry)
        m.login_success = Counter("scraper_login_success_total", "Login successes", labelnames=labelnames, registry=registry)
        m.login_failures = Counter("scraper_login_failures_total", "Login failures", labelnames=labelnames, registry=registry)
        m.session_verify_success = Counter("scraper_session_verify_success_total", "Session verify success", labelnames=labelnames, registry=registry)
        m.session_verify_failures = Counter("scraper_session_verify_failures_total", "Session verify failures", labelnames=labelnames, registry=registry)
        m.discover_runs = Counter("scraper_discover_runs_total", "Edition discovery runs", labelnames=labelnames, registry=registry)
        m.discover_pages_found = Histogram(
            "scraper_discover_pages_found", "Pages found per run", labelnames=labelnames,
            buckets=(0, 1, 5, 10, 20, 40, 80, 160), registry=registry
        )
        m.action_seconds = Histogram(
            "scraper_action_seconds", "Duration of key scraper actions", labelnames=action_labels,
            buckets=(0.2, 0.5, 1, 2, 3, 5, 8, 13, 21), registry=registry
        )
        return m

    def push(self) -> None:
        if not self.enabled or not self.pushgateway or push_to_gateway is None:
            return
        try:
            push_to_gateway(self.pushgateway, job=self.job, registry=self.registry, grouping_key=self.grouping_key)
        except Exception:
            logging.getLogger(__name__).debug("pushgateway failed", exc_info=True)

    # ---- convenience helpers with labels ----
    @staticmethod
    def _label_tuple(publication: Optional[str], proxy: Optional[str]) -> tuple[str, str]:
        pub = publication or "unknown"
        prox = proxy or "direct"
        return (pub, prox)

    @staticmethod
    def _action_labels(action: str, publication: Optional[str], proxy: Optional[str]) -> tuple[str, str, str]:
        pub, prox = Metrics._label_tuple(publication, proxy)
        return (action, pub, prox)

    def inc_login_attempt(self, publication: Optional[str], proxy: Optional[str]) -> None:
        if self.login_attempts:
            self.login_attempts.labels(*self._label_tuple(publication, proxy)).inc()

    def inc_login_success(self, publication: Optional[str], proxy: Optional[str]) -> None:
        if self.login_success:
            self.login_success.labels(*self._label_tuple(publication, proxy)).inc()

    def inc_login_failure(self, publication: Optional[str], proxy: Optional[str]) -> None:
        if self.login_failures:
            self.login_failures.labels(*self._label_tuple(publication, proxy)).inc()

    def inc_verify_success(self, publication: Optional[str], proxy: Optional[str]) -> None:
        if self.session_verify_success:
            self.session_verify_success.labels(*self._label_tuple(publication, proxy)).inc()

    def inc_verify_failure(self, publication: Optional[str], proxy: Optional[str]) -> None:
        if self.session_verify_failures:
            self.session_verify_failures.labels(*self._label_tuple(publication, proxy)).inc()

    def inc_discover_run(self, publication: Optional[str], proxy: Optional[str]) -> None:
        if self.discover_runs:
            self.discover_runs.labels(*self._label_tuple(publication, proxy)).inc()

    def observe_pages_found(self, pages: int, publication: Optional[str], proxy: Optional[str]) -> None:
        if self.discover_pages_found:
            self.discover_pages_found.labels(*self._label_tuple(publication, proxy)).observe(pages)

    def observe_action(self, action: str, seconds: float, publication: Optional[str], proxy: Optional[str]) -> None:
        if self.action_seconds:
            self.action_seconds.labels(*self._action_labels(action, publication, proxy)).observe(seconds)

    # Lightweight timer context manager
    def timer(self, action: str, publication: Optional[str] = None, proxy: Optional[str] = None):
        class _T:
            def __init__(self, outer: Metrics):
                self.outer = outer
                self.start = 0.0
            def __enter__(self_inner):
                self_inner.start = time.perf_counter()
                return self_inner
            def __exit__(self_inner, exc_type, exc, tb):
                dur = max(0.0, time.perf_counter() - self_inner.start)
                self.observe_action(action, dur, publication, proxy)
        return _T(self)


def traces_dir() -> Path:
    d = Path(os.getenv("TRACES_DIR", "artifacts/traces"))
    d.mkdir(parents=True, exist_ok=True)
    return d


class TraceHelper:
    def __init__(self, context) -> None:
        self.context = context
        self._enabled = bool(str(os.getenv("PW_TRACE", "1")).lower() in ("1", "true", "yes"))

    def start(self) -> None:
        if not self._enabled:
            return
        try:
            self.context.tracing.start(screenshots=True, snapshots=True, sources=False)
        except Exception:
            logging.getLogger(__name__).debug("tracing.start failed", exc_info=True)

    def stop(self, name: str) -> Optional[Path]:
        if not self._enabled:
            return None

def proxy_label_from_settings(settings) -> str:
    try:
        server = settings.get_playwright_proxy().get("server")
        return server or "direct"
    except Exception:
        return "direct"
        try:
            path = traces_dir() / f"{name}.zip"
            self.context.tracing.stop(path=str(path))
            return path
        except Exception:
            logging.getLogger(__name__).debug("tracing.stop failed", exc_info=True)
            return None
