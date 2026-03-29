#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

cleanup() {
  echo -e "\n${YELLOW}Shutting down...${NC}"
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  docker compose -f "$ROOT_DIR/docker-compose.yml" down 2>/dev/null || true
  echo -e "${GREEN}All services stopped.${NC}"
}

trap cleanup EXIT INT TERM

# --- Docker services (MinIO) ---
echo -e "${CYAN}Starting Docker services (MinIO)...${NC}"
docker compose -f "$ROOT_DIR/docker-compose.yml" up minio -d

# Wait for MinIO to be healthy
echo -e "${CYAN}Waiting for MinIO...${NC}"
for i in $(seq 1 30); do
  if curl -sf http://localhost:9000/minio/health/live > /dev/null 2>&1; then
    echo -e "${GREEN}MinIO is ready.${NC}"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo -e "${RED}MinIO failed to start.${NC}"
    exit 1
  fi
  sleep 1
done

# --- Config ---
if [ ! -f "$ROOT_DIR/bigrag.toml" ]; then
  echo -e "${YELLOW}No bigrag.toml found, copying from example...${NC}"
  cp "$ROOT_DIR/bigrag.example.toml" "$ROOT_DIR/bigrag.toml"
fi

# --- Rust backend ---
echo -e "${CYAN}Starting Rust backend (cargo run)...${NC}"
(cd "$ROOT_DIR" && cargo run --release 2>&1 | sed "s/^/[backend] /") &
PIDS+=($!)

# --- UI ---
echo -e "${CYAN}Starting Next.js UI...${NC}"
(cd "$ROOT_DIR/ui" && pnpm dev 2>&1 | sed "s/^/[ui] /") &
PIDS+=($!)

echo -e "${GREEN}All services started:${NC}"
echo -e "  Backend  → http://localhost:8080"
echo -e "  UI       → http://localhost:3000"
echo -e "  MinIO    → http://localhost:9001 (console)"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services.${NC}"

wait
