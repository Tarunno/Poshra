// Package logging emits the same JSON shape as the other Poshra services, so
// one collector can read them all and a request can be followed across them.
package logging

import (
	"context"
	"log/slog"
	"os"

	"google.golang.org/grpc/metadata"
)

const requestIDKey = "x-request-id"

func New(level string) *slog.Logger {
	var lvl slog.Level
	if err := lvl.UnmarshalText([]byte(level)); err != nil {
		lvl = slog.LevelInfo
	}
	handler := slog.NewJSONHandler(os.Stdout, &slog.HandlerOptions{Level: lvl})
	return slog.New(handler).With("service", "inventory")
}

// RequestID pulls the gateway's correlation id out of the gRPC metadata, so
// one identifier spans the gateway, the caller and this service.
func RequestID(ctx context.Context) string {
	md, ok := metadata.FromIncomingContext(ctx)
	if !ok {
		return ""
	}
	if values := md.Get(requestIDKey); len(values) > 0 {
		return values[0]
	}
	return ""
}
