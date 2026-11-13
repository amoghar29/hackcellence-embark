-- Tables mirror data/catalog/*.json 1:1: table = file name, column = JSON field.
-- Nested objects ({amount, currency}) and destinations' sections stay JSONB to keep the exact shape.

CREATE TABLE destinations (
  departure_cities jsonb NOT NULL,
  countries        jsonb NOT NULL,
  rules            jsonb NOT NULL
);

CREATE TABLE airports (
  code          text PRIMARY KEY,
  name          text NOT NULL,
  city          text NOT NULL,
  country       text NOT NULL,
  timezone      text NOT NULL,
  lat           double precision NOT NULL,
  lng           double precision NOT NULL,
  serves_cities text[]            -- NULL = field absent (Indian airports), {} = ITM
);

CREATE TABLE flights (
  flight_id        text PRIMARY KEY,
  airline          text NOT NULL,
  flight_number    text NOT NULL,
  "from"           text NOT NULL REFERENCES airports(code),
  "to"             text NOT NULL REFERENCES airports(code),
  departure_local  timestamp NOT NULL,
  arrival_local    timestamp NOT NULL,
  stops            int NOT NULL,
  duration_minutes int NOT NULL,
  price_per_seat   jsonb NOT NULL,
  seats_left       int NOT NULL,
  cabin            text NOT NULL
);

CREATE TABLE hotels (
  hotel_id        text PRIMARY KEY,
  name            text NOT NULL,
  aliases         text[] NOT NULL,
  city            text NOT NULL,
  area            text NOT NULL,
  lat             double precision NOT NULL,
  lng             double precision NOT NULL,
  rating          numeric(3,1) NOT NULL,
  stars           int NOT NULL,
  check_in_from   text NOT NULL,
  check_out_until text NOT NULL,
  family_friendly boolean NOT NULL,
  image           text NOT NULL
);

CREATE TABLE rooms (
  room_id         text PRIMARY KEY,
  hotel_id        text NOT NULL REFERENCES hotels(hotel_id),
  room_type       text NOT NULL,
  name            text NOT NULL,
  max_adults      int NOT NULL,
  max_children    int NOT NULL,
  price_per_night jsonb NOT NULL,
  refundable      boolean NOT NULL
);

CREATE TABLE availability (
  room_id    text NOT NULL REFERENCES rooms(room_id),
  date       date NOT NULL,
  rooms_left int NOT NULL,
  PRIMARY KEY (room_id, date)
);

CREATE TABLE transfers (
  transfer_id       text PRIMARY KEY,
  type              text NOT NULL,
  name              text NOT NULL,
  airport           text REFERENCES airports(code),
  city              text,
  area              text,
  from_point        text NOT NULL,
  to_point          text NOT NULL,
  max_passengers    int NOT NULL,
  service_from      text NOT NULL,   -- HH:MM, may be "24:00"; kept as text
  service_until     text NOT NULL,
  duration_minutes  int NOT NULL,
  pricing           text NOT NULL,
  price             jsonb NOT NULL,
  child_price       jsonb,
  from_city         text,
  to_city           text,
  frequency_minutes int,
  door_to_door      boolean
);

CREATE TABLE attractions (
  attraction_id    text PRIMARY KEY,
  name             text NOT NULL,
  name_ja          text,
  city             text NOT NULL,
  category         text NOT NULL,
  lat              double precision NOT NULL,
  lng              double precision NOT NULL,
  open_days        text[] NOT NULL,
  open_from        text NOT NULL,
  open_until       text NOT NULL,
  aliases          text[] NOT NULL,
  visit_minutes    int NOT NULL,
  child_friendly   boolean NOT NULL,
  accessible       boolean NOT NULL,
  price_per_person jsonb NOT NULL,
  image            text NOT NULL,
  child_price      jsonb,
  closed_dates     date[]
);

-- Seed: full catalog, loaded straight from the mounted JSON files.
INSERT INTO destinations SELECT * FROM jsonb_populate_record(NULL::destinations, pg_read_file('/catalog/destinations.json')::jsonb);
INSERT INTO airports     SELECT * FROM jsonb_populate_recordset(NULL::airports,     pg_read_file('/catalog/airports.json')::jsonb);
INSERT INTO flights      SELECT * FROM jsonb_populate_recordset(NULL::flights,      pg_read_file('/catalog/flights.json')::jsonb);
INSERT INTO hotels       SELECT * FROM jsonb_populate_recordset(NULL::hotels,       pg_read_file('/catalog/hotels.json')::jsonb);
INSERT INTO rooms        SELECT * FROM jsonb_populate_recordset(NULL::rooms,        pg_read_file('/catalog/rooms.json')::jsonb);
INSERT INTO availability SELECT * FROM jsonb_populate_recordset(NULL::availability, pg_read_file('/catalog/availability.json')::jsonb);
INSERT INTO transfers    SELECT * FROM jsonb_populate_recordset(NULL::transfers,    pg_read_file('/catalog/transfers.json')::jsonb);
INSERT INTO attractions  SELECT * FROM jsonb_populate_recordset(NULL::attractions,  pg_read_file('/catalog/attractions.json')::jsonb);
