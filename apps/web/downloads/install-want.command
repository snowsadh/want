#!/bin/bash

set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This judge installer currently supports macOS."
  exit 1
fi

if ! open -Ra "Google Chrome"; then
  echo "Google Chrome was not found. Install Chrome, then run this installer again."
  exit 1
fi

install_root="${HOME:?}/Library/Application Support/WANT"
extension_dir="$install_root/extension"
archive_url="https://snowsadh.github.io/want/downloads/want-chrome.zip"
temp_dir="$(mktemp -d)"

cleanup() {
  if [[ -n "${temp_dir:-}" && -d "$temp_dir" && ( "$temp_dir" == /var/folders/* || "$temp_dir" == /tmp/* ) ]]; then
    rm -rf -- "$temp_dir"
  fi
}
trap cleanup EXIT

mkdir -p "$extension_dir"

echo "Downloading WANT!"
curl -fL "$archive_url" -o "$temp_dir/want-chrome.zip"
unzip -oq "$temp_dir/want-chrome.zip" -d "$extension_dir"

if [[ ! -f "$extension_dir/manifest.json" ]]; then
  echo "The downloaded extension is incomplete. Please try again."
  exit 1
fi

printf '%s' "$extension_dir" | pbcopy
open -R "$extension_dir/manifest.json"
open -a "Google Chrome" "chrome://extensions/"

echo
echo "WANT! is downloaded. The extension folder path is on your clipboard."
echo "Chrome requires one final approval:"
echo "  1. Turn on Developer mode."
echo "  2. Click Load unpacked."
echo "  3. Press Command-Shift-G, paste the copied path, and choose Select."
echo
echo "The judge build connects to the hosted WANT! service automatically."
echo
read -r -p "Press Return to close this window."
