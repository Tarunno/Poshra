package store_test

import (
	"context"
	"errors"
	"fmt"
	"os"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/testcontainers/testcontainers-go"
	tcpostgres "github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"

	"github.com/Tarunno/Poshra/services/checkout/internal/store"
)

var db *store.Store

func TestMain(m *testing.M) {
	ctx := context.Background()
	container, err := tcpostgres.Run(ctx, "postgres:17-alpine",
		tcpostgres.WithDatabase("checkout"),
		tcpostgres.WithUsername("checkout"),
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
	db, err = store.New(ctx, dsn)
	if err != nil {
		panic(err)
	}
	if err := db.Migrate(ctx); err != nil {
		panic(err)
	}

	code := m.Run()
	db.Close()
	_ = testcontainers.TerminateContainer(container)
	os.Exit(code)
}

// writeOrder commits one order and its event, the way checkout does.
func writeOrder(t *testing.T) string {
	t.Helper()
	orderID := uuid.NewString()
	err := db.CreateOrder(context.Background(),
		store.Order{
			ID:            orderID,
			UserID:        uuid.NewString(),
			Status:        "confirmed",
			TotalMinor:    1200,
			Currency:      "BDT",
			ReservationID: orderID,
			PaymentRef:    "pay_" + orderID,
			CreatedAt:     time.Now().UTC(),
			Items: []store.OrderItem{{
				SKUID: uuid.NewString(), Quantity: 1, UnitMinor: 1200,
				Title: "Nakshi kantha", ArtisanName: "Rupa",
			}},
		},
		store.OutboxEvent{
			AggregateID: orderID,
			Topic:       "poshra.orders.created.v1",
			EventType:   "order.created",
			Payload:     map[string]any{"order_id": orderID},
			Headers:     map[string]string{"event_type": "order.created"},
		})
	if err != nil {
		t.Fatalf("create order: %v", err)
	}
	return orderID
}

func TestPublishBatchMarksEventsPublished(t *testing.T) {
	orderID := writeOrder(t)
	ctx := context.Background()

	var sent []store.PendingEvent
	count, err := db.PublishBatch(ctx, 10, func(events []store.PendingEvent) error {
		sent = append(sent, events...)
		return nil
	})
	if err != nil {
		t.Fatalf("publish: %v", err)
	}
	if count != len(sent) || count == 0 {
		t.Fatalf("published %d events but sent %d", count, len(sent))
	}

	var found bool
	for _, event := range sent {
		if event.Key == orderID {
			found = true
			// The key is the aggregate id: everything about one order goes to
			// one partition and so stays in order.
			if event.Topic != "poshra.orders.created.v1" {
				t.Fatalf("unexpected topic %q", event.Topic)
			}
		}
	}
	if !found {
		t.Fatalf("the order's event was not claimed")
	}

	// A second pass must find nothing: published rows are not sent twice.
	count, err = db.PublishBatch(ctx, 10, func([]store.PendingEvent) error {
		t.Fatal("send called with no pending events")
		return nil
	})
	if err != nil || count != 0 {
		t.Fatalf("second pass published %d (err %v), want 0", count, err)
	}
}

// A failed send must leave the rows for the next tick: this is what makes a
// Kafka outage harmless rather than a source of lost events.
func TestPublishBatchKeepsEventsWhenSendFails(t *testing.T) {
	writeOrder(t)
	ctx := context.Background()
	boom := errors.New("kafka is down")

	if _, err := db.PublishBatch(ctx, 10, func([]store.PendingEvent) error {
		return boom
	}); !errors.Is(err, boom) {
		t.Fatalf("got %v, want the send error", err)
	}

	count, err := db.PublishBatch(ctx, 10, func([]store.PendingEvent) error { return nil })
	if err != nil {
		t.Fatalf("publish: %v", err)
	}
	if count == 0 {
		t.Fatal("the unsent events were lost")
	}
}

// Two relays running at once must split the work rather than both sending the
// same rows. SKIP LOCKED is what makes the second one take different rows
// instead of waiting for the first to commit.
func TestConcurrentRelaysDoNotSendTheSameEvent(t *testing.T) {
	for i := 0; i < 4; i++ {
		writeOrder(t)
	}
	ctx := context.Background()

	claimed := make(chan struct{})
	release := make(chan struct{})
	first := make(chan []store.PendingEvent, 1)

	go func() {
		_, _ = db.PublishBatch(ctx, 2, func(events []store.PendingEvent) error {
			first <- events
			close(claimed)
			<-release // hold the rows locked while the other relay runs
			return nil
		})
	}()

	<-claimed
	var second []store.PendingEvent
	if _, err := db.PublishBatch(ctx, 2, func(events []store.PendingEvent) error {
		second = events
		return nil
	}); err != nil {
		t.Fatalf("second relay: %v", err)
	}
	close(release)

	seen := map[int64]bool{}
	for _, event := range <-first {
		seen[event.ID] = true
	}
	if len(second) == 0 {
		t.Fatal("the second relay claimed nothing; it waited instead of skipping")
	}
	for _, event := range second {
		if seen[event.ID] {
			t.Fatalf("event %d was claimed by both relays", event.ID)
		}
	}
}

// Migrating twice must be a no-op. The Jobs run on every deploy, so a migrator
// that re-applies its files would break on the first statement that is not
// guarded with IF NOT EXISTS.
func TestMigrateIsSafeToRunAgain(t *testing.T) {
	ctx := context.Background()
	if err := db.Migrate(ctx); err != nil {
		t.Fatalf("second migrate: %v", err)
	}
	if err := db.Migrate(ctx); err != nil {
		t.Fatalf("third migrate: %v", err)
	}

	// And the data still works afterwards, so nothing was dropped or reset.
	writeOrder(t)
	count, err := db.PublishBatch(ctx, 10, func([]store.PendingEvent) error { return nil })
	if err != nil || count == 0 {
		t.Fatalf("published %d (err %v) after re-migrating, want at least 1", count, err)
	}
}
