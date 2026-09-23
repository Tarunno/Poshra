// Package store holds checkout's data access: carts, orders and the outbox.
//
// The important method is CreateOrder, which writes the order, its lines and
// the event that announces it in a single transaction. Anything less and the
// system can end up with an order nobody was told about, or an announcement
// for an order that was rolled back.
package store

import (
	"context"
	"embed"
	"encoding/json"
	"errors"
	"fmt"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

//go:embed migrations/*.sql
var migrations embed.FS

var (
	ErrNotFound      = errors.New("not found")
	ErrEmptyCart     = errors.New("cart is empty")
	ErrKeyConflict   = errors.New("idempotency key reused with a different request")
	ErrKeyInProgress = errors.New("an identical request is still in progress")
)

type CartItem struct {
	SKUID    string `json:"sku_id"`
	Quantity int32  `json:"quantity"`
}

type OrderItem struct {
	SKUID       string `json:"sku_id"`
	Quantity    int32  `json:"quantity"`
	UnitMinor   int64  `json:"unit_minor"`
	Title       string `json:"title"`
	ArtisanName string `json:"artisan_name"`
}

type Order struct {
	ID            string      `json:"id"`
	UserID        string      `json:"user_id"`
	Status        string      `json:"status"`
	TotalMinor    int64       `json:"total_minor"`
	Currency      string      `json:"currency"`
	ReservationID string      `json:"reservation_id"`
	PaymentRef    string      `json:"payment_ref,omitempty"`
	FailureReason string      `json:"failure_reason,omitempty"`
	CreatedAt     time.Time   `json:"created_at"`
	Items         []OrderItem `json:"items"`
}

// OutboxEvent is the message that will be published once the order is
// committed. It is written inside the same transaction as the order.
type OutboxEvent struct {
	AggregateID string
	Topic       string
	EventType   string
	Payload     any
	Headers     map[string]string
}

type Store struct{ pool *pgxpool.Pool }

func New(ctx context.Context, dsn string) (*Store, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parse database url: %w", err)
	}
	cfg.MaxConns = 8
	cfg.MinConns = 1
	cfg.MaxConnIdleTime = 5 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("connect: %w", err)
	}
	return &Store{pool: pool}, nil
}

func (s *Store) Close()                         { s.pool.Close() }
func (s *Store) Ping(ctx context.Context) error { return s.pool.Ping(ctx) }

func (s *Store) Migrate(ctx context.Context) error {
	entries, err := migrations.ReadDir("migrations")
	if err != nil {
		return err
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		names = append(names, entry.Name())
	}
	sort.Strings(names)

	for _, name := range names {
		body, err := migrations.ReadFile("migrations/" + name)
		if err != nil {
			return err
		}
		if _, err := s.pool.Exec(ctx, string(body)); err != nil {
			return fmt.Errorf("apply %s: %w", name, err)
		}
	}
	return nil
}

// --- cart -------------------------------------------------------------------

