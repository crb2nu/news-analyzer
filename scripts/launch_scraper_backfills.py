#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import time
import json
from datetime import datetime, timedelta, date


def read_env(name: str, default: str | None = None) -> str:
    val = os.environ.get(name, default)
    if val is None:
        print(f"Missing required env: {name}", file=sys.stderr)
        sys.exit(2)
    return val


def iter_windows(start: date, end: date, unit: str):
    def next_boundary(d: date):
        if unit == "daily":
            return d, d
        if unit == "biweekly":
            return d, min(end, d + timedelta(days=13))
        return d, min(end, d + timedelta(days=6))

    cur = start
    while cur <= end:
        s, e = next_boundary(cur)
        # include only windows that have Wed/Sat
        d = s
        keep = False
        while d <= e:
            if d.weekday() in (2, 5):
                keep = True
                break
            d += timedelta(days=1)
        if keep:
            yield s, e
        cur = e + timedelta(days=1)


def build_job_yaml(
    name: str,
    start: date,
    end: date,
    publications: str,
    force: bool,
    par: int = 2,
    req_cpu: str = "2",
    req_mem: str = "1Gi",
    lim_cpu: str = "2",
    lim_mem: str = "3Gi",
) -> str:
    # Minimal differences from Makefile template; env tuned here.
    return f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: {name}
  namespace: news-analyzer
  labels:
    app: news-analyzer
    component: scraper
    type: backfill
spec:
  template:
    metadata:
      labels:
        app: news-analyzer
        component: scraper
        type: backfill
    spec:
      restartPolicy: Never
      imagePullSecrets:
      - name: harbor-regcred
      securityContext:
        runAsNonRoot: true
        runAsUser: 1000
        fsGroup: 1000
      volumes:
      - name: session-storage
        emptyDir: {{}}
      - name: scraper-login-override
        configMap:
          name: scraper-login-override
      - name: scraper-discover-override
        configMap:
          name: scraper-discover-override
      containers:
      - name: scraper
        image: registry.harbor.lan/library/news-analyzer-scraper:latest
        imagePullPolicy: Always
        env:
        - name: PW_TRACE
          value: "0"
        - name: SCRAPER_PARALLELISM
          value: "{par}"
        - name: HOME
          value: /home/scraper
        - name: PLAYWRIGHT_BROWSERS_PATH
          value: /home/scraper/.cache/ms-playwright
        - name: EEDITION_USER
          valueFrom:
            secretKeyRef:
              name: news-analyzer-secrets
              key: EEDITION_USER
        - name: EEDITION_PASS
          valueFrom:
            secretKeyRef:
              name: news-analyzer-secrets
              key: EEDITION_PASS
        - name: SMARTPROXY_USERNAME
          valueFrom:
            secretKeyRef:
              name: news-analyzer-secrets
              key: SMARTPROXY_USERNAME
        - name: SMARTPROXY_PASSWORD
          valueFrom:
            secretKeyRef:
              name: news-analyzer-secrets
              key: SMARTPROXY_PASSWORD
        - name: SMARTPROXY_HOST
          valueFrom:
            configMapKeyRef:
              name: news-analyzer-config
              key: SMARTPROXY_HOST
        - name: MINIO_ENDPOINT
          valueFrom:
            configMapKeyRef:
              name: news-analyzer-config
              key: MINIO_ENDPOINT
        - name: MINIO_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: news-analyzer-secrets
              key: MINIO_ACCESS_KEY
        - name: MINIO_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: news-analyzer-secrets
              key: MINIO_SECRET_KEY
        - name: MINIO_BUCKET
          valueFrom:
            configMapKeyRef:
              name: news-analyzer-config
              key: MINIO_BUCKET
        - name: SCRAPER_USER_AGENT
          valueFrom:
            configMapKeyRef:
              name: news-analyzer-config
              key: SCRAPER_USER_AGENT
        - name: START_DATE
          value: "{start.isoformat()}"
        - name: END_DATE
          value: "{end.isoformat()}"
        - name: FORCE_DOWNLOAD
          value: "{1 if force else 0}"
        - name: PUBLICATIONS
          value: "{publications}"
        resources:
          requests:
            memory: "{req_mem}"
            cpu: "{req_cpu}"
          limits:
            memory: "{lim_mem}"
            cpu: "{lim_cpu}"
        command:
        - /bin/sh
        - -c
        - |
          set -e
          mkdir -p /app/storage
          python - <<'PY' > /tmp/download-dates.txt
          from datetime import datetime, timedelta
          import os
          start = datetime.strptime(os.environ['START_DATE'], '%Y-%m-%d').date()
          end = datetime.strptime(os.environ['END_DATE'], '%Y-%m-%d').date()
          cur = start
          while cur <= end:
              if cur.weekday() in (2, 5):
                  print(cur.isoformat())
              cur += timedelta(days=1)
          PY
          PUB_LIST="${{PUBLICATIONS:-{publications}}}"
          while read d; do
            [ -z "$d" ] && continue
            echo "Processing edition $d"
            extra=""; [ "$FORCE_DOWNLOAD" = "1" ] && extra="--force"
            OLD_IFS="$IFS"; IFS=,; for pub in $PUB_LIST; do
              pub_trim=$(echo "$pub" | sed -e "s/^ *//" -e "s/ *$//")
              [ -z "$pub_trim" ] && continue
              echo "  -> $pub_trim"
              python -m scraper.downloader --date "$d" $extra --publication "$pub_trim" --storage /app/storage/storage_state.json
              sleep 1
            done; IFS="$OLD_IFS"
          done < /tmp/download-dates.txt
        volumeMounts:
        - name: session-storage
          mountPath: /app/storage
        - name: scraper-login-override
          mountPath: /app/scraper/login.py
          subPath: login.py
        - name: scraper-discover-override
          mountPath: /app/scraper/discover.py
          subPath: discover.py
  backoffLimit: 0
  ttlSecondsAfterFinished: 172800
