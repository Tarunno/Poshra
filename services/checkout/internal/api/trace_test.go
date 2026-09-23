package api

import (
	"context"
	"testing"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/propagation"
	"go.opentelemetry.io/otel/trace"
)

// The outbox is where in-process propagation ends, so the trace context has to
// be written into the event itself.
//
// This is the test that would have caught the function being defined and never
// called: Go objects to an unused import or an unused local, but an unused
// package-level function compiles quietly, so everything still built and every
// event went out with no trace on it.
func TestTheEventCarriesTheTraceContext(t *testing.T) {
	previous := otel.GetTextMapPropagator()
	otel.SetTextMapPropagator(propagation.TraceContext{})
	defer otel.SetTextMapPropagator(previous)

	ctx := trace.ContextWithSpanContext(context.Background(), trace.NewSpanContext(
		trace.SpanContextConfig{
			TraceID: trace.TraceID{
				0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08,
				0x09, 0x0a, 0x0b, 0x0c, 0x0d, 0x0e, 0x0f, 0x10,
			},
			SpanID:     trace.SpanID{0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08},
			TraceFlags: trace.FlagsSampled,
		}))

	headers := traceHeaders(ctx, map[string]string{"event_type": "order.created"})

	if headers["traceparent"] == "" {
		t.Fatal("the event carries no traceparent, so everything it causes is an orphan")
	}
	if headers["event_type"] != "order.created" {
		t.Fatal("the headers it was given were lost")
	}
}
