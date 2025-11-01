.PHONY: extractor-run summarizer-run extractor-logs summarizer-logs backfill

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
	@python extractor/backfill.py $(START) $(END) $(if $(FORCE),--force)
