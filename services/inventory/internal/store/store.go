// Package store holds every statement that touches inventory data.
//
// The rules that prevent overselling live here rather than in the gRPC layer,
// because they are only safe inside a transaction: read the current numbers,
// decide, and write, with the rows locked throughout.
package store

import (
	"context"
	"embed"
	"errors"
	"fmt"
	"sort"
	"time"

	"github.com/jackc/pgx/v5"
	"github.com/jackc/pgx/v5/pgxpool"
)

//go:embed migrations/*.sql
var migrations embed.FS

// Errors the gRPC layer turns into status codes.
var (
	ErrNotFound       = errors.New("reservation not found")
	ErrInsufficient   = errors.New("insufficient stock")
	ErrUnknownSKU     = errors.New("unknown sku")
	ErrAlreadySettled = errors.New("reservation already settled")
)

type State string

const (
	StateHeld      State = "held"
	StateCommitted State = "committed"
	StateReleased  State = "released"
	StateExpired   State = "expired"
)

type Item struct {
	SKUID    string
	Quantity int32
}

type Reservation struct {
	ID        string
	OrderID   string
	State     State
	ExpiresAt time.Time
	Items     []Item
}

type Level struct {
	SKUID     string
	Available int32
	Reserved  int32
}

type Store struct {
	pool *pgxpool.Pool
}

func New(ctx context.Context, dsn string) (*Store, error) {
	cfg, err := pgxpool.ParseConfig(dsn)
	if err != nil {
		return nil, fmt.Errorf("parse database url: %w", err)
	}
	// A pool per pod, sized so that pods × connections stays well inside
	// Postgres's limit. Connections are not free on the server side.
	cfg.MaxConns = 8
	cfg.MinConns = 1
	cfg.MaxConnIdleTime = 5 * time.Minute

	pool, err := pgxpool.NewWithConfig(ctx, cfg)
	if err != nil {
		return nil, fmt.Errorf("connect: %w", err)
	}
	return &Store{pool: pool}, nil
}

func (s *Store) Close() { s.pool.Close() }

func (s *Store) Ping(ctx context.Context) error { return s.pool.Ping(ctx) }

// Migrate applies the embedded schema. Run as a one-off job before a rollout,
// never from a serving pod: several replicas starting at once would race.
func (s *Store) Migrate(ctx context.Context) error {
	entries, err := migrations.ReadDir("migrations")
	if err != nil {
		return err
	}
	names := make([]string, 0, len(entries))
	for _, entry := range entries {
		names = append(names, entry.Name())
	}
	sort.Strings(names) // applied in filename order

	conn, err := s.pool.Acquire(ctx)
	if err != nil {
		return err
	}
	defer conn.Release()

	if _, err := conn.Exec(ctx, `
		CREATE TABLE IF NOT EXISTS schema_migrations (
			name       TEXT PRIMARY KEY,
			applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
		)`); err != nil {
		return fmt.Errorf("create migration ledger: %w", err)
	}

	for _, name := range names {
		body, err := migrations.ReadFile("migrations/" + name)
		if err != nil {
			return err
		}
		if err := applyOnce(ctx, conn.Conn(), name, string(body)); err != nil {
			return err
		}
	}
	return nil
}

// migrationLock serialises migration runs for this service. Any constant will
// do, as long as every replica of this service uses the same one and no other
// service sharing the database uses it too.
const migrationLock int64 = 7326104002

// applyOnce runs one migration if the ledger has not recorded it already.
//
// The whole thing is one transaction: Postgres applies DDL transactionally, so
// a migration that fails halfway leaves nothing behind, and the ledger row
// exists only if the schema change does. The advisory lock is what makes this
// safe to run from two places at once — a rolling deploy, or two syncs racing
// — because the second run waits, then finds the file already applied.
func applyOnce(ctx context.Context, conn *pgx.Conn, name, body string) error {
	return pgx.BeginFunc(ctx, conn, func(tx pgx.Tx) error {
		if _, err := tx.Exec(ctx, `SELECT pg_advisory_xact_lock($1)`, migrationLock); err != nil {
			return err
		}

		var applied bool
		if err := tx.QueryRow(ctx,
			`SELECT EXISTS (SELECT 1 FROM schema_migrations WHERE name = $1)`,
			name).Scan(&applied); err != nil {
			return err
		}
		if applied {
			return nil
		}

		if _, err := tx.Exec(ctx, body); err != nil {
			return fmt.Errorf("apply %s: %w", name, err)
		}
		_, err := tx.Exec(ctx, `INSERT INTO schema_migrations (name) VALUES ($1)`, name)
		return err
	})
}

