package consumer

import (
	"context"
	"errors"
	"io"
	"log/slog"
	"testing"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"

	"github.com/Tarunno/Poshra/services/inventory/internal/store"
)

type fakeSettler struct {
	calls  []string
	errs   []error // returned in order, one per call
	always error   // returned once errs is exhausted
	callNo int
}

func (f *fakeSettler) Commit(_ context.Context, reservationID string) (store.State, error) {
	f.calls = append(f.calls, reservationID)
	err := f.always
	if f.callNo < len(f.errs) {
		err = f.errs[f.callNo]
	}
	f.callNo++
	if err != nil {
		return "", err
	}
	return store.StateCommitted, nil
}

func newConsumer(settler Settler) *Consumer {
	return &Consumer{
		store:        settler,
		log:          slog.New(slog.NewTextHandler(io.Discard, nil)),
		retryBackoff: time.Millisecond,
		maxBackoff:   2 * time.Millisecond,
	}
}

func record(payload string) *kgo.Record {
	return &kgo.Record{Topic: "poshra.orders.created.v1", Value: []byte(payload)}
}

func TestSettlesTheReservationNamedInTheEvent(t *testing.T) {
	settler := &fakeSettler{}
	consumer := newConsumer(settler)

	ok := consumer.process(context.Background(),
		record(`{"order_id":"order-1","reservation_id":"res-1","total_minor":1200}`))

	if !ok {
		t.Fatal("the record was not marked done")
	}
	if len(settler.calls) != 1 || settler.calls[0] != "res-1" {
		t.Fatalf("committed %v, want [res-1]", settler.calls)
	}
}

// At-least-once means the same event can arrive twice. The second pass must
// settle to the same state rather than double-counting the sale, which the
// store guarantees and the consumer must not undermine.
func TestADuplicateEventIsHarmless(t *testing.T) {
	settler := &fakeSettler{}
	consumer := newConsumer(settler)
	event := record(`{"order_id":"order-1","reservation_id":"res-1"}`)

	for i := 0; i < 2; i++ {
		if !consumer.process(context.Background(), event) {
			t.Fatalf("attempt %d was not marked done", i+1)
		}
	}
	if len(settler.calls) != 2 {
		t.Fatalf("made %d calls, want 2", len(settler.calls))
	}
}

// A message that can never be processed must not block its partition: every
// order behind it would stop settling.
func TestUnprocessableEventsAreDroppedNotRetried(t *testing.T) {
	for name, payload := range map[string]string{
		"malformed json":    `{"order_id":`,
		"no reservation id": `{"order_id":"order-1"}`,
	} {
		t.Run(name, func(t *testing.T) {
			settler := &fakeSettler{}
			consumer := newConsumer(settler)

			if !consumer.process(context.Background(), record(payload)) {
				t.Fatal("the record was not marked done")
			}
			if len(settler.calls) != 0 {
				t.Fatalf("called the store %d times for an unusable event", len(settler.calls))
			}
		})
	}
}

// A hold that was released or expired cannot be committed. Retrying would
// never succeed, so the event is dropped loudly instead.
func TestASettledReservationIsNotRetried(t *testing.T) {
	settler := &fakeSettler{errs: []error{store.ErrAlreadySettled}}
	consumer := newConsumer(settler)

	if !consumer.process(context.Background(), record(`{"reservation_id":"res-1"}`)) {
		t.Fatal("the record was not marked done")
	}
	if len(settler.calls) != 1 {
		t.Fatalf("made %d attempts, want 1", len(settler.calls))
	}
}

// The database being down is temporary, so the event is retried rather than
// dropped: this is the case the outbox exists to survive.
func TestATemporaryFailureIsRetriedUntilItSucceeds(t *testing.T) {
	down := errors.New("connection refused")
	settler := &fakeSettler{errs: []error{down, down}}
	consumer := newConsumer(settler)

	if !consumer.process(context.Background(), record(`{"reservation_id":"res-1"}`)) {
		t.Fatal("the record was not marked done")
	}
	if len(settler.calls) != 3 {
		t.Fatalf("made %d attempts, want 3 (two failures then a success)", len(settler.calls))
	}
}

// Shutting down mid-retry must leave the offset uncommitted, so the event is
// redelivered to whoever picks the partition up next.
func TestShutdownLeavesTheEventUnprocessed(t *testing.T) {
	settler := &fakeSettler{always: errors.New("the database is down")}
	consumer := newConsumer(settler)

	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Millisecond)
	defer cancel()

	if consumer.process(ctx, record(`{"reservation_id":"res-1"}`)) {
		t.Fatal("the record was marked done although it never settled")
	}
}
