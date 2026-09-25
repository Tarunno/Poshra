package api

import (
	"context"
	"log/slog"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/metric"
)

// orderMetrics counts what the business cares about, which is not what the RED
// dashboard shows.
//
// Rate, errors and duration describe the service: whether it answered, and how
// quickly. These describe the shop: how many pieces sold, for how much, and
// how often a card was refused. A checkout can be perfectly healthy by every
// technical measure while declining every payment, and that is precisely the
// morning somebody needs to be told.
type orderMetrics struct {
	orders metric.Int64Counter
	value  metric.Int64Counter
}

func newOrderMetrics(log *slog.Logger) orderMetrics {
	meter := otel.Meter("poshra.checkout")

	orders, err := meter.Int64Counter(
		"poshra.orders",
		metric.WithDescription("Orders, by how they ended."),
		metric.WithUnit("{order}"),
	)
	if err != nil {
		log.Error("order counter unavailable", "error", err)
	}

	value, err := meter.Int64Counter(
		"poshra.orders.value",
		// Minor units, like everywhere else here: a float would make the
		// total of a day's sales an approximation.
		metric.WithDescription("What confirmed orders came to, in minor units."),
		metric.WithUnit("{minor}"),
	)
	if err != nil {
		log.Error("order value counter unavailable", "error", err)
	}

	return orderMetrics{orders: orders, value: value}
}

// confirmed records a sale. The currency is a dimension because a total across
// taka and euros is not a number.
func (m orderMetrics) confirmed(ctx context.Context, totalMinor int64, currency string) {
	if m.orders == nil {
		return
	}
	attrs := metric.WithAttributes(
		attribute.String("outcome", "confirmed"),
		attribute.String("currency", currency),
	)
	m.orders.Add(ctx, 1, attrs)
	if m.value != nil {
		m.value.Add(ctx, totalMinor, attrs)
	}
}

// ended records an order that did not become a sale: a declined card, stock
// that went while the buyer was deciding, a charge that could not be written
// down. Counted separately from the errors on the dashboard, because a decline
// is the system working.
func (m orderMetrics) ended(ctx context.Context, outcome string) {
	if m.orders == nil {
		return
	}
	m.orders.Add(ctx, 1, metric.WithAttributes(attribute.String("outcome", outcome)))
}
