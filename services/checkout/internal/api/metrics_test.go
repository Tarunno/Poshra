package api_test

import (
	"context"
	"net/http"
	"testing"

	"github.com/google/uuid"
	"go.opentelemetry.io/otel"
	sdkmetric "go.opentelemetry.io/otel/sdk/metric"
	"go.opentelemetry.io/otel/sdk/metric/metricdata"

	"github.com/Tarunno/Poshra/services/checkout/internal/payment"
)

// collected reads every counter out of a manual reader, keyed by the outcome
// it was recorded against.
func collected(t *testing.T, reader *sdkmetric.ManualReader, name string) map[string]int64 {
	t.Helper()

	var collected metricdata.ResourceMetrics
	if err := reader.Collect(context.Background(), &collected); err != nil {
		t.Fatalf("collect: %v", err)
	}

	byOutcome := map[string]int64{}
	for _, scope := range collected.ScopeMetrics {
		for _, m := range scope.Metrics {
			if m.Name != name {
				continue
			}
			sum, ok := m.Data.(metricdata.Sum[int64])
			if !ok {
				t.Fatalf("%s is not an int64 sum, got %T", name, m.Data)
			}
			for _, point := range sum.DataPoints {
				outcome, _ := point.Attributes.Value("outcome")
				byOutcome[outcome.AsString()] += point.Value
			}
		}
	}
	return byOutcome
}

// counting installs a meter provider for one test and hands back its reader.
func counting(t *testing.T) *sdkmetric.ManualReader {
	t.Helper()

	reader := sdkmetric.NewManualReader()
	previous := otel.GetMeterProvider()
	otel.SetMeterProvider(sdkmetric.NewMeterProvider(sdkmetric.WithReader(reader)))
	t.Cleanup(func() { otel.SetMeterProvider(previous) })
	return reader
}

func TestASaleIsCountedWithWhatItWasWorth(t *testing.T) {
	reader := counting(t)
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Jute mat", 430_000)})
	h.addToCart(t, sku, 2)

	if res := h.placeOrder(t, uuid.NewString(), "tok_ok"); res.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", res.Code, res.Body.String())
	}

	if orders := collected(t, reader, "poshra.orders")["confirmed"]; orders != 1 {
		t.Fatalf("expected one confirmed order, got %d", orders)
	}
	// Minor units, and the total rather than the unit price: two mats at
	// 4,300 taka is 8,600 taka of business, which is the number the shop
	// cares about.
	if value := collected(t, reader, "poshra.orders.value")["confirmed"]; value != 860_000 {
		t.Fatalf("expected 860000 minor units, got %d", value)
	}
}

func TestADeclineIsCountedAndIsNotASale(t *testing.T) {
	reader := counting(t)
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Terracotta jar", 210_000)})
	h.addToCart(t, sku, 1)

	if res := h.placeOrder(t, uuid.NewString(), payment.DeclineToken); res.Code != http.StatusPaymentRequired {
		t.Fatalf("expected 402, got %d", res.Code)
	}

	orders := collected(t, reader, "poshra.orders")
	if orders["declined"] != 1 {
		t.Fatalf("expected one declined order, got %d", orders["declined"])
	}
	// The distinction the RED dashboard cannot make: a checkout declining
	// every card is healthy by every technical measure.
	if orders["confirmed"] != 0 {
		t.Fatalf("a decline was counted as a sale")
	}
	if value := collected(t, reader, "poshra.orders.value")["confirmed"]; value != 0 {
		t.Fatalf("a declined order added %d to the day's takings", value)
	}
}
