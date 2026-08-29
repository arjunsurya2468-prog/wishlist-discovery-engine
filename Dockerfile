FROM python:3.14-slim

WORKDIR /opt/app

# Runtime-only dependencies — no umap/hdbscan/sklearn/numba/gspread/firecrawl.
# Keeps the image under the 512 MB free-tier RAM cap.
COPY requirements-runtime.txt .
RUN pip install --no-cache-dir -r requirements-runtime.txt

# Copy only what the running app needs:
# - pipeline/ for the shared normalize/embed/assign code the live path calls
# - app/ for backend + frontend + static assets (incl. live_fallback/ and analysis.json)
# - data/taxonomy/ for the locked centroids the live run assigns against (~4.4 MB)
COPY pipeline/ ./pipeline/
COPY app/ ./app/
COPY data/taxonomy/ ./data/taxonomy/

EXPOSE 8080

# Render injects $PORT; default 8080 for local docker-run.
CMD ["sh", "-c", "python -m uvicorn app.backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
