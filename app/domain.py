from dataclasses import dataclass, replace
from enum import StrEnum

MAX_ATTEMPTS = 3
class ParcelState(StrEnum):
    CREATED = "created"
    OUT_FOR_DELIVERY = "out_for_delivery"
    FAILED_ATTEMPT = "failed_attempt"
    DELIVERED = "delivered"
    RETURNED = "returned"
class EventType(StrEnum):
    DISPATCH = "dispatch"
    DELIVER = "deliver"
    FAIL = "fail"
    RETURN = "return"
class InvalidTransition(Exception): ...
@dataclass(frozen=True)
class Parcel:
    id: str
    merchant_ref: str
    cod_amount_piastres: int
    address_text: str
    state: ParcelState = ParcelState.CREATED
    attempts: int = 0

_TRANSITIONS = {
    (ParcelState.CREATED, EventType.DISPATCH): ParcelState.OUT_FOR_DELIVERY,
    (ParcelState.OUT_FOR_DELIVERY, EventType.DELIVER): ParcelState.DELIVERED,
    (ParcelState.OUT_FOR_DELIVERY, EventType.FAIL): ParcelState.FAILED_ATTEMPT,
    (ParcelState.FAILED_ATTEMPT, EventType.DISPATCH): ParcelState.OUT_FOR_DELIVERY,
    (ParcelState.FAILED_ATTEMPT, EventType.RETURN): ParcelState.RETURNED,
}
def apply_event(parcel: Parcel, event: EventType) -> Parcel:
    """Return a new Parcel. Raise InvalidTransition if the event is not allowed."""
    new_state = _TRANSITIONS.get((parcel.state, event))
    if new_state is None:
        raise InvalidTransition(f"{event} not allowed from {parcel.state}")

    attempts = parcel.attempts
    if event == EventType.DISPATCH:
        if parcel.state == ParcelState.FAILED_ATTEMPT and attempts >= MAX_ATTEMPTS:
            raise InvalidTransition("no attempts left, only return is allowed")
        attempts += 1

    return replace(parcel, state=new_state, attempts=attempts)