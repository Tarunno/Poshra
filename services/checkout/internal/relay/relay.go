// Package relay publishes outbox rows to Kafka.
//
// Checkout writes an event into the outbox inside the order's transaction, so
// the order and its announcement commit together or not at all. Publishing is
// then a separate concern: this loop reads unpublished rows, sends them, and
// marks them sent.
//
// The consequence to keep in mind is delivery semantics. If the send succeeds
// but marking the rows fails, the events are published again — at-least-once,
// not exactly-once. Consumers must therefore be idempotent, which is why
// CommitReservation can be called repeatedly with the same result.
package relay

import (
	"context"
	"encoding/json"
	"errors"
	"log/slog"
	"time"

	"github.com/twmb/franz-go/pkg/kgo"
	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/codes"
	"go.opentelemetry.io/otel/propagation"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
	"go.opentelemetry.io/otel/trace"

	"github.com/Tarunno/Poshra/services/checkout/internal/store"
)

type Relay struct {
	store     *store.Store
	client    *kgo.Client
	log       *slog.Logger
	tracer    trace.Tracer
	batchSize int
	interval  time.Duration
}

func New(db *store.Store, brokers []string, log *slog.Logger) (*Relay, error) {
	client, err := kgo.NewClient(
		kgo.SeedBrokers(brokers...),
		// Wait for every in-sync replica before calling a write durable. The
		// weaker settings return as soon as the leader has the record, and
		// lose it when that broker dies — which would defeat the outbox.
		kgo.RequiredAcks(kgo.AllISRAcks()),
		// With acks=all the client keeps its idempotent producer enabled, so a
		// retry after a timeout cannot append the same record twice. Lowering
		// acks would force us to turn that off.
		kgo.ProducerBatchCompression(kgo.SnappyCompression()),
		// A tick's rows arrive together; a few milliseconds of linger lets them
		// share one request instead of paying a round trip each.
		kgo.ProducerLinger(5*time.Millisecond),
		kgo.RecordRetries(5),
		// Bounds how long a failing send can hold the outbox rows locked.
		kgo.RecordDeliveryTimeout(20*time.Second),
	)
	if err != nil {
		return nil, err
	}
	return &Relay{
		store:     db,
		client:    client,
		log:       log,
		tracer:    otel.Tracer("poshra/outbox-relay"),
		batchSize: 100,
		interval:  time.Second,
	}, nil
}

func (r *Relay) Close() { r.client.Close() }

// Run publishes pending events until the context is cancelled.
func (r *Relay) Run(ctx context.Context) {
	ticker := time.NewTicker(r.interval)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return
		case <-ticker.C:
			published, err := r.store.PublishBatch(ctx, r.batchSize, r.send)
			switch {
			case errors.Is(err, context.Canceled):
				return
			case err != nil:
				// Kafka being down is not an emergency: the rows stay in the
				// outbox and go out when it comes back. Nothing is lost, and
				// orders keep being accepted in the meantime.
				r.log.Error("outbox relay failed", "error", err)
			case published > 0:
				r.log.Info("published outbox events", "count", published)
			}
		}
	}
}

// send publishes one claimed batch and waits for the brokers to acknowledge it.
//
// Each event resumes the trace stored with it when the order was written, so
// the publish appears inside that order rather than as an orphan. The span's
// duration is therefore the outbox's own latency — how long the row sat
// waiting — which is the number you want when asking whether the relay is
// keeping up.
func (r *Relay) send(events []store.PendingEvent) error {
	records := make([]*kgo.Record, 0, len(events))
	spans := make([]trace.Span, 0, len(events))

	for _, event := range events {
		headers := map[string]string{}
		if len(event.Headers) > 0 {
			_ = json.Unmarshal(event.Headers, &headers)
		}

		// Pick the trace back up from the row, then hand the consumers this
		// publish span rather than the original order's — so the chain reads
		// order, publish, consume, in that order.
		ctx := otel.GetTextMapPropagator().Extract(
			context.Background(), propagation.MapCarrier(headers),
		)
		ctx, span := r.tracer.Start(ctx, "publish "+event.Topic,
			trace.WithSpanKind(trace.SpanKindProducer),
			trace.WithAttributes(
				semconv.MessagingSystemKafka,
				semconv.MessagingDestinationName(event.Topic),
				semconv.MessagingMessageIDKey.String(event.Key),
			),
		)
		spans = append(spans, span)

		carrier := propagation.MapCarrier(headers)
		otel.GetTextMapPropagator().Inject(ctx, carrier)

		recordHeaders := make([]kgo.RecordHeader, 0, len(headers))
		for key, value := range headers {
			recordHeaders = append(recordHeaders, kgo.RecordHeader{Key: key, Value: []byte(value)})
		}
		records = append(records, &kgo.Record{
			Topic: event.Topic,
			// The key decides the partition, so every event about one order
			// lands in the same one and keeps its order relative to its
			// siblings. Ordering is per partition, never across a topic.
			Key:     []byte(event.Key),
			Value:   event.Payload,
			Headers: recordHeaders,
		})
	}

	err := r.client.ProduceSync(context.Background(), records...).FirstErr()
	for _, span := range spans {
		if err != nil {
			span.RecordError(err)
			span.SetStatus(codes.Error, "publish failed")
		}
		span.End()
	}
	return err
}