func (s *Store) Cart(ctx context.Context, userID string) ([]CartItem, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT sku_id, quantity FROM cart_items WHERE user_id = $1 ORDER BY added_at`, userID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := []CartItem{}
	for rows.Next() {
		var item CartItem
		if err := rows.Scan(&item.SKUID, &item.Quantity); err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

// AddToCart adds to the quantity already there, so adding the same piece twice
// means two of it rather than a silent overwrite.
func (s *Store) AddToCart(ctx context.Context, userID, skuID string, quantity int32) error {
	return pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx,
			`INSERT INTO carts (user_id) VALUES ($1)
			 ON CONFLICT (user_id) DO UPDATE SET updated_at = now()`, userID); err != nil {
			return err
		}
		_, err := tx.Exec(ctx,
			`INSERT INTO cart_items (user_id, sku_id, quantity) VALUES ($1, $2, $3)
			 ON CONFLICT (user_id, sku_id)
			 DO UPDATE SET quantity = cart_items.quantity + EXCLUDED.quantity`,
			userID, skuID, quantity)
		return err
	})
}

// SetCartQuantity replaces the quantity, removing the line at zero.
func (s *Store) SetCartQuantity(ctx context.Context, userID, skuID string, quantity int32) error {
	if quantity <= 0 {
		return s.RemoveFromCart(ctx, userID, skuID)
	}
	return pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx,
			`INSERT INTO carts (user_id) VALUES ($1)
			 ON CONFLICT (user_id) DO UPDATE SET updated_at = now()`, userID); err != nil {
			return err
		}
		_, err := tx.Exec(ctx,
			`INSERT INTO cart_items (user_id, sku_id, quantity) VALUES ($1, $2, $3)
			 ON CONFLICT (user_id, sku_id) DO UPDATE SET quantity = EXCLUDED.quantity`,
			userID, skuID, quantity)
		return err
	})
}

func (s *Store) RemoveFromCart(ctx context.Context, userID, skuID string) error {
	_, err := s.pool.Exec(ctx,
		`DELETE FROM cart_items WHERE user_id = $1 AND sku_id = $2`, userID, skuID)
	return err
}

func (s *Store) ClearCart(ctx context.Context, userID string) error {
	_, err := s.pool.Exec(ctx, `DELETE FROM cart_items WHERE user_id = $1`, userID)
	return err
}

// --- idempotency ------------------------------------------------------------

// StoredResponse is a previous answer to an identical request.
type StoredResponse struct {
	StatusCode int
	Body       []byte
	OrderID    string
}

// LookupIdempotencyKey returns a previous answer for this key, if any.
//
// Checked before anything else, because the first call changes state the
// request depended on: after an order, the cart it came from is empty, and
// re-validating would reject the retry the key exists to serve.
func (s *Store) LookupIdempotencyKey(ctx context.Context, key, userID string) (*StoredResponse, error) {
	var (
		storedUser string
		statusCode int
		orderID    *string
		response   []byte
	)
	err := s.pool.QueryRow(ctx,
		`SELECT user_id, status_code, order_id, response FROM idempotency_keys WHERE key = $1`, key).
		Scan(&storedUser, &statusCode, &orderID, &response)
	if errors.Is(err, pgx.ErrNoRows) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	if storedUser != userID {
		return nil, ErrKeyConflict
	}
	if statusCode == 0 {
		return nil, ErrKeyInProgress
	}

	stored := &StoredResponse{StatusCode: statusCode, Body: response}
	if orderID != nil {
		stored.OrderID = *orderID
	}
	return stored, nil
}

// ClaimIdempotencyKey reserves a key for this request, or returns the answer
// given the first time.
//
// The insert is the lock: two identical requests race, one wins the row, and
// the other is told the work is already in progress rather than doing it twice.
func (s *Store) ClaimIdempotencyKey(
	ctx context.Context, key, userID, requestHash string,
) (*StoredResponse, error) {
	tag, err := s.pool.Exec(ctx,
		`INSERT INTO idempotency_keys (key, user_id, request_hash) VALUES ($1, $2, $3)
		 ON CONFLICT (key) DO NOTHING`, key, userID, requestHash)
	if err != nil {
		return nil, err
	}
	if tag.RowsAffected() == 1 {
		return nil, nil // first time: go and do the work
	}

	var (
		storedUser string
		storedHash string
		statusCode int
		orderID    *string
		response   []byte
	)
	err = s.pool.QueryRow(ctx,
		`SELECT user_id, request_hash, status_code, order_id, response
		   FROM idempotency_keys WHERE key = $1`, key).
		Scan(&storedUser, &storedHash, &statusCode, &orderID, &response)
	if err != nil {
		return nil, err
	}
	// The same key with a different body is a client bug, not a retry: replying
	// with the old order would hide it.
	if storedUser != userID || storedHash != requestHash {
		return nil, ErrKeyConflict
	}
	if statusCode == 0 {
		return nil, ErrKeyInProgress
	}

	stored := &StoredResponse{StatusCode: statusCode, Body: response}
	if orderID != nil {
		stored.OrderID = *orderID
	}
	return stored, nil
}

func (s *Store) CompleteIdempotencyKey(
	ctx context.Context, key string, statusCode int, orderID string, body []byte,
) error {
	var id *string
	if orderID != "" {
		id = &orderID
	}
	_, err := s.pool.Exec(ctx,
		`UPDATE idempotency_keys SET status_code = $2, order_id = $3, response = $4 WHERE key = $1`,
		key, statusCode, id, body)
	return err
}

// ReleaseIdempotencyKey frees a claimed key when the work failed before an
// answer was recorded, so the client can retry rather than being stuck.
func (s *Store) ReleaseIdempotencyKey(ctx context.Context, key string) error {
	_, err := s.pool.Exec(ctx,
		`DELETE FROM idempotency_keys WHERE key = $1 AND status_code = 0`, key)
	return err
}

// --- orders -----------------------------------------------------------------

// CreateOrder writes the order, its lines, the event announcing it, and clears
// the cart, in one transaction.
//
// This is the transactional outbox: Postgres and Kafka cannot be committed
// together, so the event is stored with the order and published afterwards by
// a relay. Either both the order and its event exist, or neither does.
func (s *Store) CreateOrder(ctx context.Context, order Order, event OutboxEvent) error {
	payload, err := json.Marshal(event.Payload)
	if err != nil {
		return err
	}
	headers, err := json.Marshal(event.Headers)
	if err != nil {
		return err
	}

	return pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx,
			`INSERT INTO orders (id, user_id, status, total_minor, currency, reservation_id, payment_ref)
			 VALUES ($1, $2, $3, $4, $5, $6, $7)`,
			order.ID, order.UserID, order.Status, order.TotalMinor,
			order.Currency, order.ReservationID, order.PaymentRef); err != nil {
			return err
		}

		for _, item := range order.Items {
			if _, err := tx.Exec(ctx,
				`INSERT INTO order_items (order_id, sku_id, quantity, unit_minor, title, artisan_name)
				 VALUES ($1, $2, $3, $4, $5, $6)`,
				order.ID, item.SKUID, item.Quantity, item.UnitMinor,
				item.Title, item.ArtisanName); err != nil {
				return err
			}
		}

		if _, err := tx.Exec(ctx,
			`INSERT INTO outbox (aggregate_id, topic, event_type, payload, headers)
			 VALUES ($1, $2, $3, $4, $5)`,
			event.AggregateID, event.Topic, event.EventType, payload, headers); err != nil {
			return err
		}

		// The cart is emptied in the same transaction: an order that exists
		// beside the cart that produced it invites a double purchase.
		_, err := tx.Exec(ctx, `DELETE FROM cart_items WHERE user_id = $1`, order.UserID)
		return err
	})
}

func (s *Store) Order(ctx context.Context, userID, orderID string) (Order, error) {
	var order Order
	err := s.pool.QueryRow(ctx,
		`SELECT id, user_id, status, total_minor, currency, reservation_id,
		        payment_ref, failure_reason, created_at
		   FROM orders WHERE id = $1 AND user_id = $2`, orderID, userID).
		Scan(&order.ID, &order.UserID, &order.Status, &order.TotalMinor, &order.Currency,
			&order.ReservationID, &order.PaymentRef, &order.FailureReason, &order.CreatedAt)
	if errors.Is(err, pgx.ErrNoRows) {
		// Not "forbidden": telling a stranger an order exists is itself a leak.
		return Order{}, ErrNotFound
	}
	if err != nil {
		return Order{}, err
	}

	items, err := s.orderItems(ctx, order.ID)
	if err != nil {
		return Order{}, err
	}
	order.Items = items
	return order, nil
}

func (s *Store) Orders(ctx context.Context, userID string, limit int) ([]Order, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT id, user_id, status, total_minor, currency, reservation_id,
		        payment_ref, failure_reason, created_at
		   FROM orders WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2`, userID, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	orders := []Order{}
	for rows.Next() {
		var order Order
		if err := rows.Scan(&order.ID, &order.UserID, &order.Status, &order.TotalMinor,
			&order.Currency, &order.ReservationID, &order.PaymentRef,
			&order.FailureReason, &order.CreatedAt); err != nil {
			return nil, err
		}
		orders = append(orders, order)
	}
	if err := rows.Err(); err != nil {
		return nil, err
	}

	for i := range orders {
		items, err := s.orderItems(ctx, orders[i].ID)
		if err != nil {
			return nil, err
		}
		orders[i].Items = items
	}
	return orders, nil
}

