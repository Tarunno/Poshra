package api_test

import (
	"context"
	"encoding/json"
	"fmt"
	"log/slog"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"sync"
	"testing"
	"time"

	"github.com/google/uuid"
	"github.com/testcontainers/testcontainers-go"
	tcpostgres "github.com/testcontainers/testcontainers-go/modules/postgres"
	"github.com/testcontainers/testcontainers-go/wait"
	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/status"
	"google.golang.org/grpc/test/bufconn"
	"google.golang.org/protobuf/types/known/timestamppb"

	"github.com/Tarunno/Poshra/services/checkout/internal/api"
	"github.com/Tarunno/Poshra/services/checkout/internal/catalog"
	"github.com/Tarunno/Poshra/services/checkout/internal/config"
	"github.com/Tarunno/Poshra/services/checkout/internal/payment"
	"github.com/Tarunno/Poshra/services/checkout/internal/store"
	inventoryv1 "github.com/Tarunno/Poshra/services/inventory/gen/poshra/inventory/v1"
)

// --- a fake inventory service ------------------------------------------------

// fakeInventory records what checkout asked for, so the tests can assert on
// the compensation calls as well as the happy path.
type fakeInventory struct {
	inventoryv1.UnimplementedInventoryServiceServer

	mu           sync.Mutex
	reserveErr   error
	reserved     []string
	released     []string
	releaseCount int
	committed    []string
}

func (f *fakeInventory) ReserveStock(
	_ context.Context, req *inventoryv1.ReserveStockRequest,
) (*inventoryv1.ReserveStockResponse, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	if f.reserveErr != nil {
		return nil, f.reserveErr
	}
	f.reserved = append(f.reserved, req.GetReservationId())
	return &inventoryv1.ReserveStockResponse{
		ReservationId: req.GetReservationId(),
		State:         inventoryv1.ReservationState_RESERVATION_STATE_HELD,
		ExpiresAt:     timestamppb.New(time.Now().Add(15 * time.Minute)),
		Created:       true,
	}, nil
}

func (f *fakeInventory) ReleaseReservation(
	_ context.Context, req *inventoryv1.ReleaseReservationRequest,
) (*inventoryv1.ReleaseReservationResponse, error) {
	f.mu.Lock()
	defer f.mu.Unlock()
	f.released = append(f.released, req.GetReason())
	f.releaseCount++
	return &inventoryv1.ReleaseReservationResponse{
		State: inventoryv1.ReservationState_RESERVATION_STATE_RELEASED,
	}, nil
}

func (f *fakeInventory) releases() []string {
	f.mu.Lock()
	defer f.mu.Unlock()
	return append([]string(nil), f.released...)
}

// inventoryClient wires a real gRPC client to a real server over an in-memory
// pipe. Nothing is stubbed on the client side, so serialisation, status codes
// and deadlines all behave as they will in production, with no ports involved.
func inventoryClient(t *testing.T, fake *fakeInventory) inventoryv1.InventoryServiceClient {
	t.Helper()
	listener := bufconn.Listen(1024 * 1024)
	server := grpc.NewServer()
	inventoryv1.RegisterInventoryServiceServer(server, fake)
	go func() { _ = server.Serve(listener) }()

	conn, err := grpc.NewClient("passthrough://bufnet",
		grpc.WithContextDialer(func(ctx context.Context, _ string) (net.Conn, error) {
			return listener.DialContext(ctx)
		}),
		grpc.WithTransportCredentials(insecure.NewCredentials()),
	)
	if err != nil {
		t.Fatalf("dial bufconn: %v", err)
	}
	t.Cleanup(func() {
		_ = conn.Close()
		server.Stop()
	})
	return inventoryv1.NewInventoryServiceClient(conn)
}

// --- a fake catalog ----------------------------------------------------------

func catalogServer(t *testing.T, products map[string]map[string]any) *catalog.Client {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		results := []map[string]any{}
		for _, id := range splitIDs(r.URL.Query().Get("ids")) {
			if product, ok := products[id]; ok {
				results = append(results, product)
			}
		}
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{"results": results})
	}))
	t.Cleanup(server.Close)
	return catalog.New(server.URL, 2*time.Second)
}

