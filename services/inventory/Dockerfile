# syntax=docker/dockerfile:1

# ---- build ----
FROM golang:1.25 AS builder
WORKDIR /src

# Dependencies first: this layer is reused until go.mod or go.sum changes.
COPY go.mod go.sum ./
RUN --mount=type=cache,target=/go/pkg/mod go mod download

COPY . .
# CGO off gives a static binary that runs on a distroless image.
# Trimming paths and symbols keeps the binary small and reproducible.
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/inventory .

# ---- runtime ----
# Distroless: no shell, no package manager, nothing to exploit but the binary.
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/inventory /inventory
USER 65532:65532
EXPOSE 50051 8081
ENTRYPOINT ["/inventory"]
