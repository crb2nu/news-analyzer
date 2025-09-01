# GitHub Actions Runner Controller (ARC) v2 Deployment Guide

## Overview

This guide covers the deployment and management of GitHub Actions Runner Controller v2 for the news-analyzer project. ARC v2 provides auto-scaling, self-hosted GitHub Actions runners in your Kubernetes cluster.

## Quick Start

### Prerequisites

1. **Kubernetes Cluster** (v1.23+)
2. **kubectl** configured with cluster access
3. **GitHub Personal Access Token** or GitHub App credentials

### Installation Steps

```bash
# 1. Create GitHub Personal Access Token
# Go to: https://github.com/settings/tokens
# Required scopes: repo, workflow

# 2. Export your token
export GITHUB_TOKEN=ghp_your_token_here

# 3. Create namespaces
kubectl apply -f arc-namespace.yaml

# 4. Create GitHub secret
kubectl create secret generic github-pat-secret \
  --from-literal=github_token="$GITHUB_TOKEN" \
  --namespace=arc-runners

# 5. Install CRDs (Custom Resource Definitions)
kubectl apply -f https://github.com/actions/actions-runner-controller/releases/download/gha-runner-scale-set-controller-0.9.3/actions-runner-controller-crds.yaml

# 6. Deploy ARC controller
kubectl apply -f arc-controller.yaml

# 7. Wait for controller to be ready
kubectl wait --for=condition=ready pod -l app.kubernetes.io/name=arc-controller -n arc-systems --timeout=300s

# 8. Configure RBAC for cross-namespace access
kubectl apply -f arc-runner-rbac-news-analyzer.yaml

# 9. Deploy runner scale set
kubectl apply -f arc-runner-scale-set.yaml

# 10. Verify deployment
kubectl get pods -n arc-runners
kubectl get autoscalingrunnersets -n arc-runners
```

## Architecture

```
GitHub.com
    │
    ├── news-analyzer Repository
    │   ├── PR Checks Workflow
    │   ├── Release Workflow
    │   └── Scheduled Tasks Workflow
    │
    └── GitHub API
        │
        ▼
Kubernetes Cluster
    │
    ├── arc-systems namespace
    │   └── ARC Controller (manages runner lifecycle)
    │
    ├── arc-runners namespace
    │   ├── AutoscalingRunnerSet (1-10 runners)
    │   └── Runner Pods (execute workflows)
    │
    └── news-analyzer namespace
        └── Application deployments (target for runners)
```

## Configuration Details

### Runner Labels

The runners are configured with the following labels:
- `self-hosted`
- `linux` 
- `x64`
- `news-analyzer-runners`

Your workflows already use this in `.github/workflows/*.yml`:
```yaml
jobs:
  build:
    runs-on: news-analyzer-runners
```

### Scaling Configuration

The runners auto-scale between 1 and 10 instances based on job demand.

To adjust scaling limits, edit `arc-runner-scale-set.yaml`:
```yaml
spec:
  minRunners: 1   # Minimum idle runners
  maxRunners: 10  # Maximum total runners
```

### Resource Limits

Each runner pod is configured with:
- **Requests**: 500m CPU, 1Gi Memory
- **Limits**: 2 CPU, 4Gi Memory

## Operations

### Check Runner Status

```bash
# List all runner pods
kubectl get pods -n arc-runners

# View runner scale set details
kubectl describe autoscalingrunnersets news-analyzer-runners -n arc-runners

# View runner logs
kubectl logs -n arc-runners -l app=github-runner --tail=50

# Check controller logs
kubectl logs -n arc-systems -l app.kubernetes.io/name=arc-controller
```

### Manual Scaling

```bash
# Scale runners manually
kubectl patch autoscalingrunnersets news-analyzer-runners -n arc-runners \
  --type merge -p '{"spec":{"minRunners":2,"maxRunners":15}}'
```

### Troubleshooting

#### Runner Not Starting

