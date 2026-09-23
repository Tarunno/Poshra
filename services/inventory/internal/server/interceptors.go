package server

import (
	"context"
	"log/slog"
	"runtime/debug"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/Tarunno/Poshra/services/inventory/internal/logging"
)

// LoggingInterceptor records one structured line per RPC.
//
// An interceptor is gRPC's middleware: it wraps every handler, so
// cross-cutting concerns live in one place instead of in each method.
func LoggingInterceptor(log *slog.Logger) grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (any, error) {
		started := time.Now()
		resp, err := handler(ctx, req)

		attrs := []any{
			"rpc", info.FullMethod,
			"code", status.Code(err).String(),
			"duration_ms", float64(time.Since(started).Microseconds()) / 1000,
		}
		if id := logging.RequestID(ctx); id != "" {
			attrs = append(attrs, "request_id", id)
		}
		// A deadline tells you how much budget the caller gave this hop, which
		// is what you want when chasing a timeout across services.
		if deadline, ok := ctx.Deadline(); ok {
			attrs = append(attrs, "deadline_ms", time.Until(deadline).Milliseconds())
		}
		if err != nil {
			attrs = append(attrs, "error", err.Error())
			log.Error("rpc", attrs...)
		} else {
			log.Info("rpc", attrs...)
		}
		return resp, err
	}
}

// RecoveryInterceptor turns a panic into an error for that one call, instead
// of taking the whole process down with every in-flight request on it.
func RecoveryInterceptor(log *slog.Logger) grpc.UnaryServerInterceptor {
	return func(
		ctx context.Context,
		req any,
		info *grpc.UnaryServerInfo,
		handler grpc.UnaryHandler,
	) (resp any, err error) {
		defer func() {
			if recovered := recover(); recovered != nil {
				log.Error("panic in rpc",
					"rpc", info.FullMethod,
					"panic", recovered,
					"stack", string(debug.Stack()))
				// Never leak the panic message to the caller.
				err = status.Error(codes.Internal, "internal error")
			}
		}()
		return handler(ctx, req)
	}
}
