# Deployment Update - Frontend Integration

**Date**: November 7, 2025
**Changes**: Integrated SvelteKit frontend into summarizer Docker image

---

## What Changed

### 1. **Summarizer Dockerfile** - Multi-stage Build

The summarizer Dockerfile now uses a multi-stage build to:
1. **Stage 1 (frontend-builder)**: Build the SvelteKit static site with Node.js 20
2. **Stage 2 (python app)**: Copy the built frontend and serve it via FastAPI

**Key changes:**
- Added Node.js build stage
- Copies `frontend/` source code
- Runs `npm install` and `npm run build`
- Copies built files to `./static/ui` in the Python container
- Total build time increases by ~2-3 minutes (one-time, cached after)

### 2. **Build Script** - Updated Context

Modified `scripts/build-and-push.sh`:
- Changed summarizer build context from `summarizer/` to `.` (repo root)
- This allows Docker to access both `summarizer/` and `frontend/` directories
- Other components (scraper, extractor, notifier) unchanged

### 3. **FastAPI API** - SPA Serving

Updated `summarizer/api.py`:
- Removed old `/` route that served simple HTML
- Added catch-all route `/{full_path:path}` at the END of route registration
- Serves SvelteKit SPA with client-side routing support
- Falls back to `200.html` (or `index.html`) for SPA routes
- Skips API paths to avoid conflicts

**Route Priority:**
1. API routes (`/feed`, `/search`, `/analytics`, etc.) - matched first
2. Static files (`/_app/*`, `/favicon.svg`, etc.) - served directly
3. SPA routes (`/discover`, `/events`, etc.) - fall back to 200.html

### 4. **Docker Ignore Files**

Added `.dockerignore` files to:
- Exclude `node_modules` and build artifacts from Docker context
- Reduce build context size
- Speed up image builds

---

## Build & Deploy

### Local Testing

```bash
# Build the summarizer image with frontend
cd news-analyzer
docker build -f summarizer/Dockerfile -t news-analyzer-summarizer:test .

# Run it
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e OPENAI_API_KEY=... \
  news-analyzer-summarizer:test

# Open http://localhost:8000
# You should see the SvelteKit frontend
```

### Production Build & Push

```bash
# Build all components including updated summarizer
./scripts/build-and-push.sh --push

# Or build just summarizer
./scripts/build-and-push.sh -c summarizer --push

# Tag with specific version
TAG=v1.0.0 ./scripts/build-and-push.sh -c summarizer --push
```

### Deploy to Kubernetes

```bash
# Deploy with updated summarizer image
./scripts/deploy.sh

# Or if summarizer is already deployed, just restart it to pull new image
kubectl -n news-analyzer rollout restart deployment/news-analyzer-summarizer
kubectl -n news-analyzer rollout status deployment/news-analyzer-summarizer

# Check logs
kubectl -n news-analyzer logs -l app=news-analyzer,component=summarizer --tail=50
```

---

## Verification

### 1. Check Image Contents

```bash
# Verify frontend files are in the image
docker run --rm news-analyzer-summarizer:latest ls -la static/ui

# Should show:
# 200.html
# index.html
# _app/
# favicon.svg
# etc.
```

### 2. Test Routes

Once deployed, test these URLs:

**Frontend (SvelteKit SPA):**
- `http://your-domain/` - Feed view
- `http://your-domain/discover` - Discover/search view
- `http://your-domain/events` - Events calendar

**API (FastAPI):**
- `http://your-domain/health` - Health check (JSON)
- `http://your-domain/feed/dates` - Feed dates (JSON)
- `http://your-domain/search?q=test` - Search (JSON)

### 3. Check Logs

```bash
# Look for these log messages:
kubectl -n news-analyzer logs -l component=summarizer | grep -i "serving ui"
# Should show: "Serving UI from: /app/static/ui"

kubectl -n news-analyzer logs -l component=summarizer | grep -i "frontend spa"
# Should show: "Frontend SPA routing enabled"
```

---

## Rollback Plan

If there are issues with the new image:

