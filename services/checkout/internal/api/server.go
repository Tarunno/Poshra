// Package api exposes checkout over HTTP: the cart, and placing an order.
//
// Requests arrive through the gateway, which has already verified the session
// and set X-User-Id. This service never parses a token.
package api

import (
	"encoding/json"
	"log/slog"
	"net/http"
	"strings"
	"time"

	"github.com/Tarunno/Poshra/services/checkout/internal/catalog"
	"github.com/Tarunno/Poshra/services/checkout/internal/config"
	"github.com/Tarunno/Poshra/services/checkout/internal/payment"
	"github.com/Tarunno/Poshra/services/checkout/internal/store"
	inventoryv1 "github.com/Tarunno/Poshra/services/inventory/gen/poshra/inventory/v1"
)

type Server struct {
	cfg       config.Config
	log       *slog.Logger
	store     *store.Store
	catalog   *catalog.Client
	inventory inventoryv1.InventoryServiceClient
	payments  payment.Processor
	metrics   orderMetrics
}

func New(
	cfg config.Config,
	log *slog.Logger,
	db *store.Store,
	products *catalog.Client,
	inventory inventoryv1.InventoryServiceClient,
	payments payment.Processor,
) *Server {
	return &Server{cfg: cfg, log: log, store: db, catalog: products,
		inventory: inventory, payments: payments, metrics: newOrderMetrics(log)}
}

func (s *Server) Handler() http.Handler {
	mux := http.NewServeMux()

	// Liveness never touches a dependency: an outage elsewhere must not
	// restart this service.
	mux.HandleFunc("GET /healthz", func(w http.ResponseWriter, _ *http.Request) {
		writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
	})
	mux.HandleFunc("GET /readyz", func(w http.ResponseWriter, r *http.Request) {
		if err := s.store.Ping(r.Context()); err != nil {
			writeJSON(w, http.StatusServiceUnavailable,
				map[string]any{"status": "unavailable", "checks": map[string]string{"database": "fail"}})
			return
		}
		writeJSON(w, http.StatusOK,
			map[string]any{"status": "ready", "checks": map[string]string{"database": "ok"}})
	})

	mux.HandleFunc("GET /cart", s.getCart)
	mux.HandleFunc("POST /cart/items", s.addCartItem)
	mux.HandleFunc("PUT /cart/items/{sku}", s.setCartItem)
	mux.HandleFunc("DELETE /cart/items/{sku}", s.deleteCartItem)
	mux.HandleFunc("DELETE /cart", s.clearCart)

	mux.HandleFunc("POST /orders", s.createOrder)
	mux.HandleFunc("GET /orders", s.listOrders)
	mux.HandleFunc("GET /orders/{id}", func(w http.ResponseWriter, r *http.Request) {
		s.getOrder(w, r, r.PathValue("id"))
	})

	// Support: an order number is the only way in, and every use is logged.
	mux.HandleFunc("GET /support/orders/{id}", func(w http.ResponseWriter, r *http.Request) {
		s.lookUpOrder(w, r, r.PathValue("id"))
	})

	return s.withLogging(mux)
}

// withLogging emits one structured line per request, in the same shape as the
// other services, carrying the gateway's request id.
func (s *Server) withLogging(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		started := time.Now()
		recorder := &statusRecorder{ResponseWriter: w, status: http.StatusOK}

		ctx := withRequestID(r.Context(), r.Header.Get("X-Request-ID"))
		next.ServeHTTP(recorder, r.WithContext(ctx))

		attrs := []any{
			"http_method", r.Method,
			"http_path", r.URL.Path,
			"http_status", recorder.status,
			"duration_ms", float64(time.Since(started).Microseconds()) / 1000,
		}
		if id := requestIDFrom(ctx); id != "" {
			attrs = append(attrs, "request_id", id)
		}
		if user := userIDFrom(r); user != "" {
			attrs = append(attrs, "user_id", user)
		}
		s.log.Info("request", attrs...)
	})
}

type statusRecorder struct {
	http.ResponseWriter
	status int
}

func (r *statusRecorder) WriteHeader(code int) {
	r.status = code
	r.ResponseWriter.WriteHeader(code)
}

// userIDFrom reads the identity the gateway verified and injected. A
// client-supplied value cannot reach here: the gateway strips it.
func userIDFrom(r *http.Request) string {
	return strings.TrimSpace(r.Header.Get("X-User-Id"))
}

func (s *Server) fail(w http.ResponseWriter, what string, err error) {
	// The detail goes to the log; the caller gets nothing that describes the
	// internals.
	s.log.Error(what, "error", err)
	writeError(w, http.StatusInternalServerError, "an unexpected error occurred")
}

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, status int, detail string) {
	writeJSON(w, status, map[string]string{"detail": detail})
}

func errorBody(detail string) []byte {
	body, _ := json.Marshal(map[string]string{"detail": detail})
	return body
}
