#!/bin/sh
set -eu

api_url="${RAG_COMPUTER_URL:-http://localhost:4000}"
escaped_api_url="$(printf "%s" "$api_url" | sed 's/\\/\\\\/g; s/"/\\"/g')"
printf 'window.__RAG_COMPUTER_APP_CONFIG__ = { RAG_COMPUTER_URL: "%s" };\n' "$escaped_api_url" > /usr/share/nginx/html/config.js
connect_src="$(printf "%s" "$api_url" | sed -E 's#^([^/]+//[^/]+).*$#\1#')"
escaped_connect_src="$(printf "%s" "$connect_src" | sed 's/[\/&]/\\&/g')"
sed -i "s/__RAG_COMPUTER_CONNECT_SRC__/$escaped_connect_src/g" /etc/nginx/conf.d/default.conf
