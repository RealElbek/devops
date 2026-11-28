-- booking-service database: bookings and the seats they hold. Safe to run many times.
-- seat_id / event_id point to event-service data (another database), so they are plain
-- integers, not foreign keys. Label and price are copied at booking time.

CREATE TABLE IF NOT EXISTS bookings (
    id              SERIAL PRIMARY KEY,
    event_id        INT         NOT NULL,
    customer_name   TEXT        NOT NULL,
    customer_email  TEXT        NOT NULL,
    status          TEXT        NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'paid', 'cancelled', 'expired')),
    total           INT         NOT NULL,
    expires_at      TIMESTAMPTZ NOT NULL,          -- unpaid holds are released after this
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS booking_seats (
    booking_id  INT  NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
    seat_id     INT  NOT NULL,
    label       TEXT NOT NULL,
    price       INT  NOT NULL,
    PRIMARY KEY (booking_id, seat_id)
);

CREATE INDEX IF NOT EXISTS idx_booking_seats_seat ON booking_seats (seat_id);
CREATE INDEX IF NOT EXISTS idx_bookings_status   ON bookings (status, expires_at);
