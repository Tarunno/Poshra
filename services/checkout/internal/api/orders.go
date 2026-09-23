package api

import (
	"context"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"net/http"
	"time"

	"github.com/google/uuid"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"github.com/Tarunno/Poshra/services/checkout/internal/payment"
	"github.com/Tarunno/Poshra/services/checkout/internal/store"
	inventoryv1 "github.com/Tarunno/Poshra/services/inventory/gen/poshra/inventory/v1"
)

// OrdersTopic is where the event announcing a new order is published.
const OrdersTopic = "poshra.orders.created.v1"

type createOrderRequest struct {
	// Passed to the payment processor. A real one would exchange a token from
	// its own SDK; the fake accepts "decline" to exercise the failure path.
	PaymentToken string `json:"payment_token"`
}

// createOrder runs the checkout saga.
//
// There is no transaction spanning inventory, the payment processor and this
// database, so each step is local and failure is compensated:
//
//	reserve stock ──▶ charge ──▶ write order + event in one transaction
//	     │               │
//	     │               └─ declined ──▶ release the hold, reply 402
//	     └─ crash here ──────────────────▶ the reservation TTL returns the stock
func (s *Server) createOrder(w http.ResponseWriter, r *http.Request) {
	userID := userIDFrom(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}

	// A retry must not charge twice, so the key is mandatory rather than
	// optional-and-usually-forgotten.
	key := r.Header.Get("Idempotency-Key")
	if key == "" {
		writeError(w, http.StatusBadRequest, "Idempotency-Key header is required")
		return
	}
	if _, err := uuid.Parse(key); err != nil {
		writeError(w, http.StatusBadRequest, "Idempotency-Key must be a uuid")
		return
	}

	var body createOrderRequest
	if r.Body != nil {
		_ = json.NewDecoder(r.Body).Decode(&body) // an empty body is fine
	}

	ctx := r.Context()

	// Before anything else: if this key already has an answer, give it back.
	// A retry arrives after the first call emptied the cart, so validating the
	// cart first would reject exactly the request idempotency exists to serve.
	if replay, err := s.store.LookupIdempotencyKey(ctx, key, userID); err != nil {
		switch {
		case errors.Is(err, store.ErrKeyConflict):
			writeError(w, http.StatusConflict, "this idempotency key belongs to another request")
		case errors.Is(err, store.ErrKeyInProgress):
			writeError(w, http.StatusConflict, "an identical request is already in progress")
		default:
			s.fail(w, "look up idempotency key", err)
		}
		return
	} else if replay != nil {
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Idempotent-Replay", "true")
		w.WriteHeader(replay.StatusCode)
		_, _ = w.Write(replay.Body)
		return
	}

	items, err := s.store.Cart(ctx, userID)
	if err != nil {
		s.fail(w, "load cart", err)
		return
	}
	if len(items) == 0 {
		writeError(w, http.StatusBadRequest, "cart is empty")
		return
	}

	requestHash := hashRequest(items, body.PaymentToken)
	stored, err := s.store.ClaimIdempotencyKey(ctx, key, userID, requestHash)
	switch {
	case errors.Is(err, store.ErrKeyConflict):
		writeError(w, http.StatusConflict, "this idempotency key was used for a different request")
		return
	case errors.Is(err, store.ErrKeyInProgress):
		// 409 rather than a duplicate attempt: the first call is still running.
		writeError(w, http.StatusConflict, "an identical request is already in progress")
		return
	case err != nil:
		s.fail(w, "claim idempotency key", err)
		return
	}
	if stored != nil {
		// Two identical requests raced and the other one finished first.
		w.Header().Set("Content-Type", "application/json")
		w.Header().Set("Idempotent-Replay", "true")
		w.WriteHeader(stored.StatusCode)
		_, _ = w.Write(stored.Body)
		return
	}

	order, statusCode, body2, err := s.placeOrder(ctx, userID, items, body.PaymentToken)
	if err != nil {
		// Free the key so the client can genuinely retry; keeping it would
		// leave them stuck with a failure they never got an answer for.
		_ = s.store.ReleaseIdempotencyKey(context.WithoutCancel(ctx), key)
		s.fail(w, "place order", err)
		return
	}

	orderID := ""
	if order != nil {
		orderID = order.ID
	}
	if err := s.store.CompleteIdempotencyKey(
		context.WithoutCancel(ctx), key, statusCode, orderID, body2); err != nil {
		s.log.Error("could not record idempotent response", "error", err, "key", key)
	}

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(statusCode)
	_, _ = w.Write(body2)
}