func (s *Store) orderItems(ctx context.Context, orderID string) ([]OrderItem, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT sku_id, quantity, unit_minor, title, artisan_name
		   FROM order_items WHERE order_id = $1 ORDER BY title`, orderID)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	items := []OrderItem{}
	for rows.Next() {
		var item OrderItem
		if err := rows.Scan(&item.SKUID, &item.Quantity, &item.UnitMinor,
			&item.Title, &item.ArtisanName); err != nil {
			return nil, err
		}
		items = append(items, item)
	}
	return items, rows.Err()
}

// PendingEvent is an outbox row on its way to Kafka.
type PendingEvent struct {
	ID      int64
	Topic   string
	Key     string
	Payload []byte
	Headers []byte
}

// UnpublishedEvents lists rows the relay has not sent yet. It takes no locks,
// so it is for inspection and tests; PublishBatch is what the relay uses.
func (s *Store) UnpublishedEvents(ctx context.Context, limit int) ([]PendingEvent, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT id, topic, aggregate_id, payload, headers
		   FROM outbox WHERE published_at IS NULL ORDER BY id LIMIT $1`, limit)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var events []PendingEvent
	for rows.Next() {
		var event PendingEvent
		if err := rows.Scan(&event.ID, &event.Topic, &event.Key,
			&event.Payload, &event.Headers); err != nil {
			return nil, err
		}
		events = append(events, event)
	}
	return events, rows.Err()
}

