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

py-check: ## Run exactly what CI runs for the Python services (lint, format, tests)
	cd services/marketplace && uv run ruff check . && uv run ruff format --check . && uv run pytest -q
	cd services/assistant && uv run ruff check . && uv run ruff format --check . && uv run pytest -q

kong-validate: ## Validate gateway/kong/kong.yaml
	@python3 gateway/kong/tests/no_duplicate_keys.py gateway/kong/kong.yaml
	$(COMPOSE) run --rm --no-deps kong kong config parse /kong/kong.yaml

kong-test: ## Run Kong plugin unit tests
	$(COMPOSE) run --rm --no-deps --entrypoint resty kong /kong/tests/gcra_test.lua
	$(COMPOSE) run --rm --no-deps --entrypoint resty kong /kong/tests/claims_test.lua

kong-reload: ## Apply gateway/kong/kong.yaml to the running Kong without a restart
	curl -sf -X POST http://127.0.0.1:$${KONG_ADMIN_HOST_PORT:-8001}/config -F config=@gateway/kong/kong.yaml > /dev/null && echo "kong config reloaded"

jwt-keys: ## Print a fresh RSA key pair as base64 env lines (paste into .env)
	@python3 -c "import base64;from cryptography.hazmat.primitives import serialization as s;from cryptography.hazmat.primitives.asymmetric import rsa;k=rsa.generate_private_key(public_exponent=65537,key_size=2048);priv=k.private_bytes(s.Encoding.PEM,s.PrivateFormat.PKCS8,s.NoEncryption());pub=k.public_key().public_bytes(s.Encoding.PEM,s.PublicFormat.SubjectPublicKeyInfo);print('JWT_PRIVATE_KEY_B64='+base64.b64encode(priv).decode());print('JWT_PUBLIC_KEY_B64='+base64.b64encode(pub).decode())"

k8s-secrets: ## Create namespace + generated secrets (passwords and keys, made once)
	kubectl get ns poshra >/dev/null 2>&1 || kubectl create ns poshra
	kubectl -n poshra get secret poshra-db >/dev/null 2>&1 || kubectl -n poshra create secret generic poshra-db \
		--from-literal=POSTGRES_SUPERUSER_PASSWORD=$$(openssl rand -hex 24) \
		--from-literal=MARKETPLACE_DB_PASSWORD=$$(openssl rand -hex 24) \
		--from-literal=CHECKOUT_DB_PASSWORD=$$(openssl rand -hex 24) \
		--from-literal=INVENTORY_DB_PASSWORD=$$(openssl rand -hex 24) \
		--from-literal=ASSISTANT_DB_PASSWORD=$$(openssl rand -hex 24)
	kubectl -n poshra get secret poshra-django >/dev/null 2>&1 || kubectl -n poshra create secret generic poshra-django \
		--from-literal=DJANGO_SECRET_KEY=$$(openssl rand -base64 48 | tr -d '\n')
	@kubectl -n poshra get secret poshra-checkout >/dev/null 2>&1 || kubectl -n poshra create secret generic poshra-checkout \
		--from-literal=DATABASE_URL="postgres://checkout:$$(kubectl -n poshra get secret poshra-db -o jsonpath='{.data.CHECKOUT_DB_PASSWORD}' | base64 -d)@postgres:5432/checkout?sslmode=disable"
	@kubectl -n poshra get secret poshra-inventory >/dev/null 2>&1 || kubectl -n poshra create secret generic poshra-inventory \
		--from-literal=DATABASE_URL="postgres://inventory:$$(kubectl -n poshra get secret poshra-db -o jsonpath='{.data.INVENTORY_DB_PASSWORD}' | base64 -d)@postgres:5432/inventory?sslmode=disable"
	@kubectl -n poshra get secret poshra-jwt >/dev/null 2>&1 || ( \
		tmp=$$(mktemp -d); \
		openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out $$tmp/key.pem 2>/dev/null; \
		openssl rsa -in $$tmp/key.pem -pubout -out $$tmp/pub.pem 2>/dev/null; \
		kubectl -n poshra create secret generic poshra-jwt \
			--from-literal=JWT_PRIVATE_KEY_B64=$$(base64 -w0 < $$tmp/key.pem) \
			--from-literal=JWT_PUBLIC_KEY_B64=$$(base64 -w0 < $$tmp/pub.pem); \
		rm -rf $$tmp )
	@kubectl -n poshra get secret

	@kubectl -n poshra get secret poshra-redis >/dev/null 2>&1 || ( \
		pass=$$(openssl rand -hex 24); \
		kubectl -n poshra create secret generic poshra-redis \
			--from-literal=REDIS_PASSWORD="$$pass" \
			--from-literal=REDIS_URL="redis://:$$pass@redis:6379" )
	@kubectl -n poshra get secret poshra-media >/dev/null 2>&1 || kubectl -n poshra create secret generic poshra-media \
		--from-literal=MEDIA_ACCESS_KEY=poshra \
		--from-literal=MEDIA_SECRET_KEY=$$(openssl rand -hex 24)