// placeOrder performs the saga and returns the response to send.
func (s *Server) placeOrder(
	ctx context.Context, userID string, items []store.CartItem, paymentToken string,
) (*store.Order, int, []byte, error) {
	ids := make([]string, 0, len(items))
	for _, item := range items {
		ids = append(ids, item.SKUID)
	}

	catalogCtx, cancel := context.WithTimeout(ctx, s.cfg.CatalogTimeout)
	products, err := s.catalog.ProductsByID(catalogCtx, ids)
	cancel()
	if err != nil {
		return nil, 0, nil, fmt.Errorf("price cart: %w", err)
	}

	// Price the cart from the catalog, and refuse anything that has since been
	// withdrawn or is priced in another currency.
	var (
		total      int64
		currency   string
		orderItems []store.OrderItem
		reserve    []*inventoryv1.StockItem
	)
	for _, item := range items {
		product, ok := products[item.SKUID]
		if !ok {
			body := errorBody(fmt.Sprintf("a piece in your cart is no longer available: %s", item.SKUID))
			return nil, http.StatusConflict, body, nil
		}
		if currency == "" {
			currency = product.Currency
		} else if currency != product.Currency {
			// Mixing currencies in one total would silently invent a rate.
			return nil, http.StatusConflict, errorBody("a cart cannot mix currencies"), nil
		}
		total += product.PriceMinor * int64(item.Quantity)
		orderItems = append(orderItems, store.OrderItem{
			SKUID:       item.SKUID,
			Quantity:    item.Quantity,
			UnitMinor:   product.PriceMinor,
			Title:       product.Title,
			ArtisanName: product.Artisan.DisplayName,
		})
		reserve = append(reserve, &inventoryv1.StockItem{
			SkuId:    item.SKUID,
			Quantity: item.Quantity,
		})
	}

	orderID := uuid.NewString()
	// The order id doubles as the reservation id: one identifier ties the hold,
	// the order and the event together, and makes retries land on the same hold.
	reservationID := orderID

	reserveCtx, cancelReserve := context.WithTimeout(ctx, s.cfg.InventoryTimeout)
	_, err = s.inventory.ReserveStock(reserveCtx, &inventoryv1.ReserveStockRequest{
		ReservationId: reservationID,
		OrderId:       orderID,
		Items:         reserve,
		TtlSeconds:    int32(s.cfg.ReservationTTL.Seconds()),
	})
	cancelReserve()
	if err != nil {
		if status.Code(err) == codes.FailedPrecondition {
			// Sold out between browsing and paying: a normal outcome, not an
			// error to alert on.
			return nil, http.StatusConflict, errorBody("some pieces are no longer in stock"), nil
		}
		return nil, 0, nil, fmt.Errorf("reserve stock: %w", err)
	}

	payCtx, cancelPay := context.WithTimeout(ctx, s.cfg.PaymentTimeout)
	receipt, err := s.payments.Charge(payCtx, payment.Charge{
		OrderID:    orderID,
		AmountRate: total,
		Currency:   currency,
		Token:      paymentToken,
	})
	cancelPay()
	if err != nil {
		// Compensation: give the stock back immediately rather than waiting
		// for the hold to expire. Uses a context detached from the request so
		// a client that hung up cannot cancel the release.
		s.releaseQuietly(reservationID, "payment_failed")
		if errors.Is(err, payment.ErrDeclined) {
			return nil, http.StatusPaymentRequired, errorBody("payment was declined"), nil
		}
		return nil, 0, nil, fmt.Errorf("charge: %w", err)
	}

	order := store.Order{
		ID:            orderID,
		UserID:        userID,
		Status:        "confirmed",
		TotalMinor:    total,
		Currency:      currency,
		ReservationID: reservationID,
		PaymentRef:    receipt.Reference,
		CreatedAt:     time.Now().UTC(),
		Items:         orderItems,
	}

	event := store.OutboxEvent{
		AggregateID: orderID,
		Topic:       OrdersTopic,
		EventType:   "order.created",
		Payload: map[string]any{
			"event_id":       uuid.NewString(),
			"occurred_at":    order.CreatedAt.Format(time.RFC3339Nano),
			"order_id":       orderID,
			"user_id":        userID,
			"reservation_id": reservationID,
			"total_minor":    total,
			"currency":       currency,
			"items":          orderItems,
		},
		Headers: map[string]string{
			"event_type": "order.created",
			// Carries the gateway's correlation id into the event, so a
			// consumer's logs can be tied back to the request that caused it.
			"request_id": requestIDFrom(ctx),
		},
	}

	if err := s.store.CreateOrder(ctx, order, event); err != nil {
		// The money is taken but the order did not persist. Release the hold
		// and surface it: this needs a refund, which is a human decision.
		s.releaseQuietly(reservationID, "order_persist_failed")
		return nil, 0, nil, fmt.Errorf("persist order: %w", err)
	}

	body, err := json.Marshal(order)
	if err != nil {
		return nil, 0, nil, err
	}
	return &order, http.StatusCreated, body, nil
}

// releaseQuietly compensates without letting the failure hide the original one.
func (s *Server) releaseQuietly(reservationID, reason string) {
	ctx, cancel := context.WithTimeout(context.Background(), s.cfg.InventoryTimeout)
	defer cancel()

	if _, err := s.inventory.ReleaseReservation(ctx, &inventoryv1.ReleaseReservationRequest{
		ReservationId: reservationID,
		Reason:        reason,
	}); err != nil {
		// Not fatal: the reservation expires on its own. Worth an alert if it
		// happens often, because it means stock is held longer than needed.
		s.log.Error("could not release reservation",
			"reservation_id", reservationID, "reason", reason, "error", err)
	}
}

func (s *Server) listOrders(w http.ResponseWriter, r *http.Request) {
	userID := userIDFrom(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}
	orders, err := s.store.Orders(r.Context(), userID, 50)
	if err != nil {
		s.fail(w, "list orders", err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"results": orders})
}

func (s *Server) getOrder(w http.ResponseWriter, r *http.Request, orderID string) {
	userID := userIDFrom(r)
	if userID == "" {
		writeError(w, http.StatusUnauthorized, "authentication required")
		return
	}
	order, err := s.store.Order(r.Context(), userID, orderID)
	if errors.Is(err, store.ErrNotFound) {
		// Someone else's order is "not found", never "forbidden": the latter
		// confirms it exists.
		writeError(w, http.StatusNotFound, "order not found")
		return
	}
	if err != nil {
		s.fail(w, "load order", err)
		return
	}
	writeJSON(w, http.StatusOK, order)
}

// hashRequest identifies what was asked for, so the same key with a different
// cart is caught as a client bug rather than replayed.
func hashRequest(items []store.CartItem, token string) string {
	payload, _ := json.Marshal(struct {
		Items []store.CartItem `json:"items"`
		Token string           `json:"token"`
	}{items, token})
	sum := sha256.Sum256(payload)
	return hex.EncodeToString(sum[:])
}
