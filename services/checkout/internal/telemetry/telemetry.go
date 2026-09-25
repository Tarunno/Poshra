// Package telemetry wires this service into the collector.
//
// One thing matters more than the spans: the propagator. Without it a request
// that crosses a service boundary starts a new trace on the other side, and
// you get two unrelated traces instead of one story. W3C trace context is what
// makes the gateway, this service and the next agree they are the same request.
//
// Nothing here fails a start-up. A service that will not run because it cannot
// reach its telemetry backend has made observability a dependency of serving
// traffic, which is exactly backwards.
package telemetry

import (
	"context"
	"log/slog"
	"os"
	"time"

	"go.opentelemetry.io/otel"
	"go.opentelemetry.io/otel/attribute"
	"go.opentelemetry.io/otel/exporters/otlp/otlpmetric/otlpmetricgrpc"
	"go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
	"go.opentelemetry.io/otel/propagation"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/resource"
	sdktrace "go.opentelemetry.io/otel/sdk/trace"
	semconv "go.opentelemetry.io/otel/semconv/v1.26.0"
)

// Shutdown flushes whatever has not been sent yet. Call it on the way out, or
// the spans describing a shutdown are the ones you lose.
type Shutdown func(context.Context) error

// Start configures tracing from the standard OTEL_ environment variables.
//
// With no endpoint set it does nothing at all and says so: tests and local
// runs should not need a collector, and a silent no-op is worse than a line in
// the log saying tracing is off.
func Start(ctx context.Context, service string, log *slog.Logger) (Shutdown, error) {
	endpoint := os.Getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
	if endpoint == "" {
		log.Info("tracing is off", "reason", "OTEL_EXPORTER_OTLP_ENDPOINT is not set")
		return func(context.Context) error { return nil }, nil
	}

	exporter, err := otlptracegrpc.New(ctx)
	if err != nil {
		return nil, err
	}

	attrs, err := resource.New(ctx,
		resource.WithFromEnv(), // OTEL_RESOURCE_ATTRIBUTES, if anyone sets it
		resource.WithProcess(),
		resource.WithAttributes(
			semconv.ServiceName(service),
			attribute.String("deployment.environment", os.Getenv("DEPLOY_ENV")),
		),
	)
	if err != nil {
		return nil, err
	}

	provider := sdktrace.NewTracerProvider(
		// Every request is sampled. That is affordable on a home cluster and
		// wrong at scale, where the sampler is the first thing to tune.
		sdktrace.WithSampler(sdktrace.AlwaysSample()),
		sdktrace.WithBatcher(exporter, sdktrace.WithBatchTimeout(5*time.Second)),
		sdktrace.WithResource(attrs),
	)
	otel.SetTracerProvider(provider)

	// Trace context first, baggage second: the first carries the ids, the
	// second carries anything the services choose to pass along with them.
	otel.SetTextMapPropagator(propagation.NewCompositeTextMapPropagator(
		propagation.TraceContext{},
		propagation.Baggage{},
	))

	// Metrics go the same way as the spans, to the same collector. Counting
	// orders is not something a trace can do: a trace answers "what happened
	// to this request", and "how many pieces sold today" is a different
	// question that no sampling strategy can be trusted with.
	meterShutdown := func(context.Context) error { return nil }
	if metrics, err := otlpmetricgrpc.New(ctx); err != nil {
		// A service that will not take orders because it cannot count them
		// has the priorities backwards.
		log.Error("metrics are off", "error", err)
	} else {
		meterProvider := sdkmetric.NewMeterProvider(
			sdkmetric.WithResource(attrs),
			// Long enough that the export is not most of the traffic, short
			// enough that a dashboard is not describing the last minute.
			sdkmetric.WithReader(sdkmetric.NewPeriodicReader(metrics,
				sdkmetric.WithInterval(15*time.Second))),
		)
		otel.SetMeterProvider(meterProvider)
		meterShutdown = meterProvider.Shutdown
	}

	log.Info("tracing on", "service", service, "collector", endpoint)
	return func(ctx context.Context) error {
		// Both, and the first error rather than neither: a failed flush of one
		// is not a reason to skip the other.
		traceErr := provider.Shutdown(ctx)
		if err := meterShutdown(ctx); err != nil && traceErr == nil {
			return err
		}
		return traceErr
	}, nil
}
