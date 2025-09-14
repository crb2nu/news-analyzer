# K3s Secret Deployment Guide for News Analyzer

## Overview
This guide provides step-by-step instructions for properly deploying secrets to your K3s cluster for the News Analyzer application. Since this is a private repository with internal hosting, the secrets are tracked in git for convenience, but proper coordination between different secret resources is critical.

## Secret Components

The News Analyzer uses multiple secret resources that must be coordinated:

1. **Main Application Secrets** (`news-analyzer-secrets`)
   - E-edition credentials
   - SmartProxy credentials
   - Database URL
   - MinIO credentials
   - OpenAI API key
   - Notification tokens

2. **PostgreSQL Secrets** (`postgres-secret`)
   - Database password
   - Database connection URL

3. **MinIO Secrets** (`minio-secret`)
   - Root user
   - Root password

## Important: Secret Synchronization

⚠️ **CRITICAL**: The following values MUST match across multiple secret files:

### Database Password
- `k8s/secrets.yaml`: `DATABASE_URL` password portion
- `k8s/postgres-deployment.yaml`: `POSTGRES_PASSWORD` in `postgres-secret`

### MinIO Credentials
- `k8s/secrets.yaml`: `MINIO_ACCESS_KEY` and `MINIO_SECRET_KEY`
- `k8s/minio-statefulset.yaml`: `rootUser` and `rootPassword` in `minio-secret`

## Pre-Deployment Checklist

Before deploying secrets, ensure:

- [ ] K3s cluster is running: `kubectl cluster-info`
- [ ] Namespace exists: `kubectl get namespace news-analyzer`
- [ ] You have the required credentials:
  - [ ] Southwest Virginia Today e-edition login
  - [ ] OpenAI API key with credits
  - [ ] SmartProxy credentials (provided in secrets.yaml)

## Deployment Steps

### Step 1: Create the Namespace (if not exists)

```bash
kubectl apply -f k8s/namespace.yaml
```

### Step 2: Review and Update Secrets

Since the secrets are already configured in the repository:

1. **Review the current secrets:**
   ```bash
   cat k8s/secrets.yaml
   ```

2. **Update any values if needed:**
   - If you need different passwords, update them in ALL related files
   - Ensure OpenAI API key is valid
   - Verify e-edition credentials are correct

3. **For production deployment with different credentials:**
   ```bash
   # Create a local override file (don't commit this)
   cp k8s/secrets.yaml k8s/secrets-local.yaml
   # Edit with your production values
   nano k8s/secrets-local.yaml
   ```

### Step 3: Deploy Secrets in Order

Deploy the secrets in this specific order to ensure dependencies are met:

```bash
# 1. Deploy PostgreSQL secret first
kubectl apply -f k8s/postgres-deployment.yaml --dry-run=client -o yaml | \
  kubectl apply -f - --selector="kind=Secret"

# 2. Deploy MinIO secret
kubectl apply -f k8s/minio-statefulset.yaml --dry-run=client -o yaml | \
  kubectl apply -f - --selector="kind=Secret"

# 3. Deploy main application secrets
kubectl apply -f k8s/secrets.yaml

# 4. Verify all secrets are created
kubectl get secrets -n news-analyzer
```

Expected output:
```
NAME                     TYPE     DATA   AGE
news-analyzer-secrets    Opaque   8      10s
postgres-secret          Opaque   2      20s
minio-secret            Opaque   2      15s
```

### Step 4: Deploy the Complete Stack

Now deploy the rest of the infrastructure:

```bash
# Deploy database
kubectl apply -f k8s/postgres-deployment.yaml

# Deploy MinIO storage
kubectl apply -f k8s/minio-statefulset.yaml

# Deploy ConfigMap
kubectl apply -f k8s/configmap.yaml

# Wait for infrastructure to be ready
kubectl wait --for=condition=ready pod -l component=postgres -n news-analyzer --timeout=300s
kubectl wait --for=condition=ready pod -l component=minio -n news-analyzer --timeout=300s

# Deploy application components
kubectl apply -f k8s/scraper-cronjob.yaml
kubectl apply -f k8s/extractor-cronjob.yaml
kubectl apply -f k8s/summarizer-deployment.yaml
kubectl apply -f k8s/notifier-deployment.yaml
kubectl apply -f k8s/ntfy-deployment.yaml
```

## Verification

### Verify Secret Contents (without exposing values)

```bash
# Check that secrets contain expected keys
kubectl get secret news-analyzer-secrets -n news-analyzer -o jsonpath='{.data}' | jq 'keys'

# Expected keys:
# ["DATABASE_URL", "EEDITION_PASS", "EEDITION_USER", "MINIO_ACCESS_KEY", 
#  "MINIO_SECRET_KEY", "NTFY_TOKEN", "OPENAI_API_KEY", "SLACK_WEBHOOK_URL",
#  "SMARTPROXY_PASSWORD", "SMARTPROXY_USERNAME"]
```

### Test Database Connection

