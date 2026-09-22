.DEFAULT_GOAL := help

COMPOSE := docker compose --env-file .env -f deploy/compose/compose.yaml

help: ## Show available commands
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

env: ## Create .env from .env.example (won't overwrite)
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "created .env")

up: ## Start the local stack in the background
	$(COMPOSE) up -d --wait

down: ## Stop the local stack (keeps data)
	$(COMPOSE) down

reset: ## Stop the stack and DELETE all local data volumes
	$(COMPOSE) down -v

ps: ## Show service status
	$(COMPOSE) ps

logs: ## Follow logs (e.g. make logs s=postgres)
	$(COMPOSE) logs -f $(s)

psql: ## Open psql as a service role (e.g. make psql db=marketplace)
	$(COMPOSE) exec postgres psql -U $(or $(db),postgres) -d $(or $(db),postgres)