1. Check GitHub authentication:
```bash
kubectl get secret github-pat-secret -n arc-runners
```

2. Check controller logs:
```bash
kubectl logs -n arc-systems -l app.kubernetes.io/name=arc-controller
```

3. Check events:
```bash
kubectl get events -n arc-runners --sort-by='.lastTimestamp'
```

#### Authentication Issues

Test GitHub API access:
```bash
curl -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/crb2nu/news-analyzer
```

#### Resource Issues

Check node capacity:
```bash
kubectl top nodes
kubectl describe nodes
```

## Security Features

- **RBAC**: Runners have limited permissions scoped to required namespaces
- **Pod Security**: Runners run as non-root with security contexts
- **Service Accounts**: Dedicated service accounts for controller and runners
- **Network Isolation**: Can be enhanced with NetworkPolicies if needed

## Monitoring

### View Metrics

```bash
# Port-forward to access controller metrics
kubectl port-forward -n arc-systems svc/arc-controller-metrics 8080:8080

# Access metrics
curl http://localhost:8080/metrics
```

Key metrics to monitor:
- `arc_runner_scale_set_runners_current` - Current runners
- `arc_runner_scale_set_jobs_pending` - Pending jobs
- `arc_runner_scale_set_jobs_running` - Running jobs

## Maintenance

### Update Runner Image

```bash
kubectl set image deployment/news-analyzer-runners \
  runner=ghcr.io/actions/actions-runner:2.320.0 \
  -n arc-runners
```

### Clean Up Old Runner Pods

```bash
# Delete completed pods
kubectl delete pods -n arc-runners --field-selector=status.phase=Succeeded

# Delete failed pods
kubectl delete pods -n arc-runners --field-selector=status.phase=Failed
```

### Backup Configuration

```bash
# Backup all ARC resources
kubectl get all,secrets,configmaps -n arc-systems -o yaml > arc-backup-systems.yaml
kubectl get all,secrets,configmaps -n arc-runners -o yaml > arc-backup-runners.yaml
```

## Migration from Old Runner Setup

If you have the old runner deployments running:

```bash
# 1. Deploy new ARC setup (follow installation steps above)

# 2. Test with a manual workflow run

# 3. Once verified, remove old runners
kubectl delete -f github-runner.yaml
kubectl delete -f github-runner-v2.yaml
kubectl delete -f github-runner-v3.yaml
kubectl delete -f github-runner-rbac.yaml
```

## Uninstallation

To completely remove the ARC setup:

```bash
# Remove runners
kubectl delete -f arc-runner-scale-set.yaml

# Remove RBAC
kubectl delete -f arc-runner-rbac-news-analyzer.yaml

# Remove controller
kubectl delete -f arc-controller.yaml

# Remove namespaces
kubectl delete namespace arc-runners arc-systems

# Remove CRDs (affects all ARC installations)
kubectl delete crd autoscalingrunnersets.actions.github.com
kubectl delete crd ephemeralrunners.actions.github.com
kubectl delete crd ephemeralrunnersets.actions.github.com
```

## Common Issues and Solutions

### Issue: Workflows stuck in "Queued" state
**Solution**: Check runner labels match workflow requirements and runners are running

### Issue: Docker commands fail in runner
**Solution**: Verify Docker socket is mounted correctly in runner pods

### Issue: Runner pods frequently restarting
**Solution**: Check resource limits and node capacity

### Issue: Slow job startup
**Solution**: Increase `minRunners` to keep warm runners available

## Support

- [ARC Documentation](https://docs.github.com/en/actions/hosting-your-own-runners/managing-self-hosted-runners-with-actions-runner-controller)
- [ARC GitHub Repository](https://github.com/actions/actions-runner-controller)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)

## Next Steps

1. Monitor runner performance and adjust scaling as needed
2. Consider implementing persistent tool caches for faster builds
3. Set up monitoring dashboards if using Prometheus/Grafana
4. Configure network policies for enhanced security