// PublishBatch claims a batch of unpublished events, hands them to send, and
// marks them published if send succeeds.
//
// The claim uses FOR UPDATE SKIP LOCKED so several replicas can relay at once:
// each takes rows the others are not holding instead of queueing behind them.
// Sending happens inside that transaction, so a failed send rolls back and the
// rows are simply picked up on the next pass.
//
// The one thing it cannot promise is exactly-once: if the send succeeds and
// the commit does not, the event goes out again. That is why every consumer of
// these events has to be idempotent.
func (s *Store) PublishBatch(
	ctx context.Context, limit int, send func([]PendingEvent) error,
) (int, error) {
	var claimed int

	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		rows, err := tx.Query(ctx,
			`SELECT id, topic, aggregate_id, payload, headers
			   FROM outbox
			  WHERE published_at IS NULL
			  ORDER BY id
			  LIMIT $1
			  FOR UPDATE SKIP LOCKED`, limit)
		if err != nil {
			return err
		}

		var events []PendingEvent
		for rows.Next() {
			var event PendingEvent
			if err := rows.Scan(&event.ID, &event.Topic, &event.Key,
				&event.Payload, &event.Headers); err != nil {
				rows.Close()
				return err
			}
			events = append(events, event)
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}
		if len(events) == 0 {
			return nil
		}

		if err := send(events); err != nil {
			return err
		}

		ids := make([]int64, 0, len(events))
		for _, event := range events {
			ids = append(ids, event.ID)
		}
		if _, err := tx.Exec(ctx,
			`UPDATE outbox SET published_at = now() WHERE id = ANY($1)`, ids); err != nil {
			return err
		}
		claimed = len(events)
		return nil
	})
	return claimed, err
}
