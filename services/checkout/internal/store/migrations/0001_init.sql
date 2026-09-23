-- One open cart per buyer. Kept in Postgres rather than a cache: a cart is
-- worth keeping across a restart, and it is read far more often than written.
CREATE TABLE IF NOT EXISTS carts (
    user_id     UUID PRIMARY KEY,
    currency    TEXT NOT NULL DEFAULT 'BDT',
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cart_items (
    user_id   UUID NOT NULL REFERENCES carts (user_id) ON DELETE CASCADE,
    sku_id    UUID NOT NULL,
    quantity  INTEGER NOT NULL CHECK (quantity > 0),
    added_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (user_id, sku_id)
);

CREATE TABLE IF NOT EXISTS orders (
    id              UUID PRIMARY KEY,
    user_id         UUID NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('pending', 'confirmed', 'failed', 'cancelled')),
    -- Prices are integer minor units plus a currency code, never floats.
    total_minor     BIGINT NOT NULL CHECK (total_minor >= 0),
    currency        TEXT NOT NULL,
    reservation_id  UUID NOT NULL,
    payment_ref     TEXT NOT NULL DEFAULT '',
    failure_reason  TEXT NOT NULL DEFAULT '',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS orders_user_idx ON orders (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS order_items (
    order_id     UUID NOT NULL REFERENCES orders (id) ON DELETE CASCADE,
    sku_id       UUID NOT NULL,
    quantity     INTEGER NOT NULL CHECK (quantity > 0),
    -- The price at the time of sale. A later price change must not rewrite
    -- what someone already paid.
    unit_minor   BIGINT NOT NULL CHECK (unit_minor >= 0),
    title        TEXT NOT NULL,
    artisan_name TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (order_id, sku_id)
);

-- Transactional outbox: an event is written in the same transaction as the
-- order it describes, so the two cannot disagree. A relay publishes the rows
-- to Kafka afterwards and marks them sent.
CREATE TABLE IF NOT EXISTS outbox (
    id            BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    aggregate_id  UUID NOT NULL,
    topic         TEXT NOT NULL,
    event_type    TEXT NOT NULL,
    payload       JSONB NOT NULL,
    headers       JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    published_at  TIMESTAMPTZ
);

-- The relay scans for unpublished rows; a partial index keeps that cheap once
-- most rows have been sent.
CREATE INDEX IF NOT EXISTS outbox_unpublished_idx
    ON outbox (created_at) WHERE published_at IS NULL;

-- An Idempotency-Key makes a retried order creation return the first result
-- instead of charging again.
CREATE TABLE IF NOT EXISTS idempotency_keys (
    key          TEXT PRIMARY KEY,
    user_id      UUID NOT NULL,
    request_hash TEXT NOT NULL,
    order_id     UUID,
    status_code  INTEGER NOT NULL DEFAULT 0,
    response     JSONB,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
