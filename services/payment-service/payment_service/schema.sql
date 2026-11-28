-- payment-service database. Safe to run many times.
-- booking_id points to booking-service data (another database): plain integer, not a foreign key.

CREATE TABLE IF NOT EXISTS payments (
    id          SERIAL PRIMARY KEY,
    booking_id  INT         NOT NULL UNIQUE,      -- one payment per booking
    amount      INT         NOT NULL,
    method      TEXT        NOT NULL,
    status      TEXT        NOT NULL CHECK (status IN ('pending', 'succeeded', 'failed')),
    reference   TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
