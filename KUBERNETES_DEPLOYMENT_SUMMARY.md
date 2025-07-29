# News Analyzer Kubernetes Deployment Summary

## Deployment Status

The news-analyzer application has been successfully deployed to the Kubernetes cluster with the following components:

### ✅ Successfully Running Components

1. **PostgreSQL Database** (postgres-0)
   - Status: Running
   - Service: postgres-service (headless)
   - PVC: Using longhorn storage class

2. **MinIO Object Storage** (minio-0)
   - Status: Running
   - Services: 
     - minio (headless service on ports 9000, 9001)
     - minio-service (ClusterIP on ports 80, 9001)
   - PVC: Using longhorn storage class
   - Bucket setup job: Completed

3. **Ntfy Push Notification Service** (ntfy-6fd587b865-d5ngt)
   - Status: Running
   - Service: ntfy-service (ClusterIP on port 80)
   - PVCs: ntfy-cache and ntfy-data using longhorn storage class

### ⚠️ Components with Image Pull Issues

The following components are experiencing ImagePullBackOff errors due to missing container images:

1. **News Analyzer Extractor** (CronJob)
   - Schedule: Every 15 minutes
   - Image: harbor.lan/news-analyzer/extractor:latest
   - Error: Cannot resolve harbor.lan hostname

2. **News Analyzer Summarizer** (Deployment + CronJob)
   - Deployment: news-analyzer-summarizer (API service)
   - CronJob: news-analyzer-summarizer-batch (runs every 30 minutes)
   - Image: harbor.lan/news-analyzer/summarizer:latest
   - Error: Cannot resolve harbor.lan hostname

3. **News Analyzer Scraper** (CronJob)
   - Schedule: Daily at 10 AM EST
   - Image: harbor.lan/news-analyzer/scraper:latest
   - No active pods yet (scheduled for future)

4. **News Analyzer Auth Refresh** (CronJob)
   - Schedule: Weekly on Sundays at 9 AM EST
   - Image: harbor.lan/news-analyzer/scraper:latest
   - No active pods yet (scheduled for future)

5. **News Analyzer Notifier** (CronJob)
   - Schedule: Daily at 8 AM
   - Image: harbor.lan/news-analyzer/notifier:latest
   - No active pods yet (scheduled for future)

## Key Configuration Updates

### LiteLLM Integration
- The summarizer has been configured to use LiteLLM instead of direct OpenAI API calls
- Environment variable `OPENAI_API_BASE` set to: `http://litellm.litellm.svc.cluster.local:4000`
- The existing `OPENAI_API_KEY` will be used for LiteLLM authentication

### Ntfy Integration
- Replaced SendGrid email service with ntfy push notifications
- Ntfy service URL: `http://ntfy-service.news-analyzer.svc.cluster.local`
- Topic and authentication token configured via secrets

## Resource Quotas and Limits
- Namespace: news-analyzer
- ResourceQuota adjusted: PVC limit increased from 5 to 10
- All deployments configured with appropriate resource requests and limits
- Security contexts applied (non-root user, fsGroup)

## Next Steps

To complete the deployment, you need to:

1. **Build and Push Container Images**
   ```bash
   # Build images for each component
   docker build -t harbor.lan/news-analyzer/scraper:latest ./scraper
   docker build -t harbor.lan/news-analyzer/extractor:latest ./extractor
   docker build -t harbor.lan/news-analyzer/summarizer:latest ./summarizer
   docker build -t harbor.lan/news-analyzer/notifier:latest ./notifier
   
   # Push to your Harbor registry
   docker push harbor.lan/news-analyzer/scraper:latest
   docker push harbor.lan/news-analyzer/extractor:latest
   docker push harbor.lan/news-analyzer/summarizer:latest
   docker push harbor.lan/news-analyzer/notifier:latest
   ```

2. **Verify LiteLLM Service**
   - Ensure LiteLLM is deployed in the `litellm` namespace
   - Verify it's accessible at `http://litellm.litellm.svc.cluster.local:4000`
   - Confirm it has the `gpt-4o-mini` model available

3. **Monitor Initial Runs**
   - The extractor CronJob runs every 15 minutes
   - Check logs: `kubectl logs -n news-analyzer -l component=extractor`
   - Monitor ntfy notifications on your configured topic

## Services Summary

| Service | Type | Port | Purpose |
|---------|------|------|---------|
| postgres-service | Headless | 5432 | PostgreSQL database |
| minio-service | ClusterIP | 80, 9001 | MinIO object storage |
| ntfy-service | ClusterIP | 80 | Push notifications |
| news-analyzer-summarizer-service | ClusterIP | 8000 | Summarizer API |

## CronJob Schedule Summary

| Component | Schedule | Timezone | Purpose |
|-----------|----------|----------|---------|
| scraper | 0 10 * * * | America/New_York | Daily article scraping |
| auth-refresh | 0 9 * * 0 | America/New_York | Weekly auth refresh |
| extractor | 15 * * * * | America/New_York | Hourly PDF extraction |
| summarizer-batch | */30 * * * * | UTC | Batch summarization |
| notifier | 0 8 * * * | UTC | Daily digest notification |

## Troubleshooting

If pods continue to fail after pushing images:
1. Check image pull secrets if using a private registry
2. Verify DNS resolution for harbor.lan in your cluster
3. Review pod logs: `kubectl logs -n news-analyzer <pod-name>`
4. Check events: `kubectl get events -n news-analyzer --sort-by='.lastTimestamp'`