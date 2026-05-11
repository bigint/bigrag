#!/bin/sh
set -eu

api_url="${BIGRAG_URL:-http://localhost:4000}"
escaped_api_url="$(printf "%s" "$api_url" | sed 's/\\/\\\\/g; s/"/\\"/g')"
printf 'window.__BIGRAG_APP_CONFIG__ = { BIGRAG_URL: "%s" };\n' "$escaped_api_url" > /usr/share/nginx/html/config.js
connect_src="$(printf "%s" "$api_url" | sed -E 's#^([^/]+//[^/]+).*$#\1#')"
escaped_connect_src="$(printf "%s" "$connect_src" | sed 's/[\/&]/\\&/g')"
sed -i "s/__BIGRAG_CONNECT_SRC__/$escaped_connect_src/g" /etc/nginx/conf.d/default.conf
