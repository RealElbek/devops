-- event-service database: the event catalog and its seat maps. Safe to run many times.

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