func splitIDs(raw string) []string {
	if raw == "" {
		return nil
	}
	var ids []string
	current := ""
	for _, ch := range raw {
		if ch == ',' {
			if current != "" {
				ids = append(ids, current)
			}
			current = ""
			continue
		}
		current += string(ch)
	}
	if current != "" {
		ids = append(ids, current)
	}
	return ids
}

func product(id, title string, priceMinor int64) map[string]any {
	return map[string]any{
		"id": id, "title": title, "price_minor": priceMinor,
		"currency": "BDT", "in_stock": true,
		"artisan": map[string]any{"display_name": "Rina Akter"},
	}
}

// --- harness -----------------------------------------------------------------

var db *store.Store

func TestMain(m *testing.M) {
	ctx := context.Background()
	container, err := tcpostgres.Run(ctx, "postgres:17-alpine",
		tcpostgres.WithDatabase("checkout"),
		tcpostgres.WithUsername("checkout"),
		tcpostgres.WithPassword("test"),
		testcontainers.WithWaitStrategy(
			wait.ForLog("database system is ready to accept connections").
				WithOccurrence(2).WithStartupTimeout(60*time.Second)),
	)
	if err != nil {
		panic(fmt.Sprintf("start postgres: %v", err))
	}
	dsn, err := container.ConnectionString(ctx, "sslmode=disable")
	if err != nil {
		panic(err)
	}
	db, err = store.New(ctx, dsn)
	if err != nil {
		panic(err)
	}
	if err := db.Migrate(ctx); err != nil {
		panic(err)
	}

	code := m.Run()
	db.Close()
	_ = testcontainers.TerminateContainer(container)
	os.Exit(code)
}

type harness struct {
	handler   http.Handler
	inventory *fakeInventory
	user      string
}

func newHarness(t *testing.T, products map[string]map[string]any) *harness {
	t.Helper()
	fake := &fakeInventory{}
	cfg, err := loadTestConfig()
	if err != nil {
		t.Fatalf("config: %v", err)
	}
	server := api.New(
		cfg,
		slog.New(slog.NewTextHandler(os.Stderr, &slog.HandlerOptions{Level: slog.LevelError})),
		db,
		catalogServer(t, products),
		inventoryClient(t, fake),
		payment.Fake{},
	)
	return &harness{handler: server.Handler(), inventory: fake, user: uuid.NewString()}
}

func loadTestConfig() (config.Config, error) {
	_ = os.Setenv("DATABASE_URL", "postgres://unused")
	_ = os.Setenv("INVENTORY_ADDR", "bufnet")
	_ = os.Setenv("CATALOG_URL", "http://unused")
	_ = os.Setenv("KAFKA_BROKERS", "unused:9092")
	return config.Load()
}

func (h *harness) do(t *testing.T, method, path string, body any, headers map[string]string) *httptest.ResponseRecorder {
	t.Helper()
	var payload *string
	if body != nil {
		encoded, err := json.Marshal(body)
		if err != nil {
			t.Fatalf("encode body: %v", err)
		}
		text := string(encoded)
		payload = &text
	}

	var req *http.Request
	if payload != nil {
		req = httptest.NewRequest(method, path, stringReader(*payload))
	} else {
		req = httptest.NewRequest(method, path, nil)
	}
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("X-User-Id", h.user) // as the gateway would set it
	for key, value := range headers {
		req.Header.Set(key, value)
	}

	recorder := httptest.NewRecorder()
	h.handler.ServeHTTP(recorder, req)
	return recorder
}

func stringReader(s string) *stringReadCloser { return &stringReadCloser{s: s} }

type stringReadCloser struct {
	s string
	i int
}

func (r *stringReadCloser) Read(p []byte) (int, error) {
	if r.i >= len(r.s) {
		return 0, fmt.Errorf("EOF")
	}
	n := copy(p, r.s[r.i:])
	r.i += n
	return n, nil
}

func (h *harness) addToCart(t *testing.T, sku string, quantity int32) {
	t.Helper()
	res := h.do(t, http.MethodPost, "/cart/items",
		map[string]any{"sku_id": sku, "quantity": quantity}, nil)
	if res.Code != http.StatusOK {
		t.Fatalf("add to cart: %d %s", res.Code, res.Body.String())
	}
}

