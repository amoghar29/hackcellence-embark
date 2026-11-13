"""Reservations (the booking tables in db/01_schema.sql). Nothing is stored before booking.

Each section of a package is its own row, linked to the booking by its reservation number. The package shown
to the traveler is rebuilt from those rows and the catalog, so it survives a restart unchanged.
"""
import secrets
from collections.abc import Callable
from datetime import datetime, timedelta

import psycopg

from app.services.errors import IdempotencyKeyReused, SoldOut

PART_TABLES = ("booking_flights", "booking_hotels", "booking_transfers", "booking_attractions")


class PackageRepository:
    def __init__(self, connect: Callable[[], psycopg.Connection]):
        self._connect = connect

    def book(self, request: dict, selection: dict, trip: dict, country_code: str, key: str, payload_hash: str) -> str:
        """Books the whole package in ONE transaction: takes the seats and rooms, then writes the booking and one row
        per flight, hotel, transfer and attraction. If any step fails (a sold-out part, a failed insert) nothing
        is kept. Returns the 10-digit reservation number; the same key with the same package returns the number it
        got before. Raises IdempotencyKeyReused (the key booked another package) or SoldOut."""
        with self._connect() as conn:
            # one request per key at a time, so a replay waits for the first and then finds its booking
            conn.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (key,))
            done = conn.execute("SELECT reference, payload_hash FROM bookings WHERE idempotency_key = %s",
                                (key,)).fetchone()
            if done:
                if done["payload_hash"] != payload_hash:
                    raise IdempotencyKeyReused()
                return done["reference"]
            self._take_inventory(conn, selection, trip)
            while True:
                reference = str(secrets.randbelow(9 * 10**9) + 10**9)  # 10 digits, never starts with 0
                try:
                    with conn.transaction():  # a savepoint: a taken number retries without losing the inventory
                        conn.execute(
                            "INSERT INTO bookings (reference, home_airport, country_code, start_date, end_date, nights, "
                            "adults, child_ages, budget_inr, total_inr, idempotency_key, payload_hash) "
                            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                            (reference, request["departure_city"], country_code, request["start_date"],
                             request["end_date"], request["nights"], request["adults"], request["child_ages"],
                             request["budget_inr"], trip["total_inr"], key, payload_hash))
                    break
                except psycopg.errors.UniqueViolation as e:
                    if e.diag.constraint_name != "bookings_pkey":
                        raise
            self._insert_parts(conn, reference, selection, trip)
            return reference

    def load(self, reference: str) -> tuple[dict, dict] | None:
        """(booking row, selection), or None for an unknown reference."""
        with self._connect() as conn:
            b = conn.execute("SELECT * FROM bookings WHERE reference = %s", (reference,)).fetchone()
            if not b:
                return None

            def rows(table, order):
                return conn.execute(f"SELECT * FROM {table} WHERE booking_id = %s ORDER BY {order}",
                                    (reference,)).fetchall()

            flights = {r["id"]: r for r in rows("booking_flights", "id")}
            transfers = {r["id"]: r for r in rows("booking_transfers", "pickup_at, id")}

            def leg(side):
                t = transfers.pop(b[f"{side}_transfer_booking_id"])
                return {"flight_id": flights[b[f"{side}_flight_booking_id"]]["flight_id"],
                        "transfer_id": t["transfer_id"], "pickup": t["pickup_at"]}

            selection = {
                "arrival": leg("arrival"), "return": leg("return"),
                "stays": [{"hotel_id": r["hotel_id"], "room_id": r["room_id"], "rooms": r["rooms"],
                           "check_in": r["check_in"], "check_out": r["check_out"]}
                          for r in rows("booking_hotels", "position")],
                "intercity": [{"transfer_id": t["transfer_id"], "pickup": t["pickup_at"]} for t in transfers.values()],
                "attractions": [{"attraction_id": r["attraction_id"], "start": r["start_at"]}
                                for r in rows("booking_attractions", "start_at, id")],
            }
            return b, selection

    def references(self) -> list[str]:
        """Every reservation number, newest first."""
        with self._connect() as conn:
            rows = conn.execute("SELECT reference FROM bookings ORDER BY created_at DESC, reference").fetchall()
            return [r["reference"] for r in rows]

    @staticmethod
    def _take_inventory(conn: psycopg.Connection, selection: dict, trip: dict) -> None:
        """Rows are taken in one order (flights by id, then rooms by id and night), so two bookings never deadlock.
        Transfers and attractions have no inventory in the catalog; they are booked with the package."""
        flights = sorted((i for i in trip["items"] if i["type"] == "flight"), key=lambda i: i["catalog_id"])
        for f in flights:
            if not conn.execute("UPDATE flights SET seats_left = seats_left - %s WHERE flight_id = %s "
                                "AND seats_left >= %s", (f["quantity"], f["catalog_id"], f["quantity"])).rowcount:
                raise SoldOut("flight", f"Flight {f['details']['flight_number']} no longer has {f['quantity']} "
                                        "free seats.")
        hotels = {i["item_id"]: i for i in trip["items"] if i["type"] == "hotel"}
        nights = sorted(((s["room_id"], s["check_in"] + timedelta(n), s["rooms"], hotels[f"hotel-{k}"])
                         for k, s in enumerate(selection["stays"], 1)
                         for n in range((s["check_out"] - s["check_in"]).days)), key=lambda x: x[:2])
        for room_id, night, rooms, hotel in nights:
            if not conn.execute("UPDATE availability SET rooms_left = rooms_left - %s WHERE room_id = %s "
                                "AND date = %s AND rooms_left >= %s", (rooms, room_id, night, rooms)).rowcount:
                raise SoldOut("hotel", f"{hotel['name']} no longer has {rooms} {hotel['details']['room_name']} free "
                                       f"on {night.isoformat()}.")

    @staticmethod
    def _insert_parts(conn: psycopg.Connection, reference: str, selection: dict, trip: dict) -> None:
        prices = _prices(trip)

        def flight(leg, key):
            return conn.execute(
                "INSERT INTO booking_flights (booking_id, flight_id, seats, price_inr) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (reference, leg["flight_id"], *prices[key])).fetchone()["id"]

        def transfer(leg, key):
            quantity, price, arrive = prices[key]
            return conn.execute(
                "INSERT INTO booking_transfers (booking_id, transfer_id, pickup_at, arrive_at, quantity, price_inr) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (reference, leg["transfer_id"], leg["pickup"], arrive, quantity, price)).fetchone()["id"]

        ids = (flight(selection["arrival"], "flight-arrival"), flight(selection["return"], "flight-return"),
               transfer(selection["arrival"], "transfer-arrival"), transfer(selection["return"], "transfer-return"))
        for n, leg in enumerate(selection["intercity"], 1):
            transfer(leg, f"transfer-city-{n}")
        for n, s in enumerate(selection["stays"], 1):
            conn.execute(
                "INSERT INTO booking_hotels (booking_id, position, hotel_id, room_id, check_in, check_out, rooms, "
                "price_inr) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (reference, n, s["hotel_id"], s["room_id"], s["check_in"], s["check_out"], s["rooms"],
                 prices[f"hotel-{n}"][1]))
        for v in selection["attractions"]:
            tickets, price, end = prices[f"attraction-{v['attraction_id']}"]
            conn.execute(
                "INSERT INTO booking_attractions (booking_id, attraction_id, start_at, end_at, tickets, price_inr) "
                "VALUES (%s, %s, %s, %s, %s, %s)", (reference, v["attraction_id"], v["start"], end, tickets, price))
        conn.execute(
            "UPDATE bookings SET arrival_flight_booking_id = %s, return_flight_booking_id = %s, "
            "arrival_transfer_booking_id = %s, return_transfer_booking_id = %s WHERE reference = %s",
            (*ids, reference))


def _prices(trip: dict) -> dict:
    """item_id -> (quantity, price[, end time]) from the assembled package."""
    out = {}
    for it in trip["items"]:
        row = (it["quantity"], it["price_inr"])
        if it["type"] in ("transfer", "attraction"):
            row += (datetime.fromisoformat(it["end"]),)
        out[it["item_id"]] = row
    return out
