-- ticket-service database. Safe to run many times.
-- Event details are copied in when the ticket is issued: a ticket must stay readable even if
-- event-service is down, and must not change later.

CREATE TABLE IF NOT EXISTS tickets (
    id             SERIAL PRIMARY KEY,
    code           TEXT        NOT NULL UNIQUE,
    booking_id     INT         NOT NULL,
    event_id       INT         NOT NULL,
    seat_id        INT         NOT NULL UNIQUE,   -- a seat can be sold only once
    seat_label     TEXT        NOT NULL,
    event_title    TEXT        NOT NULL,
    venue          TEXT        NOT NULL,
    starts_at      TIMESTAMPTZ NOT NULL,
    customer_name  TEXT        NOT NULL,
    issued_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tickets_booking ON tickets (booking_id);
