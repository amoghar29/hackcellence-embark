class NotFound(Exception):
    def __init__(self, what: str):
        super().__init__(f"{what} not found.")


class AlreadyBooked(Exception):
    def __init__(self):
        super().__init__("This package is booked and cannot be changed.")