```bash
# Test PostgreSQL connection using the secret
kubectl run psql-test --rm -it --restart=Never \
  --image=postgres:16-alpine \
  --env-from=secretRef/postgres-secret \
  -n news-analyzer \
  -- psql -h postgres-service -U news_analyzer -d news_analyzer -c "SELECT version();"
```

### Test MinIO Connection

```bash
# Test MinIO connection
kubectl run mc-test --rm -it --restart=Never \
  --image=minio/mc:latest \
  --env-from=secretRef/minio-secret \
  -n news-analyzer \
  -- sh -c 'mc alias set test http://minio-service.news-analyzer.svc.cluster.local $MINIO_ROOT_USER $MINIO_ROOT_PASSWORD && mc ls test'
```

## Updating Secrets

To update secrets after deployment:

### Option 1: Delete and Recreate
```bash
kubectl delete secret news-analyzer-secrets -n news-analyzer
kubectl apply -f k8s/secrets.yaml
```

### Option 2: Patch Specific Values
```bash
# Update a single value
kubectl patch secret news-analyzer-secrets -n news-analyzer \
  --type='json' \
  -p='[{"op": "replace", "path": "/data/OPENAI_API_KEY", "value": "'$(echo -n "new-api-key" | base64)'"}]'
```

### Option 3: Edit Directly
```bash
# Opens in your default editor
kubectl edit secret news-analyzer-secrets -n news-analyzer
```

## Rollback Procedure

If secrets cause issues:

```bash
# Save current secrets as backup
kubectl get secret news-analyzer-secrets -n news-analyzer -o yaml > secrets-backup.yaml

# If rollback needed:
kubectl apply -f secrets-backup.yaml
```

## Security Best Practices

Even though this is a private repo with internal hosting:

1. **Rotate credentials periodically**
   - OpenAI API keys every 90 days
   - Database passwords every 180 days
   - E-edition password when prompted by the service

2. **Monitor secret usage**
   ```bash
   # Check which pods are using secrets
   kubectl get pods -n news-analyzer -o json | \
     jq '.items[] | select(.spec.containers[].envFrom[]?.secretRef.name == "news-analyzer-secrets") | .metadata.name'
   ```

3. **Audit secret access**
   ```bash
   # View secret access events
   kubectl get events -n news-analyzer --field-selector involvedObject.kind=Secret
   ```

## Troubleshooting

### Issue: Pod can't access secrets
```bash
# Check if secret exists
kubectl get secret news-analyzer-secrets -n news-analyzer

# Check pod's service account permissions
kubectl get pod <pod-name> -n news-analyzer -o jsonpath='{.spec.serviceAccountName}'

# Restart the pod to reload secrets
kubectl delete pod <pod-name> -n news-analyzer
```

### Issue: Wrong credentials in secret
```bash
# Decode and check current value (be careful not to expose)
kubectl get secret news-analyzer-secrets -n news-analyzer -o jsonpath='{.data.DATABASE_URL}' | base64 -d

# Update and restart affected pods
kubectl apply -f k8s/secrets.yaml
kubectl rollout restart deployment/summarizer -n news-analyzer
```

### Issue: Secret synchronization problems
```bash
# Check all related secrets have matching values
for secret in news-analyzer-secrets postgres-secret minio-secret; do
  echo "=== $secret ==="
  kubectl get secret $secret -n news-analyzer -o yaml | grep -E "POSTGRES_PASSWORD|DATABASE_URL|rootUser|rootPassword|MINIO_"
done
```

## Environment-Specific Configurations

For different environments (dev/staging/prod), you can:

1. **Use different namespaces:**
   ```bash
   # Dev environment
   kubectl apply -f k8s/secrets.yaml -n news-analyzer-dev
   
   # Production environment  
   kubectl apply -f k8s/secrets.yaml -n news-analyzer-prod
   ```

2. **Use Kustomize overlays:**
   ```yaml
   # k8s/overlays/production/kustomization.yaml
   namespace: news-analyzer-prod
   secretGenerator:
   - name: news-analyzer-secrets
     behavior: replace
     files:
     - secrets.env
   ```

3. **Use environment-specific secret files:**
   ```bash
   # Apply based on environment
   kubectl apply -f k8s/secrets-${ENVIRONMENT}.yaml
   ```

## Next Steps

After successfully deploying secrets:

1. Test the scraper authentication:
   ```bash
   kubectl create job --from=cronjob/news-analyzer-scraper-auth test-auth -n news-analyzer
   kubectl logs -f job/test-auth -n news-analyzer
   ```

2. Verify OpenAI connectivity:
   ```bash
   kubectl exec -it deployment/summarizer -n news-analyzer -- python -c "import openai; print('OpenAI connected')"
   ```

3. Set up ntfy notifications (if desired):
   - Follow instructions in `k8s/DEPLOYMENT_GUIDE.md` section 5

## Support

For issues with secret deployment:
1. Check the assessment report: `k8s/K3S_DEPLOYMENT_ASSESSMENT.md`
2. Review application logs: `kubectl logs -n news-analyzer -l app=news-analyzer`
3. Verify K3s cluster health: `kubectl get nodes` and `kubectl get pods -A`