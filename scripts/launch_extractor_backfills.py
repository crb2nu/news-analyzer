#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import json
from datetime import datetime, date


def d(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()


def main():
    ns = os.environ.get("NAMESPACE", "news-analyzer")
    start = d(os.environ.get("START", date.today().strftime("%Y-%m-%d")))
    end = d(os.environ.get("END", date.today().strftime("%Y-%m-%d")))

    try:
        q = subprocess.check_output(["kubectl", "get", "resourcequota", "news-analyzer-quota", "-n", ns, "-o", "json"]).decode()
        hard = (json.loads(q).get("status", {}) or {}).get("hard", {})
        limit_jobs = int(hard.get("count/jobs.batch", 40))
    except Exception:
        limit_jobs = 40
    try:
        cur_jobs = len(json.loads(subprocess.check_output(["kubectl", "get", "jobs", "-n", ns, "-o", "json"]).decode()).get("items", []))
    except Exception:
        cur_jobs = 0
    if cur_jobs >= limit_jobs:
        print(f"No capacity: {cur_jobs}/{limit_jobs} jobs in namespace", file=sys.stderr)
        sys.exit(0)

    name = f"extractor-backfill-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
    tpl = f"""
apiVersion: batch/v1
kind: Job
metadata:
  name: {name}
  namespace: {ns}
  labels:
    app: news-analyzer
    component: extractor
    type: backfill
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 172800
  template:
    metadata:
      labels:
        app: news-analyzer
        component: extractor
        type: backfill
    spec:
      restartPolicy: Never
      imagePullSecrets:
      - name: harbor-regcred
      containers:
      - name: extractor
        image: registry.harbor.lan/library/news-analyzer-extractor:latest
        imagePullPolicy: Always
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: news-analyzer-secrets
              key: DATABASE_URL
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
        resources:
          requests:
            memory: 1Gi
            cpu: 500m
          limits:
            memory: 2Gi
            cpu: 1000m
        command:
        - /bin/sh
        - -c
        - |
          set -e
          START_DATE={start.isoformat()}
          END_DATE={end.isoformat()}
          python - <<'PY' > /tmp/dates.txt
          import os
          from datetime import datetime, timedelta
          start = datetime.strptime(os.environ.get('START_DATE'), '%Y-%m-%d').date()
          end = datetime.strptime(os.environ.get('END_DATE'), '%Y-%m-%d').date()
          cur = start
          while cur <= end:
              print(cur.isoformat())
              cur += timedelta(days=1)
          PY
          while read d; do
            echo "Extracting $d"
            python -m processor --date "$d"
          done < /tmp/dates.txt
"""

    proc = subprocess.run(["kubectl", "apply", "-f", "-"], input=tpl.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr.decode())
        sys.exit(proc.returncode)
    print(proc.stdout.decode().strip())


if __name__ == "__main__":
    main()

