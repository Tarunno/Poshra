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

kong-test: ## Run Kong plugin unit tests
	$(COMPOSE) run --rm --no-deps --entrypoint resty kong /kong/tests/gcra_test.lua

kong-reload: ## Apply gateway/kong/kong.yaml to the running Kong without a restart
	curl -sf -X POST http://127.0.0.1:$${KONG_ADMIN_HOST_PORT:-8001}/config -F config=@gateway/kong/kong.yaml > /dev/null && echo "kong config reloaded"

k8s-secrets: ## Create namespace + secrets in the cluster (generates random passwords once)
	kubectl get ns poshra >/dev/null 2>&1 || kubectl create ns poshra
	kubectl -n poshra get secret poshra-db >/dev/null 2>&1 || kubectl -n poshra create secret generic poshra-db \
		--from-literal=POSTGRES_SUPERUSER_PASSWORD=$$(openssl rand -hex 24) \
		--from-literal=MARKETPLACE_DB_PASSWORD=$$(openssl rand -hex 24) \
		--from-literal=CHECKOUT_DB_PASSWORD=$$(openssl rand -hex 24) \
		--from-literal=INVENTORY_DB_PASSWORD=$$(openssl rand -hex 24) \
		--from-literal=ASSISTANT_DB_PASSWORD=$$(openssl rand -hex 24)
	kubectl -n poshra get secret poshra-django >/dev/null 2>&1 || kubectl -n poshra create secret generic poshra-django \
		--from-literal=DJANGO_SECRET_KEY=$$(openssl rand -base64 48 | tr -d '\n')
	@kubectl -n poshra get secret

k8s-deploy: ## Apply manifests to the cluster (TAG=<image tag>, default dev)
	cd deploy/k8s/overlays/local && kubectl kustomize . | kubectl apply -f -
	kubectl -n poshra rollout status deploy/marketplace --timeout=180s
	kubectl -n poshra rollout status deploy/kong --timeout=120s

k8s-migrate: ## Run Django migrations in the cluster as a one-off Job
	@IMAGE=$$(kubectl -n poshra get deploy marketplace -o jsonpath='{.spec.template.spec.containers[0].image}'); \
	sed "s|IMAGE_PLACEHOLDER|$$IMAGE|" deploy/k8s/jobs/migrate.yaml | kubectl create -f - -o name | \
	xargs -I{} kubectl -n poshra wait --for=condition=complete --timeout=180s {}

k8s-status: ## Show what is running in the poshra namespace
	kubectl -n poshra get pods,svc,pvc -o wide

psql: ## Open psql as a service role (e.g. make psql db=marketplace)
	$(COMPOSE) exec postgres psql -U $(or $(db),postgres) -d $(or $(db),postgres)
