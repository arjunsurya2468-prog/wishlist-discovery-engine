#!/usr/bin/env bash
# Build the static mirror for Netlify — copies the frontend + analysis.json +
# live_fallback into a self-contained public/ directory. No backend, no API.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
OUT="$ROOT/public"

rm -rf "$OUT"
mkdir -p "$OUT/static"

# Frontend files
cp "$ROOT/app/frontend/index.html" "$OUT/"
cp "$ROOT/app/frontend/app.js"     "$OUT/"
cp "$ROOT/app/frontend/styles.css" "$OUT/"

# The dashboard is the entire frontend. It is backend-less here by design: the Live Run
# tab calls /api/live-run, which the _redirects below proxy to the Render service. With
# the proxy in place the mirror is fully functional; without it every other tab still
# renders, because they read the static analysis.json.

# Static data (the pre-computed analysis + fallback samples)
cp "$ROOT/app/static/analysis.json" "$OUT/static/"
if [ -d "$ROOT/app/static/live_fallback" ]; then
    cp -r "$ROOT/app/static/live_fallback" "$OUT/static/"
fi

# Generate Netlify _redirects to proxy backend API calls and engine routes to Render
cat << 'EOF' > "$OUT/_redirects"
/healthz    https://wishlist-discovery-engine.onrender.com/healthz   200
/api/*      https://wishlist-discovery-engine.onrender.com/api/:splat 200
EOF

echo "Static build complete → $OUT/"
ls -lh "$OUT/"
ls -lh "$OUT/static/"
