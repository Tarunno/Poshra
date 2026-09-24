# syntax=docker/dockerfile:1

# ---- dependencies ----
FROM node:22-slim AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

# ---- build ----
FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .

# The commit this image was built from. Next stamps it on to the assets and
# the server functions it emits, so a browser holding an older page can be
# told it is holding an older page instead of calling a server action that no
# longer exists. Empty in a local build, which is the same as not using it.
ARG NEXT_DEPLOYMENT_ID=""
ENV NEXT_DEPLOYMENT_ID=$NEXT_DEPLOYMENT_ID
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build

# ---- runtime ----
# `output: standalone` emits a server with only the files it needs, so the
# runtime image carries no build tools and no full node_modules tree.
FROM node:22-slim AS runtime
WORKDIR /app

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

USER 1000:1000
EXPOSE 3000
CMD ["node", "server.js"]
