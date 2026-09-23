# syntax=docker/dockerfile:1

# ---- build ----
# The build context is services/, because checkout compiles against the
# inventory module's generated client (a replace directive in go.mod).
FROM golang:1.25 AS builder
WORKDIR /src

COPY checkout/go.mod checkout/go.sum ./checkout/
COPY inventory/go.mod inventory/go.sum ./inventory/
COPY inventory/gen ./inventory/gen
WORKDIR /src/checkout
RUN --mount=type=cache,target=/go/pkg/mod go mod download

WORKDIR /src
COPY inventory ./inventory
COPY checkout ./checkout
WORKDIR /src/checkout
RUN --mount=type=cache,target=/go/pkg/mod --mount=type=cache,target=/root/.cache/go-build \
    CGO_ENABLED=0 GOOS=linux go build -trimpath -ldflags="-s -w" -o /out/checkout .

# ---- runtime ----
FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /out/checkout /checkout
USER 65532:65532
EXPOSE 8080
ENTRYPOINT ["/checkout"]
