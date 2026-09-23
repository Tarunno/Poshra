-- Stock is one row per listing, with the two numbers that matter kept
-- separate: what anyone may still take, and what is already spoken for.
CREATE TABLE IF NOT EXISTS stock (
    sku_id      UUID PRIMARY KEY,
    available   INTEGER NOT NULL DEFAULT 0 CHECK (available >= 0),
    reserved    INTEGER NOT NULL DEFAULT 0 CHECK (reserved >= 0),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS reservations (
    -- Chosen by the caller, which is what makes a retry safe.
    id          UUID PRIMARY KEY,
    order_id    UUID NOT NULL,
    state       TEXT NOT NULL CHECK (state IN ('held', 'committed', 'released', 'expired')),
    reason      TEXT NOT NULL DEFAULT '',
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at  TIMESTAMPTZ NOT NULL,
    settled_at  TIMESTAMPTZ
);

-- The sweeper looks for held reservations past their expiry; this keeps that
-- query off a sequential scan as the table grows.
CREATE INDEX IF NOT EXISTS reservations_expiry_idx
    ON reservations (expires_at) WHERE state = 'held';

CREATE INDEX IF NOT EXISTS reservations_order_idx ON reservations (order_id);

CREATE TABLE IF NOT EXISTS reservation_items (
    reservation_id  UUID NOT NULL REFERENCES reservations (id) ON DELETE CASCADE,
    sku_id          UUID NOT NULL,
    quantity        INTEGER NOT NULL CHECK (quantity > 0),
    PRIMARY KEY (reservation_id, sku_id)
);
