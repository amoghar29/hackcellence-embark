-- Schema. One column per field, no JSON columns.
-- Catalog tables: one per file in data/catalog/, same name, read-only after seeding (02_seed.sql).
-- Booking tables: what the app creates (docs/API.md). Safe to run again: everything is IF NOT EXISTS.

-- ---------- catalog ----------

-- destinations.json: one row per destination city.
-- departure_cities and rules are not rows; the app reads them from the file.
CREATE TABLE IF NOT EXISTS destinations (
  city         text PRIMARY KEY,
  country_code text NOT NULL,
  country_name text NOT NULL,
  timezone     text NOT NULL,
  airports     text[] NOT NULL
);

CREATE TABLE IF NOT EXISTS airports (
  code          text PRIMARY KEY,
  name          text NOT NULL,
  city          text NOT NULL,
  country       text NOT NULL,
  timezone      text NOT NULL,
  lat           double precision NOT NULL,
  lng           double precision NOT NULL,
  serves_cities text[] NOT NULL          -- {} for the Indian airports and ITM
);

CREATE TABLE IF NOT EXISTS flights (
  flight_id        text PRIMARY KEY,
  airline          text NOT NULL,
  flight_number    text NOT NULL,
  from_airport     text NOT NULL REFERENCES airports(code),
  to_airport       text NOT NULL REFERENCES airports(code),
  departure_local  timestamp NOT NULL,   -- local time of from_airport
  arrival_local    timestamp NOT NULL,   -- local time of to_airport
  stops            int NOT NULL,
  duration_minutes int NOT NULL,
  price_inr        int NOT NULL,         -- price_per_seat.amount
  seats_left       int NOT NULL,
  cabin            text NOT NULL
);

CREATE TABLE IF NOT EXISTS hotels (
  hotel_id        text PRIMARY KEY,
  name            text NOT NULL,
  aliases         text[] NOT NULL,
  city            text NOT NULL,
  area            text NOT NULL,
  lat             double precision NOT NULL,
  lng             double precision NOT NULL,
  rating          numeric(3,1) NOT NULL,
  stars           int NOT NULL,
  check_in_from   text NOT NULL,         -- HH:MM
  check_out_until text NOT NULL,
  family_friendly boolean NOT NULL,
  image           text NOT NULL
);

CREATE TABLE IF NOT EXISTS rooms (
  room_id      text PRIMARY KEY,
  hotel_id     text NOT NULL REFERENCES hotels(hotel_id),
  room_type    text NOT NULL,
  name         text NOT NULL,
  max_adults   int NOT NULL,
  max_children int NOT NULL,
  price_inr    int NOT NULL,             -- price_per_night.amount
  refundable   boolean NOT NULL
);

CREATE TABLE IF NOT EXISTS availability (
  room_id    text NOT NULL REFERENCES rooms(room_id),
  date       date NOT NULL,              -- the night
  rooms_left int NOT NULL,
  PRIMARY KEY (room_id, date)
);

CREATE TABLE IF NOT EXISTS transfers (
  transfer_id       text PRIMARY KEY,
  type              text NOT NULL,
  name              text NOT NULL,
  airport           text REFERENCES airports(code),  -- airport transfers only
  city              text,
  area              text,                            -- NULL = every area of the city
  from_city         text,                            -- transfers between cities only
  to_city           text,
  door_to_door      boolean,
  from_point        text NOT NULL,
  to_point          text NOT NULL,
  max_passengers    int NOT NULL,
  service_from      text NOT NULL,       -- HH:MM; "24:00" possible, so text
  service_until     text NOT NULL,
  frequency_minutes int,
  duration_minutes  int NOT NULL,
  pricing           text NOT NULL,       -- PER_VEHICLE | PER_PERSON
  price_inr         int NOT NULL,        -- price.amount
  child_price_inr   int                  -- child_price.amount, NULL = none
);

