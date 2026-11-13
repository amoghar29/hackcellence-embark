"""Price and quantity formulas (handout section 4, "Prices"). All amounts are whole INR."""
import math


def rooms_needed(room, adults, children):
    """Fewest rooms of this type that fit the travelers, or None. Each room needs an adult."""
    for k in range(1, adults + 1):
        if adults <= k * room["max_adults"] and adults + children <= k * (room["max_adults"] + room["max_children"]):
            return k
    return None


def flight_price(flight, travelers):
    return flight["price_inr"] * travelers


def hotel_price(room, rooms, nights):
    return room["price_inr"] * rooms * nights


def _per_person(record, adults, children):
    child = record["child_price_inr"]  # None = children pay the adult price; 0 = free
    return adults * record["price_inr"] + children * (record["price_inr"] if child is None else child)


def transfer_quantity(transfer, adults, children):
    """Tickets (PER_PERSON) or vehicles (PER_VEHICLE)."""
    if transfer["pricing"] == "PER_PERSON":
        return adults + children
    return math.ceil((adults + children) / transfer["max_passengers"])


def transfer_price(transfer, adults, children):
    if transfer["pricing"] == "PER_PERSON":
        return _per_person(transfer, adults, children)
    return transfer["price_inr"] * transfer_quantity(transfer, adults, children)


def attraction_price(attraction, adults, children):
    return _per_person(attraction, adults, children)
