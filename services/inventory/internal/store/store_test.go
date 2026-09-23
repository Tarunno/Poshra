package store_test

import (
	"context"
	"errors"
	"fmt"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/testcontainers/testcontainers-go"
	tcpostgres "github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"

	"github.com/Tarunno/Poshra/services/inventory/internal/store"
)

// These tests run against a real Postgres in a container. The rules being
// tested — no overselling, idempotent retries, safe concurrent holds — depend
// on row locking and transaction isolation, which a fake would not reproduce.
var shared *store.Store

func TestMain(m *testing.M) {
	ctx := context.Background()
	container, err := tcpostgres.Run(ctx, "postgres:17-alpine",
		tcpostgres.WithDatabase("inventory"),
		tcpostgres.WithUsername("inventory"),
		tcpostgres.WithPassword("test"),
		testcontainers.WithWaitStrategy(
			wait.ForLog("database system is ready to accept connections").
				WithOccurrence(2).WithStartupTimeout(60*time.Second)),
	)
	if err != nil {
		panic(fmt.Sprintf("start postgres: %v", err))
	}

	dsn, err := container.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		panic(err)
	}
	shared, err = store.New(ctx, dsn)
	if err != nil {
		panic(err)
	}
	if err := shared.Migrate(ctx); err != nil {
		panic(err)
	}

	code := m.Run()

	shared.Close()
	_ = testcontainers.TerminateContainer(container)
	if code != 0 {
		panic("tests failed")
	}
}

func newSKU(t *testing.T, quantity int32) string {
	t.Helper()
	sku := uuid.NewString()
	if _, err := shared.SetStock(context.Background(), sku, quantity); err != nil {
		t.Fatalf("set stock: %v", err)
	}
	return sku
}

func reserve(t *testing.T, sku string, quantity int32) (string, error) {
	t.Helper()
	id := uuid.NewString()
	_, _, err := shared.Reserve(context.Background(), id, uuid.NewString(),
		[]store.Item{{SKUID: sku, Quantity: quantity}}, time.Minute)
	return id, err
}

func levelOf(t *testing.T, sku string) store.Level {
	t.Helper()
	levels, err := shared.Levels(context.Background(), []string{sku})
	if err != nil {
		t.Fatalf("levels: %v", err)
	}
	if len(levels) != 1 {
		t.Fatalf("expected one level, got %d", len(levels))
	}
	return levels[0]
}

func TestReserveMovesStockFromAvailableToReserved(t *testing.T) {
	sku := newSKU(t, 5)
	if _, err := reserve(t, sku, 2); err != nil {
		t.Fatalf("reserve: %v", err)
	}

	level := levelOf(t, sku)
	if level.Available != 3 || level.Reserved != 2 {
		t.Fatalf("expected 3 available and 2 reserved, got %+v", level)
	}
}

func TestReserveRefusesMoreThanExists(t *testing.T) {
	sku := newSKU(t, 1)
	_, err := reserve(t, sku, 2)
	if !errors.Is(err, store.ErrInsufficient) {
		t.Fatalf("expected insufficient stock, got %v", err)
	}
	if level := levelOf(t, sku); level.Available != 1 || level.Reserved != 0 {
		t.Fatalf("a failed reservation must not move stock, got %+v", level)
	}
}

func TestReserveIsAllOrNothing(t *testing.T) {
	plenty := newSKU(t, 5)
	scarce := newSKU(t, 1)

	_, _, err := shared.Reserve(context.Background(), uuid.NewString(), uuid.NewString(),
		[]store.Item{{SKUID: plenty, Quantity: 1}, {SKUID: scarce, Quantity: 3}}, time.Minute)
	if !errors.Is(err, store.ErrInsufficient) {
		t.Fatalf("expected the whole reservation to fail, got %v", err)
	}
	// The item that could have been held must not be: a partial hold would
	// strand stock for an order that can never complete.
	if level := levelOf(t, plenty); level.Reserved != 0 {
		t.Fatalf("expected no hold on the available item, got %+v", level)
	}
}

func TestReserveIsIdempotent(t *testing.T) {
	sku := newSKU(t, 5)
	id := uuid.NewString()
	order := uuid.NewString()
	items := []store.Item{{SKUID: sku, Quantity: 2}}

	_, createdFirst, err := shared.Reserve(context.Background(), id, order, items, time.Minute)
	if err != nil || !createdFirst {
		t.Fatalf("first reserve: created=%v err=%v", createdFirst, err)
	}

	// A client whose reply was lost retries with the same id.
	_, createdAgain, err := shared.Reserve(context.Background(), id, order, items, time.Minute)
	if err != nil {
		t.Fatalf("retry: %v", err)
	}
	if createdAgain {
		t.Fatal("a retry must not create a second hold")
	}
	if level := levelOf(t, sku); level.Reserved != 2 {
		t.Fatalf("expected stock held once, got %+v", level)
	}
}

