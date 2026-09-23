// Checkout service: carts, and the order saga.
//
//	checkout            serve HTTP
//	checkout migrate    apply the schema and exit
package main

import (
	"context"
	"errors"
	"log/slog"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"github.com/Tarunno/Poshra/services/checkout/internal/api"
	"github.com/Tarunno/Poshra/services/checkout/internal/catalog"
	"github.com/Tarunno/Poshra/services/checkout/internal/config"
	"github.com/Tarunno/Poshra/services/checkout/internal/logging"
	"github.com/Tarunno/Poshra/services/checkout/internal/payment"
	"github.com/Tarunno/Poshra/services/checkout/internal/store"
	inventoryv1 "github.com/Tarunno/Poshra/services/inventory/gen/poshra/inventory/v1"
)

func main() {
	cfg, err := config.Load()
	if err != nil {
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
	// dns:/// with round_robin balances across inventory's pods. gRPC holds one
	// long-lived connection, so without this a client would pin itself to
	// whichever pod it first resolved.
	conn, err := grpc.NewClient(
		"dns:///"+cfg.InventoryURL,
		grpc.WithTransportCredentials(insecure.NewCredentials()),
		grpc.WithDefaultServiceConfig(`{
			"loadBalancingConfig": [{"round_robin": {}}],
			"methodConfig": [{
				"name": [{"service": "poshra.inventory.v1.InventoryService"}],
				"retryPolicy": {
					"maxAttempts": 3,
					"initialBackoff": "0.05s",
					"maxBackoff": "0.5s",
					"backoffMultiplier": 2,
					"retryableStatusCodes": ["UNAVAILABLE"]
				}
			}]
		}`),
	)
	if err != nil {
		return err
	}
	defer conn.Close()

	server := api.New(
		cfg, log, db,
		catalog.New(cfg.CatalogURL, cfg.CatalogTimeout),
		inventoryv1.NewInventoryServiceClient(conn),
		payment.Fake{},
	)

	httpServer := &http.Server{
		Addr:              cfg.HTTPAddr,
		Handler:           server.Handler(),
		ReadHeaderTimeout: 5 * time.Second,
		// Generous enough for a slow payment, bounded so a stuck request
		// cannot hold a connection forever.
		WriteTimeout: 30 * time.Second,
		IdleTimeout:  60 * time.Second,
	}

	stop := make(chan os.Signal, 1)
	signal.Notify(stop, syscall.SIGINT, syscall.SIGTERM)

	serveErr := make(chan error, 1)
	go func() {
		log.Info("checkout listening", "addr", cfg.HTTPAddr, "inventory", cfg.InventoryURL)
		if err := httpServer.ListenAndServe(); err != nil && !errors.Is(err, http.ErrServerClosed) {
			serveErr <- err
		}
	}()

	select {
	case err := <-serveErr:
		return err
	case <-stop:
		log.Info("shutting down")
	}

	// Let in-flight orders finish: cutting a request between charging and
	// writing the order is exactly the case the saga works hardest to avoid.
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer cancel()
	return httpServer.Shutdown(shutdownCtx)
}