CREATE TABLE IF NOT EXISTS attractions (
  attraction_id   text PRIMARY KEY,
  name            text NOT NULL,
  name_ja         text,
  city            text NOT NULL,
  category        text NOT NULL,
  lat             double precision NOT NULL,
  lng             double precision NOT NULL,
  open_days       text[] NOT NULL,       -- MON..SUN
  open_from       text NOT NULL,         -- HH:MM, "24:00" possible
  open_until      text NOT NULL,
  closed_dates    date[] NOT NULL,       -- {} when the field is absent
  aliases         text[] NOT NULL,
  visit_minutes   int NOT NULL,
  child_friendly  boolean NOT NULL,
  accessible      boolean NOT NULL,
  price_inr       int NOT NULL,          -- price_per_person.amount
  child_price_inr int,                   -- child_price.amount, NULL = none (0 = free)
  image           text NOT NULL
);

-- ---------- bookings ----------

CREATE TABLE IF NOT EXISTS bookings (
  id                          text PRIMARY KEY,   -- trip_id
  home_airport                text NOT NULL REFERENCES airports(code),
  country_code                text NOT NULL,
  start_date                  date NOT NULL,
  end_date                    date NOT NULL,
  nights                      int NOT NULL,
  adults                      int NOT NULL,
  child_ages                  int[] NOT NULL,
  budget_inr                  int NOT NULL,
  total_inr                   int NOT NULL,
  status                      text NOT NULL DEFAULT 'PLANNED',  -- PLANNED | BOOKED
  reference                   char(10) UNIQUE,                  -- set on book
  arrival_flight_booking_id   int,   -- -> booking_flights.id
  return_flight_booking_id    int,   -- -> booking_flights.id
  arrival_transfer_booking_id int,   -- -> booking_transfers.id (airport -> first hotel)
  return_transfer_booking_id  int,   -- -> booking_transfers.id (last hotel -> airport)
  created_at                  timestamptz NOT NULL DEFAULT now(),
  updated_at                  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS booking_flights (
  id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  booking_id text NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  flight_id  text NOT NULL REFERENCES flights(flight_id),
  seats      int NOT NULL,
  price_inr  int NOT NULL
);

CREATE TABLE IF NOT EXISTS booking_hotels (
  id         int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  booking_id text NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  position   int NOT NULL,               -- order of the cities
  hotel_id   text NOT NULL REFERENCES hotels(hotel_id),
  room_id    text NOT NULL REFERENCES rooms(room_id),
  check_in   date NOT NULL,
  check_out  date NOT NULL,
  rooms      int NOT NULL,
  price_inr  int NOT NULL,
  UNIQUE (booking_id, position)
);

CREATE TABLE IF NOT EXISTS booking_transfers (
  id          int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  booking_id  text NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  transfer_id text NOT NULL REFERENCES transfers(transfer_id),
  pickup_at   timestamp NOT NULL,
  arrive_at   timestamp NOT NULL,
  quantity    int NOT NULL,              -- vehicles or tickets
  price_inr   int NOT NULL
);

CREATE TABLE IF NOT EXISTS booking_attractions (
  id            int GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  booking_id    text NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  attraction_id text NOT NULL REFERENCES attractions(attraction_id),
  start_at      timestamp NOT NULL,
  end_at        timestamp NOT NULL,
  tickets       int NOT NULL,
  price_inr     int NOT NULL,
  UNIQUE (booking_id, attraction_id)     -- each attraction at most once
);

-- Idempotency-Key header of POST /book: a key books one package only.
CREATE TABLE IF NOT EXISTS booking_idempotency_keys (
  key        text PRIMARY KEY,
  booking_id text NOT NULL REFERENCES bookings(id) ON DELETE CASCADE,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- bookings <-> child tables reference each other, so these foreign keys are added last.
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'bookings_arrival_flight_fk') THEN
    ALTER TABLE bookings
      ADD CONSTRAINT bookings_arrival_flight_fk   FOREIGN KEY (arrival_flight_booking_id)   REFERENCES booking_flights(id),
      ADD CONSTRAINT bookings_return_flight_fk    FOREIGN KEY (return_flight_booking_id)    REFERENCES booking_flights(id),
      ADD CONSTRAINT bookings_arrival_transfer_fk FOREIGN KEY (arrival_transfer_booking_id) REFERENCES booking_transfers(id),
      ADD CONSTRAINT bookings_return_transfer_fk  FOREIGN KEY (return_transfer_booking_id)  REFERENCES booking_transfers(id);
  END IF;
END $$;
