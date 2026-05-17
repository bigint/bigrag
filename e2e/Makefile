.PHONY: up down logs install test-api test-sdk-py test-sdk-ts test-ui test e2e wait-ready

COMPOSE = docker compose -f ../docker-compose.yml -f docker-compose.e2e.yml
API_BASE ?= http://localhost:4000

up:
	$(COMPOSE) up -d --build
	$(MAKE) wait-ready

wait-ready:
	@echo "Waiting for $(API_BASE)/health/ready ..."
	@for i in $$(seq 1 60); do \
		if curl -fsS $(API_BASE)/health/ready >/dev/null 2>&1; then \
			echo "ready"; exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "timed out waiting for /health/ready"; exit 1

down:
	$(COMPOSE) down -v

logs:
	$(COMPOSE) logs -f --tail=200

install:
	uv sync
	pnpm install

test-api:
	uv run pytest tests/api -v

test-sdk-py:
	uv run pytest tests/sdk_python -v

test-sdk-ts:
	pnpm vitest run tests/sdk_typescript

test-ui:
	pnpm playwright test

test: test-api test-sdk-py test-sdk-ts test-ui

e2e:
	$(MAKE) up
	@if ! $(MAKE) test; then \
		echo "=== bigrag-api logs (last 1000 lines) ==="; \
		$(COMPOSE) logs --tail=1000 bigrag-api || true; \
		echo "=== bigrag-worker logs (last 1000 lines) ==="; \
		$(COMPOSE) logs --tail=1000 bigrag-worker || true; \
		$(MAKE) down; \
		exit 1; \
	fi
	$(MAKE) down
