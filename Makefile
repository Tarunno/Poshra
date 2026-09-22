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

build: ## Build service images
	$(COMPOSE) build

migrate: ## Apply Django migrations for marketplace (one-off container)
	$(COMPOSE) run --rm marketplace python manage.py migrate

kong-validate: ## Validate gateway/kong/kong.yaml
	$(COMPOSE) run --rm --no-deps kong kong config parse /kong/kong.yaml

kong-reload: ## Apply gateway/kong/kong.yaml to the running Kong without a restart
	curl -sf -X POST http://127.0.0.1:$${KONG_ADMIN_HOST_PORT:-8001}/config -F config=@gateway/kong/kong.yaml > /dev/null && echo "kong config reloaded"

psql: ## Open psql as a service role (e.g. make psql db=marketplace)
	$(COMPOSE) exec postgres psql -U $(or $(db),postgres) -d $(or $(db),postgres)