// Reserve holds stock for an order, all items or none.
//
// Idempotent: calling again with the same reservation id returns the existing
// reservation untouched, so a client that retries after a lost reply does not
// hold stock twice.
func (s *Store) Reserve(
	ctx context.Context,
	reservationID, orderID string,
	items []Item,
	ttl time.Duration,
) (Reservation, bool, error) {
	var (
		reservation Reservation
		created     bool
	)

	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		existing, err := loadReservation(ctx, tx, reservationID, true)
		if err == nil {
			reservation = existing
			return nil // already held (or settled): report what we have
		}
		if !errors.Is(err, ErrNotFound) {
			return err
		}

		// Lock the stock rows in a deterministic order. Two concurrent orders
		// touching the same pair of SKUs in opposite orders would otherwise
		// deadlock, each holding the row the other needs.
		skus := make([]string, 0, len(items))
		wanted := make(map[string]int32, len(items))
		for _, item := range items {
			wanted[item.SKUID] += item.Quantity
		}
		for sku := range wanted {
			skus = append(skus, sku)
		}
		sort.Strings(skus)

		rows, err := tx.Query(ctx,
			`SELECT sku_id, available FROM stock WHERE sku_id = ANY($1) ORDER BY sku_id FOR UPDATE`,
			skus)
		if err != nil {
			return err
		}
		available := make(map[string]int32, len(skus))
		for rows.Next() {
			var sku string
			var count int32
			if err := rows.Scan(&sku, &count); err != nil {
				rows.Close()
				return err
			}
			available[sku] = count
		}
		rows.Close()
		if err := rows.Err(); err != nil {
			return err
		}

		for _, sku := range skus {
			have, ok := available[sku]
			if !ok {
				return fmt.Errorf("%w: %s", ErrUnknownSKU, sku)
			}
			if have < wanted[sku] {
				return fmt.Errorf("%w: %s (want %d, have %d)", ErrInsufficient, sku, wanted[sku], have)
			}
		}

		expiresAt := time.Now().Add(ttl)
		if _, err := tx.Exec(ctx,
			`INSERT INTO reservations (id, order_id, state, expires_at)
			 VALUES ($1, $2, 'held', $3)`,
			reservationID, orderID, expiresAt); err != nil {
			return err
		}

		for _, sku := range skus {
			quantity := wanted[sku]
			if _, err := tx.Exec(ctx,
				`INSERT INTO reservation_items (reservation_id, sku_id, quantity) VALUES ($1, $2, $3)`,
				reservationID, sku, quantity); err != nil {
				return err
			}
			// The WHERE clause is the real guard: even if the check above
			// raced, the update refuses to take stock that is not there.
			tag, err := tx.Exec(ctx,
				`UPDATE stock
				    SET available = available - $2, reserved = reserved + $2, updated_at = now()
				  WHERE sku_id = $1 AND available >= $2`,
				sku, quantity)
			if err != nil {
				return err
			}
			if tag.RowsAffected() == 0 {
				return fmt.Errorf("%w: %s", ErrInsufficient, sku)
			}
		}

		created = true
		reservation = Reservation{
			ID:        reservationID,
			OrderID:   orderID,
			State:     StateHeld,
			ExpiresAt: expiresAt,
			Items:     itemsFromMap(wanted),
		}
		return nil
	})

	return reservation, created, err
}

// Commit turns a hold into a sale: the reserved count drops and the stock is
// gone for good. Idempotent for an already committed reservation.
func (s *Store) Commit(ctx context.Context, reservationID string) (State, error) {
	var state State
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		reservation, err := loadReservation(ctx, tx, reservationID, true)
		if err != nil {
			return err
		}
		switch reservation.State {
		case StateCommitted:
			state = StateCommitted
			return nil // retry of a call that already succeeded
		case StateReleased, StateExpired:
			// The hold is gone; committing now would sell stock nobody holds.
			return fmt.Errorf("%w: %s", ErrAlreadySettled, reservation.State)
		}

		for _, item := range reservation.Items {
			if _, err := tx.Exec(ctx,
				`UPDATE stock SET reserved = reserved - $2, updated_at = now() WHERE sku_id = $1`,
				item.SKUID, item.Quantity); err != nil {
				return err
			}
		}
		if _, err := tx.Exec(ctx,
			`UPDATE reservations SET state = 'committed', settled_at = now() WHERE id = $1`,
			reservationID); err != nil {
			return err
		}
		state = StateCommitted
		return nil
	})
	return state, err
}

