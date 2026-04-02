#!/usr/bin/env bash
set -eo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

cleanup() {
  echo -e "\n${YELLOW}Shutting down...${NC}"
  for pid in "${PIDS[@]+"${PIDS[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  docker compose -f "$ROOT_DIR/docker-compose.yml" down 2>/dev/null || true
  echo -e "${GREEN}All services stopped.${NC}"
}

trap cleanup EXIT INT TERM

# --- Kill stale processes on dev ports ---
for port in 8080 3000; do
  stale=$(lsof -ti:"$port" 2>/dev/null || true)
  if [ -n "$stale" ]; then
    echo -e "${YELLOW}Killing stale process(es) on port $port${NC}"
    echo "$stale" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
done

# --- Preflight checks ---
for cmd in docker python3 pnpm curl; do
  if ! command -v "$cmd" > /dev/null 2>&1; then
    echo -e "${RED}Required command not found: $cmd${NC}"
    exit 1
  fi
done

# --- Docker services ---
echo -e "${CYAN}Starting Docker services (Postgres, Redis, Milvus)...${NC}"
docker compose -f "$ROOT_DIR/docker-compose.yml" up postgres redis milvus-etcd milvus -d

# Wait for Postgres
echo -e "${CYAN}Waiting for Postgres...${NC}"
for i in $(seq 1 30); do
  if docker exec bigrag-postgres pg_isready -U bigrag > /dev/null 2>&1; then
    echo -e "${GREEN}Postgres is ready.${NC}"
    break
  fi
  if [ "$i" -eq 30 ]; then echo -e "${RED}Postgres failed to start.${NC}"; exit 1; fi
  sleep 1
done

# Wait for Redis
echo -e "${CYAN}Waiting for Redis...${NC}"
for i in $(seq 1 15); do
  if docker exec bigrag-redis redis-cli ping > /dev/null 2>&1; then
    echo -e "${GREEN}Redis is ready.${NC}"
    break
  fi
  if [ "$i" -eq 15 ]; then echo -e "${RED}Redis failed to start.${NC}"; exit 1; fi
  sleep 1
done

# Wait for Milvus
echo -e "${CYAN}Waiting for Milvus...${NC}"
for i in $(seq 1 60); do
  if curl -sf http://localhost:9091/healthz > /dev/null 2>&1; then
    echo -e "${GREEN}Milvus is ready.${NC}"
    break
  fi
  if [ "$i" -eq 60 ]; then echo -e "${RED}Milvus failed to start within 60s.${NC}"; exit 1; fi
  sleep 1
done

DATABASE_URL="postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable"
MILVUS_URI="http://localhost:19530"
REDIS_URL="redis://localhost:6379/0"

# --- Python backend ---
echo -e "${CYAN}Setting up Python backend...${NC}"
if [ ! -d "$ROOT_DIR/api/.venv" ]; then
  echo -e "${CYAN}Creating virtual environment...${NC}"
  python3 -m venv "$ROOT_DIR/api/.venv"
fi
source "$ROOT_DIR/api/.venv/bin/activate"

echo -e "${CYAN}Installing Python dependencies...${NC}"
pip install -e "$ROOT_DIR/api" --quiet

echo -e "${CYAN}Starting Python backend (auto-reload)...${NC}"
BIGRAG_DATABASE_URL="$DATABASE_URL" \
BIGRAG_MILVUS_URI="$MILVUS_URI" \
BIGRAG_REDIS_URL="$REDIS_URL" \
PYTHONUNBUFFERED=1 \
python -m uvicorn bigrag.main:create_app \
  --factory --host 0.0.0.0 --port 8080 \
  --reload --reload-dir "$ROOT_DIR/api/bigrag" \
  --log-level info 2>&1 | while IFS= read -r line; do printf '[backend] %s\n' "$line"; done &
PIDS+=($!)

# Wait for backend
echo -e "${CYAN}Waiting for backend...${NC}"
for i in $(seq 1 120); do
  if curl -sf http://localhost:8080/health > /dev/null 2>&1; then
    echo -e "${GREEN}Backend is ready.${NC}"
    break
  fi
  if [ "$i" -eq 120 ]; then echo -e "${RED}Backend failed to start within 120s.${NC}"; exit 1; fi
  sleep 1
done

# --- UI ---
echo -e "${CYAN}Installing UI dependencies...${NC}"
(cd "$ROOT_DIR/ui" && pnpm install --frozen-lockfile 2>&1 | tail -1)

echo -e "${CYAN}Starting Next.js UI...${NC}"
(cd "$ROOT_DIR/ui" && pnpm dev 2>&1 | while IFS= read -r line; do printf '[ui] %s\n' "$line"; done) &
PIDS+=($!)

echo -e "${GREEN}All services started:${NC}"
echo -e "  Backend  → http://localhost:8080"
echo -e "  API Docs → http://localhost:8080/docs"
echo -e "  UI       → http://localhost:3000"
echo -e "  Postgres → localhost:5432"
echo -e "  Redis    → localhost:6379"
echo -e "  Milvus   → localhost:19530"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services.${NC}"

wait
