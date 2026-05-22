#!/usr/bin/env bash
set -eo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
PIDS=()

START_INFRA=false
START_BACKEND=false
START_WEBSITE=false
NO_INSTALL=false
STARTED_INFRA=false

if [ $# -eq 0 ]; then
  START_INFRA=true
  START_BACKEND=true
else
  for arg in "$@"; do
    case "$arg" in
      --infra)    START_INFRA=true ;;
      --backend)  START_INFRA=true; START_BACKEND=true ;;
      --website)  START_WEBSITE=true ;;
      --no-install) NO_INSTALL=true ;;
      --help|-h)
        echo "Usage: ./dev.sh [flags]"
        echo "  (no flags)    Start infra + backend"
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
  if [ "$STARTED_INFRA" = true ]; then
    docker compose -f "$ROOT_DIR/docker-compose.yml" down 2>/dev/null || true
  fi
  echo -e "${GREEN}All services stopped.${NC}"
}

trap cleanup EXIT INT TERM

wait_for() {
  local name="$1"
  local check_cmd="$2"
  local attempts="$3"
  echo -e "${CYAN}Waiting for ${name}...${NC}"
  for i in $(seq 1 "$attempts"); do
    if eval "$check_cmd" > /dev/null 2>&1; then
      echo -e "${GREEN}${name} is ready.${NC}"
      return 0
    fi
    if [ "$i" -eq "$attempts" ]; then
      echo -e "${RED}${name} failed to start within ${attempts}s.${NC}"
      exit 1
    fi
    sleep 1
  done
}

prefix_logs() {
  local tag="$1"
  local color="$CYAN"
  local label="$tag"
  case "$tag" in
    backend) color="$GREEN"; label="api" ;;
    worker) color="$YELLOW"; label="work" ;;
    website) color="$CYAN"; label="docs" ;;
  esac
  while IFS= read -r line; do printf '%b%-5s%b | %s\n' "$color" "$label" "$NC" "$line"; done
}

if [ "$START_BACKEND" = true ] || [ "$START_WEBSITE" = true ]; then
  ports=()
  [ "$START_BACKEND" = true ] && ports+=(4000)
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
if [ "$START_BACKEND" = true ]; then
  stale_workers=$(ps -axo pid=,command= | awk -v root="$ROOT_DIR" '$0 ~ root "/api" && $0 ~ /bigrag-worker/ {print $1}' || true)
  if [ -n "$stale_workers" ]; then
    echo -e "${YELLOW}Killing stale bigrag-worker process(es)${NC}"
    echo "$stale_workers" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
fi

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

if [ "$START_INFRA" = true ]; then
  echo -e "${CYAN}Starting Docker services (Postgres, Redis)...${NC}"
  if ! docker compose -f "$ROOT_DIR/docker-compose.yml" ps --status running --quiet postgres redis | grep -q .; then
    STARTED_INFRA=true
  fi
  docker compose -f "$ROOT_DIR/docker-compose.yml" up postgres redis -d

  wait_for "Postgres" "docker exec bigrag-postgres pg_isready -U bigrag" 30
  wait_for "Redis" "docker exec bigrag-redis redis-cli ping" 15
fi

DATABASE_URL="postgres://bigrag:bigrag@localhost:5432/bigrag?sslmode=disable"
REDIS_URL="redis://localhost:6379/0"

if [ "$START_BACKEND" = true ]; then
  echo -e "${CYAN}Setting up Python backend...${NC}"

  if [ "$NO_INSTALL" = false ]; then
    echo -e "${CYAN}Installing Python dependencies...${NC}"
    uv sync --directory "$ROOT_DIR/api" --quiet
  fi

  DEV_MASTER_KEY="${BIGRAG_MASTER_KEY:-Zm5VZ4vO8r0y3rVsT0xz7nxV_wP7u6-n5tB1GAlHZIw=}"

  export BIGRAG_DATABASE_URL="$DATABASE_URL"
  export BIGRAG_REDIS_URL="$REDIS_URL"
  export BIGRAG_MASTER_KEY="$DEV_MASTER_KEY"
  export BIGRAG_CORS_ORIGINS="${BIGRAG_CORS_ORIGINS:-[\"http://localhost:3000\"]}"
  export BIGRAG_LOG_LEVEL="${BIGRAG_LOG_LEVEL:-info}"
  export PYTHONUNBUFFERED=1

  echo -e "${CYAN}Starting Python backend (auto-reload)...${NC}"
  uv run --directory "$ROOT_DIR/api" uvicorn bigrag.main:create_app \
    --factory --host 0.0.0.0 --port 4000 \
    --reload --reload-dir "$ROOT_DIR/api/bigrag" \
    --log-level info 2>&1 | prefix_logs backend &
  PIDS+=($!)

  wait_for "Backend" "curl -sf http://localhost:4000/health" 120

  echo -e "${CYAN}Starting Python worker (Dramatiq)...${NC}"
  uv run --directory "$ROOT_DIR/api" bigrag-worker --processes "${BIGRAG_WORKER_PROCESSES:-5}" --threads "${BIGRAG_WORKER_THREADS:-8}" \
    2>&1 | prefix_logs worker &
  PIDS+=($!)
fi

if [ "$START_WEBSITE" = true ]; then
  if [ "$NO_INSTALL" = false ]; then
    echo -e "${CYAN}Installing website dependencies...${NC}"
    pnpm --filter @bigrag/docs install --silent
  fi

  echo -e "${CYAN}Starting website dev server...${NC}"
  pnpm --filter @bigrag/docs dev 2>&1 | prefix_logs website &
  PIDS+=($!)
fi

echo -e "\n${GREEN}Services started:${NC}"
[ "$START_BACKEND" = true ] && echo -e "  Backend  → http://localhost:4000"
[ "$START_BACKEND" = true ] && echo -e "  Worker   → Dramatiq on Redis"
[ "$START_BACKEND" = true ] && echo -e "  API Docs → http://localhost:4000/docs"
[ "$START_INFRA" = true ]   && echo -e "  Postgres → localhost:5432"
[ "$START_INFRA" = true ]   && echo -e "  Redis    → localhost:6379"
[ "$START_WEBSITE" = true ] && echo -e "  Website  → http://localhost:3100"
echo -e "\n${YELLOW}Press Ctrl+C to stop all services.${NC}"

wait