"""


def main():
    start = datetime.strptime(read_env("START"), "%Y-%m-%d").date()
    end = datetime.strptime(read_env("END"), "%Y-%m-%d").date()
    unit = os.environ.get("SPLIT", "weekly")
    publications = os.environ.get("PUBLICATIONS", "Smyth County News & Messenger,The News & Press,The Bland County Messenger,The Floyd Press,Wytheville Enterprise,Washington County News")
    force = os.environ.get("FORCE", "0") in ("1", "true", "True")
    # Optional cleanup to free quota slots
    if os.environ.get("CLEANUP_COMPLETED", "1") in ("1", "true", "True"):
        subprocess.run([
            "kubectl", "delete", "job",
            "-n", "news-analyzer",
            "-l", "component=scraper,type=backfill",
            "--field-selector", "status.successful==1"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        subprocess.run([
            "kubectl", "delete", "job",
            "-n", "news-analyzer",
            "-l", "component=scraper,type=backfill",
            "--field-selector", "status.failed>0"
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Compute available capacity from quota and current jobs
    try:
        q = subprocess.check_output(["kubectl", "get", "resourcequota", "news-analyzer-quota", "-n", "news-analyzer", "-o", "json"]).decode()
        rq = json.loads(q)
        hard = rq.get("status", {}).get("hard", {}) or rq.get("spec", {}).get("hard", {})
        limit_jobs = int(hard.get("count/jobs.batch", 40))
    except Exception:
        limit_jobs = 40
    try:
        cur_jobs_json = subprocess.check_output(["kubectl", "get", "jobs", "-n", "news-analyzer", "-o", "json"]).decode()
        cur_jobs = len(json.loads(cur_jobs_json).get("items", []))
    except Exception:
        cur_jobs = 0
    capacity = max(0, limit_jobs - cur_jobs)

    # Basic auto-tuning from recent pod/job outcomes
    try:
        pods_json = subprocess.check_output(["kubectl", "get", "pods", "-n", "news-analyzer", "-l", "component=scraper,type=backfill", "-o", "json"]).decode()
        oom = pods_json.count("OOMKilled")
    except Exception:
        oom = 0
    try:
        jobs_json = subprocess.check_output(["kubectl", "get", "jobs", "-n", "news-analyzer", "-l", "component=scraper,type=backfill", "-o", "json"]).decode()
        succ = jobs_json.count('"succeeded": 1')
    except Exception:
        succ = 0

    par = 2
    req_cpu = "2"; req_mem = "1Gi"; lim_cpu = "2"; lim_mem = "3Gi"
    max_new_env = int(os.environ.get("MAX_NEW_PER_RUN", "5"))
    if oom > 0:
        par = 1
        lim_mem = "4Gi"
    elif succ > 5 and capacity >= 5:
        max_new_env = max(max_new_env, 8)
    # Build existing window signatures to avoid duplicates even if labels are missing
    try:
        cur_jobs_json = subprocess.check_output(["kubectl", "get", "jobs", "-n", "news-analyzer", "-o", "json"]).decode()
        names = [j["metadata"]["name"] for j in json.loads(cur_jobs_json).get("items", [])]
    except Exception:
        names = []
    existing_windows = set()
    for n in names:
        # Look for suffix pattern -YYYYMMDD-YYYYMMDD
        parts = n.split("-")
        if len(parts) >= 3 and parts[-2].isdigit() and parts[-1].isdigit():
            existing_windows.add((parts[-2], parts[-1]))

    created = 0
    for s, e in iter_windows(start, end, unit):
        ts = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        name = f"scraper-backfill-{ts}-{s.strftime('%Y%m%d')}-{e.strftime('%Y%m%d')}"
        sig = (s.strftime("%Y%m%d"), e.strftime("%Y%m%d"))
        if sig in existing_windows:
            continue
        if created >= capacity:
            print(f"Capacity reached ({capacity} jobs). Stopping creation.")
            break
        yaml = build_job_yaml(name, s, e, publications, force, par, req_cpu, req_mem, lim_cpu, lim_mem)
        print(f"Applying {name} [{s}..{e}] ...")
        proc = subprocess.run(["kubectl", "apply", "-f", "-"], input=yaml.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if proc.returncode != 0:
            sys.stderr.write(proc.stderr.decode())
            break
        created += 1
        time.sleep(0.2)
    print(f"Created {created} jobs")


if __name__ == "__main__":
    main()