func TestConcurrentReservationsNeverOversell(t *testing.T) {
	// Ten buyers race for three pieces. Exactly three must win.
	const stock, buyers = 3, 10
	sku := newSKU(t, stock)

	var wg sync.WaitGroup
	results := make(chan error, buyers)
	for range buyers {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_, _, err := shared.Reserve(context.Background(), uuid.NewString(), uuid.NewString(),
				[]store.Item{{SKUID: sku, Quantity: 1}}, time.Minute)
			results <- err
		}()
	}
	wg.Wait()
	close(results)

	won, lost := 0, 0
	for err := range results {
		switch {
		case err == nil:
			won++
		case errors.Is(err, store.ErrInsufficient):
			lost++
		default:
			t.Fatalf("unexpected error: %v", err)
		}
	}
	if won != stock || lost != buyers-stock {
		t.Fatalf("expected %d winners and %d losers, got %d and %d", stock, buyers-stock, won, lost)
	}
	if level := levelOf(t, sku); level.Available != 0 || level.Reserved != stock {
		t.Fatalf("expected all stock held exactly once, got %+v", level)
	}
}

func TestCommitSellsTheHeldStock(t *testing.T) {
	sku := newSKU(t, 4)
	id, err := reserve(t, sku, 3)
	if err != nil {
		t.Fatalf("reserve: %v", err)
	}
	if _, err := shared.Commit(context.Background(), id); err != nil {
		t.Fatalf("commit: %v", err)
	}
	// Sold stock leaves both counts: it is neither available nor held.
	if level := levelOf(t, sku); level.Available != 1 || level.Reserved != 0 {
		t.Fatalf("expected 1 available and 0 reserved, got %+v", level)
	}
}

func TestCommitIsIdempotent(t *testing.T) {
	sku := newSKU(t, 2)
	id, _ := reserve(t, sku, 1)
	if _, err := shared.Commit(context.Background(), id); err != nil {
		t.Fatalf("commit: %v", err)
	}
	if _, err := shared.Commit(context.Background(), id); err != nil {
		t.Fatalf("second commit should be a no-op, got %v", err)
	}
	if level := levelOf(t, sku); level.Available != 1 || level.Reserved != 0 {
		t.Fatalf("a repeated commit must not sell twice, got %+v", level)
	}
}

func TestReleaseReturnsStock(t *testing.T) {
	sku := newSKU(t, 3)
	id, _ := reserve(t, sku, 2)
	if _, err := shared.Release(context.Background(), id, "payment_declined", false); err != nil {
		t.Fatalf("release: %v", err)
	}
	if level := levelOf(t, sku); level.Available != 3 || level.Reserved != 0 {
		t.Fatalf("expected the stock back, got %+v", level)
	}
}

func TestReleasingASaleIsRefused(t *testing.T) {
	sku := newSKU(t, 2)
	id, _ := reserve(t, sku, 1)
	if _, err := shared.Commit(context.Background(), id); err != nil {
		t.Fatalf("commit: %v", err)
	}
	// Releasing a committed reservation would invent stock that was sold.
	if _, err := shared.Release(context.Background(), id, "late", false); !errors.Is(err, store.ErrAlreadySettled) {
		t.Fatalf("expected refusal, got %v", err)
	}
}

func TestCommittingAReleasedReservationIsRefused(t *testing.T) {
	sku := newSKU(t, 2)
	id, _ := reserve(t, sku, 1)
	if _, err := shared.Release(context.Background(), id, "abandoned", false); err != nil {
		t.Fatalf("release: %v", err)
	}
	if _, err := shared.Commit(context.Background(), id); !errors.Is(err, store.ErrAlreadySettled) {
		t.Fatalf("expected refusal, got %v", err)
	}
}

func TestExpiredHoldsAreSweptBack(t *testing.T) {
	sku := newSKU(t, 4)
	id := uuid.NewString()
	// A hold that expired immediately: the caller crashed before paying.
	if _, _, err := shared.Reserve(context.Background(), id, uuid.NewString(),
		[]store.Item{{SKUID: sku, Quantity: 2}}, -time.Second); err != nil {
		t.Fatalf("reserve: %v", err)
	}

	swept, err := shared.SweepExpired(context.Background(), 10)
	if err != nil {
		t.Fatalf("sweep: %v", err)
	}
	if swept < 1 {
		t.Fatal("expected the expired hold to be released")
	}
	if level := levelOf(t, sku); level.Available != 4 || level.Reserved != 0 {
		t.Fatalf("expected the stock back after sweeping, got %+v", level)
	}
}

func TestUnknownSKUIsReported(t *testing.T) {
	_, err := reserve(t, uuid.NewString(), 1)
	if !errors.Is(err, store.ErrUnknownSKU) {
		t.Fatalf("expected unknown sku, got %v", err)
	}
}

func TestSetStockKeepsHeldStockPromised(t *testing.T) {
	sku := newSKU(t, 5)
	if _, err := reserve(t, sku, 2); err != nil {
		t.Fatalf("reserve: %v", err)
	}
	// The artisan corrects the count down to 3 while 2 are held.
	level, err := shared.SetStock(context.Background(), sku, 3)
	if err != nil {
		t.Fatalf("set stock: %v", err)
	}
	if level.Available != 1 || level.Reserved != 2 {
		t.Fatalf("expected 1 available beside the 2 held, got %+v", level)
	}
}

func TestSetStockNeverGoesNegative(t *testing.T) {
	sku := newSKU(t, 5)
	if _, err := reserve(t, sku, 4); err != nil {
		t.Fatalf("reserve: %v", err)
	}
	// Fewer on hand than are already promised: availability floors at zero
	// rather than going negative, and the holds stand.
	level, err := shared.SetStock(context.Background(), sku, 1)
	if err != nil {
		t.Fatalf("set stock: %v", err)
	}
	if level.Available != 0 || level.Reserved != 4 {
		t.Fatalf("expected no availability and the holds intact, got %+v", level)
	}
}
