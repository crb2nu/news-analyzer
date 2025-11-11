# 📱 News Analyzer Deployment Guide with iPhone Push Notifications

This guide explains how to deploy the complete news analyzer system to your K3s cluster with free push notifications to your iPhone using self-hosted ntfy.

## 🎯 What This System Does

1. **Daily Scraping** - Automatically downloads Southwest Virginia Today's e-edition
2. **Text Extraction** - Extracts articles from PDFs/HTML with deduplication
3. **AI Summarization** - Uses OpenAI to create concise summaries
4. **Push Notifications** - Sends daily digest to your iPhone via ntfy

## 📋 Prerequisites

- K3s cluster with:
  - `news-analyzer` namespace created
  - MinIO operator in `utilities` namespace
  - `local-path` storage class
  - Ingress controller (nginx)
  - cert-manager for SSL certificates
- iPhone with ntfy app installed
- OpenAI API key with credits
- Southwest Virginia Today e-edition subscription

## 🚀 Deployment Steps

### 1. Create Namespace

```bash
kubectl apply -f k8s/namespace.yaml
```

### 2. Deploy PostgreSQL Database

```bash
# First, edit the password in postgres-deployment.yaml
# Change "changeme-strong-password-here" to a secure password

kubectl apply -f k8s/postgres-deployment.yaml

# Wait for PostgreSQL to be ready
kubectl wait --for=condition=ready pod -l app=news-analyzer,component=postgres -n news-analyzer --timeout=300s

# Initialize the database
kubectl apply -f k8s/postgres-deployment.yaml --dry-run=client -o yaml | kubectl create -f -
```

### 3. Deploy MinIO for Object Storage

Since we're using the MinIO operator:

```bash
# First, edit the credentials in minio-tenant.yaml
# Change the accesskey and secretkey to secure values

kubectl apply -f k8s/minio-tenant.yaml

# Wait for MinIO to be ready
kubectl wait --for=condition=ready pod -l v1.min.io/tenant=news-analyzer-minio -n news-analyzer --timeout=300s
```

### 4. Deploy ntfy for Push Notifications

```bash
# First, update the base-url in ntfy-deployment.yaml
# Change "ntfy.yourdomain.com" to your actual domain

kubectl apply -f k8s/ntfy-deployment.yaml

# Wait for ntfy to be ready
kubectl wait --for=condition=ready pod -l app=news-analyzer,component=ntfy -n news-analyzer --timeout=300s
```

### 5. Set Up iPhone Push Notifications

1. **Configure ntfy server:**
   ```bash
   # Create a user for the news analyzer
   kubectl exec -it deployment/ntfy -n news-analyzer -- ntfy user add news-analyzer
   # Enter a secure password when prompted
   
   # Grant access to the news-digest topic
   kubectl exec -it deployment/ntfy -n news-analyzer -- ntfy access news-analyzer news-digest write
   ```

2. **Set up iPhone:**
   - Download ntfy from the App Store
   - Open the app and go to Settings
   - Change "Default server" to `https://ntfy.yourdomain.com`
   - Subscribe to the "news-digest" topic
   - Enable notifications in iOS Settings > ntfy

### 6. Create Secrets

```bash
# Copy the template
cp k8s/secrets-template.yaml k8s/secrets.yaml

# Edit k8s/secrets.yaml with your actual credentials:
# - EEDITION_USER: Your swvatoday.com email
# - EEDITION_PASS: Your swvatoday.com password
# - DATABASE_URL: Update password to match postgres-secret
# - MINIO_ACCESS_KEY/SECRET_KEY: Match minio-creds-secret
# - OPENAI_API_KEY: Your OpenAI API key

# Apply the secrets
kubectl apply -f k8s/secrets.yaml

# IMPORTANT: Add to .gitignore
echo "k8s/secrets.yaml" >> .gitignore
```

### 7. Deploy Application Components

