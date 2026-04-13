#!/usr/bin/env bash
set -euo pipefail

BOARDS_DIR="boards"
IMAGES_DIR="images"
DRY_RUN=false
SINGLE_SLUG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run) DRY_RUN=true; shift ;;
    --slug) SINGLE_SLUG="$2"; shift 2 ;;
    *) echo "Usage: $0 [--dry-run] [--slug SLUG]"; exit 1 ;;
  esac
done

if ! command -v python3 &>/dev/null; then echo "python3 required"; exit 1; fi
if ! command -v curl &>/dev/null; then echo "curl required"; exit 1; fi

CANONICAL_PREFIX="https://raw.githubusercontent.com/ne0-asref/ubds-database/main/images/"

for yaml_file in "$BOARDS_DIR"/*.ubds.yaml; do
  slug=$(python3 -c "import yaml; print(yaml.safe_load(open('$yaml_file'))['slug'])")

  if [[ -n "$SINGLE_SLUG" && "$slug" != "$SINGLE_SLUG" ]]; then continue; fi

  image_url=$(python3 -c "
import yaml
d = yaml.safe_load(open('$yaml_file'))
m = d.get('meta', {})
url = m.get('image_url', '')
print(url if url else '')
" 2>/dev/null || echo "")

  # Skip if no URL, already canonical, or already cached
  if [[ -z "$image_url" ]]; then
    echo "SKIP $slug: no image_url"
    continue
  fi
  if [[ "$image_url" == "$CANONICAL_PREFIX"* ]]; then
    echo "SKIP $slug: already canonical URL"
    continue
  fi
  if [[ -f "$IMAGES_DIR/$slug/top-view.png" ]]; then
    echo "SKIP $slug: already cached"
    continue
  fi

  if $DRY_RUN; then
    echo "WOULD FETCH $slug: $image_url → $IMAGES_DIR/$slug/top-view.png"
    continue
  fi

  mkdir -p "$IMAGES_DIR/$slug"
  echo "FETCH $slug: $image_url"
  if curl -fsSL --max-time 30 -o "$IMAGES_DIR/$slug/top-view.png" "$image_url"; then
    echo "  OK: $IMAGES_DIR/$slug/top-view.png"
  else
    echo "  FAIL: could not download $image_url"
    rm -f "$IMAGES_DIR/$slug/top-view.png"
    rmdir "$IMAGES_DIR/$slug" 2>/dev/null || true
  fi
done

echo "Done."
