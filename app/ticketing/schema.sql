-- Ticket booking schema. Safe to run many times (IF NOT EXISTS).
-- Flow: event -> seats -> booking (holds seats) -> payment -> tickets

CREATE TABLE IF NOT EXISTS events (
    id          SERIAL PRIMARY KEY,
    title       TEXT        NOT NULL,
    venue       TEXT        NOT NULL,
    starts_at   TIMESTAMPTZ NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seats (
    id        SERIAL PRIMARY KEY,
    event_id  INT  NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    label     TEXT NOT NULL,                       -- e.g. "A1", "C12"
    price     INT  NOT NULL CHECK (price >= 0),    -- in UZS (so'm)
    UNIQUE (event_id, label)
);

CREATE TABLE IF NOT EXISTS bookings (
    id              SERIAL PRIMARY KEY,
    event_id        INT         NOT NULL REFERENCES events(id),
    customer_name   TEXT        NOT NULL,
    customer_email  TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'paid', 'cancelled', 'expired')),
    total           INT         NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,          -- unpaid holds are released after this
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS booking_seats (
    booking_id  INT NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    seat_id     INT NOT NULL REFERENCES seats(id),
    PRIMARY KEY (booking_id, seat_id)
);

CREATE TABLE IF NOT EXISTS payments (
    id          SERIAL PRIMARY KEY,
    booking_id  INT         NOT NULL UNIQUE REFERENCES bookings(id),  -- one payment per booking
    amount      INT         NOT NULL,
    method      TEXT        NOT NULL,
    status      TEXT        NOT NULL CHECK (status IN ('succeeded', 'failed')),
    reference   TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tickets (
    id          SERIAL PRIMARY KEY,
    code        TEXT        NOT NULL UNIQUE,
    booking_id  INT         NOT NULL REFERENCES bookings(id),
    seat_id     INT         NOT NULL UNIQUE REFERENCES seats(id),  -- a seat can be sold only once
    issued_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_booking_seats_seat ON booking_seats (seat_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status   ON bookings (status, expires_at);