```bash
# Deploy ConfigMap
kubectl apply -f k8s/configmap.yaml

# Deploy Scraper (daily download + weekly auth refresh)
kubectl apply -f k8s/scraper-cronjob.yaml

# Deploy Extractor (processes PDFs/HTML)
kubectl apply -f k8s/extractor-job.yaml

# Deploy Summarizer (AI service)
kubectl apply -f k8s/summarizer-deployment.yaml

# Deploy Notifier (sends push notifications)
kubectl apply -f k8s/notifier-deployment.yaml
```

### 8. Build and Push Docker Images

```bash
# Set your registry
export REGISTRY=harbor.lan/news-analyzer

# Build and push all images
docker build -f Dockerfile -t $REGISTRY/scraper:latest .
docker build -f extractor/Dockerfile -t $REGISTRY/extractor:latest .
docker build -f summarizer/Dockerfile -t $REGISTRY/summarizer:latest .
docker build -f notifier/Dockerfile -t $REGISTRY/notifier:latest .

docker push $REGISTRY/scraper:latest
docker push $REGISTRY/extractor:latest
docker push $REGISTRY/summarizer:latest
docker push $REGISTRY/notifier:latest
```

## 📱 Testing Push Notifications

```bash
# Test ntfy directly
kubectl exec -it deployment/ntfy -n news-analyzer -- \
  curl -d "Test notification from news analyzer" \
  http://localhost/news-digest

# Run manual notification job
kubectl create job --from=cronjob/news-analyzer-notifier-daily \
  test-notifier -n news-analyzer
```

## 🔧 Configuration Options

### Notification Schedule
Edit the cron schedule in `k8s/notifier-deployment.yaml`:
```yaml
schedule: "0 11 * * *"  # 7:00 AM EST daily
```

### OpenAI/LiteLLM Model
Use the LiteLLM route alias in `k8s/configmap.yaml` so you can switch backends centrally:
```yaml
OPENAI_MODEL: "active"  # LiteLLM alias; retarget in LiteLLM config
```

### Storage Retention
Adjust cache retention in `k8s/configmap.yaml`:
```yaml
CACHE_RETENTION_DAYS: "7"
```

## 🔍 Monitoring

```bash
# Check pod status
kubectl get pods -n news-analyzer

# View scraper logs
kubectl logs -l app=news-analyzer,component=scraper -n news-analyzer

# View summarizer logs
kubectl logs -l app=news-analyzer,component=summarizer -n news-analyzer

# Check cronjob schedules
kubectl get cronjobs -n news-analyzer
```

## 🚨 Troubleshooting

### No Push Notifications
1. Check ntfy logs: `kubectl logs deployment/ntfy -n news-analyzer`
2. Verify iPhone app is connected to your server
3. Check topic subscription in the app
4. Test with curl command above

### Scraper Failures
1. Verify credentials: `kubectl get secret news-analyzer-secrets -n news-analyzer -o yaml`
2. Check proxy is working: `kubectl logs -l component=scraper -n news-analyzer`
3. Manual login test: `kubectl exec -it <scraper-pod> -- python -m scraper.login`

### Database Issues
1. Check PostgreSQL: `kubectl logs statefulset/postgres -n news-analyzer`
2. Connect manually: `kubectl exec -it postgres-0 -n news-analyzer -- psql -U news_analyzer`

## 💰 Cost Optimization

- **OpenAI**: Using gpt-4o-mini keeps costs under $5/month
- **Storage**: MinIO with 50GB storage is sufficient for months of articles
- **Compute**: Total resource usage ~2 CPU cores and 4GB RAM

## 🔒 Security Notes

- All credentials are stored in Kubernetes secrets
- ntfy uses authentication to prevent unauthorized access
- Database is not exposed outside the cluster
- SmartProxy provides anonymity for scraping

## 📱 Daily Usage

Once deployed, you'll receive:
- **7:00 AM Daily**: Push notification with news summary
- **Notification includes**: Top 3 articles with brief summaries
- **Click to read**: Opens full e-edition website

The system runs automatically - just ensure your iPhone has notifications enabled!
