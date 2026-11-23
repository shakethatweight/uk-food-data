#!/usr/bin/env bash
# Build the UK CSV from the Open Food Facts export and publish it as a GitHub Release.
# Usage: publish.sh [WORKDIR]   (default /var/www/shared/uk-food-data-work)
# Needs: python3, gh (authenticated, push access to the repo). Keeps the last 8 releases.
set -euo pipefail

REPO="shakethatweight/uk-food-data"
KEEP=8
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORK="${1:-/var/www/shared/uk-food-data-work}"
OUT="$WORK/out"
TAG="$(TZ=Europe/London date +%F)"

rm -rf "$OUT"
mkdir -p "$OUT"

# Memory-capped in its own cgroup so a runaway dies alone
systemd-run --user --wait --collect -P -p MemoryMax=1500M -p MemorySwapMax=0 -p OOMScoreAdjust=1000 \
  /usr/bin/python3 -I "$HERE/build-off-uk.py" --download "$WORK" --outdir "$OUT"

CSV="$(ls "$OUT"/off-uk-*.csv.gz)"
KEPT="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['rows_kept'])" "$OUT/stats.json")"
if [ "$KEPT" -lt 100000 ]; then
  echo "Only $KEPT rows kept; refusing to publish (expected far more)." >&2
  exit 1
fi

gh release delete "$TAG" --repo "$REPO" --yes --cleanup-tag >/dev/null 2>&1 || true
gh release create "$TAG" "$CSV" "$OUT/stats.json" --repo "$REPO" \
  --title "UK food data $TAG" \
  --notes "Contains data from Open Food Facts, available under the Open Database License (ODbL 1.0). Contents under the Database Contents License. See the README for columns and filters."

# Keep the newest $KEEP releases
gh release list --repo "$REPO" --limit 100 --json tagName,createdAt \
  --jq "sort_by(.createdAt) | reverse | .[$KEEP:] | .[].tagName" |
while read -r old; do
  gh release delete "$old" --repo "$REPO" --yes --cleanup-tag
done
