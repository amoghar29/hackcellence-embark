class NotFound(Exception):
    def __init__(self, what: str):
        super().__init__(f"{what} not found.")


class AlreadyBooked(Exception):
    def __init__(self):
        super().__init__("This package is booked and cannot be changed.")


class SoldOut(Exception):
    """A flight or room of the package was taken before booking; nothing was booked."""
    def __init__(self, part: str, message: str):
        super().__init__(message)
        self.part = part


class IdempotencyKeyReused(Exception):
    def __init__(self):
        super().__init__("This Idempotency-Key already booked another package. Send a new key.")