// Release gives a hold back. Used when payment fails, when a buyer abandons
// checkout, and by the sweeper for expired holds.
func (s *Store) Release(ctx context.Context, reservationID, reason string, expired bool) (State, error) {
	var state State
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		reservation, err := loadReservation(ctx, tx, reservationID, true)
		if err != nil {
			return err
		}
		switch reservation.State {
		case StateReleased, StateExpired:
			state = reservation.State
			return nil // already given back
		case StateCommitted:
			// Releasing a sale would invent stock. Refunds are a different flow.
			return fmt.Errorf("%w: committed", ErrAlreadySettled)
		}

		for _, item := range reservation.Items {
			if _, err := tx.Exec(ctx,
				`UPDATE stock
				    SET available = available + $2, reserved = reserved - $2, updated_at = now()
				  WHERE sku_id = $1`,
				item.SKUID, item.Quantity); err != nil {
				return err
			}
		}

		newState := StateReleased
		if expired {
			newState = StateExpired
		}
		if _, err := tx.Exec(ctx,
			`UPDATE reservations SET state = $2, reason = $3, settled_at = now() WHERE id = $1`,
			reservationID, string(newState), reason); err != nil {
			return err
		}
		state = newState
		return nil
	})
	return state, err
}

// SweepExpired releases holds whose time ran out, and reports how many.
//
// This is the safety net: compensation after a failed payment is the fast
// path, but if that call never arrives the stock still comes back.
func (s *Store) SweepExpired(ctx context.Context, limit int) (int, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT id FROM reservations
		  WHERE state = 'held' AND expires_at < now()
		  ORDER BY expires_at
		  LIMIT $1`, limit)
	if err != nil {
		return 0, err
	}
	var ids []string
	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err != nil {
			rows.Close()
			return 0, err
		}
		ids = append(ids, id)
	}
	rows.Close()
	if err := rows.Err(); err != nil {
		return 0, err
	}

	swept := 0
	for _, id := range ids {
		// One transaction each: a single stuck row must not block the rest.
		if _, err := s.Release(ctx, id, "expired", true); err != nil {
			if errors.Is(err, ErrAlreadySettled) || errors.Is(err, ErrNotFound) {
				continue // someone settled it between the query and now
			}
			return swept, err
		}
		swept++
	}
	return swept, nil
}

func (s *Store) Levels(ctx context.Context, skuIDs []string) ([]Level, error) {
	rows, err := s.pool.Query(ctx,
		`SELECT sku_id, available, reserved FROM stock WHERE sku_id = ANY($1) ORDER BY sku_id`,
		skuIDs)
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	levels := make([]Level, 0, len(skuIDs))
	for rows.Next() {
		var level Level
		if err := rows.Scan(&level.SKUID, &level.Available, &level.Reserved); err != nil {
			return nil, err
		}
		levels = append(levels, level)
	}
	return levels, rows.Err()
}

// SetStock records how many the artisan has on hand. The value is absolute,
// not a delta, so a repeated call is harmless.
func (s *Store) SetStock(ctx context.Context, skuID string, quantity int32) (Level, error) {
	var level Level
	err := pgx.BeginFunc(ctx, s.pool, func(tx pgx.Tx) error {
		// Reserved stock is already promised to someone, so the new total is
		// spread over what remains. GREATEST keeps availability at zero rather
		// than negative when an artisan lowers the count below what is held.
		row := tx.QueryRow(ctx,
			`INSERT INTO stock (sku_id, available, reserved)
			      VALUES ($1, $2, 0)
			 ON CONFLICT (sku_id) DO UPDATE
			      SET available = GREATEST($2 - stock.reserved, 0), updated_at = now()
			 RETURNING sku_id, available, reserved`,
			skuID, quantity)
		return row.Scan(&level.SKUID, &level.Available, &level.Reserved)
	})
	return level, err
}

func loadReservation(ctx context.Context, tx pgx.Tx, id string, lock bool) (Reservation, error) {
	query := `SELECT id, order_id, state, expires_at FROM reservations WHERE id = $1`
	if lock {
		query += " FOR UPDATE"
	}

	var reservation Reservation
	var state string
	err := tx.QueryRow(ctx, query, id).Scan(
		&reservation.ID, &reservation.OrderID, &state, &reservation.ExpiresAt)
	if errors.Is(err, pgx.ErrNoRows) {
		return Reservation{}, ErrNotFound
	}
	if err != nil {
		return Reservation{}, err
	}
	reservation.State = State(state)

	rows, err := tx.Query(ctx,
		`SELECT sku_id, quantity FROM reservation_items WHERE reservation_id = $1 ORDER BY sku_id`, id)
	if err != nil {
		return Reservation{}, err
	}
	defer rows.Close()
	for rows.Next() {
		var item Item
		if err := rows.Scan(&item.SKUID, &item.Quantity); err != nil {
			return Reservation{}, err
		}
		reservation.Items = append(reservation.Items, item)
	}
	return reservation, rows.Err()
}

func itemsFromMap(quantities map[string]int32) []Item {
	skus := make([]string, 0, len(quantities))
	for sku := range quantities {
		skus = append(skus, sku)
	}
	sort.Strings(skus)

	items := make([]Item, 0, len(skus))
	for _, sku := range skus {
		items = append(items, Item{SKUID: sku, Quantity: quantities[sku]})
	}
	return items
}
