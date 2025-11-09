# Backfill & Reprocessing Playbook

This document summarizes what we fixed, how the pipeline behaves under load, and provides concrete commands and queries to operate, monitor, and (re)process historical content safely.

## Executive Summary

- OOM root cause fixed by properly stopping Playwright tracing and closing contexts; tracing disabled for batch runs.
- Scraper backfills run with `PW_TRACE=0`, `SCRAPER_PARALLELISM=2`, `req: 1Gi / lim: 3Gi` and are stable.
- A continuous, quota‑aware controller enqueues weekly backfills (scraper → extractor) for 2025.
- Summarizer CronJob processes new articles every 30 minutes; 118 summaries were produced in the last 24 hours.

## Current State (as of UTC 2025‑11‑09)

- Scraper backfills
  - Four weekly windows previously completed successfully (Jan 1–7, Jan 8–14); additional windows are being scheduled by the controller.
- Extractor backfills
  - One completed and one running in the most recent loop.
- Postgres (last 24h)
  - Articles: 155 new; status breakdown: summarized 118, notified 26, extracted 11.
  - Processing history (sample): 2025‑11‑09 html 263 found / 11 new / 252 dup.
- MinIO
  - Cache is populated under date‑prefixed keys (e.g., `YYYY‑MM‑DD/...`).

## Architecture Notes

- Controller: `k8s/ops/ops-backfill-controller.yaml` (Deployment)
  - Reads namespace Job quota and recent OOMs; enqueues weekly windows that include Wed/Sat (publication days).
  - Labels every Job with `component`, `type=backfill`, `win-start`, `win-end` to avoid duplicates.
  - Auto‑tunes: on OOMKilled scraper pods → `SCRAPER_PARALLELISM=1`, memory lim to 4Gi for new Jobs.

## Resource & Tuning Defaults

- Scraper backfill Job
  - Env: `PW_TRACE=0`, `SCRAPER_PARALLELISM=2`
  - Resources: `requests: 1Gi/2CPU`, `limits: 3Gi/2CPU`
- Extractor backfill Job
  - Resources: `requests: 1Gi/0.5CPU`, `limits: 2Gi/1CPU`
- Summarizer batch CronJob
  - Every 30 minutes; reads `OPENAI_*` from env; drains the `extracted` queue.

## Operate & Monitor

- List backfill Jobs
  - Scraper: `kubectl get jobs -n news-analyzer -l component=scraper,type=backfill -o wide`
  - Extractor: `kubectl get jobs -n news-analyzer -l component=extractor,type=backfill -o wide`
- Tail a Job
  - `kubectl logs -f -n news-analyzer job/<job>`
- Controller logs
  - `kubectl logs -n news-analyzer deploy/news-analyzer-ops-backfill-controller --tail=200`

## Data Inspection (Postgres)

Use the in‑cluster psql helper pattern (replaces host networking):

```
DB='postgresql://news_analyzer:***@postgres-service.news-analyzer.svc.cluster.local:5432/news_analyzer'
kubectl run -n news-analyzer --rm -i psql-inspect --image=postgres:16-alpine --restart=Never -- sh -lc "psql $DB -Atc \"<SQL>\""
```

- Articles in last 24h by status
```
SELECT processing_status, count(*)
FROM articles
WHERE date_extracted >= now() - interval '24 hours'
GROUP BY 1 ORDER BY 2 DESC;
```

- Processing history (last 2 days)
```
SELECT date_processed::date, source_type,
       SUM(articles_found), SUM(articles_new), SUM(articles_duplicate)
FROM processing_history
WHERE date_processed >= current_date - interval '2 days'
GROUP BY 1,2 ORDER BY 1 DESC,2;
```

- Coverage for a backfill window (example: 2025‑01‑01..2025‑01‑14)
```
SELECT edition_date, publication, source_type, count(*)
FROM articles
WHERE edition_date BETWEEN '2025-01-01' AND '2025-01-14'
GROUP BY 1,2,3 ORDER BY 1,2,3;
```

## Data Inspection (MinIO)