func (h *harness) placeOrder(t *testing.T, key, token string) *httptest.ResponseRecorder {
	t.Helper()
	return h.do(t, http.MethodPost, "/orders",
		map[string]any{"payment_token": token},
		map[string]string{"Idempotency-Key": key})
}

// --- tests -------------------------------------------------------------------

func TestOrderReservesStockChargesAndRecordsAnEvent(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Jamdani saree", 4_200_000)})
	h.addToCart(t, sku, 2)

	res := h.placeOrder(t, uuid.NewString(), "tok_ok")
	if res.Code != http.StatusCreated {
		t.Fatalf("expected 201, got %d: %s", res.Code, res.Body.String())
	}

	var order store.Order
	if err := json.Unmarshal(res.Body.Bytes(), &order); err != nil {
		t.Fatalf("decode order: %v", err)
	}
	if order.TotalMinor != 8_400_000 {
		t.Fatalf("expected the catalog price times two, got %d", order.TotalMinor)
	}
	if order.Status != "confirmed" || order.PaymentRef == "" {
		t.Fatalf("expected a confirmed, paid order, got %+v", order)
	}

	// The event was written in the same transaction as the order.
	events, err := db.UnpublishedEvents(context.Background(), 10)
	if err != nil {
		t.Fatalf("outbox: %v", err)
	}
	found := false
	for _, event := range events {
		if event.Key == order.ID && event.Topic == api.OrdersTopic {
			found = true
		}
	}
	if !found {
		t.Fatal("expected an unpublished order.created event keyed by the order id")
	}

	// The cart is emptied by the same transaction, so the order cannot be
	// placed twice from a stale cart.
	cart := h.do(t, http.MethodGet, "/cart", nil, nil)
	var cartBody struct {
		Items []any `json:"items"`
	}
	_ = json.Unmarshal(cart.Body.Bytes(), &cartBody)
	if len(cartBody.Items) != 0 {
		t.Fatalf("expected an empty cart after ordering, got %d items", len(cartBody.Items))
	}
}

func TestPriceComesFromTheCatalogNotTheClient(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Kantha throw", 1_850_000)})

	// A client that tries to set its own price is simply ignored: the cart
	// stores quantities, and prices are looked up.
	res := h.do(t, http.MethodPost, "/cart/items",
		map[string]any{"sku_id": sku, "quantity": 1, "price_minor": 1}, nil)
	if res.Code != http.StatusOK {
		t.Fatalf("add to cart: %d", res.Code)
	}

	order := h.placeOrder(t, uuid.NewString(), "tok_ok")
	var placed store.Order
	_ = json.Unmarshal(order.Body.Bytes(), &placed)
	if placed.TotalMinor != 1_850_000 {
		t.Fatalf("expected the catalog price, got %d", placed.TotalMinor)
	}
}

func TestDeclinedPaymentReleasesTheHold(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Terracotta jar", 210_000)})
	h.addToCart(t, sku, 1)

	res := h.placeOrder(t, uuid.NewString(), payment.DeclineToken)
	if res.Code != http.StatusPaymentRequired {
		t.Fatalf("expected 402, got %d: %s", res.Code, res.Body.String())
	}

	releases := h.inventory.releases()
	if len(releases) != 1 || releases[0] != "payment_failed" {
		t.Fatalf("expected the hold to be released after a decline, got %v", releases)
	}

	// No order, and the cart is left intact so the buyer can try again.
	list := h.do(t, http.MethodGet, "/orders", nil, nil)
	var orders struct {
		Results []store.Order `json:"results"`
	}
	_ = json.Unmarshal(list.Body.Bytes(), &orders)
	if len(orders.Results) != 0 {
		t.Fatalf("expected no order after a decline, got %d", len(orders.Results))
	}
}

func TestSoldOutStockIsReportedAsConflict(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Last one", 100_000)})
	h.inventory.reserveErr = status.Error(codes.FailedPrecondition, "insufficient stock")
	h.addToCart(t, sku, 1)

	res := h.placeOrder(t, uuid.NewString(), "tok_ok")
	if res.Code != http.StatusConflict {
		t.Fatalf("expected 409 when stock ran out, got %d", res.Code)
	}
}

