.PHONY: extractor-run summarizer-run extractor-logs summarizer-logs backfill scrape-range test-health-access oauth-start-access oauth-status-access
.PHONY: scrape-range-split topup-backfill
.PHONY: scrape-range-split

ROOT := $(CURDIR)
SYS_PYTHON := $(or $(shell command -v python3.13),$(shell command -v python3.12),$(shell command -v python3.11),$(shell command -v python3))
FORCE_ARG :=$(if $(FORCE), --force,)
PUBLICATIONS := Smyth County News & Messenger,The News & Press,The Bland County Messenger,The Floyd Press,Wytheville Enterprise,Washington County News
CF_HOST ?= news.flexinfer.ai

# Kick off the extractor CronJob as an ad-hoc job.
extractor-run:
	@set -e; ts=`date +%H%M%S`; \
	echo "Starting extractor job $$ts"; \
	kubectl create job --from=cronjob/news-analyzer-extractor \
	  -n news-analyzer extractor-manual-$$ts

# Kick off the summarizer CronJob as an ad-hoc job.
summarizer-run:
	@set -e; ts=`date +%H%M%S`; \
	echo "Starting summarizer job $$ts"; \
	kubectl create job --from=cronjob/news-analyzer-summarizer-batch \
	  -n news-analyzer summarizer-manual-$$ts

# Tail logs for an extractor job: make extractor-logs JOB=<job-name>
extractor-logs:
	@if [ -z "$(JOB)" ]; then \
		echo "JOB=<name> is required" >&2; exit 1; \
	fi
	@kubectl logs -f job/$(JOB) -n news-analyzer

# Tail logs for a summarizer job: make summarizer-logs JOB=<job-name>
summarizer-logs:
	@if [ -z "$(JOB)" ]; then \
		echo "JOB=<name> is required" >&2; exit 1; \
	fi
	@kubectl logs -f job/$(JOB) -n news-analyzer

# Backfill cached editions: make backfill START=YYYY-MM-DD END=YYYY-MM-DD [FORCE=1]
backfill:
	@if [ -z "$(START)" ] || [ -z "$(END)" ]; then \
		echo "Usage: make backfill START=YYYY-MM-DD END=YYYY-MM-DD [FORCE=1]" >&2; \
		exit 1; \
	fi
	@set -e; \
	ts=`date +%Y%m%d%H%M%S`; \
	job=extractor-backfill-$$ts; \
	echo "Creating backfill job $$job"; \
	printf '%s\n' \
	  "apiVersion: batch/v1" \
	  "kind: Job" \
	  "metadata:" \
	  "  name: $$job" \
	  "  namespace: news-analyzer" \
	  "  labels:" \
	  "    app: news-analyzer" \
	  "    component: extractor" \
	  "    type: backfill" \
	  "spec:" \
	  "  template:" \
	  "    metadata:" \
	  "      labels:" \
	  "        app: news-analyzer" \
	  "        component: extractor" \
	  "        type: backfill" \
	  "    spec:" \
	  "      restartPolicy: Never" \
	  "      imagePullSecrets:" \
	  "      - name: harbor-regcred" \
	  "      containers:" \
	  "      - name: extractor" \
	  "        image: registry.harbor.lan/library/news-analyzer-extractor:latest" \
	  "        imagePullPolicy: Always" \
	  "        command:" \
	  "        - /bin/sh" \
	  "        - -c" \
	  "        - |" \
	  "          set -e" \
	  "          START_DATE=$(START)" \
	  "          END_DATE=$(END)" \
	  "          export START_DATE END_DATE" \
	  '          if [ -z "$$START_DATE" ] || [ -z "$$END_DATE" ]; then' \
	  '            echo "START or END not provided" >&2' \
	  "            exit 1" \
	  "          fi" \
	  "          python - <<'PY' > /tmp/dates.txt" \
	  "          import os, textwrap" \
	  "          exec(textwrap.dedent(\"\"\"" \
	  "          from datetime import datetime, timedelta" \
	  "          start = datetime.strptime(os.environ['START_DATE'], '%Y-%m-%d').date()" \
	  "          end = datetime.strptime(os.environ['END_DATE'], '%Y-%m-%d').date()" \
	  "          if start > end:" \
	  "              raise SystemExit('start date is after end date')" \
	  "          cur = start" \
	  "          while cur <= end:" \
	  "              print(cur.isoformat())" \
	  "              cur += timedelta(days=1)" \
	  "          \"\"\"))" \
	  "          PY" \
	  '          while read d; do' \
	  '            echo "Processing $$d"' \
	  '            python -m processor --date $$d$(FORCE_ARG)' \
	  '          done < /tmp/dates.txt' \
	  "        env:" \
	  "        - name: DATABASE_URL" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: DATABASE_URL" \
	  "        - name: MINIO_ENDPOINT" \
	  "          valueFrom:" \
	  "            configMapKeyRef:" \
	  "              name: news-analyzer-config" \
	  "              key: MINIO_ENDPOINT" \
	  "        - name: MINIO_ACCESS_KEY" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: MINIO_ACCESS_KEY" \
	  "        - name: MINIO_SECRET_KEY" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: MINIO_SECRET_KEY" \
	  "        - name: MINIO_BUCKET" \
	  "          valueFrom:" \
	  "            configMapKeyRef:" \
	  "              name: news-analyzer-config" \
	  "              key: MINIO_BUCKET" \
	  "        - name: LOG_LEVEL" \
	  "          valueFrom:" \
	  "            configMapKeyRef:" \
	  "              name: news-analyzer-config" \
	  "              key: LOG_LEVEL" \
  "        resources:" \
  "          requests:" \
  "            memory: \"1Gi\"" \
  "            cpu: \"4\"" \
  "          limits:" \
  "            memory: \"2Gi\"" \
  "            cpu: \"4\"" \
  "  backoffLimit: 0" \
