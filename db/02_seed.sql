-- Seed the catalog tables from data/catalog/*.json (mounted at /catalog in the db container).
-- Safe to run again: existing rows are kept (ON CONFLICT DO NOTHING); booking rows are never touched.

INSERT INTO destinations (city, country_code, country_name, timezone, airports)
SELECT c->>'name', k->>'code', k->>'name', k->>'timezone',
       ARRAY(SELECT jsonb_array_elements_text(c->'airports'))
FROM jsonb_array_elements(pg_read_file('/catalog/destinations.json')::jsonb->'countries') k,
     jsonb_array_elements(k->'cities') c
ON CONFLICT DO NOTHING;

INSERT INTO airports (code, name, city, country, timezone, lat, lng, serves_cities)
SELECT a->>'code', a->>'name', a->>'city', a->>'country', a->>'timezone',
       (a->>'lat')::float8, (a->>'lng')::float8,
       ARRAY(SELECT jsonb_array_elements_text(COALESCE(a->'serves_cities', '[]')))
FROM jsonb_array_elements(pg_read_file('/catalog/airports.json')::jsonb) a
ON CONFLICT DO NOTHING;

INSERT INTO flights (flight_id, airline, flight_number, from_airport, to_airport, departure_local, arrival_local,
                     stops, duration_minutes, price_inr, seats_left, cabin)
SELECT f->>'flight_id', f->>'airline', f->>'flight_number', f->>'from', f->>'to',
       (f->>'departure_local')::timestamp, (f->>'arrival_local')::timestamp,
       (f->>'stops')::int, (f->>'duration_minutes')::int, (f->'price_per_seat'->>'amount')::int,
       (f->>'seats_left')::int, f->>'cabin'
FROM jsonb_array_elements(pg_read_file('/catalog/flights.json')::jsonb) f
ON CONFLICT DO NOTHING;

INSERT INTO hotels (hotel_id, name, aliases, city, area, lat, lng, rating, stars, check_in_from, check_out_until,
                    family_friendly, image)
SELECT h->>'hotel_id', h->>'name', ARRAY(SELECT jsonb_array_elements_text(h->'aliases')), h->>'city', h->>'area',
       (h->>'lat')::float8, (h->>'lng')::float8, (h->>'rating')::numeric, (h->>'stars')::int,
       h->>'check_in_from', h->>'check_out_until', (h->>'family_friendly')::boolean, h->>'image'
FROM jsonb_array_elements(pg_read_file('/catalog/hotels.json')::jsonb) h
ON CONFLICT DO NOTHING;

INSERT INTO rooms (room_id, hotel_id, room_type, name, max_adults, max_children, price_inr, refundable)
SELECT r->>'room_id', r->>'hotel_id', r->>'room_type', r->>'name', (r->>'max_adults')::int,
       (r->>'max_children')::int, (r->'price_per_night'->>'amount')::int, (r->>'refundable')::boolean
FROM jsonb_array_elements(pg_read_file('/catalog/rooms.json')::jsonb) r
ON CONFLICT DO NOTHING;

INSERT INTO availability (room_id, date, rooms_left)
SELECT a->>'room_id', (a->>'date')::date, (a->>'rooms_left')::int
FROM jsonb_array_elements(pg_read_file('/catalog/availability.json')::jsonb) a
ON CONFLICT DO NOTHING;

INSERT INTO transfers (transfer_id, type, name, airport, city, area, from_city, to_city, door_to_door, from_point,
                       to_point, max_passengers, service_from, service_until, frequency_minutes, duration_minutes,
                       pricing, price_inr, child_price_inr)
SELECT t->>'transfer_id', t->>'type', t->>'name', t->>'airport', t->>'city', t->>'area', t->>'from_city',
       t->>'to_city', (t->>'door_to_door')::boolean, t->>'from_point', t->>'to_point', (t->>'max_passengers')::int,
       t->>'service_from', t->>'service_until', (t->>'frequency_minutes')::int, (t->>'duration_minutes')::int,
       t->>'pricing', (t->'price'->>'amount')::int, (t->'child_price'->>'amount')::int
FROM jsonb_array_elements(pg_read_file('/catalog/transfers.json')::jsonb) t
ON CONFLICT DO NOTHING;

INSERT INTO attractions (attraction_id, name, name_ja, city, category, lat, lng, open_days, open_from, open_until,
                         closed_dates, aliases, visit_minutes, child_friendly, accessible, price_inr,
                         child_price_inr, image)
SELECT a->>'attraction_id', a->>'name', a->>'name_ja', a->>'city', a->>'category',
       (a->>'lat')::float8, (a->>'lng')::float8,
       ARRAY(SELECT jsonb_array_elements_text(a->'open_days')), a->>'open_from', a->>'open_until',
       ARRAY(SELECT jsonb_array_elements_text(COALESCE(a->'closed_dates', '[]')))::date[],
       ARRAY(SELECT jsonb_array_elements_text(a->'aliases')), (a->>'visit_minutes')::int,
       (a->>'child_friendly')::boolean, (a->>'accessible')::boolean,
       (a->'price_per_person'->>'amount')::int, (a->'child_price'->>'amount')::int, a->>'image'
FROM jsonb_array_elements(pg_read_file('/catalog/attractions.json')::jsonb) a
ON CONFLICT DO NOTHING;