```bash
# Rollback to previous version
kubectl -n news-analyzer rollout undo deployment/news-analyzer-summarizer

# Or deploy specific previous version
kubectl -n news-analyzer set image deployment/news-analyzer-summarizer \
  summarizer=registry.harbor.lan/library/news-analyzer-summarizer:previous-tag

# Verify rollback
kubectl -n news-analyzer rollout status deployment/news-analyzer-summarizer
```

---

## Troubleshooting

### Frontend Not Loading

**Symptom**: API works, but frontend shows 404 or blank page

**Checks:**
```bash
# 1. Verify frontend files in image
kubectl -n news-analyzer exec -it deployment/news-analyzer-summarizer -- ls -la static/ui

# 2. Check logs for UI serving message
kubectl -n news-analyzer logs -l component=summarizer | grep UI

# 3. Check if 200.html exists
kubectl -n news-analyzer exec -it deployment/news-analyzer-summarizer -- cat static/ui/200.html
```

**Fix:**
- Rebuild image with `--no-cache` if files are missing
- Ensure `frontend/build` directory was created during Docker build

### API Routes Returning HTML Instead of JSON

**Symptom**: `/feed`, `/search`, etc. return HTML instead of JSON

**Cause**: Catch-all SPA route is matching before API routes

**Fix:**
- Check that API routes are registered BEFORE the catch-all `/{full_path:path}`
- Ensure API paths are in the skip list in `serve_spa()` function

### Build Fails with npm Errors

**Symptom**: Docker build fails during `npm install` or `npm run build`

**Checks:**
```bash
# Check if frontend/package.json exists
ls -la frontend/package.json

# Try building frontend locally
cd frontend
npm install
npm run build
```

**Fix:**
- Ensure Node.js 20+ is used in Dockerfile
- Check for network issues during `npm install`
- Verify all frontend dependencies are in package.json

---

## Performance Notes

### Build Time

- **Before**: ~2 minutes (Python dependencies only)
- **After**: ~4-5 minutes (Python + Node.js + frontend build)
- **Subsequent builds**: ~2-3 minutes (Docker layer caching)

**Optimization**: Frontend build is cached unless source files change

### Image Size

- **Before**: ~500MB (Python + dependencies)
- **After**: ~520MB (Python + dependencies + static frontend)
- **Added**: ~20MB (SvelteKit build output)

**Note**: Node.js is NOT in final image (multi-stage build discards it)

### Runtime Performance

- **No impact**: Frontend is static files served by FastAPI
- **FastAPI overhead**: Minimal (StaticFiles middleware is efficient)
- **CDN recommendation**: Serve `/` through CDN/Ingress for better caching

---

## Next Steps

### Optional Enhancements

1. **CDN/Reverse Proxy Caching**
   ```nginx
   # Nginx config for static assets
   location /_app/ {
       proxy_pass http://summarizer:8000;
       proxy_cache_valid 200 1d;
       add_header Cache-Control "public, max-age=31536000, immutable";
   }
   ```

2. **Separate Frontend Service** (if needed)
   - Serve frontend from separate nginx container
   - Point to summarizer API via environment variable
   - Better for high traffic / CDN integration

3. **Frontend Environment Variables**
   - Currently `PUBLIC_API_BASE_URL=""` (relative URLs)
   - Can set to absolute URL in Dockerfile if needed:
     ```dockerfile
     ENV PUBLIC_API_BASE_URL="https://api.your-domain.com"
     RUN npm run build
     ```

---

## Summary

✅ **Completed:**
- Multi-stage Dockerfile for summarizer + frontend
- Build script updated for full repo context
- FastAPI configured for SPA routing
- Docker ignore files for efficient builds

✅ **Tested:**
- Local Docker build
- Frontend serving
- API route preservation
- SPA client-side routing

✅ **Ready for:**
- Production build with `scripts/build-and-push.sh`
- Kubernetes deployment with `scripts/deploy.sh`
- End-to-end testing in cluster

🚀 **Deploy with**: `./scripts/build-and-push.sh -c summarizer --push && kubectl -n news-analyzer rollout restart deployment/news-analyzer-summarizer`
