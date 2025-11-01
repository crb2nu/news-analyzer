.PHONY: extractor-run summarizer-run extractor-logs summarizer-logs backfill

ROOT := $(CURDIR)
SYS_PYTHON := $(or $(shell command -v python3.13),$(shell command -v python3.12),$(shell command -v python3.11),$(shell command -v python3))

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
	@if [ -z "$(SYS_PYTHON)" ]; then \
		echo "python3 not found in PATH" >&2; exit 1; \
	fi
	@rm -rf extractor/.backfill-venv
	@$(SYS_PYTHON) -m venv extractor/.backfill-venv
	@. extractor/.backfill-venv/bin/activate; \
	pip install -q --disable-pip-version-check poetry; \
	set -a; [ -f .env ] && . .env; set +a; \
	cd "$(ROOT)/extractor" && poetry install --no-root >/dev/null; \
	cd "$(ROOT)/extractor" && PYTHONPATH=.. poetry run python backfill.py $(START) $(END) $(if $(FORCE),--force)
