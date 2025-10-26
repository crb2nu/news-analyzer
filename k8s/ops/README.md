# Ops CronJobs (K3s-native)

This folder replaces GitHub scheduled workflows with in-cluster Kubernetes CronJobs for health checks and housekeeping.

What’s included:
- `ops-health-cronjob.yaml`: Runs every 6 hours. Checks pods, pending jobs, Summarizer, MinIO, and PostgreSQL; posts a summary to your ntfy topic.
- `ops-cleanup-cronjob.yaml`: Runs daily at 02:00. Deletes completed jobs older than 7 days, failed jobs older than 3 days, and evicted pods.
- `ops-rbac.yaml`: Minimal Role/RoleBinding and ServiceAccount used by the ops jobs.
- `ops-configmap.yaml`: Python scripts (health_check.py, cleanup.py, deployer.py) mounted into the pods.
- `ops-deployer-job.yaml` (optional): On-demand job to update images of CronJobs/Deployments (replacement for manual-deploy workflow).

Apply (with kustomize):

```
kubectl apply -k k8s/ops
```

Trigger deployer on-demand (override envs as needed):

```
kubectl create -f k8s/ops/ops-deployer-job.yaml \
  --dry-run=client -o yaml | \
  kubectl set env -f - COMPONENT=scraper IMAGE_TAG=v1.2.3 IMAGE_PREFIX=ghcr.io/<owner>/news-analyzer | \
  kubectl apply -f -
```

Notes:
- Health check posts to `http://ntfy-service.news-analyzer.svc.cluster.local/<NTFY_TOPIC>`. Set `NTFY_TOPIC` in `k8s/configmap.yaml` if you want a custom topic.
- PostgreSQL readiness uses `DATABASE_URL` from `news-analyzer-secrets` if present.
- The scripts use Kubernetes in-cluster credentials and only need namespace-scoped RBAC.

