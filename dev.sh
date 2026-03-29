#!/usr/bin/env bash
set -eo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

# Source cargo env if present
[ -f "$HOME/.cargo/env" ] && source "$HOME/.cargo/env"

cleanup() {
  echo -e "\n${YELLOW}Shutting down...${NC}"
  for pid in "${PIDS[@]+"${PIDS[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  docker compose -f "$ROOT_DIR/docker-compose.yml" down 2>/dev/null || true
  echo -e "${GREEN}All services stopped.${NC}"
}

trap cleanup EXIT INT TERM

# --- Preflight checks ---
for cmd in docker cargo pnpm curl; do
  if ! command -v "$cmd" > /dev/null 2>&1; then
    echo -e "${RED}Required command not found: $cmd${NC}"
    exit 1
  fi
done

# --- Docker services (Postgres + MinIO) ---
echo -e "${CYAN}Starting Docker services (Postgres, MinIO)...${NC}"
docker compose -f "$ROOT_DIR/docker-compose.yml" up postgres minio -d

# Wait for Postgres to be healthy
echo -e "${CYAN}Waiting for Postgres...${NC}"
for i in $(seq 1 30); do
  if docker exec bigrag-postgres pg_isready -U bigrag > /dev/null 2>&1; then
    echo -e "${GREEN}Postgres is ready.${NC}"
    break
  fi
  if [ "$i" -eq 30 ]; then
    echo -e "${RED}Postgres failed to start.${NC}"
    exit 1
  fi
  sleep 1
done

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

DATABASE_URL="postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable"

# --- Config ---
if [ ! -f "$ROOT_DIR/bigrag.toml" ]; then
  echo -e "${YELLOW}No bigrag.toml found, copying from example...${NC}"
  cp "$ROOT_DIR/bigrag.example.toml" "$ROOT_DIR/bigrag.toml"
fi

# --- Rust backend ---
echo -e "${CYAN}Building Rust backend...${NC}"
(cd "$ROOT_DIR" && cargo build 2>&1 | sed "s/^/[build] /")

echo -e "${CYAN}Starting Rust backend...${NC}"
(cd "$ROOT_DIR" && cargo run -- --database-url "$DATABASE_URL" 2>&1 | sed "s/^/[backend] /") &
PIDS+=($!)

# Wait for backend to be ready
echo -e "${CYAN}Waiting for backend...${NC}"
for i in $(seq 1 60); do
  if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}Backend is ready.${NC}"
    break
  fi
  if [ "$i" -eq 60 ]; then
    echo -e "${RED}Backend failed to start within 60s.${NC}"
    exit 1
  fi
  sleep 1
done

# --- UI ---
echo -e "${CYAN}Starting Next.js UI...${NC}"
(cd "$ROOT_DIR/ui" && pnpm dev 2>&1 | sed "s/^/[ui] /") &
PIDS+=($!)

echo -e "${GREEN}All services started:${NC}"
echo -e "  Backend  → http://localhost:8080"
echo -e "  UI       → http://localhost:3000"
echo -e "  Postgres → localhost:5432"
echo -e "  MinIO    → http://localhost:9001 (console)"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services.${NC}"

wait