| kubectl apply -f -; \
echo "Backfill job $$job created. Tail logs with: kubectl logs -f job/$$job -n news-analyzer"
# Download editions into cache for a date range (Wednesdays/Saturdays): make scrape-range START=YYYY-MM-DD END=YYYY-MM-DD [FORCE=1]
scrape-range:
	@if [ -z "$(START)" ] || [ -z "$(END)" ]; then \
		echo "Usage: make scrape-range START=YYYY-MM-DD END=YYYY-MM-DD [FORCE=1]" >&2; \
		exit 1; \
	fi
	@set -e; \
	ts=`date +%Y%m%d%H%M%S`; \
	job=scraper-backfill-$$ts; \
	echo "Creating scraper backfill job $$job"; \
	printf '%s\n' \
	  "apiVersion: batch/v1" \
	  "kind: Job" \
	  "metadata:" \
	  "  name: $$job" \
	  "  namespace: news-analyzer" \
	  "  labels:" \
	  "    app: news-analyzer" \
	  "    component: scraper" \
	  "    type: backfill" \
	  "spec:" \
	  "  template:" \
	  "    metadata:" \
	  "      labels:" \
	  "        app: news-analyzer" \
	  "        component: scraper" \
	  "        type: backfill" \
	  "    spec:" \
	  "      restartPolicy: Never" \
	  "      imagePullSecrets:" \
	  "      - name: harbor-regcred" \
	  "      securityContext:" \
	  "        runAsNonRoot: true" \
	  "        runAsUser: 1000" \
	  "        fsGroup: 1000" \
	  "      volumes:" \
	  "      - name: session-storage" \
	  "        emptyDir: {}" \
	  "      - name: scraper-login-override" \
	  "        configMap:" \
	  "          name: scraper-login-override" \
	  "      - name: scraper-discover-override" \
	  "        configMap:" \
	  "          name: scraper-discover-override" \
	  "      containers:" \
	  "      - name: scraper" \
	  "        image: registry.harbor.lan/library/news-analyzer-scraper:latest" \
	  "        imagePullPolicy: Always" \
	  "        env:" \
	  "        - name: PW_TRACE" \
	  "          value: \"0\"" \
	  "        - name: SCRAPER_PARALLELISM" \
	  "          value: \"2\"" \
	  "        - name: HOME" \
	  "          value: /home/scraper" \
	  "        - name: PLAYWRIGHT_BROWSERS_PATH" \
	  "          value: /home/scraper/.cache/ms-playwright" \
	  "        - name: EEDITION_USER" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: EEDITION_USER" \
	  "        - name: EEDITION_PASS" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: EEDITION_PASS" \
	  "        - name: SMARTPROXY_USERNAME" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: SMARTPROXY_USERNAME" \
	  "        - name: SMARTPROXY_PASSWORD" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: SMARTPROXY_PASSWORD" \
	  "        - name: SMARTPROXY_HOST" \
	  "          valueFrom:" \
	  "            configMapKeyRef:" \
	  "              name: news-analyzer-config" \
	  "              key: SMARTPROXY_HOST" \
	  "        - name: MINIO_ENDPOINT" \
	  "          valueFrom:" \
	  "            configMapKeyRef:" \
	  "              name: news-analyzer-config" \
	  "              key: MINIO_ENDPOINT" \
	  "        - name: MINIO_ACCESS_KEY" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: MINIO_ACCESS_KEY" \
	  "        - name: MINIO_SECRET_KEY" \
	  "          valueFrom:" \
	  "            secretKeyRef:" \
	  "              name: news-analyzer-secrets" \
	  "              key: MINIO_SECRET_KEY" \
	  "        - name: MINIO_BUCKET" \
	  "          valueFrom:" \
	  "            configMapKeyRef:" \
	  "              name: news-analyzer-config" \
	  "              key: MINIO_BUCKET" \
	  "        - name: SCRAPER_USER_AGENT" \
	  "          valueFrom:" \
	  "            configMapKeyRef:" \
	  "              name: news-analyzer-config" \
	  "              key: SCRAPER_USER_AGENT" \
	  "        - name: START_DATE" \
	  "          value: $(START)" \
	  "        - name: END_DATE" \
	  "          value: $(END)" \
	  "        - name: FORCE_DOWNLOAD" \
	  "          value: \"$(if $(FORCE),1,0)\"" \
	  "        - name: PUBLICATIONS" \
	  "          value: \"$(PUBLICATIONS)\"" \
	  "        resources:" \
  "          requests:" \
  "            memory: \"1Gi\"" \
  "            cpu: \"2\"" \
  "          limits:" \
  "            memory: \"3Gi\"" \
  "            cpu: \"2\"" \
	  "        command:" \
	  "        - /bin/sh" \
	  "        - -c" \
	  "        - |" \
	  "          set -e" \
	  "          mkdir -p /app/storage" \
	  "          python - <<'PY' > /tmp/download-dates.txt" \
	  "          from datetime import datetime, timedelta" \
	  "          import os" \
	  "          start = datetime.strptime(os.environ['START_DATE'], '%Y-%m-%d').date()" \
	  "          end = datetime.strptime(os.environ['END_DATE'], '%Y-%m-%d').date()" \
	  "          if start > end:" \
	  "              raise SystemExit('START_DATE after END_DATE')" \
	  "          cur = start" \
	  "          while cur <= end:" \
	  "              if cur.weekday() in (2, 5):" \
	  "                  print(cur.isoformat())" \
	  "              cur += timedelta(days=1)" \
	  "          PY" \
	  '          PUB_LIST="$${PUBLICATIONS:-$(PUBLICATIONS)}"' \
	  '          while read d; do' \
	  '            [ -z "$$d" ] && continue' \
	  '            echo "Processing edition $$d"' \
	  '            extra=""' \
	  '            if [ "$$FORCE_DOWNLOAD" = "1" ]; then' \
	  '              extra="--force"' \
	  '            fi' \
	  '            OLD_IFS="$$IFS"' \
  '            IFS=,; for pub in $${PUB_LIST}; do' \
  '              pub_trim=$$(echo "$$pub" | sed -e "s/^ *//" -e "s/ *$$//")' \
  '              [ -z "$$pub_trim" ] && continue' \
  '              echo "  -> $$pub_trim"' \
  '              python -m scraper.downloader --date $$d $$extra --publication "$$pub_trim" --storage /app/storage/storage_state.json' \
  '              sleep 3' \
  '            done' \
	  '            IFS="$$OLD_IFS"' \
	  "          done < /tmp/download-dates.txt" \
	  "        volumeMounts:" \
	  "        - name: session-storage" \
	  "          mountPath: /app/storage" \
	  "        - name: scraper-login-override" \
	  "          mountPath: /app/scraper/login.py" \
	  "          subPath: login.py" \
	  "        - name: scraper-discover-override" \
	  "          mountPath: /app/scraper/discover.py" \
	  "          subPath: discover.py" \
	  "  backoffLimit: 0" \
	  "  ttlSecondsAfterFinished: 86400" \
	| kubectl apply -f -; \
