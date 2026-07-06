from fastapi import FastAPI, Header, HTTPException, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uuid
import time
import base64

EMAIL = "23f2000333@ds.study.iitm.ac.in"

TOTAL_ORDERS = 49
RATE_LIMIT = 16
WINDOW = 10

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ----------------------------
# In-memory stores
# ----------------------------

idempotency_store = {}

rate_limit_store = {}

catalog = [
    {
        "id": i,
        "item": f"Item {i}"
    }
    for i in range(1, TOTAL_ORDERS + 1)
]


class Order(BaseModel):
    product: str
    quantity: int


# ----------------------------
# Rate limiting middleware
# ----------------------------

@app.middleware("http")
async def rate_limit(request, call_next):

    client = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()

    timestamps = rate_limit_store.get(client, [])

    timestamps = [
        t
        for t in timestamps
        if now - t < WINDOW
    ]

    if len(timestamps) >= RATE_LIMIT:

        retry = WINDOW - (now - timestamps[0])

        return Response(
            status_code=429,
            headers={
                "Retry-After": str(int(retry) + 1)
            },
        )

    timestamps.append(now)

    rate_limit_store[client] = timestamps

    return await call_next(request)


# ----------------------------
# Ping
# ----------------------------

@app.get("/ping")
def ping():

    return {
        "status": "ok",
        "email": EMAIL,
    }


# ----------------------------
# POST /orders
# ----------------------------

@app.post("/orders", status_code=201)
def create_order(
    order: Order,
    response: Response,
    idempotency_key: str = Header(...),
):

    if idempotency_key in idempotency_store:

        response.status_code = 200

        return idempotency_store[idempotency_key]

    new_order = {
        "id": str(uuid.uuid4()),
        "product": order.product,
        "quantity": order.quantity,
    }

    idempotency_store[idempotency_key] = new_order

    return new_order


# ----------------------------
# Pagination
# ----------------------------

@app.get("/orders")
def list_orders(
    limit: int = Query(10),
    cursor: str | None = None,
):

    start = 0

    if cursor:

        start = int(
            base64.b64decode(cursor).decode()
        )

    end = min(start + limit, TOTAL_ORDERS)

    items = catalog[start:end]

    next_cursor = None

    if end < TOTAL_ORDERS:

        next_cursor = base64.b64encode(
            str(end).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
