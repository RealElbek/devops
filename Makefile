.PHONY: help env up down ps logs test smoke resilience scale clean config backup restore

SERVICES := event booking payment ticket

help: ## Show commands
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  make %-11s %s\n", $$1, $$2}'

env: ## Create .env from the example (first time only)
	@test -f .env || cp .env.example .env

config: env ## Validate docker-compose.yml
	docker compose config --quiet && echo "compose file OK"

up: env ## Build and start everything, wait until healthy
	docker compose up --build -d --wait --wait-timeout 180 --remove-orphans

down: ## Stop (data is kept)
	docker compose down

ps: ## Container status + health
	docker compose ps

logs: ## Follow logs of the gateway and all services
	docker compose logs -f gateway event-service booking-service payment-service ticket-service

test: env ## Lint + tests of every service against real Postgres (SERVICE=booking for one)
	@set -e; for s in $(or $(SERVICE),$(SERVICES)); do \
	  echo "=== $$s-service ==="; \
	  docker compose --profile test run --rm --build tests-$$s; \
	done

smoke: ## End-to-end booking flow through the gateway (all services together)
	./scripts/smoke_test.sh

resilience: ## Persistence, scaling and fault-isolation checks
	./scripts/resilience_test.sh

scale: ## Run 3 booking-service replicas
	docker compose up -d --scale booking-service=3 --wait

backup: ## Dump the database to backups/ (keeps the newest 7)
	./scripts/backup.sh

restore: ## Restore DB (FILE=backups/x.dump, default: latest)
	./scripts/restore.sh $(FILE)

clean: ## Stop and DELETE all data
	docker compose --profile test down -v --remove-orphans
