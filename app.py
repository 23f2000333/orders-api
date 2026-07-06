from fastapi import (
    FastAPI,
    Header,
    Response,
    Request,
    HTTPException,
    Query,
    Body,
)
from fastapi.middleware.cors import CORSMiddleware
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
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -----------------------------
# In-memory stores
# -----------------------------

idempotency_store = {}

rate_limit_store = {}

catalog = [
    {
        "id": i,
        "item": f"Item {i}",
    }
    for i in range(1, TOTAL_ORDERS + 1)
]


# -----------------------------
# Rate limiting
# -----------------------------

@app.middleware("http")
async def rate_limit(request: Request, call_next):

    client = request.headers.get("X-Client-Id", "anonymous")

    now = time.time()

    timestamps = rate_limit_store.get(client, [])

    timestamps = [
        t
        for t in timestamps
        if now - t < WINDOW
    ]

    if len(timestamps) >= RATE_LIMIT:

        retry = max(1, int(WINDOW - (now - timestamps[0])) + 1)

        return Response(
            status_code=429,
            headers={
                "Retry-After": str(retry)
            },
        )

    timestamps.append(now)

    rate_limit_store[client] = timestamps

    return await call_next(request)


# -----------------------------
# Ping
# -----------------------------

@app.get("/ping")
def ping():

    return {
        "status": "ok",
        "email": EMAIL,
    }


# -----------------------------
# POST /orders
# -----------------------------

@app.post("/orders", status_code=201)
async def create_order(
    response: Response,
    request: Request,
    idempotency_key: str | None = Header(default=None),
):

    if not idempotency_key:
        raise HTTPException(
            status_code=400,
            detail="Missing Idempotency-Key",
        )

    if idempotency_key in idempotency_store:

        response.status_code = 200

        return idempotency_store[idempotency_key]

    try:
        body = await request.json()
    except Exception:
        body = {}

    if not isinstance(body, dict):
        body = {}

    order = {
        "id": str(uuid.uuid4()),
        **body,
    }

    idempotency_store[idempotency_key] = order

    return order


# -----------------------------
# GET /orders
# -----------------------------

@app.get("/orders")
def list_orders(
    limit: int = Query(default=10),
    cursor: str | None = Query(default=None),
):

    start = 0

    if cursor:

        try:
            start = int(
                base64.b64decode(cursor.encode()).decode()
            )
        except Exception:
            start = 0

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
