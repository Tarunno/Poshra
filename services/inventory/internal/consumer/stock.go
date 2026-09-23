package consumer

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"

	"github.com/Tarunno/Poshra/services/inventory/internal/store"
)

// Leveller is the part of the store the stock consumer needs.
type Leveller interface {
	SetStock(ctx context.Context, skuID string, quantity int32) (store.Level, error)
}

// StockConsumer keeps the ledger in step with what the catalog lists.
type StockConsumer struct {
	group *group
	store Leveller
	log   *slog.Logger
}

// stockChanged is what the catalog announces. It carries the level, not the
// change, so a replay or an out-of-order retry settles on the same number
// rather than adding to it twice.
type stockChanged struct {
	SKUID    string `json:"sku_id"`
	Quantity int32  `json:"quantity"`
	Status   string `json:"status"`
}

func NewStock(
	db Leveller, brokers []string, groupID, topic string, log *slog.Logger,
) (*StockConsumer, error) {
	client, err := dial(brokers, groupID, topic, log)
	if err != nil {
		return nil, err
	}
	consumer := &StockConsumer{store: db, log: log}
	consumer.group = &group{
		client:       client,
		log:          log,
		retryBackoff: 500 * time.Millisecond,
		maxBackoff:   30 * time.Second,
		handle:       consumer.handle,
		terminal:     stockTerminal,
	}
	return consumer, nil
}

func (c *StockConsumer) Close()                  { c.group.client.Close() }
func (c *StockConsumer) Run(ctx context.Context) { c.group.run(ctx) }

func (c *StockConsumer) handle(ctx context.Context, record *kgo.Record) error {
	var event stockChanged
	if err := json.Unmarshal(record.Value, &event); err != nil {
		return fmt.Errorf("%w: %w", errUnprocessable, err)
	}
	if event.SKUID == "" {
		return fmt.Errorf("%w: no sku_id", errUnprocessable)
	}
	if event.Quantity < 0 {
		return fmt.Errorf("%w: negative quantity %d", errUnprocessable, event.Quantity)
	}

	setCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	level, err := c.store.SetStock(setCtx, event.SKUID, event.Quantity)
	if err != nil {
		return err
	}
	c.log.Info("stock level set",
		"sku_id", event.SKUID, "announced", event.Quantity,
		"available", level.Available, "reserved", level.Reserved,
		"partition", record.Partition, "offset", record.Offset)
	return nil
}

// stockTerminal: only a malformed event is hopeless here. A database that is
// down is worth waiting for, because the alternative is a level that stays
// wrong until someone runs the reconciler.
func stockTerminal(err error) bool {
	return errors.Is(err, errUnprocessable)
}
