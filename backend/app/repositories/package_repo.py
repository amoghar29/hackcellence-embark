"""Saved packages and reservations (the booking tables in db/01_schema.sql).

Only the choices are stored (which flight, room, transfer, visit, and when). The package shown to the
traveler is rebuilt from them and the catalog, so it survives a restart unchanged.
"""
import secrets
import uuid
from collections.abc import Callable
from datetime import datetime

import psycopg

from app.services.errors import IdempotencyKeyReused, SoldOut

PART_TABLES = ("booking_flights", "booking_hotels", "booking_transfers", "booking_attractions")


class PackageRepository:
    def __init__(self, connect: Callable[[], psycopg.Connection]):
        self._connect = connect

    def save(self, request: dict, selection: dict, trip: dict, country_code: str) -> str:
        trip_id = uuid.uuid4().hex[:12]
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO bookings (id, home_airport, country_code, start_date, end_date, nights, adults, "
                "child_ages, budget_inr, total_inr) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (trip_id, request["departure_city"], country_code, request["start_date"], request["end_date"],
                 request["nights"], request["adults"], request["child_ages"], request["budget_inr"],
                 trip["total_inr"]))
            self._insert_parts(conn, trip_id, selection, trip)
        return trip_id

    def update(self, trip_id: str, selection: dict, trip: dict) -> None:
        """Replaces the parts of a saved package in one transaction."""
        with self._connect() as conn:
            conn.execute(
                "UPDATE bookings SET arrival_flight_booking_id = NULL, return_flight_booking_id = NULL, "
                "arrival_transfer_booking_id = NULL, return_transfer_booking_id = NULL, total_inr = %s WHERE id = %s",
                (trip["total_inr"], trip_id))
            for table in PART_TABLES:
                conn.execute(f"DELETE FROM {table} WHERE booking_id = %s", (trip_id,))
            self._insert_parts(conn, trip_id, selection, trip)

    def load(self, trip_id: str) -> tuple[dict, dict] | None:
        """(booking row, selection), or None for an unknown trip_id."""
        with self._connect() as conn:
            b = conn.execute("SELECT * FROM bookings WHERE id = %s", (trip_id,)).fetchone()
            if not b:
                return None

            def rows(table, order):
                return conn.execute(f"SELECT * FROM {table} WHERE booking_id = %s ORDER BY {order}",
                                    (trip_id,)).fetchall()

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

    def book(self, trip_id: str, key: str) -> str | None:
        """Takes the seats and rooms and books the package in one transaction: if any part is sold out, nothing
        is taken. The 10-digit reservation number (the same one if already booked), or None for an unknown trip_id.
        Raises IdempotencyKeyReused if the key booked another package, SoldOut if a flight or room is gone."""
        with self._connect() as conn:
            b = conn.execute("SELECT reference FROM bookings WHERE id = %s FOR UPDATE", (trip_id,)).fetchone()
            if not b:
                return None
            if conn.execute("SELECT 1 FROM bookings WHERE idempotency_key = %s AND id <> %s", (key, trip_id)).fetchone():
                raise IdempotencyKeyReused()
            if b["reference"]:
                return b["reference"]
            self._take_inventory(conn, trip_id)
            while True:
                reference = str(secrets.randbelow(9 * 10**9) + 10**9)  # 10 digits, never starts with 0
                try:
                    with conn.transaction():
                        conn.execute("UPDATE bookings SET status = 'BOOKED', reference = %s, idempotency_key = %s, "
                                     "updated_at = now() WHERE id = %s", (reference, key, trip_id))
                    return reference
                except psycopg.errors.UniqueViolation as e:
                    if e.diag.constraint_name == "bookings_idempotency_key_key":  # another package took the key meanwhile
                        raise IdempotencyKeyReused()

    def booked_trip_ids(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id FROM bookings WHERE status = 'BOOKED' ORDER BY updated_at DESC, id").fetchall()
            return [r["id"] for r in rows]

    def trip_id_for(self, reference: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute("SELECT id FROM bookings WHERE reference = %s", (reference,)).fetchone()
            return row["id"] if row else None

    @staticmethod
    def _take_inventory(conn: psycopg.Connection, trip_id: str) -> None:
        """Rows are taken in one order (flights by id, then rooms by id and night), so two bookings never deadlock.
        Transfers and attractions have no inventory in the catalog; they are booked with the package row."""
        flights = conn.execute(
            "SELECT bf.flight_id, bf.seats, f.flight_number FROM booking_flights bf JOIN flights f USING (flight_id) "
            "WHERE bf.booking_id = %s ORDER BY bf.flight_id", (trip_id,)).fetchall()
        for f in flights:
            if not conn.execute("UPDATE flights SET seats_left = seats_left - %s WHERE flight_id = %s "
                                "AND seats_left >= %s", (f["seats"], f["flight_id"], f["seats"])).rowcount:
                raise SoldOut("flight", f"Flight {f['flight_number']} no longer has {f['seats']} free seats.")
        nights = conn.execute(
            "SELECT bh.room_id, bh.rooms, n::date AS night, h.name AS hotel, r.name AS room "
            "FROM booking_hotels bh JOIN rooms r USING (room_id) JOIN hotels h ON h.hotel_id = bh.hotel_id, "
            "generate_series(bh.check_in, bh.check_out - 1, interval '1 day') n "
            "WHERE bh.booking_id = %s ORDER BY bh.room_id, night", (trip_id,)).fetchall()
        for n in nights:
            if not conn.execute("UPDATE availability SET rooms_left = rooms_left - %s WHERE room_id = %s "
                                "AND date = %s AND rooms_left >= %s",
                                (n["rooms"], n["room_id"], n["night"], n["rooms"])).rowcount:
                raise SoldOut("hotel", f"{n['hotel']} no longer has {n['rooms']} {n['room']} free "
                                       f"on {n['night'].isoformat()}.")

    @staticmethod
    def _insert_parts(conn: psycopg.Connection, trip_id: str, selection: dict, trip: dict) -> None:
        prices = _prices(trip)

        def flight(leg, key):
            return conn.execute(
                "INSERT INTO booking_flights (booking_id, flight_id, seats, price_inr) "
                "VALUES (%s, %s, %s, %s) RETURNING id",
                (trip_id, leg["flight_id"], *prices[key])).fetchone()["id"]

        def transfer(leg, key):
            quantity, price, arrive = prices[key]
            return conn.execute(
                "INSERT INTO booking_transfers (booking_id, transfer_id, pickup_at, arrive_at, quantity, price_inr) "
                "VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
                (trip_id, leg["transfer_id"], leg["pickup"], arrive, quantity, price)).fetchone()["id"]

        ids = (flight(selection["arrival"], "flight-arrival"), flight(selection["return"], "flight-return"),
               transfer(selection["arrival"], "transfer-arrival"), transfer(selection["return"], "transfer-return"))
        for n, leg in enumerate(selection["intercity"], 1):
            transfer(leg, f"transfer-city-{n}")
        for n, s in enumerate(selection["stays"], 1):
            conn.execute(
                "INSERT INTO booking_hotels (booking_id, position, hotel_id, room_id, check_in, check_out, rooms, "
                "price_inr) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (trip_id, n, s["hotel_id"], s["room_id"], s["check_in"], s["check_out"], s["rooms"],
                 prices[f"hotel-{n}"][1]))
        for v in selection["attractions"]:
            tickets, price, end = prices[f"attraction-{v['attraction_id']}"]
            conn.execute(
                "INSERT INTO booking_attractions (booking_id, attraction_id, start_at, end_at, tickets, price_inr) "
                "VALUES (%s, %s, %s, %s, %s, %s)", (trip_id, v["attraction_id"], v["start"], end, tickets, price))
        conn.execute(
            "UPDATE bookings SET arrival_flight_booking_id = %s, return_flight_booking_id = %s, "
            "arrival_transfer_booking_id = %s, return_transfer_booking_id = %s, updated_at = now() WHERE id = %s",
            (*ids, trip_id))


def _prices(trip: dict) -> dict:
    """item_id -> (quantity, price[, end time]) from the assembled package."""
    out = {}
    for it in trip["items"]:
        row = (it["quantity"], it["price_inr"])
        if it["type"] in ("transfer", "attraction"):
            row += (datetime.fromisoformat(it["end"]),)
        out[it["item_id"]] = row
    return out
