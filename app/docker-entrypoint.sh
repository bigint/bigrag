#!/bin/sh
set -eu

api_url="${BIGRAG_URL:-http://localhost:4000}"
escaped_api_url="$(printf "%s" "$api_url" | sed 's/\\/\\\\/g; s/"/\\"/g')"
printf 'window.__BIGRAG_APP_CONFIG__ = { BIGRAG_URL: "%s" };\n' "$escaped_api_url" > /usr/share/nginx/html/config.js
