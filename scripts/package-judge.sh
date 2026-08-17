#!/bin/bash

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
downloads_dir="$repo_root/apps/web/downloads"
temp_dir="$(mktemp -d)"
judge_api_origin="${WANT_API_ORIGIN:?Set WANT_API_ORIGIN to the deployed HTTPS API URL}"

cleanup() {
  if [[ -n "${temp_dir:-}" && -d "$temp_dir" && "$temp_dir" == /tmp/* ]]; then
    rm -rf -- "$temp_dir"
  fi
}
trap cleanup EXIT

mkdir -p "$downloads_dir"

if [[ "$judge_api_origin" != https://* ]]; then
  echo "WANT_API_ORIGIN must be an HTTPS URL."
  exit 1
fi

VITE_API_ORIGIN="$judge_api_origin" pnpm --dir "$repo_root" build

extension_archive="$downloads_dir/want-chrome.zip"
firefox_archive="$downloads_dir/want-firefox.zip"
macos_installer_archive="$downloads_dir/want-installer-macos.zip"
windows_installer_archive="$downloads_dir/want-installer-windows.zip"

rm -f -- "$extension_archive" "$firefox_archive" "$macos_installer_archive" "$windows_installer_archive"

(
  cd "$repo_root/apps/extension/dist/chrome"
  zip -qr "$extension_archive" .
)

(
  cd "$repo_root/apps/extension/dist/firefox"
  zip -qr "$firefox_archive" .
)

chmod +x "$downloads_dir/install-want.command"
cp "$downloads_dir/install-want.command" "$temp_dir/install-want.command"
(
  cd "$temp_dir"
  zip -q "$macos_installer_archive" install-want.command
)

cp "$downloads_dir/install-want-windows.cmd" "$temp_dir/install-want-windows.cmd"
(
  cd "$temp_dir"
  zip -q "$windows_installer_archive" install-want-windows.cmd
)

unzip -tq "$extension_archive"
unzip -tq "$firefox_archive"
unzip -tq "$macos_installer_archive"
unzip -tq "$windows_installer_archive"

echo "Judge packages are ready in $downloads_dir"
