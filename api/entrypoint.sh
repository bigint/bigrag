#!/bin/sh
set -e

# Start Next.js UI in the background
PORT=3000 HOSTNAME=0.0.0.0 node /app/ui/server.js &

# Start the Python API in the foreground
exec python -m bigrag.main --host 0.0.0.0 --port 6000
