// Inventory service: the single authority for how many of a piece exist.
//
//	inventory            run the gRPC server
//	inventory migrate    apply the schema and exit (run as a job, not at boot)
package main

import (
	"context"
	"errors"
	"log/slog"
	"net"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/health"
	healthpb "google.golang.org/grpc/health/grpc_health_v1"
	"google.golang.org/grpc/keepalive"
	"google.golang.org/grpc/reflection"

	inventoryv1 "github.com/Tarunno/Poshra/services/inventory/gen/poshra/inventory/v1"
	"github.com/Tarunno/Poshra/services/inventory/internal/config"
	"github.com/Tarunno/Poshra/services/inventory/internal/logging"
	"github.com/Tarunno/Poshra/services/inventory/internal/server"
	"github.com/Tarunno/Poshra/services/inventory/internal/store"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
		// No logger yet: configuration is what the logger is built from.
		println("configuration error:", err.Error())
		os.Exit(1)
	}
	log := logging.New(cfg.LogLevel)

	ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
	db, err := store.New(ctx, cfg.DatabaseURL)
	cancel()
	if err != nil {
		log.Error("cannot reach the database", "error", err)
		os.Exit(1)
	}
	defer db.Close()

	if len(os.Args) > 1 && os.Args[1] == "migrate" {
		ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
		defer cancel()
		if err := db.Migrate(ctx); err != nil {
			log.Error("migration failed", "error", err)
			os.Exit(1)
		}
		log.Info("migrations applied")
		return
	}

	if err := run(cfg, log, db); err != nil {
		log.Error("server stopped", "error", err)
		os.Exit(1)
	}
}

func run(cfg config.Config, log *slog.Logger, db *store.Store) error {
	grpcServer := grpc.NewServer(
		grpc.ChainUnaryInterceptor(
			server.RecoveryInterceptor(log),
			server.LoggingInterceptor(log),
		),
		// Long-lived HTTP/2 connections need to notice a dead peer. Without
		// keepalives a caller can hold a connection to a pod that is gone.
		grpc.KeepaliveParams(keepalive.ServerParameters{
			Time:    30 * time.Second,
			Timeout: 10 * time.Second,
		}),
		grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
			MinTime:             15 * time.Second,
			PermitWithoutStream: true,
		}),
	)

	inventoryv1.RegisterInventoryServiceServer(grpcServer, server.New(db, cfg.MaxReservationTTL))

	// The standard health service, which Kubernetes can probe directly with
	// grpc probes, and which clients use for load-balancer health.
	healthServer := health.NewServer()
	healthpb.RegisterHealthServer(grpcServer, healthServer)
	healthServer.SetServingStatus("", healthpb.HealthCheckResponse_SERVING)

	// Reflection lets grpcurl call this service without a copy of the proto.
	// Useful in a home cluster; worth disabling where the API is public.
	reflection.Register(grpcServer)

	listener, err := net.Listen("tcp", cfg.GRPCAddr)
	if err != nil {
		return err
	}

	// A plain HTTP endpoint for readiness, so the probe can also check the
	// database, which the gRPC health service alone does not.
	ready := &http.Server{
		Addr:              cfg.HealthAddr,
		ReadHeaderTimeout: 5 * time.Second,
		Handler:           readinessHandler(db),
	}
	go func() {
		if err := ready.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			log.Error("health server stopped", "error", err)
		}
	}()

	stopSweeper := startSweeper(cfg, log, db)

	log.Info("inventory listening", "grpc", cfg.GRPCAddr, "health", cfg.HealthAddr)

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	serveErr := make(chan error, 1)
	go func() { serveErr <- grpcServer.Serve(listener) }()

	select {
	case err := <-serveErr:
		return err
	case <-stop:
		log.Info("shutting down")
	}

	stopSweeper()
	// Finish in-flight calls before closing connections, so a rolling update
	// does not turn into failed requests.
	done := make(chan struct{})
	go func() {
		grpcServer.GracefulStop()
		close(done)
	}()
	select {
	case <-done:
	case <-time.After(20 * time.Second):
		grpcServer.Stop()
	}

	shutdownCtx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	return ready.Shutdown(shutdownCtx)
}

// startSweeper releases holds whose time ran out. Returns a stop function.
func startSweeper(cfg config.Config, log *slog.Logger, db *store.Store) func() {
	ctx, cancel := context.WithCancel(context.Background())
	go func() {
		ticker := time.NewTicker(cfg.SweepInterval)
		defer ticker.Stop()
		for {
			select {
			case <-ctx.Done():
				return
			case <-ticker.C:
				sweepCtx, sweepCancel := context.WithTimeout(ctx, 30*time.Second)
				released, err := db.SweepExpired(sweepCtx, 100)
				sweepCancel()
				if err != nil {
					log.Error("sweep failed", "error", err)
					continue
				}
				if released > 0 {
					log.Info("released expired reservations", "count", released)
				}
			}
		}
	}()
	return cancel
}

func readinessHandler(db *store.Store) http.Handler {
	mux := http.NewServeMux()
	// Liveness: the process is up. Never touches the database, or an outage
	// would restart every pod instead of taking them out of rotation.
	mux.HandleFunc("/healthz", func(w http.ResponseWriter, _ *http.Request) {
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"status":"ok"}`))
	})
	mux.HandleFunc("/readyz", func(w http.ResponseWriter, r *http.Request) {
		ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
		defer cancel()
		w.Header().Set("Content-Type", "application/json")
		if err := db.Ping(ctx); err != nil {
			w.WriteHeader(http.StatusServiceUnavailable)
			_, _ = w.Write([]byte(`{"status":"unavailable","checks":{"database":"fail"}}`))
			return
		}
		_, _ = w.Write([]byte(`{"status":"ready","checks":{"database":"ok"}}`))
	})
	return mux
}
