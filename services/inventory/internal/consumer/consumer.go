// Package consumer reads the event streams inventory cares about.
//
// Two of them, sharing one group loop:
//
//   - orders, which settle the holds checkout placed over gRPC. The call has to
//     be made here rather than by checkout because checkout must not block on
//     it: an order that is paid for is final, so if inventory is down the event
//     waits in the topic and is settled when it returns.
//   - stock levels, which the catalog announces when an artisan saves a
//     listing. The catalog owns what a piece is; this service owns how many can
//     be sold, and this is how the second learns about the first.
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

// Settler is the part of the store the order consumer needs, which keeps its
// tests free of a database and states the dependency exactly.
type Settler interface {
	Commit(ctx context.Context, reservationID string) (store.State, error)
}

type Consumer struct {
	group *group
	store Settler
	log   *slog.Logger
}

// orderCreated is the part of the event this service cares about. Anything
// else in the payload is deliberately ignored: a consumer that parses only
// what it uses does not break when the producer adds a field.
type orderCreated struct {
	OrderID       string `json:"order_id"`
	ReservationID string `json:"reservation_id"`
}

func New(db Settler, brokers []string, groupID, topic string, log *slog.Logger) (*Consumer, error) {
	client, err := dial(brokers, groupID, topic, log)
	if err != nil {
		return nil, err
	}
	consumer := &Consumer{store: db, log: log}
	consumer.group = &group{
		client:       client,
		log:          log,
		retryBackoff: 500 * time.Millisecond,
		maxBackoff:   30 * time.Second,
		handle:       consumer.handle,
		terminal:     terminal,
	}
	return consumer, nil
}

func (c *Consumer) Close()                  { c.group.client.Close() }
func (c *Consumer) Run(ctx context.Context) { c.group.run(ctx) }

func (c *Consumer) handle(ctx context.Context, record *kgo.Record) error {
	var event orderCreated
	if err := json.Unmarshal(record.Value, &event); err != nil {
		return fmt.Errorf("%w: %w", errUnprocessable, err)
	}
	if event.ReservationID == "" {
		return fmt.Errorf("%w: no reservation_id", errUnprocessable)
	}

	commitCtx, cancel := context.WithTimeout(ctx, 5*time.Second)
	defer cancel()

	state, err := c.store.Commit(commitCtx, event.ReservationID)
	if err != nil {
		return err
	}
	c.log.Info("settled reservation",
		"order_id", event.OrderID, "reservation_id", event.ReservationID,
		"state", state, "partition", record.Partition, "offset", record.Offset)
	return nil
}

var errUnprocessable = errors.New("unprocessable event")

// terminal reports whether retrying the same order event could ever succeed.
func terminal(err error) bool {
	return errors.Is(err, errUnprocessable) ||
		// The hold was released or expired before the event arrived, or never
		// existed. Both need a human, not another attempt.
		errors.Is(err, store.ErrAlreadySettled) ||
		errors.Is(err, store.ErrNotFound)
}
