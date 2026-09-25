package api_test

import (
	"encoding/json"
	"net/http"
	"testing"

	"github.com/google/uuid"

	"github.com/Tarunno/Poshra/services/checkout/internal/store"
)

type lookup struct {
	Order   store.Order   `json:"order"`
	History []store.Order `json:"history"`
}

func admin() map[string]string {
	return map[string]string{"X-User-Role": "admin"}
}

func TestSupportCanLookUpAnOrderByItsNumber(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Jute mat", 430_000)})
	h.addToCart(t, sku, 2)
	placed := h.placeOrder(t, uuid.NewString(), "tok_ok")
	if placed.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", placed.Code, placed.Body.String())
	}
	var order store.Order
	_ = json.Unmarshal(placed.Body.Bytes(), &order)

	found := h.do(t, http.MethodGet, "/support/orders/"+order.ID, nil, admin())
	if found.Code != http.StatusOK {
		t.Fatalf("expected 200, got %d: %s", found.Code, found.Body.String())
	}

	var body lookup
	_ = json.Unmarshal(found.Body.Bytes(), &body)
	if body.Order.ID != order.ID {
		t.Fatalf("looked up %s, got %s", order.ID, body.Order.ID)
	}
	if len(body.Order.Items) != 1 || body.Order.Items[0].Quantity != 2 {
		t.Fatalf("the order came back without its items: %+v", body.Order.Items)
	}
	// The point of the lookup: whether this has happened to them before.
	if len(body.History) != 1 {
		t.Fatalf("expected the buyer's other orders, got %d", len(body.History))
	}
}

func TestAnOrderNumberIsTheOnlyWayIn(t *testing.T) {
	h := newHarness(t, nil)

	// No route takes a user id, so there is no way to ask what a named person
	// has been buying. Support arrives with an order number; that is the door.
	missing := h.do(t, http.MethodGet, "/support/orders/"+uuid.NewString(), nil, admin())
	if missing.Code != http.StatusNotFound {
		t.Fatalf("expected 404 for an unknown order, got %d", missing.Code)
	}
}

func TestOnlyAnAdministratorMayLookUpSomebodyElsesOrder(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Jute mat", 430_000)})
	h.addToCart(t, sku, 1)
	placed := h.placeOrder(t, uuid.NewString(), "tok_ok")
	var order store.Order
	_ = json.Unmarshal(placed.Body.Bytes(), &order)

	// The buyer's own session, which can read this order through /orders/{id},
	// must not be able to read the route that reads anybody's.
	refused := h.do(t, http.MethodGet, "/support/orders/"+order.ID, nil, nil)
	if refused.Code != http.StatusForbidden {
		t.Fatalf("expected 403 without the admin role, got %d", refused.Code)
	}

	// And a role a client made up cannot be used either: the gateway strips
	// this header on the way in and sets it from the signed token. This test
	// documents that the service trusts it for that reason alone.
	for _, role := range []string{"buyer", "artisan", "administrator", ""} {
		got := h.do(t, http.MethodGet, "/support/orders/"+order.ID, nil,
			map[string]string{"X-User-Role": role})
		if got.Code != http.StatusForbidden {
			t.Fatalf("role %q got %d, expected 403", role, got.Code)
		}
	}
}
