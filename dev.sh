#!/usr/bin/env bash
set -eo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

# --- Parse flags ---
START_INFRA=false
START_BACKEND=false
START_WEBSITE=false
NO_INSTALL=false

if [ $# -eq 0 ]; then
  START_INFRA=true
  START_BACKEND=true
  START_WEBSITE=true
else
  for arg in "$@"; do
    case "$arg" in
      --infra)    START_INFRA=true ;;
      --backend)  START_INFRA=true; START_BACKEND=true ;;
      --website)  START_WEBSITE=true ;;
      --no-install) NO_INSTALL=true ;;
      --help|-h)
        echo "Usage: ./dev.sh [flags]"
        echo "  (no flags)    Start everything (infra + backend + website)"
        echo "  --infra       Start only Docker services"
        echo "  --backend     Start Docker services + Python backend"
        echo "  --website     Start only the docs website"
        echo "  --no-install  Skip dependency installation"
        exit 0
        ;;
      *)
        echo -e "${RED}Unknown flag: $arg${NC}"
        exit 1
        ;;
    esac
  done
fi

cleanup() {
  echo -e "\n${YELLOW}Shutting down...${NC}"
  for pid in "${PIDS[@]+"${PIDS[@]}"}"; do
    kill "$pid" 2>/dev/null || true
  done
  if [ "$START_INFRA" = true ]; then
    docker compose -f "$ROOT_DIR/docker-compose.yml" down 2>/dev/null || true
  fi
  echo -e "${GREEN}All services stopped.${NC}"
}

trap cleanup EXIT INT TERM

# --- Kill stale processes on dev ports ---
if [ "$START_BACKEND" = true ] || [ "$START_WEBSITE" = true ]; then
  ports=()
  [ "$START_BACKEND" = true ] && ports+=(6100)
  [ "$START_WEBSITE" = true ] && ports+=(3100)
  for port in "${ports[@]}"; do
    stale=$(lsof -ti:"$port" 2>/dev/null || true)
    if [ -n "$stale" ]; then
      echo -e "${YELLOW}Killing stale process(es) on port $port${NC}"
      echo "$stale" | xargs kill -9 2>/dev/null || true
      sleep 1
    fi
  done
fi

# --- Preflight checks ---
if [ "$START_INFRA" = true ]; then
  for cmd in docker curl; do
    if ! command -v "$cmd" > /dev/null 2>&1; then
      echo -e "${RED}Required command not found: $cmd${NC}"
      exit 1
    fi
  done
fi
if [ "$START_BACKEND" = true ]; then
  if ! command -v uv > /dev/null 2>&1; then
    echo -e "${RED}Required command not found: uv${NC}"
    exit 1
  fi
fi
if [ "$START_WEBSITE" = true ]; then
  if ! command -v pnpm > /dev/null 2>&1; then
    echo -e "${RED}Required command not found: pnpm${NC}"
    exit 1
  fi
fi

# --- Docker services ---
if [ "$START_INFRA" = true ]; then
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
fi

DATABASE_URL="postgres://bigrag:bigrag@localhost:5433/bigrag?sslmode=disable"
MILVUS_URI="http://localhost:19530"
REDIS_URL="redis://localhost:6380/0"

# --- Python backend ---
if [ "$START_BACKEND" = true ]; then
  echo -e "${CYAN}Setting up Python backend...${NC}"

  if [ "$NO_INSTALL" = false ]; then
    echo -e "${CYAN}Installing Python dependencies...${NC}"
    uv sync --directory "$ROOT_DIR/api" --quiet
  fi

  echo -e "${CYAN}Starting Python backend (auto-reload)...${NC}"
  BIGRAG_DATABASE_URL="$DATABASE_URL" \
  BIGRAG_MILVUS_URI="$MILVUS_URI" \
  BIGRAG_REDIS_URL="$REDIS_URL" \
  PYTHONUNBUFFERED=1 \
  uv run --directory "$ROOT_DIR/api" uvicorn bigrag.main:create_app \
    --factory --host 0.0.0.0 --port 6100 \
    --reload --reload-dir "$ROOT_DIR/api/bigrag" \
    --log-level info 2>&1 | while IFS= read -r line; do printf '[backend] %s\n' "$line"; done &
  PIDS+=($!)

  # Wait for backend
  echo -e "${CYAN}Waiting for backend...${NC}"
  for i in $(seq 1 120); do
    if curl -sf http://localhost:6100/health > /dev/null 2>&1; then
      echo -e "${GREEN}Backend is ready.${NC}"
      break
    fi
    if [ "$i" -eq 120 ]; then echo -e "${RED}Backend failed to start within 120s.${NC}"; exit 1; fi
    sleep 1
  done
fi

# --- Website dev server ---
if [ "$START_WEBSITE" = true ]; then
  if [ "$NO_INSTALL" = false ]; then
    echo -e "${CYAN}Installing website dependencies...${NC}"
    pnpm --filter @bigrag/docs install --silent
  fi

  echo -e "${CYAN}Starting website dev server...${NC}"
  pnpm --filter @bigrag/docs dev 2>&1 | while IFS= read -r line; do printf '[website] %s\n' "$line"; done &
  PIDS+=($!)
fi

echo -e "\n${GREEN}Services started:${NC}"
[ "$START_BACKEND" = true ] && echo -e "  Backend  → http://localhost:6100"
[ "$START_BACKEND" = true ] && echo -e "  API Docs → http://localhost:6100/docs"
[ "$START_INFRA" = true ]   && echo -e "  Postgres → localhost:5433"
[ "$START_INFRA" = true ]   && echo -e "  Redis    → localhost:6380"
[ "$START_INFRA" = true ]   && echo -e "  Milvus   → localhost:19530"
[ "$START_WEBSITE" = true ] && echo -e "  Website  → http://localhost:3100"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services.${NC}"

wait
