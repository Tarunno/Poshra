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
	"github.com/Tarunno/Poshra/services/checkout/internal/relay"
	"github.com/Tarunno/Poshra/services/checkout/internal/store"
	inventoryv1 "github.com/Tarunno/Poshra/services/inventory/gen/poshra/inventory/v1"
)

func main() {
	if len(os.Args) > 1 && os.Args[1] == "migrate" {
		if err := migrate(); err != nil {
			println("migration failed:", err.Error())
			os.Exit(1)
		}
		println("migrations applied")
		return
	}

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

	if err := run(cfg, log, db); err != nil {
		log.Error("server stopped", "error", err)
		os.Exit(1)
	}
}

// migrate applies the schema and exits.
//
// It deliberately skips config.Load: a migration needs a database and nothing
// else, so the Job that runs it should not have to carry an inventory address,
// a catalog URL and a broker list it will never use.
func migrate() error {
	dsn := os.Getenv("DATABASE_URL")
	if dsn == "" {
		return errors.New("DATABASE_URL is required")
	}
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Minute)
	defer cancel()

	db, err := store.New(ctx, dsn)
	if err != nil {
		return err
	}
	defer db.Close()
	return db.Migrate(ctx)
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

	// The relay is the other half of the outbox: orders commit an event into
	// the database, and this loop is what carries it to Kafka. It is part of
	// the service rather than a separate deployment because it only ever reads
	// this service's own table.
	outbox, err := relay.New(db, cfg.KafkaBrokers, log)
	if err != nil {
		return err
	}
	defer outbox.Close()

	relayCtx, stopRelay := context.WithCancel(context.Background())
	defer stopRelay()
	go outbox.Run(relayCtx)

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

	// Stop claiming new batches, but let the in-flight one finish: a send that
	// is cut off mid-flight would simply be retried, yet stopping cleanly keeps
	// the duplicate out of the consumers.
	stopRelay()

	// Let in-flight orders finish: cutting a request between charging and
	// writing the order is exactly the case the saga works hardest to avoid.
	shutdownCtx, cancel := context.WithTimeout(context.Background(), 25*time.Second)
	defer cancel()
	return httpServer.Shutdown(shutdownCtx)
}