Run a short‑lived pod using the scraper image (already contains MinIO client libs):

```
cat > /tmp/minio_range.yaml <<'YAML'
apiVersion: v1
kind: Pod
metadata:
  name: minio-range
  namespace: news-analyzer
spec:
  restartPolicy: Never
  imagePullSecrets:
  - name: harbor-regcred
  containers:
  - name: c
    image: registry.harbor.lan/library/news-analyzer-scraper:latest
    env:
    - name: MINIO_ENDPOINT
      valueFrom: {configMapKeyRef: {name: news-analyzer-config, key: MINIO_ENDPOINT}}
    - name: MINIO_ACCESS_KEY
      valueFrom: {secretKeyRef: {name: news-analyzer-secrets, key: MINIO_ACCESS_KEY}}
    - name: MINIO_SECRET_KEY
      valueFrom: {secretKeyRef: {name: news-analyzer-secrets, key: MINIO_SECRET_KEY}}
    - name: MINIO_BUCKET
      valueFrom: {configMapKeyRef: {name: news-analyzer-config, key: MINIO_BUCKET}}
    - name: START
      value: "2025-01-01"
    - name: END
      value: "2025-01-14"
    command: ["python","-c"]
    args:
    - |
      import os, json
      from datetime import datetime
      from minio import Minio
      ep=os.environ['MINIO_ENDPOINT']; sec=False
      if ep.startswith('http://'): ep=ep.split('://',1)[1]
      elif ep.startswith('https://'): ep=ep.split('://',1)[1]; sec=True
      mc=Minio(ep, access_key=os.environ['MINIO_ACCESS_KEY'], secret_key=os.environ['MINIO_SECRET_KEY'], secure=sec)
      b=os.environ.get('MINIO_BUCKET','news-cache')
      start=datetime.strptime(os.environ['START'],'%Y-%m-%d').date()
      end=datetime.strptime(os.environ['END'],'%Y-%m-%d').date()
      from collections import defaultdict
      by_date=defaultdict(lambda:{'count':0,'bytes':0})
      for obj in mc.list_objects(b, recursive=True):
          parts=obj.object_name.split('/',1)
          if not parts: continue
          p=parts[0]
          try:
              d=datetime.strptime(p,'%Y-%m-%d').date()
          except: continue
          if start<=d<=end:
              e=by_date[p]; e['count']+=1; e['bytes']+=obj.size
      print(json.dumps({'bucket':b,'range':[start.isoformat(), end.isoformat()], 'by_date':by_date}, default=int))
YAML
kubectl apply -f /tmp/minio_range.yaml && kubectl wait --for=condition=Ready pod/minio-range -n news-analyzer --timeout=90s
kubectl logs -n news-analyzer minio-range --tail=200
kubectl delete pod/minio-range -n news-analyzer --now
```

## Backfill Strategy

1) Continue weekly windows across 2025 with the controller (Wed/Sat only).  
2) Use `MAX_NEW_PER_RUN` to modulate throughput; default is 6 (can bump to 8 when stable).  
3) Keep `SCRAPER_PARALLELISM=2`; only increase to 3 if 0 OOMs across two loops and cluster memory permits.  
4) Let summarizer CronJob drain the queue; if backlog grows, reduce schedule to 15 minutes.  

## Troubleshooting

- OOMs reappear: controller auto‑tunes future Jobs (par=1, mem=4Gi). You can also force lower concurrency via env or limit concurrent windows by reducing `MAX_NEW_PER_RUN`.
- Slow scrape windows: verify proxies, bump CPU to 3–4 cores on the Job, keep memory at 3–4Gi.
- Duplicate windows: Jobs carry `win-start`/`win-end` labels; re‑runs are skipped by the controller.

## Change Log (relevant files)

- Fixed tracing leak & context cleanup: `scraper/observability.py`, `scraper/discover.py`
- Safer defaults for batch runs: `k8s/scraper-cronjob.yaml`, `Makefile`
- Controller (continuous backfill): `k8s/ops/ops-backfill-controller.yaml`, `scripts/controller.sh`

