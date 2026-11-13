"""The travel_times cache: Google travel times between catalog places, filled by the warm-up command."""
import psycopg


class TravelRepository:
    def __init__(self, conn: psycopg.Connection):
        self.conn = conn

    def get_all(self) -> dict:
        """{(from_id, to_id): (minutes, meters, source)}; empty when the table does not exist yet
        (a database created before the table was added)."""
        if not self.conn.execute("SELECT to_regclass('travel_times') AS t").fetchone()["t"]:
            return {}
        rows = self.conn.execute("SELECT from_id, to_id, minutes, meters, source FROM travel_times").fetchall()
        return {(r["from_id"], r["to_id"]): (r["minutes"], r["meters"], r["source"]) for r in rows}

    def put_many(self, rows) -> None:
        """rows: [(from_id, to_id, minutes, meters, source)]; a pair already cached is replaced."""
        with self.conn.cursor() as cur:
            cur.executemany("INSERT INTO travel_times (from_id, to_id, minutes, meters, source) "
                            "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (from_id, to_id) DO UPDATE SET "
                            "minutes = EXCLUDED.minutes, meters = EXCLUDED.meters, source = EXCLUDED.source", rows)
