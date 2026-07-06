from fastapi import FastAPI, Request, Response, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uuid
import time
import math
import base64

app = FastAPI()

EMAIL = "23f2000333@ds.study.iitm.ac.in"

TOTAL = 49
RATE_LIMIT = 16
WINDOW = 10

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["Retry-After"],
)

# -----------------------
# In-memory stores
# -----------------------

orders_created = {}

client_buckets = {}

catalog = [
    {
        "id": i,
        "name": f"Order {i}"
    }
    for i in range(1, TOTAL + 1)
]


@app.get("/ping")
def ping():
    return {
        "status": "ok",
        "email": EMAIL,
    }


@app.post("/orders")
async def create_order(
    request: Request,
    response: Response,
    idempotency_key: str | None = Header(default=None),
):

    if idempotency_key is None:
        raise HTTPException(400, "Missing Idempotency-Key")

    if idempotency_key in orders_created:

        response.status_code = 200

        return orders_created[idempotency_key]

    try:
        payload = await request.json()
    except Exception:
        payload = {}

    if not isinstance(payload, dict):
        payload = {}

    order = {
        "id": str(uuid.uuid4()),
        **payload,
    }

    orders_created[idempotency_key] = order

    response.status_code = 201

    return order


@app.get("/orders")
def list_orders(
    request: Request,
    limit: int = Query(10),
    cursor: str | None = Query(None),
):

    # --------------------
    # Rate limit ONLY GET /orders
    # --------------------

    client = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()

    bucket = client_buckets.get(client, [])

    bucket = [
        t
        for t in bucket
        if now - t < WINDOW
    ]

    if len(bucket) >= RATE_LIMIT:

        retry = max(
            1,
            math.ceil(WINDOW - (now - bucket[0]))
        )

        resp = JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded"
            },
        )

        resp.headers["Retry-After"] = str(retry)

        return resp

    bucket.append(now)

    client_buckets[client] = bucket

    # --------------------
    # Pagination
    # --------------------

    start = 0

    if cursor:

        try:
            start = int(
                base64.b64decode(cursor).decode()
            )
        except Exception:
            start = 0

    end = min(start + limit, TOTAL)

    items = catalog[start:end]

    next_cursor = None

    if end < TOTAL:

        next_cursor = base64.b64encode(
            str(end).encode()
        ).decode()

    return {
        "items": items,
        "next_cursor": next_cursor,
    }
