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

type fakeLeveller struct {
	set []struct {
		sku      string
		quantity int32
	}
	always error
}

func (f *fakeLeveller) SetStock(
	_ context.Context, skuID string, quantity int32,
) (store.Level, error) {
	f.set = append(f.set, struct {
		sku      string
		quantity int32
	}{skuID, quantity})
	if f.always != nil {
		return store.Level{}, f.always
	}
	return store.Level{SKUID: skuID, Available: quantity}, nil
}

func newStockConsumer(leveller Leveller) *StockConsumer {
	log := slog.New(slog.NewTextHandler(io.Discard, nil))
	consumer := &StockConsumer{store: leveller, log: log}
	consumer.group = &group{
		log:          log,
		retryBackoff: time.Millisecond,
		maxBackoff:   2 * time.Millisecond,
		handle:       consumer.handle,
		terminal:     stockTerminal,
	}
	return consumer
}

func stockRecord(payload string) *kgo.Record {
	return &kgo.Record{Topic: "poshra.catalog.stock.changed.v1", Value: []byte(payload)}
}

func TestAnAnnouncedLevelIsWrittenToTheLedger(t *testing.T) {
	leveller := &fakeLeveller{}
	consumer := newStockConsumer(leveller)

	if !consumer.group.process(context.Background(),
		stockRecord(`{"sku_id":"sku-1","quantity":5,"status":"published"}`)) {
		t.Fatal("the record was not marked done")
	}
	if len(leveller.set) != 1 || leveller.set[0].quantity != 5 {
		t.Fatalf("wrote %v, want one level of 5", leveller.set)
	}
}

// The event carries the level, not a change, so applying it twice lands on the
// same number instead of doubling it. That is what makes at-least-once safe.
func TestReplayingALevelIsHarmless(t *testing.T) {
	leveller := &fakeLeveller{}
	consumer := newStockConsumer(leveller)
	event := stockRecord(`{"sku_id":"sku-1","quantity":3,"status":"published"}`)

	consumer.group.process(context.Background(), event)
	consumer.group.process(context.Background(), event)

	for _, call := range leveller.set {
		if call.quantity != 3 {
			t.Fatalf("a replay changed the level to %d", call.quantity)
		}
	}
}

// Zero is a real instruction, not a missing field: it is how the catalog says
// a piece has been withdrawn from the shop.
func TestZeroWithdrawsThePiece(t *testing.T) {
	leveller := &fakeLeveller{}
	consumer := newStockConsumer(leveller)

	consumer.group.process(context.Background(),
		stockRecord(`{"sku_id":"sku-1","quantity":0,"status":"archived"}`))

	if len(leveller.set) != 1 || leveller.set[0].quantity != 0 {
		t.Fatalf("wrote %v, want a level of 0", leveller.set)
	}
}

func TestMalformedStockEventsAreDropped(t *testing.T) {
	for name, payload := range map[string]string{
		"broken json":       `{"sku_id":`,
		"no sku":            `{"quantity":2}`,
		"negative quantity": `{"sku_id":"sku-1","quantity":-1}`,
	} {
		t.Run(name, func(t *testing.T) {
			leveller := &fakeLeveller{}
			consumer := newStockConsumer(leveller)

			if !consumer.group.process(context.Background(), stockRecord(payload)) {
				t.Fatal("the record was not marked done")
			}
			if len(leveller.set) != 0 {
				t.Fatalf("wrote %d levels for an unusable event", len(leveller.set))
			}
		})
	}
}

// A database that is down is worth waiting for: the alternative is a level
// that stays wrong until someone runs the reconciler.
func TestADatabaseFailureIsRetried(t *testing.T) {
	leveller := &fakeLeveller{always: errors.New("connection refused")}
	consumer := newStockConsumer(leveller)

	ctx, cancel := context.WithTimeout(context.Background(), 20*time.Millisecond)
	defer cancel()

	if consumer.group.process(ctx, stockRecord(`{"sku_id":"sku-1","quantity":1}`)) {
		t.Fatal("the record was marked done although it never landed")
	}
	if len(leveller.set) < 2 {
		t.Fatalf("made %d attempts, want more than one", len(leveller.set))
	}
}
