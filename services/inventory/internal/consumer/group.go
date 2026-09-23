package consumer

import (
	"context"
	"log/slog"
	"strconv"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"
)

// handler processes one record. It returns an error to say "try again"; a
// failure that can never succeed is the handler's own to log and swallow,
// because blocking a partition on it would stop everything queued behind it.
type handler func(ctx context.Context, record *kgo.Record) error

// terminalFn reports whether retrying an error could ever succeed.
type terminalFn func(error) bool

// group is the part every consumer here shares: join, poll, process, commit.
//
// The shape is the same whatever the topic, and the parts that differ — what a
// record means, and which failures are worth retrying — are the arguments.
type group struct {
	client       *kgo.Client
	log          *slog.Logger
	tracer       trace.Tracer
	retryBackoff time.Duration
	maxBackoff   time.Duration
	handle       handler
	terminal     terminalFn
}

// dial joins a consumer group with the settings that make delivery
// at-least-once rather than at-most-once.
func dial(brokers []string, groupID, topic string, log *slog.Logger) (*kgo.Client, error) {
	return kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		// The group is what makes this horizontally scalable: Kafka hands each
		// partition to exactly one member, so two pods split the work instead
		// of both processing every event.
		kgo.ConsumerGroup(groupID),
		kgo.ConsumeTopics(topic),
		// A new group starts from the beginning of the topic. Starting at the
		// end would silently skip everything published before the first deploy.
		kgo.ConsumeResetOffset(kgo.NewOffset().AtStart()),
		// Commit after the work, never before: an offset committed early turns
		// a crash into a lost event. This is the at-least-once side of the
		// trade, and why every handler here has to be idempotent.
		kgo.DisableAutoCommit(),
		// Hold off a rebalance until the polled batch is done and committed,
		// so a partition is never handed to another member mid-batch.
		kgo.BlockRebalanceOnPoll(),
		kgo.OnPartitionsRevoked(func(ctx context.Context, cl *kgo.Client, _ map[string][]int32) {
			// Last chance to record progress before the partitions move: what
			// is not committed here is simply redelivered elsewhere.
			if err := cl.CommitUncommittedOffsets(ctx); err != nil {
				log.Error("could not commit offsets before rebalance", "error", err)
			}
		}),
	)
}

// run consumes until the context is cancelled.
// startSpan continues the producer's trace, when the record carries one.
func (g *group) startSpan(ctx context.Context, record *kgo.Record) (context.Context, trace.Span) {
	carrier := propagation.MapCarrier{}
	for _, header := range record.Headers {
		carrier[header.Key] = string(header.Value)
	}
	// Extract before starting, so the span is a child of the publish rather
	// than the root of a trace nobody can connect to anything.
	ctx = otel.GetTextMapPropagator().Extract(ctx, carrier)

	if g.tracer == nil {
		g.tracer = otel.Tracer("poshra/kafka-consumer")
	}
	return g.tracer.Start(ctx, "consume "+record.Topic,
		trace.WithSpanKind(trace.SpanKindConsumer),
		trace.WithAttributes(
			semconv.MessagingSystemKafka,
			semconv.MessagingDestinationName(record.Topic),
			semconv.MessagingKafkaMessageOffset(int(record.Offset)),
			semconv.MessagingDestinationPartitionID(strconv.Itoa(int(record.Partition))),
		),
	)
}

func (g *group) run(ctx context.Context) {
	for {
		fetches := g.client.PollRecords(ctx, 200)
		if fetches.IsClientClosed() || ctx.Err() != nil {
			return
		}
		fetches.EachError(func(topic string, partition int32, err error) {
			// Fetch errors are transient by nature — a broker restarting, a
			// leader moving. The client retries; this only makes it visible.
			g.log.Error("fetch failed", "topic", topic, "partition", partition, "error", err)
		})

		var done []*kgo.Record
		iter := fetches.RecordIter()
		for !iter.Done() {
			record := iter.Next()
			if !g.process(ctx, record) {
				break // shutting down: leave the rest uncommitted
			}
			done = append(done, record)
		}

		if len(done) > 0 {
			if err := g.client.CommitRecords(ctx, done...); err != nil {
				// Not fatal: the work is done, only the bookmark is missing.
				// These events arrive again and settle to the same state.
				g.log.Error("could not commit offsets", "error", err)
			}
		}
		g.client.AllowRebalance()
	}
}

// process handles one record, retrying while the failure looks temporary. It
// returns false only when the context is cancelled, which is the one case
// where the record must not be marked done.
//
// The record carries the trace of whatever produced it, so this work joins
// that story rather than starting a new one. A gap between the publish span
// and this one is consumer lag, visible without a single metric.
func (g *group) process(ctx context.Context, record *kgo.Record) bool {
	ctx, span := g.startSpan(ctx, record)
	defer span.End()

	backoff := g.retryBackoff
	for {
		err := g.handle(ctx, record)
		if err == nil {
			return true
		}
		if g.terminal(err) {
			span.RecordError(err)
			span.SetStatus(codes.Error, "dropped")
			// Retrying cannot help: a malformed payload stays malformed.
			// Blocking the partition on it would stop every later event.
			g.log.Error("dropping unprocessable event",
				"error", err, "topic", record.Topic, "partition", record.Partition,
				"offset", record.Offset, "key", string(record.Key))
			return true
		}

		g.log.Error("retrying event",
			"error", err, "topic", record.Topic, "partition", record.Partition,
			"offset", record.Offset, "backoff", backoff)
		select {
		case <-ctx.Done():
			return false
		case <-time.After(backoff):
		}
		if backoff *= 2; backoff > g.maxBackoff {
			backoff = g.maxBackoff
		}
	}
}