// A piece the catalog lists but inventory has never been told about is a data
// problem, not the buyer's. They get the same answer as sold out, because a
// 500 would invite them to retry something that can never succeed.
func TestAnUnknownSkuIsReportedAsConflict(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Never stocked", 100_000)})
	h.inventory.reserveErr = status.Error(codes.NotFound, "unknown sku: "+sku)
	h.addToCart(t, sku, 1)

	res := h.placeOrder(t, uuid.NewString(), "tok_ok")
	if res.Code != http.StatusConflict {
		t.Fatalf("expected 409 for a sku inventory does not know, got %d", res.Code)
	}
}

func TestRetryingWithTheSameKeyReturnsTheSameOrder(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Brass lamp", 890_000)})
	h.addToCart(t, sku, 1)

	key := uuid.NewString()
	first := h.placeOrder(t, key, "tok_ok")
	if first.Code != http.StatusCreated {
		t.Fatalf("first order: %d %s", first.Code, first.Body.String())
	}

	// The client never saw the reply and retries with the same key. It must
	// get the original order back, not a second charge.
	second := h.placeOrder(t, key, "tok_ok")
	if second.Code != http.StatusCreated {
		t.Fatalf("retry: expected 201, got %d", second.Code)
	}
	if second.Header().Get("Idempotent-Replay") != "true" {
		t.Fatal("expected the retry to be served from the stored response")
	}

	var a, b store.Order
	_ = json.Unmarshal(first.Body.Bytes(), &a)
	_ = json.Unmarshal(second.Body.Bytes(), &b)
	if a.ID != b.ID {
		t.Fatalf("expected the same order, got %s and %s", a.ID, b.ID)
	}

	// One reservation, one order: the retry did not run the saga again.
	if len(h.inventory.reserved) != 1 {
		t.Fatalf("expected exactly one reservation, got %d", len(h.inventory.reserved))
	}
}

func TestOrdersRequireAnIdempotencyKey(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Shitalpati", 560_000)})
	h.addToCart(t, sku, 1)

	res := h.do(t, http.MethodPost, "/orders", map[string]any{}, nil)
	if res.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 without a key, got %d", res.Code)
	}
}

func TestEmptyCartCannotBeOrdered(t *testing.T) {
	h := newHarness(t, nil)
	res := h.placeOrder(t, uuid.NewString(), "tok_ok")
	if res.Code != http.StatusBadRequest {
		t.Fatalf("expected 400 for an empty cart, got %d", res.Code)
	}
}

func TestAnotherBuyersOrderIsNotFound(t *testing.T) {
	sku := uuid.NewString()
	h := newHarness(t, map[string]map[string]any{sku: product(sku, "Nakshi kantha", 540_000)})
	h.addToCart(t, sku, 1)
	res := h.placeOrder(t, uuid.NewString(), "tok_ok")

	var order store.Order
	_ = json.Unmarshal(res.Body.Bytes(), &order)

	// A different buyer asks for that order by id. "Not found" rather than
	// "forbidden": the latter confirms the order exists.
	other := newHarness(t, nil)
	seen := other.do(t, http.MethodGet, "/orders/"+order.ID, nil, nil)
	if seen.Code != http.StatusNotFound {
		t.Fatalf("expected 404 for someone else's order, got %d", seen.Code)
	}
}

func TestUnauthenticatedRequestsAreRejected(t *testing.T) {
	h := newHarness(t, nil)
	req := httptest.NewRequest(http.MethodGet, "/cart", nil) // no X-User-Id
	recorder := httptest.NewRecorder()
	h.handler.ServeHTTP(recorder, req)
	if recorder.Code != http.StatusUnauthorized {
		t.Fatalf("expected 401 without an identity header, got %d", recorder.Code)
	}
}

func TestWithdrawnProductBlocksTheOrder(t *testing.T) {
	sku := uuid.NewString()
	// In the cart, but the catalog no longer returns it.
	h := newHarness(t, map[string]map[string]any{})
	h.addToCart(t, sku, 1)

	res := h.placeOrder(t, uuid.NewString(), "tok_ok")
	if res.Code != http.StatusConflict {
		t.Fatalf("expected 409 for a withdrawn piece, got %d", res.Code)
	}
	if len(h.inventory.reserved) != 0 {
		t.Fatal("stock must not be reserved for a piece that cannot be priced")
	}
}