echo "Scraper job $$job created. Tail logs with: kubectl logs -f job/$$job -n news-analyzer"

# Split the scrape into multiple jobs across the range.
# Usage: make scrape-range-split START=YYYY-MM-DD END=YYYY-MM-DD [SPLIT=weekly|daily|biweekly] [FORCE=1]
scrape-range-split:
	@if [ -z "$(START)" ] || [ -z "$(END)" ]; then \
		echo "Usage: make scrape-range-split START=YYYY-MM-DD END=YYYY-MM-DD [SPLIT=weekly|daily|biweekly] [FORCE=1]" >&2; \
		exit 1; \
	fi
	@set -e; \
	SPLIT_UNIT=$(or $(SPLIT),weekly); \
	START=$(START) END=$(END) SPLIT=$$SPLIT_UNIT python3 scripts/split_range.py > /tmp/splits.json
	@echo "Creating jobs for split windows..."; \
	jq -c '.[]' /tmp/splits.json | while read win; do \
	  s=$$(echo $$win | jq -r .start); \
	  e=$$(echo $$win | jq -r .end); \
	  ts=$$(date +%Y%m%d%H%M%S)-$${s#????-??-??}-$${e#????-??-??}; \
	  job=scraper-backfill-$$ts; \
	  echo "  -> $$job ($$s..$$e)"; \
	  printf '%s\n' \
	    "apiVersion: batch/v1" \
	    "kind: Job" \
	    "metadata:" \
	    "  name: $$job" \
	    "  namespace: news-analyzer" \
	    "  labels:" \
	    "    app: news-analyzer" \
	    "    component: scraper" \
	    "    type: backfill" \
	    "spec:" \
	    "  template:" \
	    "    metadata:" \
	    "      labels:" \
	    "        app: news-analyzer" \
	    "        component: scraper" \
	    "        type: backfill" \
	    "    spec:" \
	    "      restartPolicy: Never" \
	    "      imagePullSecrets:" \
	    "      - name: harbor-regcred" \
	    "      securityContext:" \
	    "        runAsNonRoot: true" \
	    "        runAsUser: 1000" \
	    "        fsGroup: 1000" \
	    "      volumes:" \
	    "      - name: session-storage" \
	    "        emptyDir: {}" \
	    "      - name: scraper-login-override" \
	    "        configMap:" \
	    "          name: scraper-login-override" \
	    "      - name: scraper-discover-override" \
	    "        configMap:" \
	    "          name: scraper-discover-override" \
	    "      containers:" \
	    "      - name: scraper" \
	    "        image: registry.harbor.lan/library/news-analyzer-scraper:latest" \
	    "        imagePullPolicy: Always" \
	    "        env:" \
	    "        - name: PW_TRACE" \
	    "          value: \"0\"" \
	    "        - name: SCRAPER_PARALLELISM" \
	    "          value: \"2\"" \
	    "        - name: HOME" \
	    "          value: /home/scraper" \
	    "        - name: PLAYWRIGHT_BROWSERS_PATH" \
	    "          value: /home/scraper/.cache/ms-playwright" \
	    "        - name: EEDITION_USER" \
	    "          valueFrom:" \
	    "            secretKeyRef:" \
	    "              name: news-analyzer-secrets" \
	    "              key: EEDITION_USER" \
	    "        - name: EEDITION_PASS" \
	    "          valueFrom:" \
	    "            secretKeyRef:" \
	    "              name: news-analyzer-secrets" \
	    "              key: EEDITION_PASS" \
	    "        - name: SMARTPROXY_USERNAME" \
	    "          valueFrom:" \
	    "            secretKeyRef:" \
	    "              name: news-analyzer-secrets" \
	    "              key: SMARTPROXY_USERNAME" \
	    "        - name: SMARTPROXY_PASSWORD" \
	    "          valueFrom:" \
	    "            secretKeyRef:" \
	    "              name: news-analyzer-secrets" \
	    "              key: SMARTPROXY_PASSWORD" \
	    "        - name: SMARTPROXY_HOST" \
	    "          valueFrom:" \
	    "            configMapKeyRef:" \
	    "              name: news-analyzer-config" \
	    "              key: SMARTPROXY_HOST" \
	    "        - name: MINIO_ENDPOINT" \
	    "          valueFrom:" \
	    "            configMapKeyRef:" \
	    "              name: news-analyzer-config" \
	    "              key: MINIO_ENDPOINT" \
	    "        - name: MINIO_ACCESS_KEY" \
	    "          valueFrom:" \
	    "            secretKeyRef:" \
	    "              name: news-analyzer-secrets" \
	    "              key: MINIO_ACCESS_KEY" \
	    "        - name: MINIO_SECRET_KEY" \
	    "          valueFrom:" \
	    "            secretKeyRef:" \
	    "              name: news-analyzer-secrets" \
	    "              key: MINIO_SECRET_KEY" \
	    "        - name: MINIO_BUCKET" \
	    "          valueFrom:" \
	    "            configMapKeyRef:" \
	    "              name: news-analyzer-config" \
	    "              key: MINIO_BUCKET" \
	    "        - name: SCRAPER_USER_AGENT" \
	    "          valueFrom:" \
	    "            configMapKeyRef:" \
	    "              name: news-analyzer-config" \
	    "              key: SCRAPER_USER_AGENT" \
	    "        - name: START_DATE" \
	    "          value: $$s" \
	    "        - name: END_DATE" \
	    "          value: $$e" \
	    "        - name: FORCE_DOWNLOAD" \
	    "          value: \"$(if $(FORCE),1,0)\"" \
	    "        - name: PUBLICATIONS" \
	    "          value: \"$(PUBLICATIONS)\"" \
	    "        resources:" \
	    "          requests:" \
	    "            memory: \"1Gi\"" \
	    "            cpu: \"2\"" \
	    "          limits:" \
	    "            memory: \"3Gi\"" \
	    "            cpu: \"2\"" \
	    "        command:" \
	    "        - /bin/sh" \
	    "        - -c" \
	    "        - |" \
	    "          set -e" \
	    "          mkdir -p /app/storage" \
	    "          python - <<'PY' > /tmp/download-dates.txt" \
	    "          from datetime import datetime, timedelta" \
	    "          import os" \
	    "          start = datetime.strptime(os.environ['START_DATE'], '%Y-%m-%d').date()" \
	    "          end = datetime.strptime(os.environ['END_DATE'], '%Y-%m-%d').date()" \
	    "          cur = start" \
	    "          while cur <= end:" \
	    "              if cur.weekday() in (2, 5):" \
	    "                  print(cur.isoformat())" \
	    "              cur += timedelta(days=1)" \
	    "          PY" \
	    '          PUB_LIST="$${PUBLICATIONS:-$(PUBLICATIONS)}"' \
	    '          while read d; do' \
	    '            [ -z "$$d" ] && continue' \
	    '            echo "Processing edition $$d"' \
	    '            extra=""' \
	    '            if [ "$$FORCE_DOWNLOAD" = "1" ]; then' \
	    '              extra="--force"' \
	    '            fi' \
	    '            OLD_IFS="$$IFS"' \
	    '            IFS=,; for pub in $${PUB_LIST}; do' \
	    '              pub_trim=$$(echo "$$pub" | sed -e "s/^ *//" -e "s/ *$$//")' \
	    '              [ -z "$$pub_trim" ] && continue' \
	    '              echo "  -> $$pub_trim"' \
	    '              python -m scraper.downloader --date $$d $$extra --publication "$$pub_trim" --storage /app/storage/storage_state.json' \

	    '              sleep 2' \
	    '            done' \
	    '            IFS="$$OLD_IFS"' \
	    "          done < /tmp/download-dates.txt" \
	    "        volumeMounts:" \
	    "        - name: session-storage" \
	    "          mountPath: /app/storage" \
	    "        - name: scraper-login-override" \
	    "          mountPath: /app/scraper/login.py" \
	    "          subPath: login.py" \
	    "        - name: scraper-discover-override" \
	    "          mountPath: /app/scraper/discover.py" \
	    "          subPath: discover.py" \
	    "  backoffLimit: 0" \
	    "  ttlSecondsAfterFinished: 172800" \
	  | kubectl apply -f -; \
	done; \
	echo "Created $$(jq length /tmp/splits.json) split backfill jobs."

# Quick tests through Cloudflare Access service token (reads CF_ACCESS_CLIENT_ID/SECRET from env)
# These avoid jq so they won't error on HTML responses; they show status + first lines.
test-health-access:
	@echo "==> GET https://$(CF_HOST)/health"; \
	CF_ACCESS_HOST=$(CF_HOST) scripts/cf-curl.sh -i /health | sed -n '1,40p'

oauth-start-access:
	@echo "==> GET https://$(CF_HOST)/oauth/reddit/start"; \
	CF_ACCESS_HOST=$(CF_HOST) scripts/cf-curl.sh -i /oauth/reddit/start | sed -n '1,80p'

oauth-status-access:
	@echo "==> GET https://$(CF_HOST)/oauth/reddit/status"; \
	CF_ACCESS_HOST=$(CF_HOST) scripts/cf-curl.sh -i /oauth/reddit/status | sed -n '1,80p'
topup-backfill:
	@set -e; \
	START=$${START:-2025-01-01}; END=$${END:-2025-09-30}; SPLIT=$${SPLIT:-weekly}; \
	kubectl delete job/news-analyzer-ops-backfill-topup -n news-analyzer --ignore-not-found; \
	kubectl apply -f k8s/ops/ops-backfill-topup-job.yaml; \
	kubectl set env job/news-analyzer-ops-backfill-topup -n news-analyzer START=$$START END=$$END SPLIT=$$SPLIT --overwrite; \
	kubectl logs -n news-analyzer -f job/news-analyzer-ops-backfill-topup --tail=100
