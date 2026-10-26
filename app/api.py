import secrets
from dataclasses import asdict
from http import HTTPStatus
from typing import Annotated

from fastapi import FastAPI, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.domain import EventType, InvalidTransition, Parcel, ParcelState, apply_event


class CreateParcel(BaseModel):
    merchant_ref: Annotated[str, Field(strict=True, min_length=1, max_length=64)]
    cod_amount_piastres: Annotated[int, Field(strict=True, ge=0, le=5_000_000)]
    address_text: Annotated[str, Field(strict=True, min_length=1, max_length=500)]


class EventBody(BaseModel):
    type: EventType


class ParcelOut(BaseModel):
    id: str
    merchant_ref: str
    cod_amount_piastres: int
    address_text: str
    state: ParcelState
    attempts: int


class ParcelPage(BaseModel):
    items: list[ParcelOut]
    next_cursor: str | None


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str | None = None
    errors: list[dict] | None = None


def problem(status: int, detail: str | None = None, errors: list | None = None):
    body = {"type": "about:blank", "title": HTTPStatus(status).phrase, "status": status}
    if detail:
        body["detail"] = detail
    if errors is not None:
        body["errors"] = errors
    return JSONResponse(body, status_code=status, media_type="application/problem+json")


def doc(description: str) -> dict:
    return {"description": description, "model": Problem}


def create_app() -> FastAPI:
    app = FastAPI(title="Tawseel parcel API", version="1.0.0")

    # every app gets its own store, nothing at module level
    parcels: dict[str, Parcel] = {}
    order: list[str] = []            # creation order, seq = index + 1
    refs: set[str] = set()           # merchant_refs already used
    issued: dict[str, int] = {}      # cursor token -> last seq returned

    @app.exception_handler(RequestValidationError)
    async def on_validation(request: Request, exc: RequestValidationError):
        ### one entry per field bas, mesh kol error (FastAPI may repeat the same loc)
        seen, errors = set(), []
        for e in exc.errors():
            loc = tuple(e["loc"])
            if loc in seen:
                continue
            seen.add(loc)
            errors.append({"loc": list(loc), "msg": e["msg"]})
        return problem(422, "Request validation failed", errors)

    @app.exception_handler(StarletteHTTPException)
    async def on_http(request: Request, exc: StarletteHTTPException):
        return problem(exc.status_code, str(exc.detail))

    @app.post(
        "/v1/parcels",
        operation_id="createParcel",
        status_code=201,
        response_model=ParcelOut,
        responses={409: doc("Duplicate merchant_ref"), 422: doc("Invalid body")},
    )
    def create_parcel(body: CreateParcel, response: Response):
        if body.merchant_ref in refs:
            raise StarletteHTTPException(409, "merchant_ref already exists")
        parcel_id = f"pcl_{len(order) + 1:06d}"
        parcel = Parcel(
            id=parcel_id,
            merchant_ref=body.merchant_ref,
            cod_amount_piastres=body.cod_amount_piastres,
            address_text=body.address_text,
        )
        parcels[parcel_id] = parcel
        order.append(parcel_id)
        refs.add(body.merchant_ref)
        response.headers["Location"] = f"/v1/parcels/{parcel_id}"
        return ParcelOut(**asdict(parcel))

    @app.get(
        "/v1/parcels/{parcel_id}",
        operation_id="getParcel",
        response_model=ParcelOut,
        responses={404: doc("Parcel not found")},
    )
    def get_parcel(parcel_id: str):
        parcel = parcels.get(parcel_id)
        if parcel is None:
            raise StarletteHTTPException(404, "Parcel not found")
        return ParcelOut(**asdict(parcel))

    @app.get(
        "/v1/parcels",
        operation_id="listParcels",
        response_model=ParcelPage,
        responses={400: doc("Bad cursor"), 422: doc("Bad state or limit")},
    )
    def list_parcels(
        state: ParcelState | None = None,
        limit: Annotated[int, Query(ge=1, le=100)] = 20,
        cursor: str | None = None,
    ):
        after = 0
        if cursor is not None:
            if cursor not in issued:
                raise StarletteHTTPException(400, "Invalid cursor")
            after = issued[cursor]

        ### keyset pagination: we remember the seq, msh el position, fa mafish skip aw repeat
        matches = []
        for i in range(after, len(order)):
            p = parcels[order[i]]
            if state is None or p.state == state:
                matches.append((i + 1, p))
                if len(matches) == limit + 1:
                    break

        page = matches[:limit]
        next_cursor = None
        if len(matches) > limit:
            next_cursor = secrets.token_urlsafe(12)
            issued[next_cursor] = page[-1][0]
        return ParcelPage(
            items=[ParcelOut(**asdict(p)) for _, p in page],
            next_cursor=next_cursor,
        )

    @app.post(
        "/v1/parcels/{parcel_id}/events",
        operation_id="recordParcelEvent",
        response_model=ParcelOut,
        responses={
            404: doc("Parcel not found"),
            409: doc("Invalid transition"),
            422: doc("Unknown or missing event type"),
        },
    )
    def record_parcel_event(parcel_id: str, body: EventBody):
        parcel = parcels.get(parcel_id)
        if parcel is None:
            raise StarletteHTTPException(404, "Parcel not found")
        try:
            updated = apply_event(parcel, body.type)
        except InvalidTransition as exc:
            raise StarletteHTTPException(409, str(exc))
        ### we only store after apply_event nagah, so el parcel is unchanged on 409
        parcels[parcel_id] = updated
        return ParcelOut(**asdict(updated))

    return app

app = create_app()