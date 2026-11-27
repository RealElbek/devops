.PHONY: help env up down ps logs test smoke resilience scale clean config

help: ## Show commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-11s %s\n", $$1, $$2}'

env: ## Create .env from the example (first time only)
	@test -f .env || cp .env.example .env

config: env ## Validate docker-compose.yml
	docker compose config --quiet && echo "compose file OK"

up: env ## Build and start everything, wait until healthy
	docker compose up --build -d --wait --wait-timeout 180

down: ## Stop (data is kept)
	docker compose down

ps: ## Container status + health
	docker compose ps

logs: ## Follow logs
	docker compose logs -f app nginx

test: env ## Lint + unit/integration tests against real Postgres
	docker compose --profile test run --rm --build tests

smoke: ## End-to-end booking flow through nginx
	./scripts/smoke_test.sh

resilience: ## Persistence, scaling and DB-outage checks
	./scripts/resilience_test.sh

scale: ## Run 3 app replicas
	docker compose up -d --scale app=3 --wait

clean: ## Stop and DELETE all data
	docker compose --profile test down -v
