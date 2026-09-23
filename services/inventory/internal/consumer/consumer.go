// Package consumer turns order events into committed reservations.
//
// Checkout reserves stock over gRPC and then, once the order is paid and
// persisted, announces it on poshra.orders.created.v1. This consumer is what
// closes that loop: it reads the announcement and settles the hold, so the
// reserved count becomes a sale instead of expiring back into stock.
//
// The call has to be made here rather than by checkout because checkout must
// not block on it. An order that is paid for is final; if inventory is down at
// that moment, the event waits in the topic and is settled when it returns.
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

// Settler is the part of the store this consumer needs, which keeps the tests
// free of a database and states the dependency exactly.
type Settler interface {
	Commit(ctx context.Context, reservationID string) (store.State, error)
}

type Consumer struct {
	client *kgo.Client
	store  Settler
	log    *slog.Logger

	// How long to wait before retrying an event that failed for a reason that
	// may pass, such as the database being unreachable.
	retryBackoff time.Duration
	maxBackoff   time.Duration
}

// orderCreated is the part of the event this service cares about. Anything
// else in the payload is deliberately ignored: a consumer that parses only
// what it uses does not break when the producer adds a field.
type orderCreated struct {
	OrderID       string `json:"order_id"`
	ReservationID string `json:"reservation_id"`
}

func New(db Settler, brokers []string, group, topic string, log *slog.Logger) (*Consumer, error) {
	client, err := kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		// The group is what makes this horizontally scalable: Kafka hands each
		// partition to exactly one member, so two inventory pods split the
		// work instead of both processing every event.
		kgo.ConsumerGroup(group),
		kgo.ConsumeTopics(topic),
		// A new group starts from the beginning of the topic. Starting at the
		// end would silently skip every order placed before the first deploy.
		kgo.ConsumeResetOffset(kgo.NewOffset().AtStart()),
		// Commit after the work, never before: an offset committed early turns
		// a crash into a lost event. This is the at-least-once side of the
		// trade, and it is why Commit has to be idempotent.
		kgo.DisableAutoCommit(),
		// Hold off a rebalance until the polled batch is done and committed,
		// so a partition is never handed to another member mid-batch.
		kgo.BlockRebalanceOnPoll(),
		kgo.OnPartitionsRevoked(func(ctx context.Context, cl *kgo.Client, _ map[string][]int32) {
			// Last chance to record progress before the partitions move: what
			// is not committed here will simply be redelivered elsewhere.
			if err := cl.CommitUncommittedOffsets(ctx); err != nil {
				log.Error("could not commit offsets before rebalance", "error", err)
			}
		}),
	)
	if err != nil {
		return nil, err
	}
	return &Consumer{
		client:       client,
		store:        db,
		log:          log,
		retryBackoff: 500 * time.Millisecond,
		maxBackoff:   30 * time.Second,
	}, nil
}

func (c *Consumer) Close() { c.client.Close() }

// Run consumes until the context is cancelled.
func (c *Consumer) Run(ctx context.Context) {
	for {
		fetches := c.client.PollRecords(ctx, 200)
		if fetches.IsClientClosed() || ctx.Err() != nil {
			return
		}
		fetches.EachError(func(topic string, partition int32, err error) {
			// Fetch errors are transient by nature — a broker restarting, a
			// leader moving. The client retries; this only makes it visible.
			c.log.Error("fetch failed", "topic", topic, "partition", partition, "error", err)
		})

		var done []*kgo.Record
		iter := fetches.RecordIter()
		for !iter.Done() {
			record := iter.Next()
			if !c.process(ctx, record) {
				break // shutting down: leave the rest uncommitted
			}
			done = append(done, record)
		}

		if len(done) > 0 {
			if err := c.client.CommitRecords(ctx, done...); err != nil {
				// Not fatal: the work is done, only the bookmark is missing.
				// These events will arrive again and settle to the same state.
				c.log.Error("could not commit offsets", "error", err)
			}
		}
		c.client.AllowRebalance()
	}
}

// process handles one record, retrying while the failure looks temporary.
// It returns false only when the context is cancelled, which is the one case
// where the record must not be marked done.
func (c *Consumer) process(ctx context.Context, record *kgo.Record) bool {
	backoff := c.retryBackoff
	for {
		err := c.handle(ctx, record)
		if err == nil {
			return true
		}
		if terminal(err) {
			// Retrying cannot help: a malformed payload stays malformed, and a
			// released hold will never become committable. Blocking the
			// partition on it would stop every later order behind it.
			c.log.Error("dropping unprocessable event",
				"error", err, "partition", record.Partition, "offset", record.Offset,
				"key", string(record.Key))
			return true
		}

		c.log.Error("retrying event",
			"error", err, "partition", record.Partition, "offset", record.Offset,
			"backoff", backoff)
		select {
		case <-ctx.Done():
			return false
		case <-time.After(backoff):
		}
		if backoff *= 2; backoff > c.maxBackoff {
			backoff = c.maxBackoff
		}
	}
}

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

// terminal reports whether retrying the same event could ever succeed.
func terminal(err error) bool {
	return errors.Is(err, errUnprocessable) ||
		// The hold was released or expired before the event arrived, or never
		// existed. Both need a human, not another attempt.
		errors.Is(err, store.ErrAlreadySettled) ||
		errors.Is(err, store.ErrNotFound)
}
