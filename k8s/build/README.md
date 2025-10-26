# In-Cluster Image Builds (Kaniko → Harbor)

This folder provides in-cluster builds using Kaniko, pushing images to `registry.harbor.lan/library`.

What you get
- Nightly CronJobs for each component: builds `latest` and `nightly-YYYYMMDD`
- On-demand Job template: `kaniko-build-job.yaml`
- ConfigMap for repo/ref/registry prefix

Prereqs
- Create a Docker registry secret in `news-analyzer` namespace named `harbor-regcred`:

```
kubectl create secret docker-registry harbor-regcred \
  --docker-server=registry.harbor.lan \
  --docker-username=<HARBOR_USER> \
  --docker-password=<HARBOR_PASS> \
  --docker-email=devnull@example.com \
  -n news-analyzer
```

- Set the repo URL and branch in `builder-configmap.yaml` (HTTPS or SSH). For SSH with a private repo, create a secret named `git-ssh`:

```
# id_rsa: your read-only deploy key; known_hosts optional
kubectl create secret generic git-ssh \
  --from-file=id_rsa=$HOME/.ssh/id_rsa \
  --from-file=known_hosts=$HOME/.ssh/known_hosts \
  -n news-analyzer
```

Apply nightly builders
```
kubectl apply -k k8s/build
kubectl get cronjobs -n news-analyzer
```

Run a one-off build
```
# Example: build extractor with custom tag
kubectl create -f k8s/build/kaniko-build-job.yaml \
  --dry-run=client -o yaml | \
  kubectl set env -f - COMPONENT=extractor TAG=v1.0.0 \
  | kubectl apply -f -
```

Image naming
- Images are pushed as `registry.harbor.lan/library/news-analyzer-<component>:<tag>`
- Components: `scraper`, `extractor`, `notifier`, `summarizer`

Rollout new images
- Use the in-cluster deployer (k8s/ops/ops-deployer-job.yaml) or patch directly:
```
kubectl set image deployment/news-analyzer-summarizer \
  summarizer=registry.harbor.lan/library/news-analyzer-summarizer:v1.0.0 \
  -n news-analyzer
```

Notes
- Kaniko uses an initContainer to clone the repo into an emptyDir, then builds.
- For best performance, consider adding a persistent cache (GCS/Azure/S3 not used here to keep it simple).
- If your Harbor uses self-signed certs, add CA trust to the Kaniko container or configure Harbor with a trusted cert.