# Separate from k8s-secrets: these cannot be generated, so they are supplied
# rather than made, and never written to a file in the repo. Both keys live in
# one secret so switching LLM_PROVIDER needs no other change.
k8s-secret-llm: ## Store the model API keys (GEMINI_API_KEY=... ANTHROPIC_API_KEY=... make k8s-secret-llm)
	@test -n "$$GEMINI_API_KEY$$ANTHROPIC_API_KEY" || { echo "set GEMINI_API_KEY and/or ANTHROPIC_API_KEY"; exit 1; }
	@kubectl -n poshra create secret generic poshra-llm \
		--from-literal=GEMINI_API_KEY="$$GEMINI_API_KEY" \
		--from-literal=ANTHROPIC_API_KEY="$$ANTHROPIC_API_KEY" \
		--dry-run=client -o yaml | kubectl apply -f -
	@echo "stored; restart the assistant to pick it up: kubectl -n poshra rollout restart deploy/assistant"

obs-secrets: ## Create the observability namespace's secrets (generated once)
	kubectl get ns observability >/dev/null 2>&1 || kubectl create ns observability
	@kubectl -n observability get secret grafana-admin >/dev/null 2>&1 || kubectl -n observability create secret generic grafana-admin \
		--from-literal=username=admin \
		--from-literal=password=$$(openssl rand -hex 16)
	@# Loki and Tempo keep their data in the same MinIO the catalog uses, so
	@# they need the same credentials in their own namespace.
	@kubectl -n observability get secret minio-credentials >/dev/null 2>&1 || kubectl -n observability create secret generic minio-credentials \
		--from-literal=MEDIA_ACCESS_KEY="$$(kubectl -n poshra get secret poshra-media -o jsonpath='{.data.MEDIA_ACCESS_KEY}' | base64 -d)" \
		--from-literal=MEDIA_SECRET_KEY="$$(kubectl -n poshra get secret poshra-media -o jsonpath='{.data.MEDIA_SECRET_KEY}' | base64 -d)"
	@echo "grafana admin password:"
	@kubectl -n observability get secret grafana-admin -o jsonpath='{.data.password}' | base64 -d; echo

obs-deploy: ## Apply the observability stack directly (Argo CD owns it normally)
	kubectl apply -k deploy/k8s/observability

k8s-deploy: ## Apply manifests to the cluster (TAG=<image tag>, default dev)
	cd deploy/k8s/overlays/local && kubectl kustomize . | kubectl apply -f -
	kubectl -n poshra rollout status deploy/marketplace --timeout=180s
	kubectl -n poshra rollout status deploy/kong --timeout=120s

sync-stock: ## Republish every listing's stock level to the inventory ledger
	kubectl -n poshra exec deploy/marketplace -- python manage.py sync_stock

reconcile-stock: ## Repair the catalogue's counts FROM the ledger (DRY=1 to preview)
	kubectl -n poshra exec deploy/marketplace -- python manage.py reconcile_stock $(if $(DRY),--dry-run,)

k8s-migrations: ## Show the result of the last migration run
	kubectl -n poshra get jobs -l 'app.kubernetes.io/name in (marketplace-migrate,inventory-migrate,checkout-migrate)'

k8s-status: ## Show what is running in the poshra namespace
	kubectl -n poshra get pods,svc,pvc -o wide

psql: ## Open psql as a service role (e.g. make psql db=marketplace)
	$(COMPOSE) exec postgres psql -U $(or $(db),postgres) -d $(or $(db),postgres)
