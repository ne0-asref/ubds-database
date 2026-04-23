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

fetch_one() {
  local slug="$1"
  local stem="$2"  # top-view | pinout
  local url="$3"
  local dest="$IMAGES_DIR/$slug/$stem.png"

  if [[ -z "$url" ]]; then
    echo "SKIP $slug $stem: no URL"
    return 0
  fi
  if [[ "$url" == "$CANONICAL_PREFIX$slug/$stem.png" ]]; then
    echo "SKIP $slug $stem: already canonical"
    return 0
  fi
  if [[ -f "$dest" ]]; then
    echo "SKIP $slug $stem: already cached"
    return 0
  fi
  if $DRY_RUN; then
    echo "WOULD FETCH $slug $stem: $url → $dest"
    return 0
  fi
  mkdir -p "$IMAGES_DIR/$slug"
  echo "FETCH $slug $stem: $url"
  if curl -fsSL --max-time 30 -o "$dest" "$url"; then
    echo "  OK: $dest"
  else
    echo "  FAIL: could not download $url"
    rm -f "$dest"
    rmdir "$IMAGES_DIR/$slug" 2>/dev/null || true
  fi
}

for yaml_file in "$BOARDS_DIR"/*.ubds.yaml; do
  slug=$(python3 -c "import yaml; print(yaml.safe_load(open('$yaml_file'))['slug'])")

  if [[ -n "$SINGLE_SLUG" && "$slug" != "$SINGLE_SLUG" ]]; then continue; fi

  image_url=$(python3 -c "
import yaml
d = yaml.safe_load(open('$yaml_file'))
m = d.get('meta', {}) or {}
url = m.get('image_url', '') or ''
print(url)
" 2>/dev/null || echo "")
  fetch_one "$slug" top-view "$image_url"

  pinout_url=$(python3 -c "
import yaml
d = yaml.safe_load(open('$yaml_file'))
m = d.get('meta', {}) or {}
url = m.get('pinout_image_url', '') or ''
print(url)
" 2>/dev/null || echo "")
  fetch_one "$slug" pinout "$pinout_url"
done

echo "Done."
